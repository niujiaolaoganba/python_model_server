# -*-coding:utf-8-*-

import six,os,sys,base64,hashlib, random as _random
from collections import namedtuple
from functools import update_wrapper
from threading import RLock


if six.PY2 and sys.getdefaultencoding() != 'utf8':
    reload(sys)
    sys.setdefaultencoding('utf8')


LRUCacheInfo = namedtuple("CacheInfo", ["hits", "misses", "maxsize", "currsize"])

class LRUCache(object):
    def __init__(self, usrfunc,  maxsize = 10000000, sentinel=''):
        self.usrfunc = usrfunc
        self.maxsize = maxsize
        self.hits = 0
        self.misses = 0
        self.cache = dict()
        self.lock = RLock()
        self.sentinel = object() if sentinel is None else sentinel
        self.CircularDoublyLinkedList = root = []
        root[:] = [root, root, None, None] #循环双链表, 游标处(key, result) == (None, None)


    def __repr__(self):
        return 'LRUCache[%s]: %s, hits:%s, misses:%s, curr:%s' % (self.maxsize, self.usrfunc, self.hits, self.misses, len(self.cache))

    def hit(self, keys): # 有 maxsize 限制的缓存，tracks accesses by recency
        rets = []
        miss_idxs = []
        with self.lock:
            for idx, key in enumerate(keys):
                link = self.cache.get(key)
                if link is not None: # 最近命中 key, 由原链位取出，插入标注左一位；
                    prv, nxt, key, result = link
                    prv[1] = nxt
                    nxt[0] = prv

                    root = self.CircularDoublyLinkedList
                    prv = root[0]
                    prv[1] = root[0] = link
                    link[0] = prv
                    link[1] = root
                    self.hits += 1
                    rets.append(result)
                else:
                    miss_idxs.append(idx)
                    rets.append(self.sentinel)
        return rets, miss_idxs

    def miss(self, keys, results):
        cache = self.cache
        with self.lock:
            for idx in range(len(keys)):
                key = keys[idx]
                result = results[idx]
                if cache.has_key(key):# 在运行 self.usrfunc 期间同一个key 被加入
                    pass
                elif len(cache) >= self.maxsize: # 缓存满，新key 直接替换游标处(None, None)数据，游标后移一位
                    oldroot = self.CircularDoublyLinkedList
                    oldroot[2], oldroot[3] = key, result
                    root = self.CircularDoublyLinkedList = oldroot[1]

                    # 同时设置新游标处(key, result) == (None, None)
                    oldkey, oldvalue = root[2], root[3]
                    root[2] = root[3] = None

                    # 更新缓存
                    del cache[oldkey]
                    cache[key] = oldroot

                else: # 缓存未满，构造新节点，新key 插在游标处前一位
                    root = self.CircularDoublyLinkedList
                    last = root[0]
                    last[1] = root[0] = cache[key] = [last, root, key, result]

                self.misses += 1

    def stats(self):
        """ 汇报缓存统计信息 """
        with self.lock:
            return LRUCacheInfo(self.hits, self.misses, self.maxsize, len(self.cache))

    def clear(self):
        """ 清空缓存 和 计数器　 """
        with self.lock:
            self.cache.clear()
            root = self.CircularDoublyLinkedList
            root[0] = root[1] = None
            self.CircularDoublyLinkedList = root = []
            root[:] = [root, root, None, None]
            self.hits = self.misses = 0

