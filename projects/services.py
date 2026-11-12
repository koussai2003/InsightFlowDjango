import csv
import io
from .models import Project, ProjectMember, ProjectRole


def ensure_personal_project(user):
    """Ensure a verified user has at least one personal workspace project."""
    if not user.is_authenticated or not user.is_active:
        return None

    # Check if user owns or is member of any project
    first_owned = Project.objects.filter(owner=user).first()
    if first_owned:
        return first_owned

    first_member = Project.objects.filter(members__user=user).first()
    if first_member:
        return first_member

    # Create personal project
    name_part = user.email.split("@")[0].replace(".", " ").title()
    project_name = f"{name_part}'s Workspace"
    project = Project.objects.create(
        name=project_name,
        owner=user,
    )
    ProjectMember.objects.create(
        project=project,
        user=user,
        role=ProjectRole.OWNER,
    )
    return project


def get_user_projects_with_roles(user):
    """Return list of (project, role) for all projects accessible to the user."""
    projects = []
    seen_ids = set()

    for p in Project.objects.filter(owner=user):
        projects.append((p, ProjectRole.OWNER))
        seen_ids.add(p.id)

    for m in ProjectMember.objects.filter(user=user).select_related("project"):
        if m.project.id not in seen_ids:
            projects.append((m.project, m.role))
            seen_ids.add(m.project.id)

    return projects


def parse_csv_sample(file_obj, max_preview_rows=10):
    """
    Parse uploaded CSV stream and return (headers, preview_rows, total_rows).
    Supports UTF-8 and BOM.
    """
    raw_content = file_obj.read()
    if isinstance(raw_content, bytes):
        text = raw_content.decode("utf-8-sig", errors="replace")
    else:
        text = raw_content

    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        raise ValueError("The CSV file is empty. Provide a file with header and rows.")

    headers = rows[0]
    preview_rows = rows[1 : max_preview_rows + 1]
    total_data_rows = max(0, len(rows) - 1)
    return headers, preview_rows, total_data_rows
