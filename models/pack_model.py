def gen_model_py(model_name, model_object_in_memory, *other_objects_in_memory):
    template = """#!/usr/bin/env python
# -*-coding:utf-8-*-
import six,os,sys,pickle,base64

%s

def predict_proba(items):
    '''if MODEL PREPROCESS / FEATURE ENGINEERING required, write below before the "return ..." line. '''
    return PKL_MODEL.predict_proba(items)[:,1]
"""
    import six, os, sys, pickle, base64
    to_bytes = lambda s: s.encode('utf-8') if isinstance(s, six.text_type) else s
    dump_object = lambda obj: base64.b64encode(pickle.dumps(obj, protocol=2))
    load_template = "%s = pickle.loads(base64.b64decode(%r.strip()))"

    loads = []
    load_model_str = load_template % ('PKL_MODEL', dump_object(model_object_in_memory))
    loads.append(load_model_str)

    for idx, obj in enumerate(other_objects_in_memory):
        obj_name = 'PKL_OBJ_%s' % (idx+1)
        obj_str = dump_object(obj)
        load_obj_str = load_template % (obj_name, obj_str)
        loads.append(load_obj_str)

    with open('./%s.py' % model_name, 'wb') as f:
        strs = '\n'.join(loads)
        final_str = template % strs
        f.write(to_bytes(final_str))
        f.flush()

