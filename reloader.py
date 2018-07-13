#!/usr/bin/env python
# -*-coding:utf-8-*-
import six,sys,os, simplejson as json, sklearn as sk, pandas as pd, numpy as np

CWD = os.path.abspath(os.getcwd())
if '.' not in sys.path and CWD not in sys.path:
    sys.path.insert(0, CWD)

if six.PY2 and sys.getdefaultencoding() != 'utf8':
    reload(sys)
    sys.setdefaultencoding('utf8')


from sklearn.base import BaseEstimator, TransformerMixin, ClassifierMixin
try:
    from tornado.curl_httpclient import CurlAsyncHTTPClient as AsyncHTTPClient
except:
    from tornado.httpclient import AsyncHTTPClient
from tornado import gen,ioloop

HTTP_CLIENT = AsyncHTTPClient()
THIS_DIRNAME = os.path.abspath(os.getcwd())
PORT = 8888
PINTU_FILE = './data/test.pintu__20180504.json'
PINTU = os.path.exists(PINTU_FILE)
cmd = {
    'sys': ['http://%s:%s/sys', [], {}],
    'ports': ['http://%s:%s/sys?op=ports', [], {'method':"POST", 'body':''}],
    'pintu': ['http://%s:%s/finup?model=pintu__2018051116', [], {'method':"POST", 'body': open(PINTU_FILE).read() if PINTU else None}],
    'reload': ['http://%s:%s/sys?op=reload', [], {'method':"POST", 'body':''}]
}

ret = {}

@gen.coroutine
def get(url, *args, **kws):
    d = yield HTTP_CLIENT.fetch(url, *args, **kws)
    ret[url] = d
    raise gen.Return(d)

def get_host_port():
    host = '127.0.0.1'
    port = 8888
    argv = []
    for i in sys.argv:
        if i.startswith('--host='):
            host = i.rpartition('=')[-1].strip('"').strip("'")
        elif i.startswith('--port='):
            port = int(i.rpartition('=')[-1])
        else:
            argv.append(i)
    return (host, port)

def reloader():
    io = ioloop.IOLoop.current()
    host, port = get_host_port()
    ports = None
    s, args, kws = cmd['sys']
    resp = io.run_sync(lambda: get(s % (host, port), *args, **kws))
    if resp.code != 200:
        print('请确认模型服务已经启动，监听在端口%s:%s' % (host,port))

    s, args, kws = cmd['ports']
    resp = io.run_sync(lambda: get(s % (host, port), *args, **kws))
    ports = json.loads(resp.body)

    s, args, kws = cmd['pintu']
    if PINTU:
        resp = io.run_sync(lambda: get(s % (host, port), *args, **kws))
        print('REAL REQ: %r' % json.loads(resp.body))
    rets = []

    @gen.coroutine
    def update_all():
        for p in ports:
            s, args, kws = cmd['reload']
            resp = yield get(s % (host, p), *args, **kws)
            rets.append( ('%s:%s'%(host, p), resp.body) )
    io.run_sync(update_all)
    for (p, b) in rets:
        print('%s: %s'%(p, b))

if __name__ == '__main__':
    reloader()
