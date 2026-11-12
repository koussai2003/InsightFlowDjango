"""URL patterns for the accounts app."""
from django.urls import path

from . import views

urlpatterns = [
    # --- Auth ---
    path("register", views.register, name="register"),
    path("verify/<uidb64>/<token>/", views.verify_link, name="verify_link"),
    path("verify", views.verify_code, name="verify_code"),
    path("verify/resend", views.verify_resend, name="verify_resend"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    # --- Home (redirects by role) ---
    path("", views.home, name="home"),
    # --- Workspaces ---
    path("workspaces/preparation", views.workspace_preparation, name="workspace_preparation"),
    path("workspaces/review", views.workspace_review, name="workspace_review"),
    # --- Admin ---
    path("manage/accounts", views.manage_accounts, name="manage_accounts"),
    path("manage/accounts/<int:pk>/role", views.change_role, name="change_role"),
    # --- Settings ---
    path("settings", views.settings_view, name="settings"),
    path("settings/request", views.settings_request, name="settings_request"),
    path("settings/verify", views.settings_verify, name="settings_verify"),
]
