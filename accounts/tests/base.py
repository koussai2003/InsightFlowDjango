"""
Shared test helpers and a base TestCase for accounts tests.
All tests use the in-memory email backend and Django's test client.
"""
from django.contrib.auth import SESSION_KEY
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import Role, SecurityRequest, User


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AccountsTestCase(TestCase):
    """Base class: locmem email backend + helpers."""

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------
    def make_user(self, email="user@example.com", password="validpassword123!", role=Role.DATA_SCIENTIST, active=True):
        user = User.objects.create_user(email=email, password=password, role=role)
        user.is_active = active
        user.save()
        return user

    def make_inactive_user(self, email="new@example.com", password="validpassword123!"):
        return self.make_user(email=email, password=password, active=False)

    def make_security_request(self, user, action="password", new_email=None, code="123456", new_email_code=None):
        sr, _ = SecurityRequest.objects.update_or_create(
            user=user,
            defaults={
                "action": action,
                "new_email": new_email,
                "code_hash": SecurityRequest.hash_code(code),
                "new_email_code_hash": SecurityRequest.hash_code(new_email_code) if new_email_code else None,
                "created_at": timezone.now(),
                "attempts": 0,
                "old_verified": False,
            },
        )
        return sr

    # ------------------------------------------------------------------
    # Login / session helpers
    # ------------------------------------------------------------------
    def sign_in(self, email, password="validpassword123!"):
        return self.client.post("/login", {"email": email, "password": password}, follow=True)

    def is_authenticated(self):
        return SESSION_KEY in self.client.session
