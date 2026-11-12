import uuid
from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone


class ProjectRole(models.TextChoices):
    OWNER = "owner", "Owner"
    MODERATOR = "moderator", "Moderator"
    DATA_SCIENTIST = "data_scientist", "Data Scientist"
    REVIEWER = "reviewer", "Reviewer"


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=80)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        related_name="owned_projects",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def user_role(self, user):
        if self.owner_id == user.id:
            return ProjectRole.OWNER
        membership = self.members.filter(user=user).first()
        return membership.role if membership else None


class ProjectMember(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="members",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=[
            (ProjectRole.MODERATOR, "Moderator"),
            (ProjectRole.DATA_SCIENTIST, "Data Scientist"),
            (ProjectRole.REVIEWER, "Reviewer"),
        ],
    )

    class Meta:
        unique_together = ("project", "user")

    def __str__(self):
        return f"{self.user.email} in {self.project.name} ({self.role})"


def default_invitation_expiry():
    return timezone.now() + timedelta(days=7)


class ProjectInvitation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        REVOKED = "revoked", "Revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    email = models.EmailField()
    role = models.CharField(
        max_length=20,
        choices=[
            (ProjectRole.MODERATOR, "Moderator"),
            (ProjectRole.DATA_SCIENTIST, "Data Scientist"),
            (ProjectRole.REVIEWER, "Reviewer"),
        ],
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_invitations",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(default=default_invitation_expiry)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invite for {self.email} to {self.project.name} ({self.status})"

    def is_expired(self):
        return timezone.now() > self.expires_at


class ProjectDataset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="datasets",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to="datasets/", blank=True, null=True)
    row_count = models.IntegerField(default=0)
    column_count = models.IntegerField(default=0)
    column_names = models.JSONField(default=list)
    preview_rows = models.JSONField(default=list)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]


class ProjectQuestion(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    question = models.TextField()
    dataset_name = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]
