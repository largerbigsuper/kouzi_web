import os
import random
import string
import time
import pymongo
import tokenutils
import sendsms
import re
import json
import urllib
from flask import Flask, session, redirect, url_for, \
    request, jsonify, send_from_directory
from flask_cors import CORS
from config import MONGO_HOST, MONGO_PORT, MONGO_DB_NAME
from gevent.pywsgi import WSGIServer
from bson.objectid import ObjectId

app = Flask(__name__)
CORS(app)

# 设置密钥
app.secret_key = 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT'

# 数据库连接
client = pymongo.MongoClient(host=MONGO_HOST, port=MONGO_PORT)
db = client[MONGO_DB_NAME]


def random_code():
    # 查询码生成
    code = ''.join(random.sample(string.ascii_lowercase + string.digits, 4))
    return code

# 拦截器
@app.before_request
def token_check():
    token = request.args.get('token')
    if(token is not None):
        user_token = db['user_token'].find_one({'token': token})
        if(user_token is None):
            return jsonify({'code': 99, 'desc': 'token失效'})
        else:
            print(user_token)

# 查询码创建
@app.route('/createCode', methods=['GET'])
def create_code():
    try:
        count = int(request.args.get('count'))
        name = request.args.get('name')
        phone = request.args.get('phone')
        date = time.strftime('%Y-%m-%d %H:%M:%S',
                             time.localtime(time.time()))
        if(count > 0):
            code = random_code()
            code_auth = {
                "code": code,
                "count": count,
                "total": count,
                "name": name,
                "phone": phone,
                "date": date,
                'last_query': ''
            }
            db['auth_code'].update_one(
                {'code': code, 'name': name, 'phone': 'phone'},
                {"$set": code_auth}, upsert=True)

            # 发送查询码注册短信通知
            sendsms.sendAddAuthCodeSms(name, phone, code, count)
            return jsonify({'code': 0, 'desc': '请求成功'})
    except ValueError as e:
        print(e)
        return jsonify({'code': 1, 'desc': '请求异常'})

# 后台获取查询码列表
@app.route('/codeList', methods=['GET'])
def codeList():
    # 当前在第几页
    index = int(request.args.get('index', 1))
    # 每页几条数据
    page_size = int(request.args.get('pageSize', 10))
    # 总页数查询
    total = int(db['auth_code'].count_documents({}))
    # 计算总页数
    if total % page_size > 0:
        total_page = int(total / page_size + 1)
    else:
        total_page = int(total / page_size)

    results = {}
    data = []
    # 分页查询
    for item in db['auth_code'].find() \
            .sort([('_id', pymongo.DESCENDING)]) \
            .skip(page_size*(index-1)).limit(page_size):
        item['_id'] = str(item['_id'])
        data.append(item)

    results['total'] = total
    results['total_page'] = total_page
    results['data'] = data
    return jsonify({'code': 0, 'data': results})

# 后台获取指定查询码查询的产品列表
@app.route('/productByCodeList', methods=['GET'])
def productByCodeList():
    # 查询码
    code = str(request.values.get('code'))
    reducer = """
        function(obj, prev) {
            prev.count++;
        }
    """
    results = {}
    data = []
    # 聚合查询
    for item in db['history'].group(['name'], {'code': code}, {'count': 0}, reducer):
        isCheck = 0
        pick = int(db['product_code'].count_documents(
            {'code': code, 'product': item['name']}))
        if(pick > 0):
            isCheck = 1

        productCodeObj = {
            'name': item['name'],
            'count': item['count'],
            'isCheck': isCheck
        }
        data.append(productCodeObj)

    results['data'] = data
    return jsonify({'code': 0, 'data': results})

# 后台创建监控查询码及产品名关联关系
@app.route('/bindProductAndCode', methods=['GET'])
def bindProductAndCode():
    # 查询码
    code = str(request.values.get('code'))
    # 产品名称
    product = str(request.values.get('product'))

    count = int(db['product_code'].count_documents({'code': code}))
    if(count > 3):
        return jsonify({'code': 99, 'desc': '最多监控3个产品'})

    queryObj = db['product_code'].find_one({'code': code, 'product': product})
    if(queryObj is not None):
        return jsonify({'code': 0, 'desc': '请求成功'})

    product_code = {
        'code': code,
        'product': product
    }
    db['product_code'].insert_one(product_code)

    return jsonify({'code': 0, 'desc': '请求成功'})

# 后台获取监控查询码及产品名关联列表
@app.route('/getProductAndCodeList', methods=['GET'])
def getProductAndCodeList():
    # 当前在第几页
    index = int(request.args.get('index', 1))
    # 每页几条数据
    page_size = int(request.args.get('pageSize', 10))
    # 总页数查询
    total = int(db['product_code'].count_documents({}))
    # 计算总页数
    if total % page_size > 0:
        total_page = int(total / page_size + 1)
    else:
        total_page = int(total / page_size)

    results = {}
    data = []
    # 分页查询
    for item in db['product_code'].find() \
            .sort([('_id', pymongo.DESCENDING)]) \
            .skip(page_size*(index-1)).limit(page_size):
        item['_id'] = str(item['_id'])
        data.append(item)

    results['total'] = total
    results['total_page'] = total_page
    results['data'] = data
    return jsonify({'code': 0, 'data': results})

# 后台删除监控查询码及产品名关联关系
@app.route('/delProductAndCode', methods=['GET'])
def delProductAndCode():
    # 查询码
    code = str(request.values.get('code'))
    # 产品名称
    product = str(request.values.get('product'))
    db['product_code'].find_one_and_delete({'code': code, 'product': product})
    return jsonify({'code': 0, 'desc': '请求成功'})

# 编辑查询码可查询次数
@app.route('/editCodeQueryNum')
def editCodeQueryNum():
    _id = request.values.get('_id')
    queryNum = int(request.values.get('queryNum'))
    if(_id is None or queryNum is None):
        return jsonify({'code': -1, 'desc': '请求数据错误'})

    authCode = db['auth_code'].find_one({'_id': ObjectId(_id)})
    if(authCode is not None):
        db['auth_code'].update_one({'_id': ObjectId(_id)},
                                   {"$set": {'total': queryNum + int(authCode['total']), 'count': queryNum + int(authCode['count'])}})
    return jsonify({'code': 0, 'desc': '请求成功'})

# 创建广告
@app.route('/createAd', methods=['POST'])
def create_ad():
    if 'ad_banner' in request.files:
        ad_banner = request.files.get('ad_banner')
        ad_link = request.form['ad_link']
        filename = ad_banner.filename
        img_path = os.path.join(os.getcwd(), 'static/upload/'+filename)
        ad_banner.save(img_path)
        ad_banner_link = 'https://api.yingbigege.com/static/upload/' + filename
        date = time.strftime('%Y-%m-%d %H:%M:%S',
                             time.localtime(time.time()))
        ad = {
            'ad_link': ad_link,
            'ad_banner': ad_banner_link,
            'date': date
        }
        db['ad'].drop()
        db['ad'].insert_one(ad)
        return jsonify({'code': 0, 'desc': '请求成功'})
    return jsonify({'code': 1, 'desc': '请求失败'})

# 广告后台展示
@app.route('/ad')
def ad():
    data = []
    for item in db['ad'].find({}):
        item['_id'] = str(item['_id'])
        data.append(item)
    return jsonify({'code': 0, 'data': data})

# 后台登录
@app.route('/login', methods=['GET'])
def login():
    username = request.args.get('username')
    password = request.args.get('password')
    user = db['admin'].find_one({'username': username})
    if(user is not None):
        if(user['password'] == password):
            data = {}
            data['username'] = user['username']
            data['_id'] = str(user['_id'])
            token = tokenutils.getTokenByUserId(str(user['_id']))
            data['token'] = token

            user_token = {
                "user_id": user['_id'],
                "token": str(token)
            }
            db['user_token'].update_one(
                {'user_id': user['_id']},
                {"$set": user_token}, upsert=True)

            return jsonify({'code': 0, 'desc': '登录成功', 'data': data})
    return jsonify({'code': 1, 'desc': '账号密码错误', 'data': []})

# 管理后台管理员列表
@app.route('/getAdminUserList')
def getAdminUserList():
    # 当前在第几页
    index = 1
    # 每页几条数据
    page_size = 50
    # 返回数据
    data = []
    queryList = db['admin'].find() \
        .sort([('_id', pymongo.DESCENDING)]) \
        .skip(page_size*(index-1)).limit(page_size)
    for item in queryList:
        resultList = {
            '_id': str(item['_id']),
            'username': item['username'],
        }
        data.append(resultList)
    return jsonify({'code': 0, 'desc': '请求成功', 'data': data})

# 编辑管理后台管理员信息
@app.route('/editAdminUser')
def editAdminUser():
    username = request.values.get('username')
    password = request.values.get('password')
    if(username is None or password is None):
        return jsonify({'code': -1, 'desc': '账号或密码不能为空'})

    admin = {
        'username': username,
        'password': password
    }
    user = db['admin'].find_one({'username': username})
    if(user is None):
        db['admin'].insert_one(admin)
    else:
        db['admin'].update_one(
            {'username': username}, {"$set": {'password': password}}
        )
    return jsonify({'code': 0, 'desc': '请求成功'})

# 编辑当前登录人密码
@app.route('/editUserPwd')
def editUserPwd():
    token = request.values.get('token')
    password = request.values.get('password')
    if(password is None):
        return jsonify({'code': -1, 'desc': '密码不能为空'})

    user_token = db['user_token'].find_one({'token': token})
    if(user_token is not None):
        db['admin'].update_one(
            {'_id': ObjectId(user_token['user_id'])}, {
                "$set": {'password': password}}
        )

    return jsonify({'code': 0, 'desc': '请求成功'})

# 删除管理后台管理员
@app.route('/delAdminUser')
def delAdminUser():
    _id = request.values.get('_id')
    if(_id is None):
        return jsonify({'code': -1, 'desc': '所选用户不存在'})
    db['admin'].delete_one({'_id': ObjectId(_id)})
    return jsonify({'code': 0, 'desc': '请求成功'})

# 后台退出
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

# 管理后台首页统计
@app.route('/getQueryCount')
def getQueryCount():
    data = {
        'todayCount': 0,
        'totalCount': 0
    }

    ctime = time.time()
    ctime = ctime - ctime % 86400
    data['todayCount'] = db['history'].count_documents(
        {'time': {'$gte': ctime}})
    data['totalCount'] = db['history'].count_documents({})
    return jsonify({'code': 0, 'desc': '请求成功', 'data': data})

# 管理后台查询历史记录
@app.route('/getQueryHistory')
def getQueryHistory():
    ctime = time.time()
    ctime = ctime - ctime % 86400

    # 当前在第几页
    index = int(request.args.get('index', 1))
    # 每页几条数据
    page_size = int(request.args.get('pageSize', 10))
    # 查询类型 0-全部 1-今日
    query_type = int(request.args.get('type'), 0)
    # 总页数查询
    total = 0
    if query_type == 0:
        total = db['history'].count_documents({})
    else:
        total = db['history'].count_documents({'time': {'$gte': ctime}})
    # 计算总页数
    if total % page_size > 0:
        total_page = int(total/page_size + 1)
    else:
        total_page = int(total/page_size)

    results = {}
    data = []
    queryList = []
    queryObj = {}
    # 分页查询
    if query_type == 0:
        queryList = db['history'].find() \
            .sort([('_id', pymongo.DESCENDING)]) \
            .skip(page_size*(index-1)).limit(page_size)
    else:
        queryList = db['history'].find({'time': {'$gte': ctime}}) \
            .sort([('_id', pymongo.DESCENDING)]) \
            .skip(page_size*(index-1)).limit(page_size)

    for item in queryList:
        authCode = db['auth_code'].find_one({'code': item['code']})
        username = '--'
        if authCode is not None:
            username = authCode['name']

        timeStr = time.strftime("%Y-%m-%d %H:%M:%S",
                                time.localtime(item['time']))

        queryObj = {
            '_id': str(item['_id']),
            'code': item['code'],
            'username': username,
            'name': item['name'],
            'time': timeStr
        }
        data.append(queryObj)

    results['total'] = total
    results['total_page'] = total_page
    results['data'] = data
    return jsonify({'code': 0, 'data': results})

# 小程序查询接口
@app.route('/api/v1/search', methods=['POST'])
def search():
    code = request.values.get('code')
    name = request.values.get('name')
    if(name is None):
        return jsonify({'code': -1, 'desc': '产品名称不能为空'})

    auth = db['auth_code'].find_one({'code': code})
    if(auth is not None and auth['count'] > 0):
        results = []
        for item in db['kouzi_crawler'].find({'app_name': re.compile(name)}).sort('-insert_at'):
            del item['_id']
            results.append(item)
        history = {
            'code': code,
            'name': name,
            'total': len(results),
            'time': time.time(),
            'data': results
        }
        db['history'].insert_one(history)
        last_query = time.strftime("%Y-%m-%d %H:%M:%S", time.time())
        db['auth_code'].update_one(
            {'code': code}, {"$set": {'count': auth['count']-1, 'last_query':last_query }})
        del history['_id']
        return jsonify({'code': 0, 'data': history})
    else:
        return jsonify({'code': -1, 'desc': '查询码错误或次数已用完'})

# 小程序历史查询接口
@app.route('/api/v1/history', methods=['POST'])
def history():
    code = request.values.get('code')
    results = {}
    data = []
    for item in db['history'].find({'code': code}):
        del item['_id']
        data.append(item)
    auth = db['auth_code'].find_one({'code': code})
    if auth is not None:
        results['code'] = auth['code']
        results['count'] = auth['count']
        results['total'] = auth['total']
        results['data'] = data
        return jsonify({'code': 0, 'data': results})
    else:
        return jsonify({'code': -1, 'desc': '查询码不存在'})


# 小程序广告接口
@app.route('/api/v1/ad')
def ad_api():
    data = []
    for item in db['ad'].find():
        del item['_id']
        data.append(item)
    if len(data) > 0:
        return jsonify({'code': 0, 'data': data[-1]})
    else:
        return jsonify({'code': -1, 'desc': '暂时没有广告'})

# 验证业务域名
@app.route('/siCcKnQoCi.txt')
def checkDomain():
    return 'af672ff0f7cb5c285dd015a06566d614'

# 查询码创建
@app.route('/addhhkadmin', methods=['POST'])
def addhhkadmin():
    try:
        jsonStr = request.get_data().decode('utf-8')
        data = urllib.parse.unquote(jsonStr)
        userData = json.loads(data)
        if userData is not None:
            for item in userData:
                date = time.strftime('%Y-%m-%d %H:%M:%S',
                                     time.localtime(time.time()))
                hhk_user_data = {
                    "id": item['id'],
                    "name": item['name'],
                    "phone": item['phone'],
                    "idNo": item['idNo'],
                    "date": date
                }
                db['hhk_user_info'].update_one(
                    {'phone': item['phone']},
                    {'$set': hhk_user_data}, True)
            return jsonify({'code': 0, 'desc': '请求成功'})
    except ValueError as e:
        return jsonify({'code': 1, 'desc': '请求异常: ' + str(e)})

# 监控产品是否有新的泄露源
@app.route('/checkProduct', methods=['GET'])
def checkProduct():
    try:
        for item in db['product_code'].find():
            productName = str(item['product'])
            code = str(item['code'])
            queryHistory = db['history'].find({'code': code, 'name': productName}).sort(
                [('time', pymongo.DESCENDING)]).limit(1)
            for obj in queryHistory:
                historyCount = len(obj['data'])
                print('historyCount : '+str(historyCount))
                nowCount = db['kouzi_crawler'].count_documents(
                    {'app_name': re.compile(productName)})
                print('nowCount : '+str(nowCount))
                if(nowCount > historyCount):
                    # 发送查询码注册短信通知
                    authCode = db['auth_code'].find_one({'code': code})
                    phone = str(authCode['phone'])
                    print('tel : '+phone+'  '+productName)
                    sendsms.sendUrlChangeSms(phone, productName)
                    check_product_msg = {
                        'code': code,
                        'product': productName,
                        'tel': phone,
                        'time': time.time()
                    }
                    db['check_product_msg'].insert_one(check_product_msg)
        return jsonify({'code': 0, 'desc': '请求成功'})
    except ValueError as e:
        print(e)
        return jsonify({'code': 1, 'desc': '请求异常'})


if(__name__ == "__main__"):
    # app.run(host='127.0.0.1')
    http_server = WSGIServer(('127.0.0.1', 5000), app)
    http_server.serve_forever()
