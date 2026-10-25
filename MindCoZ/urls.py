"""
URL configuration for MindCoZ project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
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
from django.contrib import admin
from django.urls import path

from MindCoZ_BackEnd import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health', views.health, name='api-health'),
    path('api/csrf', views.csrf_token, name='api-csrf'),
    path('api/login', views.login, name='api-login'),
    path('api/logout', views.logout, name='api-logout'),
    path('api/chat', views.chat, name='api-chat'),
    path('api/history', views.history, name='api-history'),
    path('api/sensor', views.sensor, name='api-sensor'),
]
