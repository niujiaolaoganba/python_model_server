# coding: utf-8
import six,time,datetime,csv,simplejson as json,gc,traceback, gzip,collections,inspect
from tornado.web import asynchronous,RequestHandler,HTTPError
from tornado.gen import coroutine,Return,is_coroutine_function
from tornado.escape import json_decode, json_encode, utf8, _unicode,to_basestring
from tornado.concurrent import run_on_executor
from tornado.log import app_log

import numpy as np, pandas as pd, hashlib, finup_model


STATS = []
CACHE_LR = {}


def text2utf8(rows, alltext=False):
    ret = []
    for row in rows:
        if alltext is False:
            ret.append([i.encode('utf8') if isinstance(i, six.text_type) else i for i in row])
        else:
            r = []
            for i in row:
                if isinstance(i, six.text_type):
                    r.append(i.encode('utf8'))
                elif isinstance(i, six.binary_type):
                    r.append(i)
                else:
                    s = six.text_type(i)
                    r.append(s.encode('utf8') if isinstance(s, six.text_type) else s)
            ret.append(r)
    return ret

class FinupHandler(RequestHandler):
    def initialize(self, *args, **kws):
        if self.request.headers.get('Connection',None) == 'keep-alive':
            self._auto_finish = False

    def pretty_stats(self, times):
        ret = []
        total_time = 1000 * times[-1][-1] - 1000 * times[0][-1]
        for idx, (stage, tm) in enumerate(times):
            if idx == 0:
                if total_time > 1000:
                    ret.append('total: %.4f, %.2fqps, %s: %.4f' % (total_time/1000, 1000/total_time, stage, tm))
                else:
                    ret.append('total: %sms, %.2fqps, %s: %.4f' % (total_time, 1000/total_time, stage, tm))
            else:
                ms = 1000 * (tm - times[idx-1][-1])
                percent = '%.4f' % (ms / total_time)
                ret.append('% 15s: %s.%s%% %.5fms' % ( stage, percent[2:4], percent[4:], ms))
        return '\n'.join(ret)

    @coroutine
    def get(self, *args, **kwargs):
        self.finish(','.join(sorted(finup_model.MODELS.keys())))

    @coroutine
    def post(self, *args, **kwargs):
        self.debug =False if self.get_query_argument('debug', None) is None else True
        if self.debug:
            import pdb;pdb.set_trace()
        model = self.get_query_argument('model', None)
        if not model:
            self.finish(finup_model.API_DOC)
            return
        models = []
        for m in model.split(','):
            if m not in finup_model.MODELS:
                self.finish('无匹配服务模型名:%r, 可用模型: %r' % (m, sorted(finup_model.MODELS.keys())))
                return
            models.append((m, finup_model.MODELS[m]))

        self.times = [('received', time.time()) ]
        self.format = self.get_query_argument('format', None)
        self.stats = self.get_query_argument('stats', None)
        logon = finup_model.LOGON
        try:
            r = yield self.preprocess()
            if logon:
                app_log.error('LOG REQ:  method:%s, uri:%s, data:%r', self.request.method, self.request.uri, self.data_origin)
            rets = yield self.process_data(models)
            if logon:
                app_log.error('LOG RET: %s\n', rets)
            self.write(rets)
            if self.format == 'csv':
                self.set_header('Content-Type', 'text/csv; charset=UTF-8')
            elif self.format == 'json':
                self.set_header('Content-Type', 'application/json; charset=UTF-8')
            self.flush()
            if self.stats:
                self.times.append(('flushed', time.time()))
                self.write('\n%s\n'% self.pretty_stats(self.times))
                self.flush()
        except:
            excstr = finup_model.print_exc(limit=2)
            self.write(excstr)
            app_log.error('ERR REQ:  method:%s, uri:%r, data:%r\n', self.request.method, self.request.uri, getattr(self,'data_origin', getattr(self, 'data')))

    @coroutine
    def process_data(self, models):
        rets = []
        if self.debug:
            import pdb;pdb.set_trace()
        max_index = len(models) - 1
        for i in range(max_index + 1):
            if i < max_index:
                self.data = self.data_origin[:]
            else:
                self.data = self.data_origin
                del self.data_origin

            modsym, model = models[i]
            self.ret = None
            self.model_module =model
            try:
                self.format_input()
                self.times.append(('format_input', time.time()))
                proc = getattr(self.model_module, 'process', None)
                if is_coroutine_function(proc):
                    r = yield proc(self)
                    if self.ret is None and r:
                        self.ret = r
                elif callable(proc):
                    r = proc(self)
                    if self.ret is None and r:
                        self.ret = r
                elif hasattr(self.model_module, 'predict_proba'):
                    predict_proba = self.model_module.predict_proba
                    if is_coroutine_function(predict_proba):
                        self.ret = yield predict_proba(self.data)
                    elif callable(predict_proba):
                        self.ret = predict_proba(self.data)
                    else:
                        raise ValueError('model:%r, entrypoint function "predict_proba" is not callable.' % modsym )
                else:
                    raise ValueError('model:%r, neither entrypoint function "process" nor "predict_proba" was defined.' % modsym )
                self.times.append(('model_process', time.time()))
                self.format_output()
                self.times.append(('format_output', time.time()))
                rets.append((modsym, self.ret))
                del self.ret
            except:
                fio = six.StringIO()
                finup_model.print_exc(file=fio)
                rets.append((modsym, fio.getvalue()))
                del fio
        if self.format == 'json':
            raise Return('{'+ ','.join([('"%s":'%(modsym.decode() if isinstance(modsym, six.binary_type) else modsym) +v) for (modsym, v) in rets ]) + '}')
        else:
            raise Return(json.dumps(dict(rets)))

    @coroutine
    def preprocess(self):
        self.data_origin = ''
        if len(self.request.files.get('files',[])) > 0:
            self.data_origin = self.request.files["files"][0].pop("body").strip()
            self.filename = filename = self.request.files["files"][0].get("filename",'')
            if self.format is None:
                self.format = 'csv' if filename.endswith('.csv') or filename.endswith('.csv.gz') else 'json'
            if filename.endswith('.gz'):
                self.data_origin = gzip.GzipFile(fileobj=six.StringIO(self.data_origin), mode='rb').read().strip()
        else:
            self.filename = None
            self.data_origin = self.request.body.strip()
            del self.request.body
            if self.debug:
                import pdb;pdb.set_trace()
            if self.format is None:
                if self.data_origin.startswith('[') and self.data_origin.endswith(']'):
                    self.format = 'json'

        assert len(self.data_origin) > 0, '未检测到任何提交数据 self.data_origin: %r' % self.data_origin
        self.times.append(('preprocess', time.time()))

    def format_input(self):
        fmt = self.format
        if fmt == 'json':
            self.data = json.loads(self.data)
        elif fmt == 'csv':
            self.data =( i.split('|') for i in  self.data.split(b'\n') if i.strip() )
        elif hasattr(self.model_module, 'format_input'):
            self.model_module.format_input(self, fmt=fmt)
        else:
            raise ValueError('未知数据格式: format=%r' % fmt)
        assert isinstance(self.data, (list, tuple, np.ndarray, pd.Series, pd.DataFrame)) and len(self.data) > 0 \
                or inspect.isgenerator(self.data) \
                or inspect.isgeneratorfunction(self.data) , \
                '请确认数据格式正确, fmt:%r, HTTP POST DATA should enclosed by "[]",\n type:%s, self.data:%r' % (fmt, type(self.data), self.data)

    def format_output(self):
        fmt = self.format
        if fmt == 'json':
            self.ret = json.dumps(self.ret)
        elif fmt == 'csv':
            sio = six.StringIO()
            csvio = csv.writer(sio, delimiter='|', quotechar='"')
            if six.PY2:
                self.ret = text2utf8(self.ret, alltext=False)
            csvio.writerows(self.ret)
            self.ret = sio.getvalue()
        elif hasattr(self.model_module, 'format_output'):
            self.model_module.format_output(self, fmt=fmt)
        else:
            raise ValueError('未知数据格式: format=%r' % fmt)
        assert len(self.ret) > 0, '结果数据为空，请确认数据格式正确, fmt:%r, self.ret:%r'%(fmt, self.ret)
