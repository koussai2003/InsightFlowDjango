def project_json(project, user):
    role = "owner" if project.owner_id == user.id else project.memberships.get(user=user).role
    return {"id": str(project.id), "name": project.name, "role": role, "created_at": project.created_at.isoformat()}
