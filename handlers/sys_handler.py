#!/usr/bin/env python3
#coding:utf-8

"""
@Author: Abael He<abaelhe@icloud.com>
@file: reloader.py
@time: 5/2/18 2:49 PM
@license: All Rights Reserved, Abael.com
"""

import six,os, sys, traceback, bisect, re, itertools, collections, time,datetime,json,gc, gzip,hashlib,base64, inspect, simplejson as json, finup_model
from tornado.web import RequestHandler,HTTPError
from tornado.gen import coroutine
from tornado.escape import json_decode, json_encode, utf8, _unicode
from tornado.concurrent import run_on_executor
from tornado.ioloop import IOLoop
from tornado.log import app_log

from sklearn.externals import joblib
import dill, numpy as np, pandas as pd
from distutils.core import setup
from Cython.Build import cythonize
from distutils.extension import Extension
from distutils.dist import Distribution


utils = __import__('libs.utils', 'libs', fromlist=['libs'])

API_DOC =utf8( r"""
接口调用(支持 批量/单次 )方法:
    批量单次 调用(文件名必须以 ".csv" 或 ".csv.gz" 结束):
        传文本CSV文件:  curl  -F 'files=@./fanpu_20180403_v2.csv'           -H 'Accept-Encoding: gzip, deflate'  'http://127.0.0.1:8888/finup?model=1' > result.csv.gz
        传压缩CSV文件:  curl  -F 'files=@./fanpu_20180403_v2_100000.csv.gz' -H 'Accept-Encoding: gzip, deflate'  'http://127.0.0.1:8888/finup?model=1' > result.csv.gz

    传HTTP BODY调用(千万注意 单引号(''), 双引号(""), 斜杆(\\) 转义这些问题， 建议使用 CSV文件调用方式):
        curl 'http://127.0.0.1:8888/finup?model=1' --data  '26SEP17:15:55:26|eb994c456276c5ea3c2ebe1cf9f2c80c|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|\N|1|1|1|113|TRUE|TRUE|\N|\N|\N|0|0|0|0|1|1|0|0|0|0|1|1|4|6|0|0|0|0|5|6|0|0|3|3|0|0|1|3|0|0|1|1|30|56|男|25-34岁|中|否|否|否|是|三线城市|银川|否|Redmi 4X|Mi|860'
        #### 注: 这里的数据请按照具体接口修改.

更多请联系:
    义军 abaelhe@icloud.com | 13522696712

""")



INTERNAL_TYPES = ('bool', 'int', 'float', 'str', 'object')
OP_PREFIX = 'handle_'

class SysHandler(RequestHandler):
    is_reload = False
    @coroutine
    def get(self, *args, **kwargs):
        self.finish(json.dumps({
            'log':finup_model.LOGON,
            'models':sorted(finup_model.MODELS.keys()),
            'ops':sorted(self.handlers.keys()),
        }))

    @coroutine
    def post(self, *args, **kwargs):
        self.debug = True if self.get_query_argument('debug', None) else False

        op = self.get_query_argument('op', None)
        if op is None or op not in self.handlers:
            self.finish('非法请求: 请设置 op=%s 参数.' % op)
            return

        self.op = op
        try:
            return self.handlers[op](*args, **kwargs)
        except:
            finup_model.print_exc(file=self, limit=2)
            app_log.error('ERR REQ:  method:%s, uri:%r, body:%r\n', self.request.method, self.request.uri, self.request.body)

    @property
    def handlers(self):
        ops = {}
        for attr in dir(self):
            if not attr.startswith(OP_PREFIX):
                continue
            callee = getattr(self, attr)
            if not inspect.ismethod(callee):
                continue
            ops[attr[len(OP_PREFIX):]] = callee
        return ops

    def handle_update(self):
        fos=[(fo['filename'],fo['body']) for fo in self.request.files['models'] if fo.get('filename','').endswith('.py') and len(fo.get('body',''))>10]
        if self.debug:
            import pdb;pdb.set_trace()
        ids =dict([(k, v) for k,v in finup_model.MODELS.items() ])
        mods = finup_model.update_modules(fos)
        self.finish(json.dumps([ mods, sorted(finup_model.MODELS.keys()) ]))

    def handle_ports(self):
        self.finish(json.dumps(finup_model.PORTS))

    def handle_log(self):
        finup_model.LOGON = 0 if finup_model.LOGON == 1 else 1
        self.get()

    def handle_reload(self):
        if self.debug:
            import pdb;pdb.set_trace()
        finup_model.reload_modules(system=True, errfile=self)
        self.finish( json.dumps(sorted(finup_model.MODELS.keys())) )

