from django.http import JsonResponse
import json
from django.db.models import Q, F
from common.common import get_ip, get_user
from service.log.log import save_log
from common.models import ProjectUser, Module, ModuleUser, User, Interface, InterfaceHistory


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
    if action == 'list_interface':
        return list_interface(request)
    elif action == 'add_interface':
        return add_interface(request)
    elif action == 'update_interface':
        return update_interface(request)
    elif action == 'update_state':
        return update_state(request)
    elif action == 'get_info':
        return get_info(request)
    elif action == 'delete_interface':
        return delete_interface(request)
    else:
        return JsonResponse({"ret": 1, "msg": "无法提供对应服务"})


def list_interface(request):
    action = '接口查询'
    user_right = interface_right(request, action)
    if user_right != 'pass':
        return user_right
    ip = get_ip(request)
    params = request.params
    params_string = json.dumps(params)
    user_id = params['user_id']
    project_id = params['project_id']
    # 如果是系统管理员和该项目管理员，返回该项目所有模块，否则只返回和其相关的模块
    # 如果不是系统管理员，需要先查询用户是否是该项目管理员，不是的话直接返回无权限
    is_project_admin = is_project_right(user_id, project_id)
    if is_project_admin:
        qs = Module.objects.filter(delete_state='0', project_id=project_id).values('id', 'name', 'parent_id')
    else:
        qs = Module.objects.filter(delete_state='0', project_id=project_id, moduleuser__delete_state='0',
                                   moduleuser__user_id=user_id).annotate(
            user_type=F('moduleuser__type')).values('id', 'name', 'user_type', 'parent_id')
    if len(qs) > 0:
        module_list = []
        module_ids = []
        interface_list = []
        index = 1
        for item in qs:
            module_ids.append(item['id'])
            module = {'id': item['id'], 'name': item['name']}
            if item['parent_id'] is not None:
                module['parent_id'] = module.parent_id
            if is_project_admin or item['user_type'] == '1':
                module['funcRight'] = {'addFlag': '1', 'editFlag': '1', 'delFlag': 1}
            module_list.append(module)
        # 查询接口信息
        interface_qs = Interface.objects.filter(module_id__in=module_ids, delete_state='0').values('id', 'name',
                                                                                                   'module_id', 'state')
        if 'name' in params_string:
            interface_qs = interface_qs.filter(name__contains=params['name'].strip())
        if 'state' in params_string:
            interface_qs = interface_qs.filter(state=params['state'])
        if len(interface_qs) > 0:
            interface_list = list(interface_qs)
        save_log(action, '0', '查询成功', ip, user_id)
        result = {'ret': 0, 'msg': '查询成功', 'ret_module_list': module_list, 'ret_interface_list': interface_list}
        return JsonResponse(result)
    save_log(action, '0', '无符合条件的接口或无权限', ip, user_id)
    return JsonResponse({"ret": 1, "msg": "暂无数据"})


def add_interface(request):
    action = '接口添加'
    user_right = interface_right(request, action)
    if user_right != 'pass':
        return user_right
    ip = get_ip(request)
    user_id = request.params['user_id']
    params = request.params['data']
    params_string = json.dumps(params)
    module_id = params['module_id']
    # 判断是否有该模块添加权限
    has_right = is_module_right(user_id, module_id)
    if has_right is False:
        save_log(action, '0', '无权限', ip, user_id)
        return JsonResponse({'ret': 1, 'msg': '无权限'})
    name = params['name'].strip()
    detail = '接口名称:' + name
    interface = Interface(name=name, module_id=module_id, user_id=user_id)
    interface_history = InterfaceHistory(action='添加', user_id=user_id)
    if 'design' in params_string:
        interface.design = params['design'].strip()
        interface_history.design = params['design'].strip()
    if 'address' in params_string:
        interface.address = params['address'].strip()
        interface_history.address = params['address'].strip()
    if 'params' in params_string:
        interface.params = params['params'].strip()
        interface_history.params = params['params'].strip()
    if 'result' in params_string:
        interface.result = params['result'].strip()
        interface_history.result = params['result'].strip()
    if 'state' in params_string:
        interface.state = params['state']
    try:
        interface.save()
        interface_history.interface_id = interface.id
        interface_history.description = '添加接口，详细信息见具体内容'
        interface_history.save()
        save_log(action, '1', detail, ip, user_id)
        return JsonResponse({'ret': 0, 'msg': '添加成功', 'interface_id': interface.id})
    except Exception:
        save_log(action, '0', '添加失败', ip, user_id)
        return JsonResponse({'ret': 1, 'msg': '添加失败，请稍候再试'})


def update_interface(request):
    action = '接口修改'
    user_right = interface_right(request, action)
    if user_right != 'pass':
        return user_right
    ip = get_ip(request)
    user_id = request.params['user_id']
    interface_id = request.params['interface_id']
    params = request.params['data']
    params_string = json.dumps(params)
    try:
        interface = Interface.objects.get(id=interface_id)
        has_right = is_module_right(user_id, interface.module_id)
        if has_right is False:
            save_log(action, '0', '无权限', ip, user_id)
            return JsonResponse({'ret': 1, 'msg': '无权限'})
        interface_history = InterfaceHistory(user_id=user_id, action='修改', interface_id=interface_id)
        if 'name' in params_string:
            interface.name = params['name'].strip()
            interface_history.name = params['name'].strip()
        if 'design' in params_string:
            interface.design = params['design'].strip()
            interface_history.design = params['design'].strip()
        if 'address' in params_string:
            interface.address = params['address'].strip()
            interface_history.address = params['address'].strip()
        if 'params' in params_string:
            interface.params = params['params'].strip()
            interface_history.params = params['params'].strip()
        if 'result' in params_string:
            interface.result = params['result'].strip()
            interface_history.result = params['result'].strip()
        if 'state' in params_string:
            state = params['state']
            interface.state = state
            state_info = get_state_info(state)
            interface_history.action = '修改并变更状态为' + state_info
        interface_history.description = '修改接口，详细信息见具体内容'
        interface.save()
        interface_history.save()
        save_log(action, '1', '修改成功,接口id:' + interface_id, ip, user_id)
        return JsonResponse({'ret': 0, 'msg': '添加成功', 'interface_id': interface.id})
    except Exception:
        save_log(action, '0', '参数错误', ip, user_id)
        return JsonResponse({'ret': 1, 'msg': '参数错误'})


def update_state(request):
    action = '变更状态'
    user_right = interface_right(request, action)
    if user_right != 'pass':
        return user_right
    ip = get_ip(request)
    user_id = request.params['user_id']
    interface_id = request.params['interface_id']
    params = request.params['data']
    params_string = json.dumps(params)
    try:
        interface = Interface.objects.get(id=interface_id)
        state = params['state']

        # 如果不是报异常，需要判断用户是否有权限
        if state != '3':
            has_right = is_module_right(user_id, interface.module_id)
            if has_right is False:
                save_log(action, '0', '无权限', ip, user_id)
                return JsonResponse({'ret': 1, 'msg': '无权限'})
        interface_history = InterfaceHistory(user_id=user_id, interface_id=interface_id)
        interface.state = state
        interface_history.action = get_state_info(state)
        if 'description' in params_string:
            interface_history.description = params['description']
        interface.save()
        interface_history.save()
        save_log(action, '1', '变更状态完成,接口id:' + interface_id, ip, user_id)
        return JsonResponse({'ret': 0, 'msg': '变更成功'})
    except Exception:
        save_log(action, '0', '参数错误', ip, user_id)
        return JsonResponse({'ret': 1, 'msg': '参数错误'})


# 查询接口详细信息，目前未判断是否有单一接口的查询权限，即未判断当前用户是否在项目中
def get_info(request):
    action = '查询接口详细信息'
    user_right = interface_right(request, action)
    if user_right != 'pass':
        return user_right
    ip = get_ip(request)
    user_id = request.params['user_id']
    interface_id = request.params['interface_id']
    try:
        interface = Interface.objects.get(id=interface_id, delete_state='0')
        history = interface.interfacehistory_set.values().order_by('create_time')
        data = {'id': interface.id, 'name': interface.name, 'design': interface.design, 'address': interface.address,
                'params': interface.params, 'result': interface.result,'state':interface.state}
        if len(history)>0:
            data['history_list']=list(history)
        result = {'ret': 0, 'msg': '查询成功','data':data }
        save_log(action,'1','查询接口信息',ip,user_id)
        return JsonResponse(result)
    except Interface.DoesNotExist:
        save_log(action, '0', '参数错误', ip, user_id)
        return JsonResponse({'ret': 1, 'msg': '参数错误'})


def delete_interface(request):
    action = '删除接口'
    user_right = interface_right(request, action)
    if user_right != 'pass':
        return user_right
    ip = get_ip(request)
    user_id = request.params['user_id']
    interface_id = request.params['interface_id']
    try:
        interface = Interface.objects.get(id=interface_id, delete_state='0')
        has_right=is_module_right(user_id,interface.module_id)
        if has_right is False:
            save_log(action, '0', '无权限', ip, user_id)
            return JsonResponse({'ret': 1, 'msg': '无权限'})
        interface.delete_state='1'
        interface_history=InterfaceHistory(action='删除接口',user_id=user_id,interface_id=interface_id)
        interface.save()
        interface_history.save()
        save_log(action, '1', '删除接口,接口id:' + interface_id, ip, user_id)
        return JsonResponse({'ret': 0, 'msg': '删除成功'})
    except Interface.DoesNotExist:
        save_log(action, '0', '参数错误', ip, user_id)
        return JsonResponse({'ret': 1, 'msg': '参数错误'})


def interface_right(request, action):
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


# 判断用户是否对整个项目有管理权限
def is_project_right(user_id, project_id):
    user = User.objects.get(id=user_id)
    if user.type == 0:
        return True
    else:
        qs = ProjectUser.objects.filter(user_id=user_id, delete_state='0', type='0', project_id=project_id)
        if len(qs) > 0:
            return True
    return False


# 判断用户针对该模块是否有增删改接口权限
def is_module_right(user_id, module_id):
    qs = ModuleUser.objects.filter(module_id=module_id, user_id=user_id, type='1', delete_state='0')
    if len(qs) > 0:
        return True
    project_id = Module.objects.get(id=module_id).project_id
    return is_project_right(user_id, project_id)


# 根据staet返回具体状态类型
def get_state_info(state):
    if state == '0':
        return '设计中'
    elif state == '3':
        return '未完成'
    elif state == '2':
        return '已完成'
    else:
        return '异常'
