#!/usr/bin/python
# coding=utf-8
import jieba
import sqlite3
import numpy as np
from tqdm import tqdm
from flask import Flask, render_template, jsonify, request
import xgboost as xgb

app = Flask(__name__)
app.config.from_object('config')

login_name = None


# --------------------- html render ---------------------
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/house_overview')
def house_overview():
    return render_template('house_overview.html')


@app.route('/house_wordcoluds')
def house_wordcoluds():
    return render_template('house_wordcoluds.html')


@app.route('/basic_analysis')
def basic_analysis():
    return render_template('basic_analysis.html')


@app.route('/influence_analysis')
def influence_analysis():
    return render_template('influence_analysis.html')


@app.route('/house_predict')
def house_predict():
    return render_template('house_predict.html')


# ------------------ ajax restful api -------------------
@app.route('/check_login')
def check_login():
    """判断用户是否登录"""
    return jsonify({'username': login_name, 'login': login_name is not None})


@app.route('/register/<name>/<password>')
def register(name, password):
    conn = sqlite3.connect('user_info.db')
    cursor = conn.cursor()

    check_sql = "SELECT * FROM sqlite_master where type='table' and name='user'"
    cursor.execute(check_sql)
    results = cursor.fetchall()
    # 数据库表不存在
    if len(results) == 0:
        # 创建数据库表
        sql = """
                CREATE TABLE user(
                    name CHAR(256), 
                    password CHAR(256)
                );
                """
        cursor.execute(sql)
        conn.commit()
        print('创建数据库表成功！')

    sql = "INSERT INTO user (name, password) VALUES (?,?);"
    cursor.executemany(sql, [(name, password)])
    conn.commit()
    return jsonify({'info': '用户注册成功！', 'status': 'ok'})


@app.route('/login/<name>/<password>')
def login(name, password):
    global login_name
    conn = sqlite3.connect('user_info.db')
    cursor = conn.cursor()

    check_sql = "SELECT * FROM sqlite_master where type='table' and name='user'"
    cursor.execute(check_sql)
    results = cursor.fetchall()
    # 数据库表不存在
    if len(results) == 0:
        # 创建数据库表
        sql = """
                CREATE TABLE user(
                    name CHAR(256), 
                    password CHAR(256)
                );
                """
        cursor.execute(sql)
        conn.commit()
        print('创建数据库表成功！')

    sql = "select * from user where name='{}' and password='{}'".format(name, password)
    cursor.execute(sql)
    results = cursor.fetchall()

    login_name = name
    if len(results) > 0:
        print(results)
        return jsonify({'info': name + '用户登录成功！', 'status': 'ok'})
    else:
        return jsonify({'info': '当前用户不存在！', 'status': 'error'})


@app.route('/xiaoqu_name_wordcloud')
def xiaoqu_name_wordcloud():
    """小区名称的词云分析"""
    conn = sqlite3.connect('all_house_infos.db')
    cursor = conn.cursor()
    sql = 'select 所属小区 from HouseInfo'
    cursor.execute(sql)
    datas = cursor.fetchall()

    word_count = {}
    for name in tqdm(datas):
        words = jieba.cut(name[0])
        for word in words:
            if word in {'(', ')', '（', '）', '组团'}:
                continue
            if len(word) < 2:
                continue
            if word in word_count:
                word_count[word] += 1
            else:
                word_count[word] = 1

    wordclout_dict = sorted(word_count.items(), key=lambda d: d[1], reverse=True)
    wordclout_dict = [{"name": k[0], "value": k[1]} for k in wordclout_dict if k[1] > 1]
    return jsonify({'词云数据': wordclout_dict})


@app.route('/query_key_count/<key>')
def query_key_count(key):
    """获取房屋属性的个数分布情况"""
    conn = sqlite3.connect('all_house_infos.db')
    cursor = conn.cursor()
    sql = 'select {} from HouseInfo'.format(key)
    cursor.execute(sql)
    datas = cursor.fetchall()

    changquanxingzhi_counts = {}
    for data in datas:
        if data not in changquanxingzhi_counts:
            changquanxingzhi_counts[data] = 0
        changquanxingzhi_counts[data] += 1

    changquanxingzhi = list(changquanxingzhi_counts.keys())
    counts = [changquanxingzhi_counts[c] for c in changquanxingzhi]
    return jsonify({'keys': changquanxingzhi, 'counts': counts})


@app.route('/area_house_count_mean_house_price')
def area_house_count_mean_house_price():
    """不同地区的平均房价情况"""
    conn = sqlite3.connect('all_house_infos.db')
    cursor = conn.cursor()
    sql = 'select 所在位置, 总价 from HouseInfo'
    cursor.execute(sql)
    datas = cursor.fetchall()

    loc_price = {}
    for data in datas:
        loc, price = data
        loc = loc.split('－')[0]

        if loc not in loc_price:
            loc_price[loc] = []

        loc_price[loc].append(price)

    loc_counts = {}
    loc_mean_price = {}
    for loc in loc_price:
        loc_counts[loc] = len(loc_price[loc])
        loc_mean_price[loc] = np.mean(loc_price[loc])

    locations = list(loc_price.keys())
    results = {
        '地区': locations,
        '地区房子数量': [loc_counts[loc] for loc in locations],
        '地区平均房价': [loc_mean_price[loc] for loc in locations],
        '地区房价数据': [loc_price[loc] for loc in locations]
    }
    return jsonify(results)


@app.route('/fetch_house_area_and_price')
def fetch_house_area_and_price():
    """获取房屋面积和价格数据"""
    conn = sqlite3.connect('all_house_infos.db')
    cursor = conn.cursor()

    sql = 'select 总价, 建筑面积, 房屋户型_室数, 房屋户型_厅数, 房屋户型_卫数 from HouseInfo'
    cursor.execute(sql)
    datas = cursor.fetchall()

    results = {'面积': [], '每间房间的面积': [], '总价': []}
    for data in datas:
        zongjia, mianji, huxin_s, huxin_t, huxin_w = data
        # 房间数
        fanjian_count = huxin_s + huxin_t + huxin_w
        # 每间房间的面积
        per_fanjian = mianji / fanjian_count
        results['面积'].append(mianji)
        results['每间房间的面积'].append(per_fanjian)
        results['总价'].append(zongjia)

    return jsonify(results)


@app.route('/fetch_influence_analysis_datas/<column_key>')
def fetch_influence_analysis_datas(column_key):
    """获取影响房价因素分析的数据"""
    conn = sqlite3.connect('all_house_infos.db')
    cursor = conn.cursor()

    sql = 'select {}, 总价 from HouseInfo'.format(column_key)
    cursor.execute(sql)
    datas = cursor.fetchall()

    results = {}
    for data in datas:
        key, value = data
        if key == '':
            continue

        if '房屋户型' in column_key:
            key = str(key) + column_key.split('_')[1][:-1]
        if key not in results:
            results[key] = [value]
        else:
            results[key].append(value)

    counts = []
    for key in results:
        counts.append(len(results[key]))
        results[key] = np.mean(results[key])

    results = list(zip(list(results.keys()), counts, list(results.values())))
    results = sorted(results, key=lambda k: k[2], reverse=False)
    zhibiao = [r[0] for r in results]
    counts = [r[1] for r in results]
    junjia = [r[2] for r in results]

    return jsonify({'指标': zhibiao, '个数': counts, '均价': junjia})


@app.route('/get_all_unique_values/<key>')
def get_all_unique_values(key):
    """获取当前指标所有的唯一值"""
    conn = sqlite3.connect('all_house_infos.db')
    cursor = conn.cursor()
    sql = 'select distinct {} from HouseInfo'.format(key)
    cursor.execute(sql)
    datas = cursor.fetchall()

    key_count = {}
    for data in datas:
        sql = "select count(*) from HouseInfo where {}='{}'".format(key, data[0])
        cursor.execute(sql)
        count = cursor.fetchall()[0][0]
        key_count[data[0]] = count

    key_count = sorted(key_count.items(), key=lambda d: d[1], reverse=True)

    return jsonify(key_count)


model = xgb.Booster(model_file='house_price.model')


@app.route('/history_and_predict_price')
def history_and_predict_price():
    """当前小区的历史价格，以及针对当前配置预测的价格"""
    conn = sqlite3.connect('all_house_infos.db')
    cursor = conn.cursor()

    xiaoqu = request.args.get('所属小区')
    sql = "select 总价, 建筑面积 from HouseInfo where 所属小区='{}'".format(xiaoqu)

    cursor.execute(sql)
    datas = cursor.fetchall()

    results = {'面积': [], '总价': []}
    for data in datas:
        zongjia, mianji = data
        results['面积'].append(mianji)
        results['总价'].append(zongjia)

    # 特征工程
    niandai_map = {'1960年': 320.0, '1979年': 185.0, '1980年': 283.6363636363636, '1981年': 257.09090909090907,
                   '1982年': 266.0, '1983年': 229.0, '1984年': 164.0, '1985年': 248.1225806451613,
                   '1986年': 220.28571428571428, '1987年': 178.125, '1988年': 222.0142857142857,
                   '1989年': 187.08695652173913, '1990年': 249.36, '1991年': 220.6, '1992年': 233.8368888888889,
                   '1993年': 312.92857142857144, '1994年': 207.65217391304347, '1995年': 251.99983333333333,
                   '1996年': 279.30379746835445, '1997年': 174.5625, '1998年': 257.4278787878788, '1999年': 298.35,
                   '2000年': 366.9286561264822, '2001年': 299.6296296296296, '2002年': 263.0690265486726,
                   '2003年': 418.0021582733813, '2004年': 328.9205128205128, '2005年': 407.87220279720276,
                   '2006年': 336.64866666666666, '2007年': 310.4661710037175, '2008年': 373.7600441501104,
                   '2009年': 382.6277456647399, '2010年': 328.01305151915454, '2011年': 334.1781395348837,
                   '2012年': 358.2414324324325, '2013年': 341.07643137254905, '2014年': 334.8586429725363,
                   '2015年': 409.5121596724668, '2016年': 374.71684256816167, '2017年': 392.8033513513514,
                   '2018年': 362.3423473684211, '2019年': 372.92428152492676, '2020年': 386.35606250000006,
                   '2021年': 467.0344827586207, '2022年': 171.25, '暂无建造': 267.42899935442216}
    chaoxiang_map = {'东': 0, '东北': 1, '东南': 2, '东西': 3, '北': 4, '南': 5, '南北': 6, '暂无朝向': 7, '西': 8, '西北': 9, '西南': 10}
    fangwuleix_map = {'公寓': 0, '别墅': 1, '平房': 2, '普通住宅': 3, '未知': 4}
    suozailouceng_map = {'中层': 0, '低层': 1, '地下': 2, '底层': 3, '高层': 4}
    zhuangxiuchengdu_map = {'暂无装修情况': 0, '毛坯': 1, '简单装修': 2, '精装修': 3, '豪华装修': 3}
    changquannianxian_map = {'40年产权': 0, '50年产权': 1, '70年产权': 2, '暂无': 3}
    dianti_map = {'无': 0, '暂无': 0, '有': 1}
    fangbennianxian_map = {'未知': 0, '满二年': 1, '满五年': 2}
    changquanxingzhi_map = {'使用权': 0, '公房': 1, '其它': 2, '动迁配套房': 3, '商住两用': 4, '商品房住宅': 5, '暂无': 6, '经济适用房': 7}
    weiyizhufang_map = {'未知': 0, '否': 0, '是': 1}

    xiaoqu = request.args.get('所属小区')
    niandai = request.args.get('建造年代')
    chaoxiang = request.args.get('房屋朝向')
    fangwuleix = request.args.get('房屋类型')
    suozailouceng = request.args.get('所在楼层')
    zhuangxiuchengdu = request.args.get('装修程度')
    changquannianxian = request.args.get('产权年限')
    dianti = request.args.get('配套电梯')
    fangbennianxian = request.args.get('房本年限')
    changquanxingzhi = request.args.get('产权性质')
    weiyizhufang = request.args.get('唯一住房')
    shishu = request.args.get('房屋户型_室数')
    tingshu = request.args.get('房屋户型_厅数')
    weishu = request.args.get('房屋户型_卫数')
    zonglouceng = request.args.get('总楼层')

    feature = {
        '建筑面积': float(request.args.get('建筑面积')),
        '建造年代平均总价': niandai_map[niandai],
        '建造年代': int(niandai[:-1]) if '暂无' not in niandai else 2015,
        '房屋朝向': chaoxiang_map[chaoxiang],
        '房屋类型': fangwuleix_map[fangwuleix],
        '所在楼层': suozailouceng_map[suozailouceng],
        '装修程度': zhuangxiuchengdu_map[zhuangxiuchengdu],
        '产权年限': changquannianxian_map[changquannianxian],
        '配套电梯': dianti_map[dianti],
        '房本年限': fangbennianxian_map[fangbennianxian],
        '产权性质': changquanxingzhi_map[changquanxingzhi],
        '唯一住房': weiyizhufang_map[weiyizhufang],
        '房屋户型_室数': int(shishu),
        '房屋户型_厅数': int(tingshu),
        '房屋户型_卫数': int(weishu),
        '总楼层': int(zonglouceng)
    }
    df_columns = ['产权性质', '房屋类型', '产权年限', '房本年限', '唯一住房', '所在楼层', '建筑面积', '装修程度', '房屋朝向', '建造年代', '配套电梯', '房屋户型_室数',
                  '房屋户型_厅数', '房屋户型_卫数', '总楼层', '建造年代平均总价']

    test_x = [feature[f] for f in df_columns]

    dtest = xgb.DMatrix(np.array([test_x]), feature_names=df_columns)
    predict_price = model.predict(dtest)[0]
    predict_price = np.expm1(predict_price)

    results['predict_price'] = str(predict_price)
    return jsonify(results)


if __name__ == "__main__":
    app.run(host='127.0.0.1')
