import json
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.middleware.csrf import get_token
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.decorators.http import require_GET, require_POST
from django.utils.decorators import method_decorator
from .forms import SignUpForm, ProjectForm, AvatarForm, DatasetForm
from .models import Project, Membership, Invitation, Notification, Dataset
from .serializers import project_json

User = get_user_model()

def payload(request):
    try: return json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError): return None

@require_GET
def health(request): return JsonResponse({"status": "ok", "service": "InsightFlow Django API"})

@require_GET
def csrf_token(request): return JsonResponse({"csrfToken": get_token(request)})

@require_POST
def signup_api(request):
    data = payload(request)
    if data is None: return JsonResponse({"detail": "Invalid JSON."}, status=400)
    form = SignUpForm(data)
    if not form.is_valid(): return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
    user = form.save()
    project = Project.objects.create(name="My first project", owner=user)
    return JsonResponse({"id": user.id, "email": user.email, "project_id": str(project.id)}, status=201)

@require_POST
def login_api(request):
    data = payload(request)
    if data is None: return JsonResponse({"detail": "Invalid JSON."}, status=400)
    user = authenticate(request, username=(data.get("email") or "").lower(), password=data.get("password"))
    if not user: return JsonResponse({"detail": "Email or password is incorrect."}, status=401)
    login(request, user)
    return JsonResponse({"id": user.id, "email": user.email, "role": user.role})

@require_POST
def logout_api(request):
    logout(request); return JsonResponse({"status": "signed out"})

@method_decorator(login_required, name="dispatch")
class ProjectListCreateView(View):
    """CBV demonstrating GET list and POST create for Postman and the UI."""
    def get(self, request):
        projects = Project.objects.filter(Q(owner=request.user) | Q(memberships__user=request.user)).distinct()
        return JsonResponse({"projects": [project_json(p, request.user) for p in projects]})
    def post(self, request):
        data = payload(request)
        if data is None: return JsonResponse({"detail": "Invalid JSON."}, status=400)
        form = ProjectForm(data)
        if not form.is_valid(): return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
        project = form.save(commit=False); project.owner = request.user
        with transaction.atomic():
            project.save(); Membership.objects.create(project=project, user=request.user, role="moderator")
        return JsonResponse(project_json(project, request.user), status=201)

@method_decorator(login_required, name="dispatch")
class ProjectDetailView(View):
    def get(self, request, project_id):
        project = get_object_or_404(Project.objects.filter(Q(owner=request.user) | Q(memberships__user=request.user)).distinct(), id=project_id)
        return JsonResponse(project_json(project, request.user))

@require_GET
@login_required
def current_user(request): return JsonResponse({"id": request.user.id, "email": request.user.email, "role": request.user.role})

@require_POST
@login_required
def upload_avatar(request):
    form = AvatarForm(request.POST, request.FILES, instance=request.user)
    if not form.is_valid(): return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
    user = form.save(); return JsonResponse({"avatar": user.avatar.url})

@require_POST
@login_required
def upload_dataset(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if project.owner_id != request.user.id and not Membership.objects.filter(project=project, user=request.user).exists(): return JsonResponse({"detail": "Not a project member."}, status=403)
    form = DatasetForm(request.POST, request.FILES)
    if not form.is_valid(): return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
    dataset = form.save(commit=False); dataset.project = project; dataset.uploaded_by = request.user; dataset.name = dataset.csv_file.name; dataset.save()
    return JsonResponse({"id": dataset.id, "name": dataset.name, "url": dataset.csv_file.url}, status=201)

@require_GET
@login_required
def project_invitations(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if project.owner_id != request.user.id and not Membership.objects.filter(project=project, user=request.user, role__in=["moderator"]).exists(): return JsonResponse({"detail": "Only the owner or a moderator can view invitations."}, status=403)
    items = project.invitations.filter(status="pending").values("id", "email", "role", "status", "created_at")
    return JsonResponse({"invitations": list(items)})

@require_POST
@login_required
def create_invitation(request, project_id):
    data = payload(request)
    if data is None: return JsonResponse({"detail": "Invalid JSON."}, status=400)
    project = get_object_or_404(Project, id=project_id)
    if project.owner_id != request.user.id and not Membership.objects.filter(project=project, user=request.user, role="moderator").exists(): return JsonResponse({"detail": "Only the owner or a moderator can invite members."}, status=403)
    email = (data.get("email") or "").strip().lower(); role = data.get("role", "data_scientist")
    if "@" not in email or role not in dict(Membership.ROLES): return JsonResponse({"detail": "Provide a valid email and project role."}, status=400)
    invite, _ = Invitation.objects.update_or_create(project=project, email=email, status="pending", defaults={"role": role, "invited_by": request.user})
    try:
        recipient = User.objects.get(email=email)
        notification = Notification.objects.create(user=recipient, message=f"You were invited to {project.name} as {role.replace('_', ' ').title()}.")
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        async_to_sync(get_channel_layer().group_send)(f"user_{recipient.id}", {"type": "notify", "message": notification.message})
    except User.DoesNotExist:
        pass  # Invitation stays available for the recipient after they create an account.
    except ImportError:
        pass  # HTTP invitations still work if optional Channels is not installed locally.
    return JsonResponse({"id": str(invite.id), "email": invite.email, "role": invite.role, "status": invite.status}, status=201)

@require_GET
@login_required
def my_invitations(request):
    items = Invitation.objects.filter(email=request.user.email, status="pending").select_related("project")
    return JsonResponse({"invitations": [{"id": str(x.id), "project": x.project.name, "project_id": str(x.project_id), "role": x.role} for x in items]})

@require_POST
@login_required
def respond_invitation(request, invitation_id):
    data = payload(request)
    if not data or data.get("action") not in ["accept", "decline"]: return JsonResponse({"detail": "Action must be accept or decline."}, status=400)
    invitation = get_object_or_404(Invitation, id=invitation_id, email=request.user.email, status="pending")
    with transaction.atomic():
        invitation.status = "accepted" if data["action"] == "accept" else "declined"; invitation.save(update_fields=["status"])
        if invitation.status == "accepted": Membership.objects.update_or_create(project=invitation.project, user=request.user, defaults={"role": invitation.role})
    return JsonResponse({"status": invitation.status, "project_id": str(invitation.project_id)})

@login_required
def home(request):
    projects = Project.objects.filter(Q(owner=request.user) | Q(memberships__user=request.user)).distinct()
    selected = projects.filter(id=request.GET.get("project")).first() if request.GET.get("project") else projects.first()
    role = "Owner" if selected and selected.owner_id == request.user.id else (selected.memberships.filter(user=request.user).first().get_role_display() if selected and selected.memberships.filter(user=request.user).exists() else "")
    return render(request, "home.html", {"projects": projects, "selected": selected, "project_role": role})

@login_required
def account_page(request):
    if request.method == "POST":
        form = AvatarForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid(): form.save(); return redirect("account")
    else: form = AvatarForm(instance=request.user)
    return render(request, "account.html", {"form": form})

def signup_page(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(); Project.objects.create(name="My first project", owner=user); login(request, user); return redirect("home")
    else: form = SignUpForm()
    return render(request, "form.html", {"form": form, "title": "Create your InsightFlow account", "button": "Sign up"})

def login_page(request):
    error = ""
    if request.method == "POST":
        user = authenticate(request, username=request.POST.get("email", "").lower(), password=request.POST.get("password"))
        if user: login(request, user); return redirect("home")
        error = "Email or password is incorrect."
    return render(request, "login.html", {"error": error})

@login_required
def create_project_page(request):
    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False); project.owner = request.user; project.save(); Membership.objects.create(project=project, user=request.user, role="moderator"); return redirect("home")
    return render(request, "form.html", {"form": form, "title": "Create a project", "button": "Create project"})
