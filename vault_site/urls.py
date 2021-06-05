"""vault_site URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
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
from vault import api, views

urlpatterns = [
    path('', views.index, name='index'),
    path('dashboard', views.dashboard, name='dashboard'),
    path('collections', views.collections, name='collections'),
    path('reports', views.reports, name='reports'),
    path('deposit', views.deposit, name='deposit'),
    path('deposit/web', views.deposit_web, name='deposit_web'),
    path('deposit/cli', views.deposit_cli, name='deposit_cli'),
    path('deposit/mail', views.deposit_mail, name='deposit_mail'),
    path('deposit/debug', views.deposit_debug, name='deposit_debug'),
    path('deposit/ait', views.deposit_ait, name='deposit_ait'),
    path('administration', views.administration, name='administration'),
    path('administration/plan', views.administration_plan, name='administration_plan'),
    path('administration/users', views.administration_users, name='administration_users'),
    path('administration/help', views.administration_help, name='administration_help'),

    path('api/collections', api.collections),
    path('api/reports', api.reports),
    path('api/collections_stats', api.collections_stats),
    path('api/reports_files', api.reports_files),
    path('api/collections_summary', api.collections_summary),
    path('api/reports_files/<collection_id>', api.reports_files_by_collection),
    path('api/report_summary/<collection_id>/<report_id>', api.report_summary),

    path('admin/', admin.site.urls),
]
