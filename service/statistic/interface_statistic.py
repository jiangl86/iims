from django.http import JsonResponse
import json
from django.db.models import Q, F
from common.common import get_ip, get_user
from service.log.log import save_log
from common.models import ProjectUser, Module, ModuleUser, User, Interface, InterfaceHistory
import datetime
import math


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
    elif action == 'interface_statistic':
        return interface_statistic(request)
    else:
        return JsonResponse({"ret": 1, "msg": "无法提供对应服务"})


def list_interface(request):
    action = '接口统计接口列表查询'
    user_right = right(request, action)
    if user_right != 'pass':
        return user_right
    ip = get_ip(request)
    params = request.params
    params_string = json.dumps(params)
    user_id = params['user_id']
    project_id = params['project_id']
    list_type = params['type']
    # 如果是按人员查询
    if 'search_user_id' in params_string:
        interface_qs = Interface.objects.filter(delete_state='0', module__project_id=project_id,
                                                user_id=params['search_user_id']).distinct()
    else:
        interface_qs = Interface.objects.filter(delete_state='0', module_id=params['module_id']).distinct()
    # 查询对应状态接口
    if 'state' in params_string:
        interface_qs = interface_qs.filter(state=params['state'])
    if len(interface_qs) == 0:
        save_log(action, '0', '无数据', ip, user_id)
        return JsonResponse({'ret': 1, 'msg': '暂无数据'})
    # 如果是按状态统计，不用查询历史记录
    result_list = []
    if list_type == 0:
        for item in interface_qs:
            interface_info = {'id': item.id, 'name': item.name,
                              'create_user_name': item.user.name}
            if item.state == '0':
                interface_info['current_state'] = '设计中'
            elif item.state == '1':
                interface_info['current_state'] = '未完成'
            elif item.state == '2':
                interface_info['current_state'] = '已完成'
            else:
                interface_info['current_state'] = '异常'
            result_list.append(interface_info)
        save_log(action, '1', '查询成功', ip, user_id)
        return JsonResponse({'ret': 0, 'msg': '查询成功', 'retlist': result_list})
    # 如果是按照操作类型查询
    else:
        interface_ids = []
        for item in interface_qs:
            interface_ids.append(item.id)
        # 查询项目下所有接口历史处理记录，便于后续统计
        interface_history_qs = InterfaceHistory.objects.filter(
            interface__module__project_id=project_id, interface_id__in=interface_ids).distinct().order_by(
            '-create_time')
        before_interface_history_qs = []
        if 'begin_date' in params_string:
            begin_date = params['begin_date']
            begin_date = datetime.datetime.strptime(begin_date, '%Y-%m-%d')
            before_interface_history_qs = interface_history_qs.filter(create_time__lt=begin_date)
            interface_history_qs = interface_history_qs.filter(create_time__gte=begin_date)
        if 'end_date' in params_string:
            end_date = params['end_date']
            end_date = end_date + ' 23:59:59'
            end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
            interface_history_qs = interface_history_qs.filter(create_time__lte=end_date)
        if len(interface_history_qs) == 0:
            save_log(action, '0', '无数据', ip, user_id)
            return JsonResponse({'ret': 1, 'msg': '暂无数据'})
        need_operate_type = params['operate_type']
        for item in interface_qs:
            # 获取接口在所选时间段内的操作类型
            operate_type = interface_operate_type(interface_history_qs, item, before_interface_history_qs)
            interface_info = {'id': item.id, 'name': item.name,
                              'create_user_name': item.user.name}
            if item.state == '0':
                interface_info['current_state'] = '设计中'
            elif item.state == '1':
                interface_info['current_state'] = '未完成'
            elif item.state == '2':
                interface_info['current_state'] = '已完成'
            else:
                interface_info['current_state'] = '异常'
            # 如果操作类型相同或者统计的是报错的列表，则计入返回列表

            if operate_type['state_type'] == need_operate_type or (
                    need_operate_type == 6 and operate_type['has_bug'] == 1):
                history_info = get_history_info(interface_history_qs, item, before_interface_history_qs,
                                                need_operate_type)
                interface_info['before_state'] = history_info['before_state']
                interface_info['operate_user_name'] = history_info['operate_user_name']
                interface_info['operate_user_time'] = history_info['operate_user_time']
                result_list.append(interface_info)
        save_log(action, '1', '查询成功', ip, user_id)
        return JsonResponse({'ret': 0, 'msg': '查询成功', 'retlist': result_list})
    save_log(action, '0', '无数据', ip, user_id)
    return JsonResponse({"ret": 1, "msg": "服务器错误"})


# 统计接口情况
def interface_statistic(request):
    action = '接口统计'
    user_right = right(request, action)
    if user_right != 'pass':
        return user_right
    ip = get_ip(request)
    params = request.params
    params_string = json.dumps(params)
    user_id = params['user_id']
    project_id = params['project_id']
    statistic_type = params['type']
    # 查询项目下所有接口列表便于后续统计
    interface_qs = Interface.objects.filter(delete_state='0', module__project_id=project_id).distinct()
    if len(interface_qs) == 0:
        save_log(action, '0', '无数据', ip, user_id)
        return JsonResponse({'ret': 1, 'msg': '暂无数据'})
    # 查询项目下所有接口历史处理记录，便于后续统计
    interface_history_qs = InterfaceHistory.objects.filter(
        interface__module__project_id=project_id).distinct().order_by(
        '-create_time')
    before_interface_history_qs = []
    if 'begin_date' in params_string:
        begin_date = params['begin_date']
        begin_date = datetime.datetime.strptime(begin_date, '%Y-%m-%d')
        before_interface_history_qs = interface_history_qs.filter(create_time__lt=begin_date)
        interface_history_qs = interface_history_qs.filter(create_time__gte=begin_date)
    if 'end_date' in params_string:
        end_date = params['end_date']
        end_date = end_date + ' 23:59:59'
        end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
        interface_history_qs = interface_history_qs.filter(create_time__lte=end_date)
    result_list = []
    result_map = {}
    for interface_item in interface_qs:
        map_key = 0
        statistic_info = {'total_num': 0, 'total_design': 0, 'total_un_finish': 0, 'total_finish': 0, 'total_bug': 0,
                          'add': 0, 'bug': 0, 'finish': 0, 'repair': 0, 'un_finish': 0, 'design': 0}
        # 如果是按照人员进行统计
        if statistic_type == 0:
            user_name = interface_item.user.name
            map_key = interface_item.user_id
            statistic_info['user_name'] = user_name
            statistic_info['user_id'] = map_key
        # 如果是按模块查询
        else:
            module_name = interface_item.module.name
            map_key = interface_item.module_id
            statistic_info['module_name'] = module_name
            statistic_info['module_id'] = map_key
        if map_key in result_map.keys():
            statistic_info = result_map[map_key]
        # 统计接口总量相关信息
        statistic_info['total_num'] = statistic_info['total_num'] + 1
        if interface_item.state == '0':
            statistic_info['total_design'] = statistic_info['total_design'] + 1
        elif interface_item.state == '1':
            statistic_info['total_un_finish'] = statistic_info['total_un_finish'] + 1
        elif interface_item.state == '2':
            statistic_info['total_finish'] = statistic_info['total_finish'] + 1
        else:
            statistic_info['total_bug'] = statistic_info['total_bug'] + 1
        # 统计时间范围内操作情况
        operate_type = interface_operate_type(interface_history_qs, interface_item, before_interface_history_qs)
        if operate_type['state_type'] == 0:
            statistic_info['add'] = statistic_info['add'] + 1
        elif operate_type['state_type'] == 1:
            statistic_info['finish'] = statistic_info['finish'] + 1
        elif operate_type['state_type'] == 2:
            statistic_info['repair'] = statistic_info['repair'] + 1
        elif operate_type['state_type'] == 3:
            statistic_info['un_finish'] = statistic_info['un_finish'] + 1
        elif operate_type['state_type'] == 4:
            statistic_info['design'] = statistic_info['design'] + 1
        if operate_type['has_bug'] == 1:
            statistic_info['bug'] = statistic_info['bug'] + 1
        result_map[map_key] = statistic_info
    # 将map转换为list
    for key in result_map.keys():
        result_list.append(result_map[key])
    # 如果是按模块查询，查询每个模块的对应的一级模块名称
    if statistic_type == 1:
        module_qs = Module.objects.filter(delete_state='0', project_id=project_id).distinct()
        for item in result_list:
            module_id = item['module_id']
            item['first_module_name'] = find_first_module_name(module_qs, module_id)
        # 对数据按照一级模块进行重新排序
        result_list.sort(key=lambda item: item['first_module_name'])
    # 为查询出的结果添加num序号
    index = 1
    for item in result_list:
        item['num'] = index
        index = index + 1
    if len(result_list) > 0:
        save_log(action, '1', '查询成功', ip, user_id)
        return JsonResponse({'ret': 0, 'msg': '查询成功', 'retlist': result_list})
    else:
        save_log(action, '0', '无数据', ip, user_id)
        return JsonResponse({'ret': 1, 'msg': '无数据'})


# historys为接口历史记录列表，已根据时间逆序排序，interface需要查询的接口,before_historys为更早的记录，可能为空
# 返回map,包含state_type和has_bug，其中type 0代表添加，1代表完成，2代表修复，3代表未完成，4代表设计,5代表无任何操作,has_bug 0代表是否有报错，0代表否，1代表是
def interface_operate_type(historys, interface, before_historys):
    interface_id = interface.id
    has_bug = 0
    state_type = None
    first_history = None
    # 获取历史状态
    old_state = None
    if len(before_historys) > 0:
        for item in before_historys:
            if item.interface_id == interface_id and item.action != '修改':
                old_state = item.action
                break
    if len(historys) > 0:
        for history in historys:
            if history.interface_id == interface_id:
                # 过滤仅仅是基础信息修改的历史记录
                if first_history is None or first_history.action == '修改':
                    first_history = history
                    if first_history.action == '添加':
                        state_type = 0
                        break
                if history.action.find('异常') != -1:
                    has_bug = 1
    # 如果没有查询时间范围内之前的历史记录
    if old_state is None:
        # 如果当前状态是已完成，则代表完成
        if interface.state == '2':
            state_type = 1
        else:
            state_type = 0  # 其他标识为新添加的接口
    else:
        # 如果查询时间范围内没有记录，则代表查询时间范围内针对该接口没有做任何操作
        if first_history is None:
            state_type = 5
        else:
            # 如果当前接口状态为完成
            if first_history.action.find('已完成') != -1:
                # 如果之前状态为异常，或者查询时间范围内有被标识过异常，则表示为修复
                if has_bug == 1 or old_state.find('异常') != -1:
                    state_type = 2
                # 否则如果之前的状态为未完成，则表示为在该周期内完成
                elif old_state.find('已完成') == -1:
                    state_type = 1
            # 如果当前状态为未完成，且查询时间段之前为已完成，则表示由添加人重新修改为未完成
            elif first_history.action.find('未完成') != -1:
                if old_state.find('已完成') != -1:
                    state_type = 3
            # 如果当前状态为设计中，且查询时间段之前为已完成，则表示由添加人重新修改为设计中
            elif first_history.action.find('设计中') != -1:
                if old_state.find('已完成') != -1:
                    state_type = 4
    return {'state_type': state_type, 'has_bug': has_bug}


# 获取某一个接口在某时间段内的操作记录，返回map对象，before_state，operate_user_name操作人名称，operate_user_time
# historys为接口历史记录列表，已根据时间逆序排序，interface需要查询的接口,before_historys为更早的记录，可能为空，operate_type0代表添加，1代表完成，2代表修复，3代表未完成，4代表设计，6代表报错
def get_history_info(historys, interface, before_historys, operate_type):
    interface_id = interface.id
    has_bug = 0
    state_type = None
    first_history = None
    # 获取历史状态
    old_state = None
    if len(before_historys) > 0:
        for item in before_historys:
            if item.interface_id == interface_id and item.action != '修改':
                old_state = item.action
                break
    if len(historys) > 0:
        for history in historys:
            if history.interface_id == interface_id:
                # 过滤仅仅是基础信息修改的历史记录
                if operate_type == 0:
                    if history.action == '添加':
                        first_history = history
                        break;
                elif operate_type == 1:
                    if history.action.find('已完成') != -1 or history.action.find('添加') != -1:
                        first_history = history
                        break;
                elif operate_type == 2:
                    if history.action.find('已完成') != -1:
                        first_history = history
                        break;
                elif operate_type == 3:
                    if history.action.find('未完成') != -1:
                        first_history = history
                        break;
                elif operate_type == 4:
                    if history.action.find('设计中') != -1:
                        first_history = history
                        break;
                elif operate_type == 6:
                    if history.action.find('异常') != -1:
                        first_history = history;
                        break;
    return {'before_state': old_state, 'operate_user_name': first_history.user.name,
            'operate_user_time': first_history.create_time}


# 查找module_id对应的一级模块名称，modules是所有的模块
def find_first_module_name(modules, module_id):
    parent_module_name = ''
    for item in modules:
        if item.id == module_id:
            if item.parent_id is None:
                return item.name
            else:
                parent_module_name = find_first_module_name(modules, item.parent_id)
            break;
    return parent_module_name


# 判断用户是否有当前模块权限
def right(request, action):
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
        return 'pass'  # 目前暂时采用所有登录用户可以查看接口统计
