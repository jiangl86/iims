from django.http import JsonResponse
import requests
import json
from django.db.models import F


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
    if action == 'list_corp_cate':
        return list_corp_cate(request)
    elif action == 'add_corp_cate':
        return add_corp_cate(request)

