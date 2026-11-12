from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from .models import (
    Project,
    ProjectDataset,
    ProjectInvitation,
    ProjectMember,
    ProjectQuestion,
    ProjectRole,
)
from .services import (
    ensure_personal_project,
    get_user_projects_with_roles,
    parse_csv_sample,
)


def _get_project_context(request, project_id=None):
    """Retrieve the project and the current user's role in it."""
    ensure_personal_project(request.user)
    projects_with_roles = get_user_projects_with_roles(request.user)

    if not projects_with_roles:
        return None, None, []

    selected_project = None
    selected_role = None

    if project_id:
        for p, r in projects_with_roles:
            if str(p.id) == str(project_id):
                selected_project = p
                selected_role = r
                break
        if not selected_project:
            raise PermissionDenied("You do not have access to this project.")
    else:
        # Default to first project
        selected_project, selected_role = projects_with_roles[0]

    return selected_project, selected_role, projects_with_roles


@login_required
def workspace_view(request):
    """Main project workspace, settings, and invitations page."""
    pid = request.GET.get("project")
    view_tab = request.GET.get("view", "studio")

    selected_project, user_role, user_projects = _get_project_context(request, pid)

    # Inbox of invitations for the logged-in user's email
    inbox = ProjectInvitation.objects.filter(
        email=request.user.email.lower(),
        status=ProjectInvitation.Status.PENDING,
        expires_at__gt=timezone.now(),
    ).select_related("project")

    members = []
    sent_invites = []
    datasets = []
    questions = []

    if selected_project:
        # Load members
        members_qs = selected_project.members.select_related("user").order_by("user__email")
        members = [
            {
                "id": m.user.id,
                "email": m.user.email,
                "role": m.role,
                "is_owner": m.role == ProjectRole.OWNER or m.user_id == selected_project.owner_id,
            }
            for m in members_qs
        ]
        # Sent pending invitations for this project
        if user_role in (ProjectRole.OWNER, ProjectRole.MODERATOR):
            sent_invites = selected_project.invitations.filter(
                status=ProjectInvitation.Status.PENDING,
                expires_at__gt=timezone.now(),
            )

        # Datasets and questions
        datasets = selected_project.datasets.all()
        questions = selected_project.questions.select_related("user").all()

    return render(
        request,
        "projects/workspace.html",
        {
            "selected": selected_project,
            "role": user_role,
            "projects": user_projects,
            "view": view_tab,
            "members": members,
            "sent_invites": sent_invites,
            "inbox": inbox,
            "datasets": datasets,
            "questions": questions,
            "is_owner": user_role == ProjectRole.OWNER,
            "is_moderator": user_role == ProjectRole.MODERATOR,
            "can_manage": user_role in (ProjectRole.OWNER, ProjectRole.MODERATOR),
        },
    )


@require_POST
@login_required
def create_project(request):
    name = request.POST.get("name", "").strip()
    if not name or len(name) > 80:
        messages.error(request, "Project name must be between 1 and 80 characters.")
        return redirect("project_workspace")

    project = Project.objects.create(name=name, owner=request.user)
    ProjectMember.objects.create(
        project=project,
        user=request.user,
        role=ProjectRole.OWNER,
    )
    messages.success(request, f"Project '{project.name}' created.")
    return redirect(f"/projects?project={project.id}&view=studio")


@require_POST
@login_required
def invite_collaborator(request, pid):
    project = get_object_or_404(Project, pk=pid)
    role = project.user_role(request.user)
    if role not in (ProjectRole.OWNER, ProjectRole.MODERATOR):
        raise PermissionDenied("You do not have permission to invite collaborators.")

    email = request.POST.get("email", "").lower().strip()
    invite_role = request.POST.get("role", "").strip()

    if invite_role not in (ProjectRole.DATA_SCIENTIST, ProjectRole.REVIEWER, ProjectRole.MODERATOR):
        messages.error(request, "Invalid project role.")
        return redirect(f"/projects?project={pid}&view=members")

    if role == ProjectRole.MODERATOR and invite_role == ProjectRole.MODERATOR:
        messages.error(request, "Moderators can only invite Data Scientists and Reviewers.")
        return redirect(f"/projects?project={pid}&view=members")

    if project.members.filter(user__email=email).exists():
        messages.error(request, "This person is already a member of the project.")
        return redirect(f"/projects?project={pid}&view=members")

    # Revoke any expired invitations for this email
    project.invitations.filter(
        email=email,
        status=ProjectInvitation.Status.PENDING,
        expires_at__lte=timezone.now(),
    ).update(status=ProjectInvitation.Status.REVOKED)

    if project.invitations.filter(
        email=email,
        status=ProjectInvitation.Status.PENDING,
    ).exists():
        messages.error(request, "A pending invitation already exists for this email.")
        return redirect(f"/projects?project={pid}&view=members")

    ProjectInvitation.objects.create(
        project=project,
        email=email,
        role=invite_role,
        invited_by=request.user,
    )
    messages.success(request, f"Invitation created for {email}.")
    return redirect(f"/projects?project={pid}&view=members")


@require_POST
@login_required
def revoke_invitation(request, pid, iid):
    project = get_object_or_404(Project, pk=pid)
    role = project.user_role(request.user)
    if role not in (ProjectRole.OWNER, ProjectRole.MODERATOR):
        raise PermissionDenied

    invitation = get_object_or_404(ProjectInvitation, pk=iid, project=project, status=ProjectInvitation.Status.PENDING)
    if role == ProjectRole.MODERATOR and invitation.role == ProjectRole.MODERATOR:
        raise PermissionDenied

    invitation.status = ProjectInvitation.Status.REVOKED
    invitation.save(update_fields=["status"])
    messages.success(request, f"Invitation for {invitation.email} revoked.")
    return redirect(f"/projects?project={pid}&view=members")


@require_POST
@login_required
def respond_invitation(request, iid, action):
    invitation = get_object_or_404(
        ProjectInvitation,
        pk=iid,
        email=request.user.email.lower(),
        status=ProjectInvitation.Status.PENDING,
    )

    if invitation.is_expired():
        invitation.status = ProjectInvitation.Status.REVOKED
        invitation.save(update_fields=["status"])
        messages.error(request, "This invitation has expired.")
        return redirect("/projects?view=invitations")

    if action == "accept":
        ProjectMember.objects.update_or_create(
            project=invitation.project,
            user=request.user,
            defaults={"role": invitation.role},
        )
        invitation.status = ProjectInvitation.Status.ACCEPTED
        invitation.save(update_fields=["status"])
        messages.success(request, f"Joined '{invitation.project.name}' as {invitation.get_role_display()}.")
        return redirect(f"/projects?project={invitation.project.id}&view=studio")
    elif action == "decline":
        invitation.status = ProjectInvitation.Status.DECLINED
        invitation.save(update_fields=["status"])
        messages.info(request, f"Declined invitation to '{invitation.project.name}'.")
        return redirect("/projects?view=invitations")

    raise Http404


@require_POST
@login_required
def update_member_role(request, pid, uid):
    project = get_object_or_404(Project, pk=pid)
    role = project.user_role(request.user)
    if role not in (ProjectRole.OWNER, ProjectRole.MODERATOR):
        raise PermissionDenied

    new_role = request.POST.get("role", "").strip()
    if new_role not in (ProjectRole.DATA_SCIENTIST, ProjectRole.REVIEWER, ProjectRole.MODERATOR):
        messages.error(request, "Invalid role.")
        return redirect(f"/projects?project={pid}&view=members")

    if role == ProjectRole.MODERATOR and new_role == ProjectRole.MODERATOR:
        raise PermissionDenied("Moderators cannot assign moderator role.")

    target_member = get_object_or_404(ProjectMember, project=project, user_id=uid)
    if target_member.user_id == project.owner_id:
        messages.error(request, "Use ownership transfer to change the owner's role.")
        return redirect(f"/projects?project={pid}&view=members")

    if role == ProjectRole.MODERATOR and target_member.role == ProjectRole.MODERATOR:
        raise PermissionDenied("Moderators cannot change another moderator's role.")

    target_member.role = new_role
    target_member.save(update_fields=["role"])

    # Revoke any invitations created by demoted member
    project.invitations.filter(
        invited_by_id=uid,
        status=ProjectInvitation.Status.PENDING,
    ).update(status=ProjectInvitation.Status.REVOKED)

    messages.success(request, f"Updated role for {target_member.user.email}.")
    return redirect(f"/projects?project={pid}&view=members")


@require_POST
@login_required
def remove_member(request, pid, uid):
    project = get_object_or_404(Project, pk=pid)
    role = project.user_role(request.user)

    target_member = get_object_or_404(ProjectMember, project=project, user_id=uid)
    is_self = str(request.user.id) == str(uid)

    if target_member.user_id == project.owner_id:
        messages.error(request, "The owner cannot leave the project without transferring ownership or deleting it.")
        return redirect(f"/projects?project={pid}&view=members")

    if not is_self:
        if role not in (ProjectRole.OWNER, ProjectRole.MODERATOR):
            raise PermissionDenied
        if role == ProjectRole.MODERATOR and target_member.role == ProjectRole.MODERATOR:
            raise PermissionDenied

    target_member.delete()
    project.invitations.filter(
        invited_by_id=uid,
        status=ProjectInvitation.Status.PENDING,
    ).update(status=ProjectInvitation.Status.REVOKED)

    if is_self:
        messages.info(request, f"You have left '{project.name}'.")
        return redirect("project_workspace")

    messages.success(request, f"Removed {target_member.user.email} from project.")
    return redirect(f"/projects?project={pid}&view=members")


@require_POST
@login_required
def transfer_ownership(request, pid):
    project = get_object_or_404(Project, pk=pid)
    if project.owner_id != request.user.id:
        raise PermissionDenied("Only the owner can transfer ownership.")

    new_owner_id = request.POST.get("new_owner_id")
    if not new_owner_id or str(new_owner_id) == str(request.user.id):
        messages.error(request, "Choose another existing member.")
        return redirect(f"/projects?project={pid}&view=members")

    new_owner = get_object_or_404(User, pk=new_owner_id)
    if not project.members.filter(user=new_owner).exists():
        messages.error(request, "The new owner must already be a project member.")
        return redirect(f"/projects?project={pid}&view=members")

    project.owner = new_owner
    project.save(update_fields=["owner"])

    # Update membership roles: new owner becomes owner, former owner becomes moderator
    project.members.filter(user=new_owner).update(role=ProjectRole.OWNER)
    project.members.filter(user=request.user).update(role=ProjectRole.MODERATOR)

    project.invitations.filter(
        invited_by=request.user,
        status=ProjectInvitation.Status.PENDING,
    ).update(status=ProjectInvitation.Status.REVOKED)

    messages.success(request, f"Ownership transferred to {new_owner.email}. You are now a Moderator.")
    return redirect(f"/projects?project={pid}&view=members")


@require_POST
@login_required
def delete_project(request, pid):
    project = get_object_or_404(Project, pk=pid)
    if project.owner_id != request.user.id:
        raise PermissionDenied("Only the owner can delete this project.")

    confirmation = request.POST.get("confirmation", "").strip()
    if confirmation != project.name:
        messages.error(request, f"Type '{project.name}' exactly to confirm deletion.")
        return redirect(f"/projects?project={pid}&view=members")

    project_name = project.name
    project.delete()
    messages.success(request, f"Project '{project_name}' has been deleted.")
    return redirect("project_workspace")


@require_POST
@login_required
def upload_csv(request, pid):
    project = get_object_or_404(Project, pk=pid)
    role = project.user_role(request.user)
    if role not in (ProjectRole.OWNER, ProjectRole.MODERATOR, ProjectRole.DATA_SCIENTIST):
        raise PermissionDenied("Your project role does not allow data upload.")

    csv_file = request.FILES.get("file")
    if not csv_file:
        messages.error(request, "Please choose a CSV file to upload.")
        return redirect(f"/projects?project={pid}&view=studio")

    if not csv_file.name.lower().endswith(".csv"):
        messages.error(request, "Only CSV files are supported.")
        return redirect(f"/projects?project={pid}&view=studio")

    if csv_file.size > 10 * 1024 * 1024:
        messages.error(request, "Please choose a CSV file smaller than 10 MB.")
        return redirect(f"/projects?project={pid}&view=studio")

    try:
        headers, preview_rows, row_count = parse_csv_sample(csv_file)
    except Exception as e:
        messages.error(request, f"Failed to read CSV: {e}")
        return redirect(f"/projects?project={pid}&view=studio")

    dataset = ProjectDataset.objects.create(
        project=project,
        uploaded_by=request.user,
        name=csv_file.name,
        file=csv_file,
        row_count=row_count,
        column_count=len(headers),
        column_names=headers,
        preview_rows=preview_rows,
    )
    messages.success(request, f"Dataset '{dataset.name}' uploaded successfully ({row_count} rows, {len(headers)} columns).")
    return redirect(f"/projects?project={pid}&view=studio")


@require_POST
@login_required
def ask_question(request, pid):
    project = get_object_or_404(Project, pk=pid)
    role = project.user_role(request.user)
    if not role:
        raise PermissionDenied

    question_text = request.POST.get("prompt", "").strip()
    dataset_name = request.POST.get("dataset_name", "").strip() or None

    if question_text:
        ProjectQuestion.objects.create(
            project=project,
            user=request.user,
            question=question_text,
            dataset_name=dataset_name,
        )

    return redirect(f"/projects?project={pid}&view=studio")
