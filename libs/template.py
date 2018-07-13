# -*-coding:utf-8-*-
import os,sys, six, base64, time, simplejson as json,csv, pandas as pd, numpy as np, dill
from cStringIO import StringIO
from sklearn.externals import joblib
from libs.cache import LRUCache
from libs.utils import load_pkl, PANDAS_EXPORT_KWARGS

if six.PY2 and sys.getdefaultencoding() != 'utf8':
    reload(sys)
    sys.setdefaultencoding('utf8')

def utf8(string):
    if isinstance(string, six.text_type):
        return string.encode('utf8')
    elif isinstance(string, six.binary_type):
        return string
    else:
        return six.text_type(string).encode('utf8')


MODEL_NAME = "{MODEL_NAME}"

MODEL_INPUT_DATA_DICT = eval('{MODEL_INPUT_DATA_DICT}')

MODEL_OUTPUT_DATA_DICT = eval('{MODEL_OUTPUT_DATA_DICT}')

MODEL_PKL_MD5 = "{MODEL_PKL_MD5}"
MODEL_PKL = '''{MODEL_PKL}'''

################################################################################################

PANDAS_COL_REQUEST_TIME = u'Time'
PANDAS_COL_DEVICE_ID = u'DeviceID'

PANDAS_DATA_DICT = [
#    (PANDAS_COL_REQUEST_TIME, np.object, 1),
#    (PANDAS_COL_DEVICE_ID, np.object, 1),
]

PANDAS_DATA_DICT.extend(MODEL_INPUT_DATA_DICT)

################################################################################################


NAN = np.NaN
NAN_STR = r'\N'

PANDAS_COL_ENABLES = tuple(col_name for col_name, col_type, enable  in PANDAS_DATA_DICT if enable)
PANDAS_COL_NAMES =tuple(col_name for col_name, col_type, enable  in PANDAS_DATA_DICT)
PANDAS_COL_DTYPES = dict((col_name, col_type) for col_name, col_type, enable  in PANDAS_DATA_DICT)
PANDAS_COL_REMOVES = (PANDAS_COL_REQUEST_TIME, PANDAS_COL_DEVICE_ID)
PANDAS_COL_EXPORTS = [i[0] for i in MODEL_OUTPUT_DATA_DICT]

PANDAS_IMPORT_KWARGS = dict(sep='|', na_values =NAN_STR, header=None, engine='c', encoding='utf8',
                     names=PANDAS_COL_NAMES, dtype=PANDAS_COL_DTYPES, usecols=PANDAS_COL_ENABLES,
                     #error_bad_lines=False, warn_bad_lines=True,
                     )


def csv2df(csvfile, **kwargs):
    kws = PANDAS_IMPORT_KWARGS.copy()
    kws.update(kwargs)
    df = pd.read_csv(csvfile, **kws)
    return  df


def df2csv(df, filename, columns=None, gzip=False, **kwargs):
    kws = PANDAS_EXPORT_KWARGS.copy()
    kws.update(kwargs)
    if not gzip:
        kws.pop('compression', None)
    df.to_csv(filename,  columns=columns,  **kws)


def csv_to_dataframe(row_csv):
    df = pd.read_csv(StringIO(row_csv), **PANDAS_IMPORT_KWARGS)
    return df


def load_pkl():
    __predict_proba = None
    try:
        VIO = StringIO(base64.b64decode(MODEL_PKL).strip())
        pipeline = joblib.load(VIO)
        __predict_proba = pipeline.predict_proba
        assert callable(__predict_proba), 'callable( PKL_FILE.predict_proba ).'
    except:
        VIO = StringIO(base64.b64decode(MODEL_PKL).strip())
        pipeline = dill.load(VIO)
        __predict_proba = pipeline.predict_proba
        assert callable(__predict_proba), 'callable( PKL_FILE.predict_proba ).'
    return __predict_proba


predict_proba = load_pkl()


def format_output(req):
    req.ret = json.dumps(req.ret)


def format_input(req, fmt=None):  #### req.ioinput,  req.iodata
    data = json.loads(req.data)
    req.data = data



def process(req):  #### req.data,
    raise ValueError('确认这里直接调用predict_proba, 处理 req.data， 生成 req.ret 供 format_output 处理')
#    scores = predict_proba_py([r[-1] for r in req.data])  # .T[1]
    scores = predict_proba(req.data).T[1]
    req.ret = ret = []
    for idx, score in enumerate(scores):
        data = req.data[idx]
        ret.append([data[0], data[1], `score`])
