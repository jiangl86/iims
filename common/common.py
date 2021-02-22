import json
import time
from common.models import User


def get_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # 所以这里是真实的ip
        ip = x_forwarded_for.split(',')[0]
    else:
        # 这里获得代理ip
        ip = request.META.get('REMOTE_ADDR')
    return ip


# 通用功能，判断当前是否已经登录，要求每天必须登录一次，
# 返回1代表正常登录，返回2表示登录超时，需重新登录，返回3代表未登录
def get_user(request):
    if 'user_id' not in json.dumps(request.params):
        return {'user': None, 'type': 3}
    user_id = request.params['user_id']
    token = request.headers['authorization']
    try:
        user = User.objects.get(id=user_id, token=token, delete_state='0', state='1')
        if int(time.time()) - user.token_time >= 7*24 * 60 * 60:
            return {'user': None, 'type': 2}
        return {'user': user, 'type': 1}
    except User.DoesNotExist:
        return {'user': None, 'type': 3}
