from django.http import JsonResponse
import requests
import json
from django.db.models import F, Q
import time, datetime
from common.models import User


def dispatcher(request):
    if request.method == 'GET':
        request.params = request.GET
    elif request.method in ['PUT', 'DELETE', 'POST']:
        request.params = json.loads(request.body)
    else:
        return JsonResponse({"ret": 1, "msg": "无法提供对应服务"})
    print(request.params)
    action = request.params['action']
    print(action)
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
    else:
        return JsonResponse({"ret": 1, "msg": "无法提供对应服务"})


def login(request):
    auth = json.loads(request.headers['authorization'])
    auth_string = json.dumps(auth)
    if 'username' not in auth_string or 'password' not in auth_string:
        return JsonResponse({"ret": 1, "msg": "请输入用户名或手机号"})
    account = auth['username']
    password = auth['password']
    try:
        # 判断是否多次尝试密码，当天超过5次登陆失败，禁止再登陆
        today = datetime.datetime.now().date()
        user = User.objects.filter(Q(account=account) | Q(phone=account), fail_times__gte=5, fail_date=today)

        if len(user) > 0:
            return JsonResponse({'ret': 1, 'msg': '多次登陆失败，账户已禁用，请明天再试'})
        user = User.objects.get(Q(account=account) | Q(phone=account), password=password, state='1')
        user.token = uuid.uuid4()
        user.token_time = int(time.time())
        user.fail_times = 0
        user.save()
        return JsonResponse({'ret': 0, 'token': user.token, 'user_id': user.id})
    except User.DoesNotExist:
        user = User.objects.filter(Q(account=account) | Q(phone=account))
        if len(user) > 0:
            user = user[0]
            if user.fail_date:
                if user.fail_date == today:
                    if user.last_ip and user_ip == user.last_ip:
                        user.fail_times = user.fail_times + 1
                    else:
                        user.last_ip = user_ip
                        user.fail_times = 1
                else:
                    user.fail_date = today
                    user.last_ip = user_ip
                    user.fail_times = 1
            else:
                user.fail_date = today
                user.last_ip = user_ip
                user.fail_times = 1
            user.save()
        return JsonResponse({'ret': 1, 'msg': '账号或密码错误'})


# 判断当前是否已经登录，要求每天必须登录一次，
# 返回1代表正常登录，返回2表示登录超时，需重新登录，返回3代表未登录
def get_user(request):
    if 'user_id' not in json.dumps(request.params):
        return {'user': None, 'type': 3}
    user_id = request.params['user_id']
    token = request.headers['authorization']
    try:
        user = User.objects.get(id=user_id, token=token)
        if int(time.time()) - user.token_time >= 24 * 60 * 60:
            return {'user': None, 'type': 2}
        return {'user': user, 'type': 1}
    except User.DoesNotExist:
        return {'user': None, 'type': 3}
