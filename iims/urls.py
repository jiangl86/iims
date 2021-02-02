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

urlpatterns = [
    # path('admin/', admin.site.urls),
    path('api/user', user.dispatcher),
    path('api/project', project.dispatcher),
    # path('api/module', corpcate.dispatcher),
    # path('api/interface', user.dispatcher),
    # path('api/log', corp.upload_file)
]
