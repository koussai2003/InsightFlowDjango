from django.utils import timezone
from .services import get_user_projects_with_roles, ensure_personal_project
from .models import ProjectInvitation


def user_projects_processor(request):
    """Context processor providing user's accessible projects and pending invites across all templates."""
    if not request.user.is_authenticated or not request.user.is_active:
        return {}

    ensure_personal_project(request.user)
    projects_with_roles = get_user_projects_with_roles(request.user)

    pending_count = ProjectInvitation.objects.filter(
        email=request.user.email.lower(),
        status=ProjectInvitation.Status.PENDING,
        expires_at__gt=timezone.now(),
    ).count()

    current_pid = request.GET.get("project")
    if not current_pid and projects_with_roles:
        current_pid = str(projects_with_roles[0][0].id)

    return {
        "sidebar_projects": projects_with_roles,
        "current_project_id": str(current_pid) if current_pid else "",
        "pending_invitations_count": pending_count,
    }
