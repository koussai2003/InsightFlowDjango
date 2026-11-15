from django.db.models import Q
from .models import Project

def workspace_projects(request):
    if not request.user.is_authenticated: return {}
    return {"nav_projects": Project.objects.filter(Q(owner=request.user) | Q(memberships__user=request.user)).distinct()}
