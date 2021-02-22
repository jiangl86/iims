"""iims URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from service.project import project
from service.user import user
from service.module import module
from service.interface import interface
from service.statistic import interface_statistic
from service.log import log

urlpatterns = [
    # path('admin/', admin.site.urls),
    path('api/user', user.dispatcher),
    path('api/project', project.dispatcher),
    path('api/module', module.dispatcher),
    path('api/interface', interface.dispatcher),
    path('api/statistic', interface_statistic.dispatcher),
    path('api/log', log.dispatcher)
]
