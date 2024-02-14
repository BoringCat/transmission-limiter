#!/usr/bin/env python3

import re
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
from threading import Event, Thread
from flask import Flask, make_response
from werkzeug.exceptions import HTTPException

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

def checkPeer(rds:redis.Redis, peer:dict, id:str, totalSize:int, time:int, zero_threshold:int = 2**16):
    willBlock = False
    try:
        peerKeys = sorted(rds.scan_iter(f"{id}/{peer['address']}/*", count=128), key=lambda x:int(x.split('/',2)[2]))
        peerStats = tuple(map(json.loads, filter(bool, rds.mget(peerKeys)))) + (peer, )
        if len(peerStats) >= 11:
            progressDiff = peerStats[-1]['progress'] - peerStats[0]['progress']
            sizeDiff = progressDiff * totalSize
            needRate = sizeDiff / len(peerStats) / 5
            avgRate = sum(map(lambda x:x['rateToPeer'], peerStats)) / len(peerStats)
            if (needRate > 0 and avgRate*2 > needRate) or (progressDiff == 0 and avgRate > zero_threshold):
                logging.info('封禁条件满足: (%f > 0 and %f > %f) or (%f == 0 and %f > %d)', needRate, avgRate*2, needRate, progressDiff, avgRate, zero_threshold)
                willBlock = True
    except json.JSONDecodeError:
        rds.delete(*peerKeys)
    except:
        logging.warning(format_exc())
    rds.set(f"{id}/{peer['address']}/{time}", json.dumps({'progress':peer['progress'],'rateToPeer':peer['rateToPeer']}), ex=602)
    return willBlock

def getBlockList(tr:Transmission, rds:redis.Redis, ttl:int = 1800, zero_threshold:int = 2**16):
    def torrentFilter(t:dict):
        if t['status'] not in [4,5,6]:
            return False
        return True
    def peerFilter(p:dict):
        return p['isUploadingTo']
    def worker():
        blocklist = set(itertools.chain.from_iterable(map(
            lambda x:x.split('\n'),
            rds.mget(rds.scan_iter('transmission::blocklist::*', count=128))
        )))
        runId = int(datetime.now().timestamp() * 1000)
        willBlocks = set()
        torrents = tr.TorrentGet(['id', 'name', 'addedDate', 'sizeWhenDone', 'status', 'peers'])
        for torrent in filter(torrentFilter, torrents):
            for peer in filter(lambda x:x['isUploadingTo'] and x['address'] not in blocklist, torrent['peers']):
                if checkPeer(rds, peer, torrent['id'], torrent['sizeWhenDone'], runId, zero_threshold):
                    logging.info('将封禁 %s(%s)', peer['address'], peer['clientName'])
                    willBlocks.add(peer['address'])
        if willBlocks:
            rds.set(f'transmission::blocklist::{runId}', '\n'.join(willBlocks), ex = ttl)
            tr.BlocklistUpdate()
    return worker

def flushBlockList(tr:Transmission):
    def worker():
        tr.BlocklistUpdate()
    return worker

def create_app(configFile:str):
    logging.basicConfig(
        stream  = sys.stderr,
        format  = '[%(asctime)s.%(msecs)03d][%(name)s][%(funcName)s][%(levelname)s] %(message)s',
        datefmt = '%Y-%m-%d %H:%M:%S',
        level   = logging.INFO,
    )
    with open(configFile, 'r', encoding='UTF-8') as f:
        conf = yaml.safe_load(f)

    rds = redis.Redis(**conf['redis'], encoding='UTF-8', decode_responses=True)
    tr = Transmission(**conf['transmission'])

    getTask   = Timer(conf['interval'], getBlockList(tr, rds, conf['ttl'], conf['zero_threshold']))
    flushTask = Timer(conf.get('ttl', 1800), tr.BlocklistUpdate)
    getTask.setDaemon(True)
    getTask.setName('getBlockList')
    flushTask.setDaemon(True)
    flushTask.setName('flushBlockList')

    app = Flask('transmission-limiter')
    static_list = []
    for idx, b in enumerate(conf.get('static_blocklist', [])):
        static_list.append(f'static{idx}:{b}')

    @app.route('/blocklist')
    def blocklist():
        dymanic_list = set(itertools.chain.from_iterable(map(
            lambda x:x.split('\n'),
            rds.mget(rds.scan_iter('transmission::blocklist::*', count=128))
        )))
        return '\n'.join(itertools.chain(
            static_list,
            map(lambda x:'dymanic{0:08d}:{1}-{1}'.format(*x), enumerate(dymanic_list))
        )) + '\n'

    @app.route('/health')
    def health():
        errs = []
        try:
            rds.ping()
        except Exception as err:
            errs.append(f'Redis: {err}\n')
        if not getTask.is_alive():
            errs.append('getTask Thread: Not Alive\n')
        if not flushTask.is_alive():
            errs.append('flushTask Thread: Not Alive\n')
        if errs:
            resp = make_response(''.join(errs), 500)
        else:
            resp = make_response('OK\n')
        return resp

    @app.errorhandler(HTTPException)
    def _http_err(e:HTTPException):
        return '{0.value} {0.phrase}\n'.format(HTTPStatus(e.code)), e.code

    getTask.start()
    flushTask.start()

    return app

if __name__ == '__main__':
    app = create_app('./config.dev.yml')
    app.run()
