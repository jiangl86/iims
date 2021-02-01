from django.db import models
import datetime


# Create your models here.
class User(models.Model):
    name = models.CharField(max_length=50)
    phone = models.CharField(max_length=11, unique=True)
    account = models.CharField(max_length=50, null=True, unique=True)
    password = models.CharField(max_length=100, null=True)
    # type 1为正常用户，0为管理员
    type = models.CharField(max_length=1, default='1')
    # state 1为正常，2为未激活
    state = models.CharField(max_length=1, default='1')
    create_time = models.DateTimeField(default=datetime.datetime.now)
    token = models.CharField(max_length=128, null=True)
    token_time = models.IntegerField(null=True)
    fail_times = models.IntegerField(null=True, default=0)
    fail_date = models.DateField(null=True)
    # delete_state 0未删除，1已删除
    delete_state = models.CharField(max_length=1, default='0')


class Log(models.Model):
    action = models.CharField(max_length=50, null=True)
    detail = models.CharField(max_length=2000, null=True)
    # 操作结果 1成功，0失败
    action_state = models.CharField(max_length=1, default='1')
    ip = models.CharField(max_length=128, null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    create_time = models.DateTimeField(default=datetime.datetime.now)


class Project(models.Model):
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=1000, null=True)
    admin = models.CharField(max_length=200, null=True)
    developer = models.CharField(max_length=1000, null=True)
    others = models.CharField(max_length=1000, null=True)
    # 项目状态，0未完成，1已完成
    state = models.CharField(max_length=1, default='0')
    create_time = models.DateTimeField(default=datetime.datetime.now)
    delete_state = models.CharField(max_length=1, default='0')


class Module(models.Model):
    name = models.CharField(max_length=200)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    parent = models.ForeignKey(to='self', null=True, on_delete=models.CASCADE)
    developer = models.CharField(max_length=1000, null=True)
    others = models.CharField(max_length=1000, null=True)
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    create_time = models.DateTimeField(default=datetime.datetime.now)
    delete_state = models.CharField(max_length=1, default='0')


class Interface(models.Model):
    name = models.CharField(max_length=400)
    module = models.ForeignKey(Module, on_delete=models.CASCADE)
    design = models.CharField(max_length=4000, null=True)
    address = models.CharField(max_length=500, null=True)
    params = models.CharField(max_length=2000, null=True)
    result = models.CharField(max_length=4000, null=True)
    state = models.CharField(max_length=1, default='1')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    delete_state = models.CharField(max_length=1, default='0')


class InterfaceHistory(models.Model):
    interface = models.ForeignKey(Interface, on_delete=models.CASCADE)
    action = models.CharField(max_length=100)
    design = models.CharField(max_length=4000, null=True)
    address = models.CharField(max_length=500, null=True)
    params = models.CharField(max_length=2000, null=True)
    result = models.CharField(max_length=4000, null=True)
    description = models.CharField(max_length=1000)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    delete_state = models.CharField(max_length=1, default='0')
