# -*-coding:utf-8-*-

import sys,os,re,six,shutil,multiprocessing ,numpy, pandas
sys.path.insert(0, '.')

from distutils.core import setup
from Cython.Build import cythonize
from distutils.extension import Extension


if len(sys.argv) == 1:
    sys.argv.extend(['build_ext',  '--inplace'])

CURRENT_FILE = os.path.abspath(__file__)
BASEDIR = os.path.dirname(CURRENT_FILE)
BASENAME  = os.path.basename(CURRENT_FILE)

extension_files = [
  ('./models/shuju_pintu__20180503_model', './models/shuju_pintu__20180503_model.c'),
]
ff = extension_files[0][0]
#cythonized_extensions = cythonize([ ff + '.py' ])
cythonized_extensions = cythonize([  Extension(ext_modname, [c_file]) for ext_modname, c_file in extension_files  ])

setup( ext_modules=cythonized_extensions, build_dir = BASEDIR, include_path = [numpy.get_include()],
)

