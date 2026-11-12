"""
Accounts models.

User   — custom AbstractUser with email login and role field.
SecurityRequest — pending account change (email | password | delete).
"""
import hashlib
import secrets

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


# ---------------------------------------------------------------------------
# Role constants
# ---------------------------------------------------------------------------
class Role(models.TextChoices):
    DATA_SCIENTIST = "data_scientist", "Data scientist"
    REVIEWER = "reviewer", "Reviewer"
    ADMINISTRATOR = "administrator", "Administrator"


# ---------------------------------------------------------------------------
# User manager
# ---------------------------------------------------------------------------
class UserManager(BaseUserManager):
    """Manager that uses email as the unique identifier (no username)."""

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", Role.ADMINISTRATOR)
        return self._create_user(email, password, **extra)


# ---------------------------------------------------------------------------
# Custom User
# ---------------------------------------------------------------------------
class User(AbstractUser):
    """Login by email; roles drive access control."""

    username = None  # type: ignore[assignment]
    email = models.EmailField("email address", unique=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.DATA_SCIENTIST,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # createsuperuser only asks for email + password

    objects = UserManager()  # type: ignore[assignment]

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self):
        return self.email


# ---------------------------------------------------------------------------
# SecurityRequest
# ---------------------------------------------------------------------------
class SecurityRequest(models.Model):
    """
    One-at-a-time pending account change per user.
    Codes are stored as SHA-256 hex digests, never plaintext.
    """

    ACTION_EMAIL = "email"
    ACTION_PASSWORD = "password"
    ACTION_DELETE = "delete"
    ACTION_CHOICES = [
        (ACTION_EMAIL, "Email change"),
        (ACTION_PASSWORD, "Password change"),
        (ACTION_DELETE, "Account deletion"),
    ]

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="security_request",
    )
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    new_email = models.EmailField(blank=True, null=True)

    # Hashed 6-digit codes (SHA-256 hex).
    # code_hash — code sent to the current email address.
    # new_email_code_hash — code sent to the new email address (email change only).
    code_hash = models.CharField(max_length=64)
    new_email_code_hash = models.CharField(max_length=64, blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    attempts = models.PositiveSmallIntegerField(default=0)
    # For email-change two-step: has the old-email code been verified?
    old_verified = models.BooleanField(default=False)

    class Meta:
        verbose_name = "security request"

    def __str__(self):
        return f"{self.user.email} – {self.action}"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def hash_code(code: str) -> str:
        """Return SHA-256 hex digest of a code string."""
        return hashlib.sha256(code.encode()).hexdigest()

    @staticmethod
    def generate_code() -> str:
        """Return a cryptographically random 6-digit string."""
        return str(secrets.randbelow(900000) + 100000)

    def code_matches(self, code: str) -> bool:
        return secrets.compare_digest(self.code_hash, self.hash_code(code))

    def new_email_code_matches(self, code: str) -> bool:
        if not self.new_email_code_hash:
            return False
        return secrets.compare_digest(self.new_email_code_hash, self.hash_code(code))

    def is_expired(self) -> bool:
        return (timezone.now() - self.created_at).total_seconds() > 600  # 10 min

    def is_locked(self) -> bool:
        return self.attempts >= 5
