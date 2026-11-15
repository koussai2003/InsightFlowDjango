from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"), path("signup/", views.signup_page, name="signup"), path("login/", views.login_page, name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"), path("account/", views.account_page, name="account"), path("projects/new/", views.create_project_page, name="project-new"),
    path("api/health/", views.health, name="api-health"), path("api/csrf/", views.csrf_token, name="api-csrf"), path("api/auth/signup/", views.signup_api, name="api-signup"),
    path("api/auth/login/", views.login_api, name="api-login"), path("api/auth/logout/", views.logout_api, name="api-logout"),
    path("api/me/", views.current_user, name="api-me"), path("api/projects/", views.ProjectListCreateView.as_view(), name="api-projects"),
    path("api/projects/<uuid:project_id>/", views.ProjectDetailView.as_view(), name="api-project-detail"),
    path("api/projects/<uuid:project_id>/invitations/", views.project_invitations, name="api-invitations-list"),
    path("api/projects/<uuid:project_id>/invitations/new/", views.create_invitation, name="api-invitation-create"),
    path("api/invitations/", views.my_invitations, name="api-my-invitations"),
    path("api/invitations/<uuid:invitation_id>/respond/", views.respond_invitation, name="api-invitation-respond"),
    path("api/projects/<uuid:project_id>/datasets/", views.upload_dataset, name="api-dataset-upload"), path("api/profile/avatar/", views.upload_avatar, name="api-avatar"),
]
