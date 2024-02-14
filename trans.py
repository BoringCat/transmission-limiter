import random
import requests
import typing as _t

class Transmission():
    @property
    def __headers(self):
        if self.__session_id:
            return {'X-Transmission-Session-Id': self.__session_id}
        return None

    @property
    def tag(self): return random.randint(0,2**20)

    def __init__(self, baseUrl:str, user:str = None, passwd:str = None):
        if not baseUrl.startswith('http'):
            baseUrl = f'http://{baseUrl}'
        if baseUrl.endswith('/'):
            baseUrl = baseUrl[:-1]
        if not baseUrl.endswith('/transmission/rpc'):
            baseUrl = f'{baseUrl}/transmission/rpc'
        self.__url = baseUrl
        if user and passwd:
            self.__auth = ( user, passwd )
        else:
            self.__auth = None
        self.__session = requests.session()
        self.__session_id = None
        self.__getSessionId()
    
    def __getSessionId(self):
        resp = self.__session.get(self.__url, auth = self.__auth, headers = self.__headers)
        if resp.status_code == 409:
            self.__session_id = resp.headers.get('X-Transmission-Session-Id')
        elif resp.status_code == 405:
            return
        else:
            raise Exception(f'GetSessionId Error: HTTP response {resp.reason}')

    def build_req(self, method:str, **args):
        return {
            'arguments': args,
            'method': method,
            'tag': self.tag
        }

    def do_req(self, req:dict):
        resp = self.__session.post(self.__url, auth = self.__auth, headers = self.__headers, json = req)
        if resp.status_code == 409:
            session_id = resp.headers.get('X-Transmission-Session-Id', None)
            if session_id:
                self.__session_id = resp.headers.get('X-Transmission-Session-Id')
                resp = self.__session.post(self.__url, auth = self.__auth, headers = self.__headers, json = req)
        resp.raise_for_status()
        data = resp.json()
        if data['tag'] != req['tag']:
            raise Exception(f'Inconsistent tag! require {req["tag"]}, got {data["tag"]}')
        if data['result'] != 'success':
            raise Exception(data['result'])
        return data['arguments']

    def TorrentGet(self, fields:_t.List[str]) -> _t.List[dict]:
        req = self.build_req(method='torrent-get', fields=fields)
        return self.do_req(req)['torrents']

    def BlocklistUpdate(self):
        req = self.build_req('blocklist-update')
        return self.do_req(req)
