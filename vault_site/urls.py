"""vault_site URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.ome, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import (
    include,
    path,
    re_path,
)

from vault import api, views

from vault.rest_api import router as rest_api_router

urlpatterns = [
    path("", views.index, name="index"),
    path("dashboard", views.dashboard, name="dashboard"),
    path("create_collection", views.create_collection, name="create_collection"),
    re_path(
        "^collections/(?P<path>.*)",
        views.render_web_components_file_view,
        name="collections",
    ),
    path("reports/<int:report_id>", views.report, name="report"),
    path("deposit", views.deposit, name="deposit"),
    path("deposit/web", views.deposit_web, name="deposit_web"),
    path("deposit/cli", views.deposit_cli, name="deposit_cli"),
    path("deposit/mail", views.deposit_mail, name="deposit_mail"),
    path("deposit/flow", views.deposit_flow, name="deposit_flow"),
    path("deposit/<int:deposit_id>", views.deposit_report, name="deposit_report"),
    path("deposit/ait", views.deposit_ait, name="deposit_ait"),
    path("administration", views.administration, name="administration"),
    path("administration/plan", views.administration_plan, name="administration_plan"),
    path(
        "administration/users", views.administration_users, name="administration_users"
    ),
    path("administration/help", views.administration_help, name="administration_help"),
    # path('accounts/', include('django.contrib.auth.urls')),
    path("api/collections", api.collections, name="api_collections"),
    path("api/reports", api.reports, name="api_reports"),
    path("api/collections_stats", api.collections_stats, name="api_collections_stats"),
    path("api/reports_files", api.reports_files, name="api_reports_files"),
    path(
        "api/collections_summary",
        api.collections_summary,
        name="api_collections_summary",
    ),
    path(
        "api/reports_files/<collection_id>",
        api.reports_files,
        name="api_reports_files_by_collection",
    ),
    path(
        "api/report_summary/<collection_id>/<report_id>",
        api.report_summary,
        name="api_report_summary",
    ),
    path(
        "api/report_files/<collection_id>/<report_id>",
        api.report_files,
        name="api_report_files",
    ),
    path(
        "api/flow_chunk",
        api.flow_chunk,
        name="api_flow_chunk",
    ),
    path("api/register_deposit", api.register_deposit, name="api_register_deposit"),
    path("api/deposit_status", api.hashed_status, name="api_deposit_status"),
    path("api/warning_deposit", api.warning_deposit, name="api_warning_deposit"),
    # Include the Django Rest Framework API routes.
    path("api/", include(rest_api_router.urls)),
    path("admin/", admin.site.urls),
]
