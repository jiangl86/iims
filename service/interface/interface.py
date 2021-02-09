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
    action = request.params['action']
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
    # 查询出项目下所有模块信息
    all_modules = Module.objects.filter(delete_state='0', project_id=project_id, project__delete_state='0').values('id',
                                                                                                                   'name',
                                                                                                                   'parent_id')
    all_modules_list = []
    if len(all_modules) > 0:
        all_modules_list = list(all_modules)
    else:
        save_log(action, '0', '无符合条件的接口或无权限', ip, user_id)
        return JsonResponse({"ret": 1, "msg": "暂无数据"})
    # 如果是系统管理员和该项目管理员，返回该项目所有模块，否则只返回和其相关的模块
    # 如果不是系统管理员，需要先查询用户是否是该项目管理员或开发人员，不是的话直接返回无权限、
    is_project_admin = is_project_right(user_id, project_id)
    if is_project_admin:
        qs = all_modules
    else:
        qs = Module.objects.filter(delete_state='0', project_id=project_id, moduleuser__delete_state='0',
                                   moduleuser__user_id=user_id).annotate(
            user_type=F('moduleuser__type')).values('id', 'name', 'user_type', 'parent_id').distinct()
    module_list = []
    module_ids = []
    interface_list = []

    # 如果包含所有模块
    if len(qs) == len(all_modules):
        index = 1
        for item in qs:
            module_ids.append(item['id'])
            module = {'id': item['id'], 'name': item['name']}
            if item['parent_id'] is not None:
                module['parent_id'] = item['parent_id']
            if is_project_admin or item['user_type'] == '1':
                module['funcRight'] = {'addFlag': '1', 'editFlag': '1', 'delFlag': '1'}
            module_list.append(module)
    # 如果不包含所有模块，需要把对应模块的上下级模块都找出来，其中上级模块的权限只有查看，下级模块的权限同当前模块
    elif len(qs) > 0 or is_project_normal_user(user_id,project_id):
        child_modules = []
        parent_modules = []
        # 先找出上下级模块
        for item in qs:
            child_modules.extend(findChildModules(all_modules, item))
            if item['parent_id'] is not None:
                parent_modules.extend(findParentModules(all_modules, item))
        # 排序
        child_modules.sort(key=lambda child: child['id'])
        parent_modules.sort(key=lambda parent: parent['id'])
        # 删除子节点和parent节点中重复的数据，包括自身重复或者和qs重复的数据
        i = len(child_modules) - 1
        while i > 0:
            if child_modules[i]['id'] == child_modules[i - 1]['id']:
                child_modules.pop(i)
            i = i - 1

        i = len(child_modules) - 1
        while i >= 0:
            for item in qs:
                if child_modules[i]['id'] == item['id']:
                    child_modules.pop(i)
                    break
            i = i - 1

        # 处理父节点
        i = len(parent_modules) - 1
        while i > 0:
            if parent_modules[i]['id'] == parent_modules[i - 1]['id']:
                parent_modules.pop(i)
            i = i - 1

        i = len(parent_modules) - 1
        while i >= 0:
            is_exist = False
            for item in qs:
                if parent_modules[i]['id'] == item['id']:
                    is_exist = True
                    parent_modules.pop(i)
                    break
            if is_exist is False:
                parent_modules[i]['user_type'] = '2'  # 如果不是权限内的上级功能点，设置为普通用户
            i = i - 1

        # 处理返回数据
        list_qs = list(qs)
        list_qs.extend(parent_modules)
        list_qs.extend(child_modules)

        # 判断用户是否是整个项目的普通用户，如果是，需要把其他按上述查找逻辑没有找出的模块添加到用户的查看列表中
        if is_project_normal_user(user_id, project_id):
            i = len(all_modules_list) - 1
            while i >= 0:
                is_exist = False
                for item in list_qs:
                    if all_modules_list[i]['id'] == item['id']:
                        all_modules_list.pop(i)
                        is_exist = True
                        break
                if is_exist is False:
                    all_modules_list[i]['user_type'] = '2'  # 如果不是权限内的功能点，设置为普通用户
                i = i - 1
            list_qs.extend(all_modules_list)

        # 给模块添加权限
        for item in list_qs:
            module_ids.append(item['id'])
            module = {'id': item['id'], 'name': item['name']}
            if item['parent_id'] is not None:
                module['parent_id'] = item['parent_id']
            if is_project_admin or item['user_type'] == '1':
                module['funcRight'] = {'addFlag': '1', 'editFlag': '1', 'delFlag': 1}
            module_list.append(module)

    if len(module_ids) > 0:
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


# 查找节点所有子节点，并处理权限，list 是所有的模块集合,module是要查找的模块
def findChildModules(module_list, module):
    child_module_list = []
    for item in module_list:
        if item['parent_id'] == module['id']:
            # 如果子节点还没有权限，或者仅是普通人员权限，则直接用父节点权限
            if item.__contains__('user_type') and item['user_type'] == '1':
                pass
            else:
                item['user_type'] = module['user_type']
            child_module_list.append(item)
            childs = findChildModules(module_list, item)
            if len(childs) > 0:
                child_module_list.extend(childs)
    return child_module_list


# 查找节点所有父节点
def findParentModules(module_list, module):
    parent_module_list = []
    for item in module_list:
        if module['parent_id'] == item['id']:
            parent_module_list.append(item)
            if item['parent_id'] is not None:
                parents = findParentModules(module_list, item)
                if len(parents) > 0:
                    parent_module_list.extend(parents)
    return parent_module_list


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
    name = params['key_name'].strip()
    detail = '接口名称:' + name
    interface = Interface(name=name, module_id=module_id, user_id=user_id)
    interface_history = InterfaceHistory(action='添加', user_id=user_id)
    if 'key_description' in params_string:
        interface.description = params['key_description'].strip()
        interface_history.description = params['key_description'].strip()
    if 'key_design' in params_string:
        interface.design = params['key_design'].strip()
        interface_history.design = params['key_design'].strip()
    if 'key_address' in params_string:
        interface.address = params['key_address'].strip()
        interface_history.address = params['key_address'].strip()
    if 'key_params' in params_string:
        interface.params = params['key_params'].strip()
        interface_history.params = params['key_params'].strip()
    if 'key_result' in params_string:
        interface.result = params['key_result'].strip()
        interface_history.result = params['key_result'].strip()
    if 'key_state' in params_string:
        interface.state = params['key_state']
    try:
        interface.save()
        interface_history.interface_id = interface.id
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
        if 'key_name' in params_string:
            interface.name = params['key_name'].strip()
            interface_history.name = params['key_name'].strip()
        if 'key_description' in params_string:
            interface.description = params['key_description'].strip()
            interface_history.description = params['key_description'].strip()
        if 'key_design' in params_string:
            interface.design = params['key_design'].strip()
            interface_history.design = params['key_design'].strip()
        if 'key_address' in params_string:
            interface.address = params['key_address'].strip()
            interface_history.address = params['key_address'].strip()
        if 'key_params' in params_string:
            interface.params = params['key_params'].strip()
            interface_history.params = params['key_params'].strip()
        if 'key_result' in params_string:
            interface.result = params['key_result'].strip()
            interface_history.result = params['key_result'].strip()
        if 'key_state' in params_string:
            state = params['key_state']
            interface.state = state
            state_info = get_state_info(state)
            interface_history.action = '修改并变更状态为' + state_info
        interface_history.description = '修改接口，详细信息见具体内容'
        interface.save()
        interface_history.save()
        detail_info = '修改成功,接口id:' + str(interface_id)
        save_log(action, '1', detail_info, ip, user_id)
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
        history = interface.interfacehistory_set.annotate(user_name=F('user__name')).values().order_by('-create_time')
        data = {'id': interface.id, 'name': interface.name, 'description': interface.description,
                'design': interface.design, 'address': interface.address,
                'params': interface.params, 'result': interface.result, 'state': interface.state}
        if len(history) > 0:
            data['history_list'] = list(history)
        result = {'ret': 0, 'msg': '查询成功', 'data': data}
        save_log(action, '1', '查询接口信息', ip, user_id)
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
    interface_id = request.params['delete_interface_id']
    try:
        interface = Interface.objects.get(id=interface_id, delete_state='0')
        has_right = is_module_right(user_id, interface.module_id)
        if has_right is False:
            save_log(action, '0', '无权限', ip, user_id)
            return JsonResponse({'ret': 1, 'msg': '无权限'})
        interface.delete_state = '1'
        interface_history = InterfaceHistory(action='删除接口', user_id=user_id, interface_id=interface_id)
        interface.save()
        interface_history.save()
        save_log(action, '1', '删除接口,接口id:' + str(interface_id), ip, user_id)
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


# 判断用户是否项目普通用户
def is_project_normal_user(user_id, project_id):
    user = User.objects.get(id=user_id)
    if user.type == '0':
        return True
    else:
        qs = ProjectUser.objects.filter(user_id=user_id, delete_state='0', project_id=project_id, type='2')
        if len(qs) > 0:
            return True
    return False


# 判断用户是否对整个项目的各个模块有接口增删改权限,系统管理员，项目管理员及整个项目的开发人员有权限
def is_project_right(user_id, project_id):
    user = User.objects.get(id=user_id)
    if user.type == '0':
        return True
    else:
        qs = ProjectUser.objects.filter(user_id=user_id, delete_state='0', project_id=project_id).filter(~Q(type='2'))
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
