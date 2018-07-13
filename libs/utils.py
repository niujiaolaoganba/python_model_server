# -*-coding:utf-8



import six,os,sys,imp,base64,hashlib,re,csv,threading, random as _random, numpy as np, pandas as pd, pickle,dill
from multiprocessing import pool, Process, Manager
from sklearn.externals import joblib
from tornado import log, process,escape

if six.PY2 and sys.getdefaultencoding() != 'utf8':
    reload(sys)
    sys.setdefaultencoding('utf8')


NAN_STR = r'\N'
PANDAS_EXPORT_KWARGS = dict( header=False, index=False, index_label=False,
    na_rep='\\N', sep='|', quoting=False, float_format='%.6f', date_format='%Y-%m-%d %H:%M:%S',
    compression='gzip', encoding='utf-8', chunksize=1000000,)


def load_pkl(dumps):
    rawstr = base64.b64decode(dumps)
    #VIO =six.BytesIO(rawstr) if isinstance(rawstr, six.binary_type) else six.StringIO(rawstr)
    VIO =six.BytesIO(rawstr) if isinstance(rawstr, six.binary_type) else six.BytesIO(escape.utf8(rawstr))
    try:
        __predict_proba= joblib.load(VIO).predict_proba
    except:
        try:
            __predict_proba = dill.load(VIO).predict_proba
        except:
            VIO.close()
            return None
    VIO.close()
    del VIO
    return __predict_proba


INTERNAL_TYPES = ('bool', 'int', 'float', 'str')
def parse_csv(req, seg, csvbody):
    if len(csvbody) < 2:
        req.write('''
interface.csv {segment}部分 定义不正确，{segment}部分:
 至少需要两行:          "字段名行",  "类型行"; 
 建议包含四行: "序号行", "字段名行", "类型行", "启用状态行"
 例如:
        0|1|2|3|4                                                         ## <- 序号行 ( 可选 )
        Time|DeviceID|性别|年龄|消费水平                                    ## <- 字段名行
        numpy.object|numpy.object|numpy.object|numpy.object|numpy.object  ## <- 类型行
        1|1|1|1|1                                                         ## <- 启用状态行 (可选， 如未指定，全部为1启用)

 注意: "##" 之后的为注释
            '''.format(segment=seg))
        return

    dim = len([i for i in csvbody[0] if i.strip()])
    if dim != len(csvbody[0]):
        csvbody = map(lambda x: x[:dim], csvbody)

    offset = (1 if (map(lambda x: str(x), range(dim)) == csvbody[0]) else 0)
    name_line = csvbody[offset + 0]
    type_line = csvbody[offset + 1]

    enable_line = None
    enable_byuser = all(map(lambda x: x in ('0', '1'), csvbody[offset + 2]))
    if enable_byuser:
        enable_line = [int(i) for i in csvbody[offset + 2]]
    else:
        enable_line = [1] * len(name_line)

    i_samples =[line for line in (csvbody[offset+3:] if enable_byuser else csvbody[offset+2:]) if sum(map(len,line)) > 0]

    if len(type_line) != len(name_line):
        req.write('''
interface.csv {segment}部分 定义不正确，所有行都应有相同列数(维度), :
    "名字行"(维度:{name_dim}): {name_line}
    "类型行"(维度:{type_dim}): {type_line}
    '''.format(name_dim=len(name_line), name_line=name_line, type_dim =len(type_line), type_line=type_line))
        return

    if len(enable_line) != len(name_line):
        req.write('''
interface.csv {segment}部分 定义不正确，所有行都应有相同列数(维度), :
    "名字行"(维度:{name_dim}): {name_line}
    "启用行"(维度:{enable_dim}): {enable_line}
    '''.format(segment=seg, name_dim=len(name_line), name_line=name_line, enalbe_dim =len(enable_line), enable_line=enable_line))
        return

    type_errmsg ='''
interface.csv {segment}部分，
    类型:{type_name} 定义不正确(序号:{seq_num}).
      {msg}
    合法类型:
      python 内部类型: (bool, int, float, str);
      numpy 内部类型: np.bool, np.int, ...
      pandas 内部类型: pd.bool, pd.str, ...

'''

    for idx,tp in enumerate(type_line):
        if tp.find('.') < 2:
            if tp not in INTERNAL_TYPES:
                req.write(type_errmsg.format(
                    segment=seg, seq_num=idx, type_name=tp, msg=('python 内部类型仅支持%s' % INTERNAL_TYPES))
                )
                return
        else:
            mod, _, attr = tp.partition('.')
            mod = mod.replace('numpy', 'np').replace('pandas', 'pd')
            if mod == 'np':
                if not hasattr(np, attr):
                    req.write(type_errmsg.format(
                    segment=seg, seq_num=idx, type_name=tp, msg='np(numpy)没有这个: %r类型属性.' % attr ))
                    return

            elif mod == 'pd':
                if not hasattr(pd, attr):
                    req.write(type_errmsg.format(
                        segment=seg, seq_num=idx, type_name=tp, msg='pd(pandas)没有这个: %r类型属性.' % attr))
                return
            else:
                req.write(type_errmsg.format(
                    segment=seg, seq_num=idx, type_name=tp, msg=''))
                return

    model_data_dict = []
    for i in range(len(name_line)):
        name = name_line[i]
        tp = type_line[i].strip()
        enable = enable_line[i]
        model_data_dict.append((name, tp, enable))

    return model_data_dict


class ComputationPool(pool.Pool):
    _current = None
    _lock = threading.Lock()
    @staticmethod
    def instance(init=True):
            current = getattr(ComputationPool._current, "instance", None)
            if current is not None:
                return current
            with ComputationPool._lock as lock:
                current = getattr(ComputationPool._current, "instance", None)
                if current is not None:
                    return current
                assert current is None
                current = ComputationPool._current = ComputationPool()
                return current

    @staticmethod
    def worker_register(states, manager, initializer, initargs):
        glbs = globals()
        _predict_proba = __import__('finup_model').predict_proba
        glbs['predict_proba'] = _predict_proba
        glbs['states'] = states
        glbs['manager'] = manager
        if initializer is not None:
            if not initargs:
                initializer()
            else:
                initializer(*initargs)

    def __init__(self, processes=None, initializer=None, initargs=(), maxtasksperchild=None):
        self.manager = Manager()
        self.states = self.manager.dict()
        new_initargs = tuple([self.states, self.manager, initializer, initargs])
        super(ComputationPool, self).__init__(processes,  ComputationPool.worker_register, new_initargs, maxtasksperchild)

#cpool = ComputationPool()
#ord_enc = category_encoders.OrdinalEncoder()
#ord_enc.fit(nd)
#nd_ordinal_encoded = ord_enc.fit_transform(nd)
#onehot_enc = category_encoders.OneHotEncoder()
#onehot_enc.fit(nd)
#nd_onehot_encoded = onehot_enc.fit_transform(nd)
















