# -*-coding:utf-8-*-
import six,sys,os, sklearn as sk, pandas as pd, numpy as np

CWD = os.path.abspath(os.getcwd())
if '.' not in sys.path and CWD not in sys.path:
    sys.path.insert(0, CWD)

if six.PY2 and sys.getdefaultencoding() != 'utf8':
    reload(sys)
    sys.setdefaultencoding('utf8')


from sklearn.base import BaseEstimator, TransformerMixin, ClassifierMixin

THIS_DIRNAME = os.path.abspath(os.getcwd())
FINUP_OTP_KEY_FILE  =os.sep.join([THIS_DIRNAME, 'data', 'finup_otp.key' ])

class fit_dummy(BaseEstimator, TransformerMixin):
    def __init__(self):
        self.colname = []

    def fit(self, x,y):
        self.colname = list(pd.get_dummies(x).columns)
        return self
    def transform(self, x):
        dum=pd.get_dummies(x)
        for aa in set(list(self.colname))-set(list(dum.columns)):
            dum[aa]=np.nan
        return dum[self.colname]

import main_server
if __name__ == '__main__':
    main_server.model_initializer()
