#!/usr/bin/env python3

import sys
import json
import yaml
import redis
import logging
import itertools
from http import HTTPStatus
from datetime import datetime
from trans import Transmission
from traceback import format_exc
from redis.client import Pipeline
from threading import Event, Thread
from flask import Flask, make_response
from werkzeug.exceptions import HTTPException

from blocker import Blocker
import args

class Timer(Thread):
    def __init__(self, interval, target=None, name=None,
                 args=(), kwargs=None, *, daemon=None):
        super().__init__(name=name, daemon=daemon)
        self.name = name
        self.interval = interval
        self.function = target
        self.args = args if args is not None else tuple()
        self.kwargs = kwargs if kwargs is not None else dict()
        self.finished = Event()

    def cancel(self):
        """Stop the timer if it hasn't finished yet."""
        self.finished.set()

    def run(self):
        self.finished.wait(self.interval)
        while not self.finished.is_set():
            self.function(*self.args, **self.kwargs)
            self.finished.wait(self.interval)

def sortKey(key:str, split:str = '/'): return int(key.split(split, 2)[2])

def checkPeer(
        rds:redis.Redis, pipe:Pipeline, peer:dict, torrent:dict[str, int|float],
        time:int, interval:int, ttl:int, threshold:dict[str, int | float]
    ):
    willBlock = False
    try:
        peerKeys = sorted(rds.scan_iter(f"{torrent['id']}/{peer['address']}/*", count=256), key=sortKey)
        peerStats = tuple(itertools.chain(map(json.loads, filter(bool, rds.mget(peerKeys))), (peer, )))
        if len(peerStats) >= threshold['data']:
            progressDiff = peerStats[-1]['progress'] - peerStats[0]['progress']
            sizeDiff = progressDiff * torrent['sizeWhenDone']
            needRate = sizeDiff / len(peerStats) / interval
            avgRate = sum(map(lambda x:x['rateToPeer'], peerStats)) / len(peerStats)
            # 进度速率大于0但平均速度大于进度 || 速率为0但速度大于阈值
            if (needRate > 0 and avgRate > needRate*threshold['avg']) or (progressDiff == 0 and avgRate > torrent['sizeWhenDone'] / 10000 / interval):
                logging.debug(
                    '封禁条件满足: (%f > 0 and %f > %f) or (%f == 0 and %f > %d)',
                    needRate, avgRate, needRate*threshold['avg'], progressDiff, avgRate, torrent['sizeWhenDone'] / 10000 / interval
                )
                willBlock = True
    except json.JSONDecodeError:
        pipe.delete(*peerKeys)
    except:
        logging.debug(format_exc())
    try:
        pipe.set(
            name  = f"{torrent['id']}/{peer['address']}/{time}",
            value = json.dumps({'progress':peer['progress'],'rateToPeer':peer['rateToPeer']}),
            ex    = ttl
        )
    except: pass
    return willBlock

def getBlockFunc(
        tr:Transmission, rds:redis.Redis, interval:int,
        ttl:dict[str, int] = {'data':602,'blocklist':1800},
        threshold:dict[str, int | float] = {'avg': 2.0,'data':3},
        blocker:Blocker = Blocker({})
    ):
    def torrentFilter(t:dict):
        if t['status'] not in [4,5,6]:
            return False
        return True
    def worker():
        blocklist = set(itertools.chain.from_iterable(map(
            lambda x:x.split('\n'),
            rds.mget(rds.scan_iter('transmission::blocklist::*', count=128))
        )))
        runId = int(datetime.now().timestamp() * 1000)
        willBlocks = set()
        torrents = tr.TorrentGet(['id', 'sizeWhenDone', 'status', 'peers'])
        pipe = rds.pipeline(False)
        checkArgs = dict(rds=rds, pipe=pipe, time=runId, interval=interval, ttl=ttl['data'], threshold=threshold)
        for torrent in filter(torrentFilter, torrents):
            for peer in filter(lambda x:x['isUploadingTo'] and x['address'] not in blocklist, torrent.pop('peers',[])):
                if blocker.doFilter(peer) or checkPeer(torrent=torrent, peer=peer, **checkArgs):
                    logging.info('将封禁 %s(%s)', peer['address'], peer['clientName'])
                    willBlocks.add(peer['address'])
        try:
            if willBlocks:
                pipe.set(f'transmission::blocklist::{runId}', '\n'.join(willBlocks), ex = ttl['blocklist'])
                pipe.execute()
                tr.BlocklistUpdate()
            else:
                pipe.execute()
        except:
            logging.debug(format_exc())
    return worker

def flushBlockList(tr:Transmission):
    def worker():
        tr.BlocklistUpdate()
    return worker

def createApp(configFile:str = args.CONFIG_FILE, debug:bool = False):
    logging.basicConfig(
        stream  = sys.stderr,
        format  = '[%(asctime)s.%(msecs)03d][%(name)s][%(funcName)s][%(levelname)s] %(message)s',
        datefmt = '%Y-%m-%d %H:%M:%S',
        level   = logging.NOTSET if debug else args.LOG_LEVEL,
    )
    logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
    with open(configFile, 'r', encoding='UTF-8') as f:
        conf = yaml.safe_load(f)

    rds = redis.Redis(connection_pool=redis.ConnectionPool(**conf['redis'], encoding='UTF-8', decode_responses=True))
    tr = Transmission(**conf['transmission'])

    blocker = Blocker(conf.get('staticBlock', None))

    getTask = Timer(
        conf['interval']['fetch'],
        getBlockFunc(tr, rds, conf['interval']['fetch'], conf['ttl'], conf['threshold'], blocker),
        name='makeBlockList',
        daemon=True
    )
    flushTask = Timer(conf['interval']['reflush'], tr.BlocklistUpdate, name='flushBlockList', daemon=True)

    app = Flask('transmission-limiter')
    @app.route('/blocklist')
    def blocklist():
        keys         = tuple(rds.scan_iter('transmission::blocklist::*', count=128))
        items        = filter(lambda x:bool(x[1]), zip(keys, rds.mget(keys)))
        dymanic_list = []
        for k, v in items:
            runId = sortKey(k, '::')
            for idx, ip in enumerate(v.split('\n')):
                dymanic_list.append(f'dymanic-{runId}-{idx}:{ip}-{ip}')
        return '\n'.join(itertools.chain(
            map(lambda x:'static-{0:08d}:{1}-{1}'.format(*x), enumerate(blocker.iplist)),
            dymanic_list
        )) + '\n'

    @app.route('/health')
    def health():
        errs = []
        try:
            rds.ping()
        except Exception as err:
            errs.append(f'Redis: {err}\n')
        try:
            tr.SessionGet(fields=['version'])
        except Exception as err:
            errs.append(f'Transmission: {err}\n')
        if not getTask.is_alive():
            errs.append(f'Thread {getTask.name}: Not Alive\n')
        if not flushTask.is_alive():
            errs.append(f'Thread {flushTask.name}: Not Alive\n')
        if errs:
            resp = make_response(''.join(errs), 500)
        else:
            resp = make_response('OK\n')
        return resp

    @app.errorhandler(HTTPException)
    def __httpErr(e:HTTPException):
        return '{0.value} {0.phrase}\n'.format(HTTPStatus(e.code)), e.code

    if not debug:
        getTask.start()
        flushTask.start()

    return app

if __name__ == '__main__':
    app = createApp('./config.dev.yml', True)
    app.run()
