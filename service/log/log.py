from django.http import JsonResponse
import json
from django.db.models import F
from common.models import Log, User
from common.common import get_user
import datetime
import math


def dispatcher(request):
    if request.method == 'PUT':
        request.params = json.loads(request.body)
    else:
        return JsonResponse({"ret": 1, "msg": "无法提供对应服务"})
    print(request.params)
    action = request.params['action']
    if action == 'list_log':
        return list_log(request)
    else:
        return JsonResponse({"ret": 1, "msg": "无法提供对应服务"})


def list_log(request):
    user_info = get_user(request)
    if user_info['type'] == 3:
        return JsonResponse({"ret": 2, "msg": "未登录"})
    elif user_info['type'] == 2:
        return JsonResponse({"ret": 2, "msg": "登录超时"})
    if user_info['type'] == 1:
        if user_info['user'].type == 1:
            return JsonResponse({"ret": 1, "msg": "没有查看该功能权限"})
        else:
            qs = Log.objects.annotate(name=F('user__name')).values().order_by(
                '-create_time')
            if 'begin_date' in json.dumps(request.params):
                begin_date = request.params['begin_date']
                begin_date = datetime.datetime.strptime(begin_date, '%Y-%m-%d')
                qs = qs.filter(create_time__gte=begin_date)
            if 'end_date' in json.dumps(request.params):
                end_date = request.params['end_date']
                end_date = end_date + ' 23:59:59'
                end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
                qs = qs.filter(create_time__lte=end_date)
            if 'user_name' in json.dumps(request.params):
                user_name = request.params['user_name']
                qs = qs.filter(name__contains=user_name)
            if 'type' in json.dumps(request.params):
                type = request.params['type']
                qs = qs.filter(action__contains=type)
            if 'description' in json.dumps(request.params):
                description = request.params['description']
                qs = qs.filter(detail__contains=description)
            if 'page_size' in json.dumps(request.params):
                page_size = int(request.params['page_size'])
                page_num = int(request.params['page_num'])
                total_count = len(qs)
                total_page = math.ceil(total_count / page_size)
                if total_page < page_num and total_page > 0:
                    page_num = total_page
                qs = qs[(page_num - 1) * page_size:page_num * page_size]
            else:
                page_num = 1
                page_size = 1000000
                total_count = len(qs)
                total_page = 1
            if len(qs) > 0:
                log_list = list(qs)
                index = (page_num - 1) * page_size + 1
                for item in log_list:
                    item['num'] = index
                    index + 1
                    if item['action_state'] == '0':
                        item['action_state'] = '失败'
                    else:
                        item['action_state'] = '成功'
                return JsonResponse(
                    {'ret': 0, 'total_page': total_page, 'total_count': total_count, 'page_num': page_num,
                     'retlist': log_list})
            return JsonResponse({"ret": 1, "msg": "暂无数据"})


def save_log(action, action_state=None, detail=None, ip=None, user_id=None):
    log = Log(action=action)
    if action_state:
        log.action_state = action_state
    if detail:
        log.detail = detail
    if ip:
        log.ip = ip
    if user_id:
        try:
            user = User.objects.get(id=user_id)
            log.user = user
        except Exception as e:
            pass
    log.save()
