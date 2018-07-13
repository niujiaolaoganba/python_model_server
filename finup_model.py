# -*-coding:utf-8-*-

import imp,marshal,gzip,collections
import os,sys,six,time,datetime,bisect,codecs,unicodedata, multiprocessing,threading,base64,hashlib,hmac,traceback,ujson as json,random as _random, csv, pandas as pd, numpy as np, category_encoders
from pandas.api import types as pdtypes


from tornado.web import RequestHandler,HTTPError
from tornado import log, process,escape,ioloop,gen
from tornado.httpclient import AsyncHTTPClient
#from tornado.curl_httpclient import CurlAsyncHTTPClien
from sklearn.externals import joblib
from sklearn.base import BaseEstimator, TransformerMixin, ClassifierMixin
from six.moves import cStringIO as StringIO, reload_module
from six.moves.queue import Queue
import tornadis


THIS_DIRNAME = os.path.abspath(os.getcwd())
if '.' not in sys.path and THIS_DIRNAME not in sys.path:
    sys.path.insert(0, THIS_DIRNAME)

if six.PY2 and sys.getdefaultencoding() != 'utf8':
    reload(sys)
    sys.setdefaultencoding('utf8')


LOGON = 0
MAGIC = imp.get_magic()
THIS_BASENAME = 'finup_model.py'
ADDR = None
PORT = None
PORTS = []
MODULES_DIR = os.path.abspath(os.sep.join([THIS_DIRNAME, 'models']))
DATA_DIR = os.path.abspath(os.sep.join([THIS_DIRNAME, 'data']))
MODELS = {}
STATSQ = collections.deque()
## --redis='redis://abc:123@10.10.210.83:6379/0'
# REDIS_SETTINGS= {'host':'127.0.0.1', 'port':6379, 'password':'aace52100ec293bc6e3220dbda812155'}
REDIS_SETTINGS= {'host':'10.10.210.83', 'port':6379, 'password':'aace52100ec293bc6e3220dbda812155'}
# REDIS_SETTINGS= {'host':'10.19.97.227', 'port':60000, 'password':'2HFb7eE5ASypDHXY'}

GET_REDIS = lambda : tornadis.Client(**REDIS_SETTINGS)
def get_redis_pipeline():
    return tornadis.Pipeline()
REDIS = None
def get_redis():
    global REDIS
    if REDIS is None:
        REDIS = tornadis.Client(**REDIS_SETTINGS)
    return REDIS

from libs.otp  import *
from libs.cache import *
from libs.utils import *

def pretty_stats(times):
    ret = []
    total_time = 1000 * times[-1][-1] - 1000 * times[0][-1]
    idx_max = len(times) -1
    if total_time > 1000:
        ret.append('total: %.4f, %.2fqps, % 15s -> %-15s' % (total_time / 1000, 1000 / total_time, times[0][0], times[-1][0]))
    else:
        ret.append('total: %sms, %.2fqps, % 15s -> %-15s' % (total_time, 1000 / total_time, times[0][0], times[-1][0]))

    for idx, (stage, tm) in enumerate(times):
        if idx < idx_max:
            ms = 1000 * (times[idx+1][-1] - tm)
            percent = '%.4f' % (ms / total_time)
            ret.append('% 15s -> %-15s: %s.%s%% %.5fms' % (stage,times[idx+1][0],  percent[2:4], percent[4:], ms))
    ret.append('')
    return '\n'.join(ret)

def print_exc(file=None, limit=2):
    etype, value, tb = sys.exc_info()
    tbs = traceback.extract_tb(tb, limit=None)
    num = len(tbs)
    ptb = tbs[-1 * limit:] if limit is not None else tbs
    rlist = traceback.format_exception_only(etype, value)
    last = True
    raised = False
    for filename, lineno, name, line in reversed(ptb):
        if filename.startswith('/'):
            continue
        line = line.strip() if line else ''
        if last:
            last = False
            if line.startswith('raise ') and not filename.startswith('/'):
                raised = True
            rlist.append('    "%s:%d, %s\n' % (filename.replace('.py', '.so'),lineno, name))
            #else:
            #    rlist.append('    "%s:%d, %s in %s\n' % (filename,lineno, line, name))
        else:
            rlist.append('    "%s:%d:%s\n' % (filename.replace('.py','.so'),lineno, name))
            #rlist.append('    "%s:%d, %s in %s\n' % (filename,lineno, line, name))
        if raised:
            break

    if file is None:
        return ''.join(rlist)
    else:
        try:
            file.write(''.join(rlist))
            file.flush()
        except:
            pass


def load_dat(name, pathname):
    abspath = os.path.abspath(pathname)
    assert abspath.startswith(MODULES_DIR), '请求模型:%r, 路径非法:%r' % (name, pathname)
    modpath = abspath.replace(MODULES_DIR, os.path.basename(MODULES_DIR))
    domain = {
    }
    with open(abspath, 'rb') as datf:
        try:
            ms = datf.read(4)
            ts = datf.read(4)
            cos = gzip.GzipFile(fileobj=StringIO(datf.read()), mode='rb').read()
            co = marshal.loads(cos)
            exec(co, domain, domain)
            predict_proba = domain.get('predict_proba', None)
            assert callable(predict_proba), '非标准模型:%r, %r, 未按标准接口定义模型入口函数: "predict_proba([item0, item1, ...])"' %(name, modpath)
            return predict_proba
        except:
            try:
                os.remove(abspath)
            except:
                pass
            raise ValueError('非标准模型:%r,%r, 请咨询何义军<abaelhe@icloud.com>, 13522696712.' %(name, modpath))


class Vmodel(object):
    def __repr__(self):
        return self.MODEL_NAME
    def __init__(self, modname, entrypoint):
        self.predict_proba = entrypoint
        self.MODEL_NAME = modname
    def format_input(self, req, fmt=None):
        req.data = json.loads(req.data)
    @gen.coroutine
    def process(self, req):
        if gen.is_coroutine_function(self.predict_proba):
            ret = yield self.predict_proba(req.data)
        else:
            ret = self.predict_proba(req.data)
        req.ret = ret

    def format_output(self, req, fmt='json'):
        req.ret = json.dumps(req.ret)


def print_modules():
        return ','.join(sorted(MODELS.keys()))

def wr_long(f, x):
    f.write(chr( x        & 0xff))
    f.write(chr((x >> 8)  & 0xff))
    f.write(chr((x >> 16) & 0xff))
    f.write(chr((x >> 24) & 0xff))


MODULE_NAME_VALID_CHARS = tuple(c for c in '0123456789_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
MODULE_NAME_VALID_CHCKS = tuple((chr(i) in MODULE_NAME_VALID_CHARS) for i in range(256))
def update_modules(fobjs):
    timestamp = long(time.time())
    mods = {}
    for filename, pybody in fobjs:
        filename = filename
        fname,_, suffix = filename.rpartition('.')
        assert suffix == 'py', '文件名:%r, 只接受 ".py" 后缀文件名.' % filename
        for c in fname:
            i = ord(c)
            assert MODULE_NAME_VALID_CHCKS[i], '修改模块名,c:%c[%d] filename:%r, fname:%r, iname:%r, 合法字符集为:大写字母[A-Z]，小写字母[a-z]，数字[0-9]，下划线"_"' % (c, i,filename, fname, [ord(c) for c in fname])
        fname=escape.to_basestring(fname)
        rpath = os.path.abspath(os.sep.join([MODULES_DIR, '%s.dat' % fname]))
        codeobject = builtins.compile(pybody, '<string>', 'exec', dont_inherit=True)
        with open(rpath, 'wb') as datf:
            datf.write('\0\0\0\0')
            wr_long(datf, timestamp)
            dumps = marshal.dumps(codeobject)
            fobj = StringIO()
            gzf = gzip.GzipFile(fileobj=fobj, mode='wb')
            gzf.write(dumps)
            gzf.flush()
            gzf.close()
            datf.write(fobj.getvalue())
            datf.flush()
            datf.seek(0, 0)
            datf.write(MAGIC)
            datf.flush()
        mods[escape.to_basestring(fname)] = Vmodel(fname, load_dat(fname, rpath))

    changes = []
    global MODELS
    for k, m in mods.items():
        om = MODELS.pop(k,None)
        MODELS[k] =m
        if om is not None:
            changes.append([k, id(om), id(m)])
            del om
        else:
            changes.append([k,   None, id(m)])

    return sorted(changes, key=lambda x:x[0])


def reload_modules(system=False, errfile=None):
    models = {}
    for mf in os.listdir(MODULES_DIR):
        mod = None
        modname = None
        fname = mf.rpartition('.')[0]
        #fname = escape.utf8(fname)
        try:
            if mf.endswith('_model.py'):
                mod = imp.load_source(fname, os.sep.join([MODULES_DIR, mf]))
                if not hasattr(mod, 'MODEL_NAME'):
                    mod.MODEL_NAME = fname.rpartition('_')[0]
            elif mf.endswith('_model.so'):
                mod = imp.load_dynamic(fname, os.sep.join([MODULES_DIR, mf]))
                if not hasattr(mod, 'MODEL_NAME'):
                    mod.MODEL_NAME = fname.rpartition('_')[0]
            elif mf.endswith('.dat'):
                mod = Vmodel(fname, load_dat(fname, os.sep.join([MODULES_DIR, mf])))
            else:
                continue
        except:
            print_exc(file=errfile if errfile else sys.stderr)
            continue
        models[mod.MODEL_NAME] = mod

    if system:
        global MODELS
        last_models = MODELS
        MODELS = models

        for k in last_models.keys():
            m = last_models.pop(k, None)
            if m:
                del m
        del last_models

