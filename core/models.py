import uuid
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

class UserManager(BaseUserManager):
    use_in_migrations = True
    def _create_user(self, email, password, **extra_fields):
        if not email: raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password); user.save(using=self._db); return user
    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False); extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True); extra_fields.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra_fields)

class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=24, default="data_scientist", choices=[("data_scientist", "Data scientist"), ("reviewer", "Reviewer"), ("administrator", "Platform administrator")])
    avatar = models.ImageField(upload_to="avatars/%Y/%m/", blank=True, null=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()
    def __str__(self): return self.email

class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=80)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="owned_projects")
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.name

class Membership(models.Model):
    ROLES = [("moderator", "Moderator"), ("data_scientist", "Data scientist"), ("reviewer", "Reviewer")]
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=24, choices=ROLES, default="data_scientist")
    joined_at = models.DateTimeField(auto_now_add=True)
    class Meta: unique_together = [("project", "user")]

class Invitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(max_length=24, choices=Membership.ROLES)
    invited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=16, default="pending", choices=[("pending", "Pending"), ("accepted", "Accepted"), ("declined", "Declined"), ("revoked", "Revoked")])
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"{self.email} → {self.project.name}"

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField(max_length=240)
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

class Dataset(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="datasets")
    uploaded_by = models.ForeignKey(User, on_delete=models.PROTECT)
    name = models.CharField(max_length=255)
    csv_file = models.FileField(upload_to="datasets/%Y/%m/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
