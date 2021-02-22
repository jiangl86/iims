from django.http import JsonResponse
import json
from django.db.models import Q
import time, datetime
from common.models import User
from service.log.log import save_log
from common.common import get_ip, get_user
import math
import uuid
import hashlib


def dispatcher(request):
    if request.method == 'GET':
        request.params = request.GET
    elif request.method in ['PUT', 'DELETE', 'POST']:
        request.params = json.loads(request.body)
    else:
        return JsonResponse({"ret": 1, "msg": "无法提供对应服务"})
    action = request.params['action']
    print(request.params)
    if action == 'login':
        return login(request)
    elif action == 'list_user':
        return list_user(request)
    elif action == 'add_user':
        return add_user(request)
    elif action == 'update_user':
        return update_user(request)
    elif action == 'update_password':
        return update_password(request)
    elif action == 'reset_password':
        return reset_password(request)
    elif action == 'delete_user':
        return delete_user(request)
    elif action=='get_self_info':
        return get_self_info(request)
    else:
        return JsonResponse({"ret": 1, "msg": "无法提供对应服务"})


def login(request):
    # auth = json.loads(request.headers['authorization'])
    password = request.headers['authorization']
    account = request.params['username']
    try:
        # 判断是否多次尝试密码，当天超过5次登陆失败，禁止再登陆
        today = datetime.datetime.now().date()
        ip = get_ip(request)
        user = User.objects.filter(Q(account=account) | Q(phone=account), fail_times__gte=5, fail_date=today)

        if len(user) > 0:
            save_log('用户登录', '0', 'account' + account, ip)
            return JsonResponse({'ret': 1, 'msg': '多次登陆失败，账户已禁用，请明天再试'})
        user = User.objects.get(Q(account=account) | Q(phone=account), password=password, state='1', delete_state='0')
        user.token = uuid.uuid4()
        user.token_time = int(time.time())
        user.fail_times = 0
        user.save()
        save_log('用户登录', '1', 'account' + account, ip, user.id)
        return JsonResponse({'ret': 0, 'token': user.token, 'user_id': user.id})
    except User.DoesNotExist:
        user = User.objects.filter(Q(account=account) | Q(phone=account))
        if len(user) > 0:
            user = user[0]
            if user.fail_date:
                if user.fail_date == today:
                    user.fail_times = user.fail_times + 1
            else:
                user.fail_date = today
                user.fail_times = 1
            save_log('用户登录', '0', 'account' + account + ',密码错误', ip, user.id)
            user.save()
        return JsonResponse({'ret': 1, 'msg': '账号或密码错误'})


def list_user(request):
    action = '用户查询'
    user_info = get_user(request)
    ip = get_ip(request)
    if user_info['type'] == 3:
        save_log(action, '0', '用户未登录', ip)
        return JsonResponse({"ret": 2, "msg": "未登录"})
    elif user_info['type'] == 2:
        save_log(action, '0', '用户登录超时', ip)
        return JsonResponse({"ret": 2, "msg": "登录超时"})
    params = request.params
    params_string = json.dumps(params)
    delete_state = params['delete_state']
    qs = User.objects.filter(delete_state=delete_state).values('id', 'name', 'phone', 'account', 'type', 'state',
                                                               'create_time',
                                                               'delete_state')
    if 'name' in params_string:
        name = params['name']
        qs = qs.filter(name__contains=name)
    if 'phone' in params_string:
        phone = params['phone']
        qs = qs.filter(phone__contains=phone)
    total_count = len(qs)
    if 'page_size' in json.dumps(request.params):
        page_size = int(request.params['page_size'])
        page_num = int(request.params['page_num'])
        total_page = math.ceil(total_count / page_size)
        if total_page < page_num and total_page > 0:
            page_num = total_page
        qs = qs[(page_num - 1) * page_size:page_num * page_size]
    else:
        page_num = 1
        page_size = 1000
        total_page = 1
    if len(qs) > 0:
        user_list = list(qs)
        index = 1
        for item in user_list:
            item['num'] = (page_num - 1) * page_size + index
            index = index + 1
        user = User.objects.get(id=request.params['user_id'])
        result = {'ret': 0, 'total_page': total_page, 'total_count': total_count, 'page_num': page_num,
                  'retlist': user_list}
        if user.type == '0':
            funcRight = {'addFlag': '1', 'delFlag': '1', 'editFlag': 1, 'resetPassFlag': 1}
            result['funcRight'] = funcRight
        return JsonResponse(result)
    return JsonResponse({"ret": 1, "msg": "暂无数据"})


# 获取用户信息
def get_self_info(request):
    action = '查询用户信息'
    user_info = get_user(request)
    ip = get_ip(request)
    if user_info['type'] == 3:
        save_log(action, '0', '用户未登录', ip)
        return JsonResponse({"ret": 2, "msg": "未登录"})
    elif user_info['type'] == 2:
        save_log(action, '0', '用户登录超时', ip)
        return JsonResponse({"ret": 2, "msg": "登录超时"})
    else:
        user = user_info['user']
        return JsonResponse({"ret": 0, "msg": "查询成功", 'user_name': user.name, 'type': user.type, 'phone': user.phone,
                             'account': user.account})


# 添加用户
def add_user(request):
    user_right = login_right(request, '用户添加')
    if user_right != 'pass':
        return user_right
    ip = get_ip(request)
    params = request.params['data']
    params_string = json.dumps(params)
    if 'name' not in params_string or 'phone' not in params_string or 'account' not in params_string or 'type' not in params_string:
        return JsonResponse({"ret": 1, "msg": "用户信息不全"})
    name = params['name'].strip()
    phone = params['phone'].strip()
    if len(phone) != 11:
        return JsonResponse({"ret": 1, "msg": "手机号格式不正确"})
    account = params['account'].strip()
    qs = User.objects.filter(Q(account=account) | Q(phone=phone))
    if len(qs) > 0:
        return JsonResponse({"ret": 1, "msg": "账户或手机号已经存在"})
    type = params['type']
    if type != '0':
        type = '1'
    initial_password = 'R' + phone + '@'  # 用md5加密转换

    initial_password = encrypt(initial_password)

    user = User(name=name, phone=phone, account=account, password=initial_password, type=type, state='1')
    user.save()
    detail = '姓名' + name + ',电话:' + phone + ',账户:' + account + ',类型:'
    if type == '0':
        detail = detail + '系统管理员'
    else:
        detail = detail + '普通用户'
    save_log('用户添加', '1', detail, ip, user.id)
    return JsonResponse({"ret": 0, "msg": "添加成功", 'user_id': user.id})


def update_user(request):
    user_right = login_right(request, '用户修改')
    if user_right != 'pass':
        return user_right
    params = request.params['data']
    params_string = json.dumps(params)
    ip = get_ip(request)
    if 'update_user_id' not in json.dumps(request.params):
        return JsonResponse({"ret": 1, "msg": "无要修改的用户id"})
    try:
        update_user_id = request.params['update_user_id']
        user = User.objects.get(id=update_user_id)
        detail = ''
        if 'phone' in params_string:
            phone = params['phone'].strip()
            if user.phone != phone:
                qs = User.objects.filter(phone=phone, delete_state='0').values()
                if len(qs) > 0:
                    return JsonResponse({"ret": 1, "msg": "手机号已使用"})
            user.phone = phone
            detail = '电话：' + phone
        if 'account' in params_string:
            account = params['account'].strip()
            if user.account != account:
                qs = User.objects.filter(account=account, delete_state='0').values()
                if len(qs) > 0:
                    return JsonResponse({"ret": 1, "msg": "账号已使用"})
            user.account = account
            detail = detail + ',账户：' + account
        if 'type' in params_string:
            type = params['type']
            if type != '0':
                type = '1'
                detail = detail + ',类型普通用户'
            else:
                detail = detail + ',类型系统管理员'
            user.type = type
        if 'state' in params_string:
            state = params['state']
            if state != '1':
                state = '2'
                detail = detail + ',状态未激活'
            else:
                detail = detail + ',状态正常'
            user.state = state
        user.save()
        save_log('用户修改', '1', detail, ip, request.params['user_id'])
        return JsonResponse({"ret": 0, "msg": "修改成功"})
    except User.DoesNotExist:
        return JsonResponse({"ret": 1, "msg": "数据错误"})


def update_password(request):
    user_info = get_user(request)
    ip = get_ip(request)
    user_id = request.params['user_id']
    action = '密码修改'
    if user_info['type'] == 3:
        save_log(action, '0', '用户未登录', ip)
        return JsonResponse({"ret": 2, "msg": "未登录"})
    elif user_info['type'] == 2:
        save_log(action, '0', '用户登录超时', ip)
        return JsonResponse({"ret": 2, "msg": "登录超时"})
    params = request.params['data']
    params_string = json.dumps(params)
    if 'old_password' not in params_string:
        return JsonResponse({"ret": 1, "msg": "请输入旧密码"})
    old_password = params['old_password']
    user = User.objects.get(id=user_id)
    if user.password != old_password:
        return JsonResponse({"ret": 1, "msg": "旧密码不正确"})
    if 'new_password' not in params_string:
        return JsonResponse({"ret": 1, "msg": "请输入修改后密码"})
    user.password = params['new_password'].strip()
    user.save()
    save_log(action, '1', '密码修改成功', ip, user_id)
    return JsonResponse({"ret": 0, "msg": "密码修改成功"})


def reset_password(request):
    user_right = login_right(request, '用户密码重置')
    if user_right != 'pass':
        return user_right
    if 'update_user_id' not in json.dumps(request.params):
        return JsonResponse({"ret": 1, "msg": "缺少需要重置的用户信息"})
    update_user_id = request.params['update_user_id']
    try:
        user = User.objects.get(id=update_user_id, delete_state='0')
        password = "R" + user.phone + '@'
        user.password = encrypt(password)  # 用sha256加密
        user.save()
        ip = get_ip(request)
        save_log('用户密码重置', '1', '重置成功', ip, request.params['user_id'])
        return JsonResponse({"ret": 0, "msg": "重置成功"})
    except User.DoesNotExist:
        return JsonResponse({"ret": 0, "msg": "参数错误，被重置用户不存在"})


def delete_user(request):
    user_right = login_right(request, '用户删除')
    if user_right != 'pass':
        return user_right
    if 'delete_user_ids' not in json.dumps(request.params):
        return JsonResponse({"ret": 1, "msg": "缺少需要删除的用户信息"})
    delete_user_ids = request.params['delete_user_ids']
    ip = get_ip(request)
    try:
        users = User.objects.filter(id__in=delete_user_ids.split(','))
        name = '成功删除用户：'
        if len(users) > 0:
            for user in users:
                name = name + user.name + ','
                user.delete_state = '1'
                user.save()
            save_log('用户删除', '1', name, ip, request.params['user_id'])
            return JsonResponse({"ret": 0, "msg": "用户删除成功"})
    except Exception:
        save_log('用户删除', '0', '用户删除失败', ip, request.params['user_id'])
        return JsonResponse({"ret": 1, "msg": "删除失败，请稍后再试"})


# 判断用户是否登录和是否有权限(仅适用本模块,因为各模块对权限判断不相同），并记录日志
# 不通过时，直接返回JsonResponse，否则返回'pass'
def login_right(request, action):
    user_info = get_user(request)
    ip = get_ip(request)
    if user_info['type'] == 3:
        save_log(action, '0', '用户未登录', ip)
        return JsonResponse({"ret": 2, "msg": "未登录"})
    elif user_info['type'] == 2:
        save_log(action, '0', '用户登录超时', ip)
        return JsonResponse({"ret": 2, "msg": "登录超时"})
    elif user_info['type'] == 1:
        if user_info['user'].type == '1':
            save_log(action, '0', '用户无权限', ip)
            return JsonResponse({"ret": 1, "msg": "没有查看该功能权限"})
    return 'pass'


def encrypt(str):
    sha256 = hashlib.sha256()
    sha256.update(str.encode('utf-8'))
    return sha256.hexdigest()
