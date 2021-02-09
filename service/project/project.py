from django.http import JsonResponse
import json
from common.common import get_ip, get_user
from service.log.log import save_log
from common.models import Project, ProjectUser, Module, User
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
    if action == 'list_project':
        return list_project(request)
    elif action == 'add_project':
        return add_project(request)
    elif action == 'update_project':
        return update_project(request)
    elif action == 'delete_project':
        return delete_project(request)
    else:
        return JsonResponse({"ret": 1, "msg": "无法提供对应服务"})


def list_project(request):
    user_right = project_right(request, '项目查询')
    if user_right != 'pass':
        return user_right
    ip = get_ip(request)
    params = request.params
    params_string = json.dumps(params)
    user_id = params['user_id']
    user = User.objects.get(id=user_id)
    project_list = []
    # 如果是系统管理员，直接返回所有的项目
    if user.type == '0':
        qs = Project.objects.filter(delete_state='0').all()
    # 否则查询所有当前用户参与的项目列表
    else:
        qs = Project.objects.filter(projectuser__user_id=user_id, projectuser__delete_state='0').distinct()
    if len(qs) > 0:
        if 'name' in params_string:
            name = params['name'].strip()
            qs = qs.filter(name__contains=name)
        if 'state' in params_string:
            qs = qs.filter(state=params['state'].strip())
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
            page_size = 1000
            total_count = len(qs)
            total_page = 1
        if len(qs) > 0:
            index = 1
            for item in qs:
                project = {'id': item.id, 'name': item.name, 'description': item.description, 'state': item.state}
                project['create_time'] = item.create_time.strftime('%Y-%m-%d %H:%M')
                project['num'] = (page_num - 1) * page_size + index
                index = index + 1
                admin = item.projectuser_set.filter(type='0', delete_state='0').annotate(
                    user_name=F('user__name')).values('user_id', 'user_name')
                developer = item.projectuser_set.filter(type='1', delete_state='0').annotate(
                    user_name=F('user__name')).values('user_id', 'user_name')
                others = item.projectuser_set.filter(type='2', delete_state='0').annotate(
                    user_name=F('user__name')).values('user_id', 'user_name')
                if len(admin) > 0:
                    project['admin'] = list(admin)
                if len(developer) > 0:
                    project['developer'] = list(developer)
                if len(others) > 0:
                    project['others'] = list(others)
                if user.type != '0':
                    is_admin = item.projectuser_set.filter(type='0', delete_state='0', user_id=user_id)
                    if len(is_admin) > 0:
                        project['editFlag'] = '1'
                project_list.append(project)
            result = {'ret': 0, 'msg': '查询成功', 'total_page': total_page, 'total_count': total_count,
                      'page_num': page_num, 'retlist': project_list}
            if user.type == '0':
                funcRight = {'addFlag': '1', 'editFlag': 1, 'delFlag': '1'}
                result['funcRight'] = funcRight
            return JsonResponse(result)
        else:
            save_log('项目查询', '0', '无符合条件的项目或无权限', ip, user_id)
            return JsonResponse({"ret": 1, "msg": "暂无数据"})


def add_project(request):
    action = '项目添加'
    user_right = project_right(request, action)
    if user_right != 'pass':
        return user_right
    ip = get_ip(request)
    user_id = request.params['user_id']
    params = request.params['data']
    params_string = json.dumps(params)
    user = User.objects.get(id=user_id, delete_state='0', state='1')
    if user.type != '0':
        save_log(action, '0', '无项目添加权限', ip, user_id)
        return JsonResponse({'ret': 1, 'msg': '无项目添加权限'})
    name = params['name'].strip()
    qs = Project.objects.filter(name=name, delete_state='0')
    if len(qs) > 0:
        save_log(action, '0', '项目名称' + name, ip, user_id)
        return JsonResponse({'ret': 1, 'msg': '项目已经存在，请使用其他名称'})
    detail = '项目名称:' + name
    project = Project(name=name)
    if 'description' in params_string:
        project.description = params['description'].strip()
        detail = detail + ',详细信息：' + params['description'].strip()
    try:
        project.save()
        if 'admin' in params_string:
            admin = params['admin'].split(',')
            batch = [ProjectUser(project_id=project.id, user_id=temp, type='0') for temp in admin]
            ProjectUser.objects.bulk_create(batch)
        if 'developer' in params_string:
            developer = params['developer'].split(',')
            batch = [ProjectUser(project_id=project.id, user_id=temp, type='1') for temp in developer]
            ProjectUser.objects.bulk_create(batch)
        if 'others' in params_string:
            others = params['others'].split(',')
            batch = [ProjectUser(project_id=project.id, user_id=temp, type='2') for temp in others]
            ProjectUser.objects.bulk_create(batch)
        save_log(action, '1', detail, ip, user_id)
        return JsonResponse({'ret': 0, 'msg': '添加成功', 'project_id': project.id})
    except Exception:
        save_log(action, '0', '添加失败', ip, user_id)
        return JsonResponse({'ret': 1, 'msg': '添加失败，请稍候再试'})


def update_project(request):
    action = '项目修改'
    user_right = project_right(request, action)
    if user_right != 'pass':
        return user_right
    params = request.params['data']
    params_string = json.dumps(params)
    ip = get_ip(request)
    user_id = request.params['user_id']
    user = User.objects.get(id=user_id, delete_state='0', state='1')
    if user.type != '0':
        save_log(action, '0', '无权限', ip, user_id)
        return JsonResponse({'ret': 1, 'msg': '无权限'})
    try:
        project = Project.objects.get(id=request.params['project_id'], delete_state='0')
        if 'name' in params_string:
            project.name = params['name'].strip()
        if 'description' in params_string:
            project.description = params['description'].strip()
        if 'state' in params_string:
            project.state = params['state'].strip()
        if 'admin' in params_string:
            ProjectUser.objects.filter(type='0', project_id=project.id).delete()
            admin = params['admin'].split(',')
            batch = [ProjectUser(project_id=project.id, user_id=temp, type='0') for temp in admin]
            ProjectUser.objects.bulk_create(batch)
        if 'developer' in params_string:
            ProjectUser.objects.filter(type='1', project_id=project.id).delete()
            developer = params['developer'].split(',')
            batch = [ProjectUser(project_id=project.id, user_id=temp, type='1') for temp in developer]
            ProjectUser.objects.bulk_create(batch)
        if 'others' in params_string:
            ProjectUser.objects.filter(type='2', project_id=project.id).delete()
            others = params['others'].split(',')
            batch = [ProjectUser(project_id=project.id, user_id=temp, type='2') for temp in others]
            ProjectUser.objects.bulk_create(batch)
        project.save()
        save_log(action, '1', '修改成功', ip, user_id)
        return JsonResponse({'ret': 0, 'msg': '修改成功'})
    except Project.DoesNotExist:
        save_log(action, '0', '参数错误', ip, user_id)
        return JsonResponse({'ret': 1, 'msg': '参数错误'})


def delete_project(request):
    action = '项目删除'
    user_right = project_right(request, action)
    if user_right != 'pass':
        return user_right
    params = request.params
    params_string = json.dumps(params)
    ip = get_ip(request)
    user_id = params['user_id']
    user = User.objects.get(id=user_id, delete_state='0', state='1')
    if user.type != '0':
        save_log(action, '0', '无权限', ip, user_id)
        return JsonResponse({'ret': 1, 'msg': '无权限'})
    try:
        delete_project_ids = params['delete_project_ids'].split(',')
        projects = Project.objects.filter(id__in=delete_project_ids).update(delete_state='1')
        ProjectUser.objects.filter(project__id__in=delete_project_ids).update(delete_state='1')
        detail = '成功删除项目：' + params['delete_project_ids']
        save_log(action, '1', detail, ip, user_id)
        return JsonResponse({"ret": 0, "msg": "删除成功"})
    except Exception:
        save_log(action, '0', '删除失败', ip, request.params['user_id'])
        return JsonResponse({"ret": 1, "msg": "删除失败，请稍后再试"})


# 判断用户是否登录和是否有权限(仅适用本模块,因为各模块对权限判断不相同），并记录日志
# 不通过时，直接返回JsonResponse，否则返回'pass'
def project_right(request, action):
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
