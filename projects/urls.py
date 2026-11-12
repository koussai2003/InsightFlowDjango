from django.urls import path
from . import views

urlpatterns = [
    path("", views.workspace_view, name="project_workspace"),
    path("create", views.create_project, name="create_project"),
    path("<uuid:pid>/invite", views.invite_collaborator, name="invite_collaborator"),
    path("<uuid:pid>/invitations/<uuid:iid>/revoke", views.revoke_invitation, name="revoke_invitation"),
    path("invitations/<uuid:iid>/<str:action>", views.respond_invitation, name="respond_invitation"),
    path("<uuid:pid>/members/<int:uid>/role", views.update_member_role, name="update_member_role"),
    path("<uuid:pid>/members/<int:uid>/remove", views.remove_member, name="remove_member"),
    path("<uuid:pid>/transfer", views.transfer_ownership, name="transfer_ownership"),
    path("<uuid:pid>/delete", views.delete_project, name="delete_project"),
    path("<uuid:pid>/upload", views.upload_csv, name="upload_csv"),
    path("<uuid:pid>/ask", views.ask_question, name="ask_question"),
]
