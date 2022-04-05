"""vault_site URL Configuration"""

from django.contrib.auth import views as auth_views
from django.contrib import admin
from django.urls import (
    include,
    path,
    re_path,
)

from vault import api, views, fixity_api, forms

from vault.rest_api import router as rest_api_router


urlpatterns = [
    path("", views.index, name="index"),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "accounts/password_change/",
        auth_views.PasswordChangeView.as_view(),
        name="password_change",
    ),
    path(
        "accounts/password_change/done/",
        auth_views.PasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
    path(
        "accounts/password_reset/",
        auth_views.PasswordResetView.as_view(form_class=forms.VaultPasswordResetForm),
        name="password_reset",
    ),
    path(
        "accounts/password_reset/done",
        auth_views.PasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "accounts/reset/<uidb64>/<token>",
        auth_views.PasswordResetConfirmView.as_view(
            form_class=forms.VaultSetPasswordForm
        ),
        name="password_reset_confirm",
    ),
    path(
        "accounts/reset/done",
        auth_views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path(
        "accounts/logout_then_login",
        auth_views.logout_then_login,
        name="logout_then_login",
    ),
    path("dashboard", views.dashboard, name="dashboard"),
    path("create_collection", views.create_collection, name="create_collection"),
    re_path(
        "^collections/(?P<path>.*)",
        views.render_web_components_file_view,
        name="collections",
    ),
    path("reports/<int:report_id>", views.report, name="report"),
    path("reports/fixity/<int:report_id>", views.fixity_report, name="fixity_report"),
    path("deposit", views.deposit, name="deposit"),
    path("deposit/web", views.deposit_web, name="deposit_web"),
    path("deposit/compat", views.deposit_compat, name="deposit_compat"),
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
    path("api/get_events/<collection_id>", api.get_events, name="api_get_events"),
    path("api/register_deposit", api.register_deposit, name="api_register_deposit"),
    path("api/deposit_status", api.hashed_status, name="api_deposit_status"),
    path("api/warning_deposit", api.warning_deposit, name="api_warning_deposit"),
    # Include the Django Rest Framework API routes.
    path("api/", include(rest_api_router.urls)),
    re_path(
        r"^fixitter/files/(?P<org_id>\d+)/(?P<path>.*)",
        fixity_api.list_files,
        name="fixitter_files",
    ),
    path(
        "fixitter/shafs/<int:org_id>/<sha256_sum>",
        fixity_api.stream_from_shafs,
        name="fixitter_shafs",
    ),
    path(
        "fixitter/run/<int:org_id>/<collection_name>/<token>",
        fixity_api.run_collection_name,
        name="fixitter_run",
    ),
    path(
        "fixitter/postback/<int:org_id>/<int:collection_id>/<token>",
        fixity_api.postback,
        name="fixitter_postback",
    ),
    path("admin/", admin.site.urls),
]
