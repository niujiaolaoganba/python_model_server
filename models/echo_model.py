# -*-coding:utf-8-*-
import os, sys, six, simplejson as json, csv, hashlib, time, pandas as pd, numpy as np

if six.PY2 and sys.getdefaultencoding() != 'utf8':
    reload(sys)
    sys.setdefaultencoding('utf8')


MODEL_NAME = 'echo_model'

def predict_proba(items):
    return items

def format_output(req, fmt='json'):
    req.ret = json.dumps(req.ret)


def format_input(req, fmt=None):  #### req.ioinput,  req.iodata
    data = json.loads(req.data)
    req.data = data
