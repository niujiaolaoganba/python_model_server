
from sklearn.externals import joblib
from pack_model import gen_model_py

model = joblib.load('./lr.pkl')
gen_model_py('./ff_tf_2018071314_model', model)