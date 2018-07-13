#!/usr/bin/env python
# -*-coding:utf-8-*-
import six,os,sys,pickle,base64
import six,os,sys,pickle,base64
import math
import pickle
import numpy as np
from collections import OrderedDict


PKL_MODEL = pickle.loads(base64.b64decode('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'.strip()))

def predict_proba(items):
    '''if MODEL PREPROCESS / FEATURE ENGINEERING required, write below before the "return ..." line. '''
    return PKL_MODEL.predict_proba(items)[:,1]

import struct,time, simplejson as json, finup_model
from tornado import gen,log

def format_output(req, fmt='json'):
    req.ret = json.dumps(req.ret)


def format_input(req, fmt=None):  #### req.ioinput,  req.iodata
    data = json.loads(req.data)
    req.data = data

def restore(s):
    if len(s) == 4:
        i = struct.unpack('>L', s)[0]
        return (i & 255), i>>8 if i>255 else 0
    else:
        return 0, 0


@gen.coroutine
def process(req):
    items = req.data
    rs = []
    dids = []
    for i in items:
        dids.append(i["userEncrypt"])
        t = i['tags']
        rs.append([float(t.get('getui.2018022816.probability(1-0)','')),t['bannertype'],t['hour'],t['weekday'],t['province'],t['city']])

    redis = finup_model.get_redis()
    pp = finup_model.get_redis_pipeline()
    _ = [pp.stack_call('GET', devid) for devid in dids ]
    if not redis.is_connected():
        _ = yield redis.connect()
    res = yield redis.call(pp)
    timestamp = time.time()
    ts = int(timestamp) % 10000000
    #print('REDIS: %r' % res)
    #import pdb;pdb.set_trace()
    for idx, bits in enumerate(res):
        if bits is not None:
            exposure_hourly, timestamp_hourly = restore(bits[ 0:4 ])
            exposure_daily, timestamp_daily   = restore(bits[ 4:8 ])
            quarter_a25, timestamp_a25        = restore(bits[ 8:12])  ## 曝光: a25
            quarter_a40, timestamp_a40        = restore(bits[12:16]) ## 一跳: a40
            quarter_a60, timestamp_a60        = restore(bits[16:20]) ## 二跳: a60
            c = ord(bits[20] if len(bits)>20 else '\x00')
            ff_register = c & 8
            qz_register = c & 4

            if exposure_hourly and (timestamp_hourly + 3600) < ts:
                exposure_hourly = 0

            if exposure_daily and (timestamp_daily + 86400) < ts:
                exposure_daily = 0
        else:
            exposure_hourly, timestamp_hourly = 0,0
            exposure_daily, timestamp_daily   = 0,0
            quarter_a25, timestamp_a25        = 0,0
            quarter_a40, timestamp_a40        = 0,0
            quarter_a60, timestamp_a60        = 0,0
            ff_register = 0
            qz_register = 0

        rs[idx].extend([quarter_a25, quarter_a40, quarter_a60, ff_register, qz_register, exposure_daily])
    ret = predict_proba(rs)
    raise gen.Return(zip(dids, ret))

