from django.http import JsonResponse
import json
from common.common import get_ip, get_user
from service.log.log import save_log
from common.models import ProjectUser, Module, ModuleUser, User
from django.db.models import Q, F
import math


# 大多数接口为针对参数做校验，仅校验了权限和登录情况，后续需要在处理
def dispatcher(request):
    if request.method == 'GET':
        request.params = request.GET
    elif request.method in ['PUT', 'DELETE', 'POST']:
        request.params = json.loads(request.body)
    else:
        return JsonResponse({"ret": 1, "msg": "无法提供对应服务"})
    action = request.params['action']
    if action == 'list_module':
        return list_module(request)
    elif action == 'add_module':
        return add_module(request)
    elif action == 'update_module':
        return update_module(request)
    elif action == 'delete_module':
        return delete_module(request)
    else:
        return JsonResponse({"ret": 1, "msg": "无法提供对应服务"})


def list_module(request):
    action = '模块查询'
    user_right = module_right(request, action)
    if user_right != 'pass':
        return user_right
    ip = get_ip(request)
    params = request.params
    params_string = json.dumps(params)
    user_id = params['user_id']
    project_id = params['project_id']
    user = User.objects.get(id=user_id)
    module_list = []
    # 如果不是系统管理员，需要先查询用户是否是该项目管理员，不是的话直接返回无权限
    if user.type != '0':
        qs = ProjectUser.objects.filter(user_id=user_id, delete_state='0', type='0', project_id=project_id)
        if len(qs) == 0:
            save_log(action, '0', '无查看模块功能权限', ip, user_id)
            return JsonResponse({'ret': 1, 'msg': '无查看模块功能权限'})

    qs = Module.objects.filter(delete_state='0', project_id=project_id).all()
    if len(qs) > 0:
        if 'name' in params_string:
            name = params['name'].strip()
            qs = qs.filter(name__contains=name)
        if len(qs) > 0:
            index = 1
            for item in qs:
                module = {'id': item.id, 'name': item.name}
                module['create_time'] = item.create_time.strftime('%Y-%m-%d %H:%M')
                module['num'] = index
                index = index + 1
                if item.parent_id is not None:
                    module['parent_id'] = item.parent_id
                developer = item.moduleuser_set.filter(type='1', delete_state='0').annotate(
                    user_name=F('user__name')).values('user_id', 'user_name')
                others = item.moduleuser_set.filter(type='2', delete_state='0').annotate(
                    user_name=F('user__name')).values('user_id', 'user_name')
                if len(developer) > 0:
                    module['developer'] = list(developer)
                if len(others) > 0:
                    module['others'] = list(others)
                module_list.append(module)
            result = {'ret': 0, 'msg': '查询成功', 'retlist': module_list}
            return JsonResponse(result)
    save_log('项目查询', '0', '无符合条件的项目或无权限', ip, user_id)
    return JsonResponse({"ret": 1, "msg": "暂无数据"})


def add_module(request):
    action = '模块添加'
    user_right = module_right(request, action)
    if user_right != 'pass':
        return user_right
    ip = get_ip(request)
    user_id = request.params['user_id']
    params = request.params['data']
    params_string = json.dumps(params)
    user = User.objects.get(id=user_id, delete_state='0', state='1')
    project_id = params['project_id']
    if user.type != '0':
        qs = ProjectUser.objects.filter(user_id=user_id, delete_state='0', type='0', project_id=project_id)
        if len(qs) == 0:
            save_log(action, '0', '无添加模块功能权限', ip, user_id)
            return JsonResponse({'ret': 1, 'msg': '无添加模块功能权限'})
    name = params['name'].strip()
    detail = '模块名称:' + name
    module = Module(name=name, project_id=project_id, user_id=user_id)
    if 'parent_id' in params_string:
        module.parent_id = params['parent_id']
    try:
        module.save()
        if 'developer' in params_string:
            developer = params['developer'].split(',')
            batch = [ModuleUser(module_id=module.id, user_id=temp, type='1') for temp in developer]
            ModuleUser.objects.bulk_create(batch)
        if 'others' in params_string:
            others = params['others'].split(',')
            # 删除其他用户中已在开发人员中存在的用户
            if 'developer' in params_string:
                i = len(others) - 1
                while i >= 0:
                    for dev_user in developer:
                        if others[i] == dev_user:
                            others.pop(i)
                    i = i - 1
            batch = [ModuleUser(module_id=module.id, user_id=temp, type='2') for temp in others]
            ModuleUser.objects.bulk_create(batch)
        save_log(action, '1', detail, ip, user_id)
        return JsonResponse({'ret': 0, 'msg': '添加成功', 'module_id': module.id})
    except Exception:
        save_log(action, '0', '添加失败', ip, user_id)
        return JsonResponse({'ret': 1, 'msg': '添加失败，请稍候再试'})


def update_module(request):
    action = '模块修改'
    user_right = module_right(request, action)
    if user_right != 'pass':
        return user_right
    params = request.params['data']
    params_string = json.dumps(params)
    ip = get_ip(request)
    user_id = request.params['user_id']
    user = User.objects.get(id=user_id, delete_state='0', state='1')
    module_id = request.params['module_id']
    if user.type != '0':
        try:
            qs = Module.objects.get(id=module_id, delete_state='0').project.projectuser_set.filter(user_id=user_id,
                                                                                                   type='0',
                                                                                                   delete_state='0')
            if len(qs) == 0:
                save_log(action, '0', '无修改模块功能权限', ip, user_id)
                return JsonResponse({'ret': 1, 'msg': '无修改模块功能权限'})
        except Exception:
            save_log(action, '0', '无修改模块功能权限', ip, user_id)
            return JsonResponse({'ret': 1, 'msg': '无修改模块功能权限'})
    try:
        module = Module.objects.get(id=module_id, delete_state='0')
        if 'name' in params_string:
            module.name = params['name'].strip()
        if 'developer' in params_string:
            ModuleUser.objects.filter(type='1', module_id=module.id).delete()
            developer = params['developer'].split(',')
            batch = [ModuleUser(module_id=module.id, user_id=temp, type='1') for temp in developer]
            ModuleUser.objects.bulk_create(batch)
        if 'others' in params_string:
            ModuleUser.objects.filter(type='2', module_id=module.id).delete()
            others = params['others'].split(',')
            # 删除其他用户中已在开发人员中存在的用户
            if 'developer' in params_string:
                i = len(others) - 1
                while i >= 0:
                    for dev_user in developer:
                        if others[i] == dev_user:
                            others.pop(i)
                    i = i - 1
            batch = [ModuleUser(module_id=module.id, user_id=temp, type='2') for temp in others]
            ModuleUser.objects.bulk_create(batch)
        module.save()
        save_log(action, '1', '修改成功', ip, user_id)
        return JsonResponse({'ret': 0, 'msg': '修改成功'})
    except Module.DoesNotExist:
        save_log(action, '0', '参数错误', ip, user_id)
        return JsonResponse({'ret': 1, 'msg': '参数错误'})


def delete_module(request):
    action = '模块删除'
    user_right = module_right(request, action)
    if user_right != 'pass':
        return user_right
    params = request.params
    params_string = json.dumps(params)
    ip = get_ip(request)
    user_id = params['user_id']
    user = User.objects.get(id=user_id, delete_state='0', state='1')
    delete_module_ids = params['delete_module_ids'].split(',')
    if user.type != '0':
        qs = Module.objects.filter(id__in=delete_module_ids, delete_state='0')
        if len(qs) > 0:
            for item in qs:
                temp_qs = item.project.projectuser_set.filter(user_id=user_id, type='0', delete_state='0')
                if len(temp_qs) == 0:
                    save_log(action, '0', '无修改模块功能权限', ip, user_id)
                    return JsonResponse({'ret': 1, 'msg': '无修改模块功能权限'})
        else:
            save_log(action, '0', params_string, ip, user_id)
            return JsonResponse({'ret': 1, 'msg': '参数错误'})
    try:
        Module.objects.filter(id__in=delete_module_ids).update(delete_state='1')
        ModuleUser.objects.filter(module_id__in=delete_module_ids).update(delete_state='1')
        detail = '成功删除模块：' + params['delete_module_ids']
        save_log(action, '1', detail, ip, user_id)
        return JsonResponse({"ret": 0, "msg": "删除成功"})
    except Exception:
        save_log(action, '0', '删除失败', ip, request.params['user_id'])
        return JsonResponse({"ret": 1, "msg": "删除失败，请稍后再试"})


# 判断用户是否登录和是否有权限(仅适用本模块,因为各模块对权限判断不相同），并记录日志
# 不通过时，直接返回JsonResponse，否则返回'pass'
def module_right(request, action):
    user_info = get_user(request)
    ip = get_ip(request)
    user_id = request.params['user_id']
    if user_info['type'] == 3:
        save_log(action, '0', '用户未登录', ip)
        return JsonResponse({"ret": 2, "msg": "未登录"})
    elif user_info['type'] == 2:
        save_log(action, '0', '用户登录超时', ip)
        return JsonResponse({"ret": 2, "msg": "登录超时"})
    elif user_info['type'] == 1:
        return 'pass'  # 此处不做权限判断，在各个子模块直接判断
