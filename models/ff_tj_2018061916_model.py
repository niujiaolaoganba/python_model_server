#!/usr/bin/env python
# -*-coding:utf-8-*-

import pandas as pd
from random import shuffle
import finup_model
import simplejson as json
import struct, time
from tornado import gen, log, ioloop
import operator

# loan_order = ['15','02','25','42','21','01','41','05','12','35','10','03','37','38','23','07','26','31','13','28','39','24','34','09','32','16','30','08','17','29','18','06','14','20','22','11','04','33','36','40']
manage_order = ["031", "030"]
credit_order = ['0505_03','0506_08','0505_05','0506_10','0505_01','0506_09','0506_11','0510_03','0505_07','0511_01','0511_04','0506_12','0511_05','0505_09','0508_01','0511_08','0507_13','0508_02','0507_14','0511_06','0511_02','0513_04','0513_01','0507_07','0510_04','0511_03','0505_08','0505_06','0507_15','0508_03','0510_05','0507_01','0506_06','0505_10','0505_02','0506_15','0513_03','0514_01','0507_06','0506_14','0513_05','0507_08','0507_12','0513_02','0507_09','0507_05','0501_04','0507_11','0506_02','0506_13','0501_03','0514_02','0518_01','0501_01','0501_05','0514_03','0501_02','0514_04','0506_01','0501_06','0505_04','0501_07','0506_07','0506_05','0510_01','0507_10','0507_03','0511_07','0506_03','0518_02','0507_02','0506_04','0507_04','0502_01']

loan_names = []
loan_id_name = {}
loan_order = []

class FFRank():
    def _user_type(self, tags):
        user_type = 1
        if tags and 'getuirisk.white.2018041718.score' in tags and tags['getuirisk.white.2018041718.score'] <= 0.384:
            user_type = 5
        elif tags and 'getui.2018022816.probability(1-0)' in tags and tags['getui.2018022816.probability(1-0)'] >= 0.8328:
            user_type = 1
        elif tags and 'gtlicai.2018050719.label' in tags and tags['gtlicai.2018050719.label'] >= 86:
            user_type = 2
        return user_type

    def _loan_rank(self, loan_ids, tags, usertype):
        rank_loan_ids = [item for item in loan_order if item in loan_ids] # 规则排序
        new_ids = [item for item in loan_ids if item not in loan_order] # 新品
        shuffle(new_ids)
        new_loan_ids = rank_loan_ids[:13] + new_ids + rank_loan_ids[13:]

        # applist已安装b2降权
        if tags and 'applist' in tags:
            loan_installed = [loan_id_name[lp] for lp in tags['applist'].split(',') if lp in loan_id_name]
            if len(loan_installed) > 0 :
                for lp in loan_installed:
                    new_loan_ids.remove(lp)
                    new_loan_ids.append(lp)

        # 万卡置顶
        if '01' in new_loan_ids:
            new_loan_ids.remove('01')
            new_loan_ids.insert(0, '01')

        # 预授信钱站置顶
        if usertype == 5:
            new_loan_ids.remove('01')
            new_loan_ids.insert(0, '01')

        return ','.join(new_loan_ids)

    def _credit_rank(self, credit_ids):
        rank_credit_ids = [item for item in credit_order if item in credit_ids]
        new_ids = [item for item in credit_ids if item not in credit_order]
        shuffle(new_ids)
        for i in range(len(new_ids)):
            if 3 + i * 2 < len(rank_credit_ids):
                rank_credit_ids.insert(3 + i * 2, new_ids[i])
            else:
                rank_credit_ids.append(new_ids[i])

        return ','.join(rank_credit_ids)

    def _manage_rank(self, manage_ids):
        rank_manage_ids = [item for item in manage_order if item in manage_ids]
        new_ids = [item for item in manage_ids if item not in manage_order]
        shuffle(new_ids)
        rank_manage_ids = new_ids + rank_manage_ids
        return ','.join(rank_manage_ids)

    def predict_proba(self, items):
        for item in items:
            item['user_type'] = self._user_type(item['tags'])
            if 'loan_ids' in item and len(item['loan_ids']) > 1:
                item['loan_ids'] = self._loan_rank(item['loan_ids'].split(','), item['tags'], item['user_type'])
            else :
                item['loan_ids'] = self._loan_rank(lpcode, item['tags'], item['user_type'])

            if 'credit_ids' in item and len(item['credit_ids']) > 1:
                item['credit_ids'] = self._credit_rank(item['credit_ids'].split(','))
            else :
                item['credit_ids'] = self._credit_rank(cardcode)

            if 'manage_ids' in item and len(item['manage_ids']) > 1:
                item['manage_ids'] = self._manage_rank(item['manage_ids'].split(','))
            else:
                item['manage_ids'] = self._manage_rank(ipcode)

        return items

def format_input(req, fmt=None):  #### req.ioinput,  req.iodata
    data = json.loads(req.data)
    req.data = data

def format_output(req, fmt='json'):
    req.ret = json.dumps(req.ret)

@gen.coroutine
def PeriodcUpdate():
    redis = finup_model.get_redis()
    pp = finup_model.get_redis_pipeline()

    if not redis.is_connected():
        _ = yield redis.connect()

    global lpcode
    lpcode = yield redis.call('smembers', 'lpcode')
    global cardcode
    cardcode = yield redis.call('smembers', 'xinyongka_code')
    global ipcode
    ipcode = yield redis.call('smembers', 'licai_code')

    _ = [pp.stack_call('GET', index) for index in lpcode]
    df = yield redis.call(pp)

    global loan_names
    loan_names = [item.split('|')[1] for item in df]
    global loan_id_name
    loan_id_name = {item.split('|')[1]: item.split('|')[0] for item in df}
    global loan_order
    loan_order = {item.split('|')[0]: float(item.split('|')[3]) for item in df if item.split('|')[3] != 'nan'}
    loan_order = sorted(loan_order, key=loan_order.get, reverse=True)


PeriodvTime = 60 * 1000
PeriodicTask = ioloop.PeriodicCallback(PeriodcUpdate, PeriodvTime)
PeriodicTask.start()


@gen.coroutine
def process(req):
    req.ret = predict_proba(req.data)


def predict_proba(items):
    r = FFRank()
    return r.predict_proba(items)



if __name__ == "__main__":
    import simplejson as json
    test = json.load(open('../data/test.ff_tj_2018061916.json', 'rb'))
    print test
    ret = predict_proba(test)
    print(ret)