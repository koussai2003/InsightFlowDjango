"""
Tests: registration and email verification.

Covers:
- Signup requires email verification; no session before verification
- Wrong verification code rejected
- Correct code activates account
- Password confirmation mismatch rejected at registration
- Role injection via form input rejected
- Resend rate limit enforced
"""
from django.contrib.auth import SESSION_KEY
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from accounts.models import Role, SecurityRequest, User

from .base import AccountsTestCase


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RegistrationTests(AccountsTestCase):

    def test_register_creates_inactive_user(self):
        response = self.client.post("/register", {
            "email": "alice@example.com",
            "password": "strongpassword123!",
            "confirm_password": "strongpassword123!",
        })
        # Redirect to verify page
        self.assertRedirects(response, "/verify?email=alice@example.com", fetch_redirect_response=False)
        user = User.objects.get(email="alice@example.com")
        self.assertFalse(user.is_active, "New user must be inactive until email is verified")
        self.assertEqual(user.role, Role.DATA_SCIENTIST, "New users always get data_scientist role")

    def test_no_session_before_verification(self):
        self.client.post("/register", {
            "email": "bob@example.com",
            "password": "strongpassword123!",
            "confirm_password": "strongpassword123!",
        })
        # Attempting to log in with an unverified account
        self.client.post("/login", {"email": "bob@example.com", "password": "strongpassword123!"})
        self.assertNotIn(SESSION_KEY, self.client.session, "Session must not exist before email verification")

    def test_verification_email_sent(self):
        self.client.post("/register", {
            "email": "charlie@example.com",
            "password": "strongpassword123!",
            "confirm_password": "strongpassword123!",
        })
        self.assertEqual(len(mail.outbox), 1, "One verification email should be sent")
        self.assertIn("charlie@example.com", mail.outbox[0].to)

    def test_wrong_code_rejected(self):
        self.client.post("/register", {
            "email": "dave@example.com",
            "password": "strongpassword123!",
            "confirm_password": "strongpassword123!",
        })
        # Submit wrong code
        response = self.client.post("/verify", {
            "email": "dave@example.com",
            "code": "000000",
        })
        self.assertEqual(response.status_code, 200, "Wrong code should re-render verify page")
        user = User.objects.get(email="dave@example.com")
        self.assertFalse(user.is_active, "Account must remain inactive after wrong code")

    def test_correct_code_activates_account(self):
        self.client.post("/register", {
            "email": "eve@example.com",
            "password": "strongpassword123!",
            "confirm_password": "strongpassword123!",
        })
        user = User.objects.get(email="eve@example.com")
        sr = SecurityRequest.objects.get(user=user)
        # Reconstruct the real code from the email
        real_code = None
        for line in mail.outbox[0].body.split("\n"):
            line = line.strip()
            if line.isdigit() and len(line) == 6:
                real_code = line
                break
        self.assertIsNotNone(real_code, "Code should be in the email body")
        response = self.client.post("/verify", {
            "email": "eve@example.com",
            "code": real_code,
        }, follow=True)
        user.refresh_from_db()
        self.assertTrue(user.is_active, "Account should be active after correct code")
        self.assertRedirects(response, "/login")

    def test_password_mismatch_rejected(self):
        response = self.client.post("/register", {
            "email": "frank@example.com",
            "password": "strongpassword123!",
            "confirm_password": "differentpassword456!",
        })
        self.assertEqual(response.status_code, 200, "Mismatch should re-render form")
        self.assertFalse(User.objects.filter(email="frank@example.com").exists())

    def test_password_too_short_rejected(self):
        response = self.client.post("/register", {
            "email": "grace@example.com",
            "password": "short",
            "confirm_password": "short",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="grace@example.com").exists())

    def test_role_injection_rejected(self):
        """POSTing a role field along with registration must be ignored."""
        self.client.post("/register", {
            "email": "hacker@example.com",
            "password": "strongpassword123!",
            "confirm_password": "strongpassword123!",
            "role": "administrator",  # injected field — must be ignored
        })
        if User.objects.filter(email="hacker@example.com").exists():
            user = User.objects.get(email="hacker@example.com")
            self.assertEqual(user.role, Role.DATA_SCIENTIST, "Role injection must be blocked")

    def test_duplicate_email_rejected(self):
        self.make_user(email="existing@example.com")
        response = self.client.post("/register", {
            "email": "existing@example.com",
            "password": "strongpassword123!",
            "confirm_password": "strongpassword123!",
        })
        self.assertEqual(response.status_code, 200)

    def test_resend_rate_limit(self):
        self.client.post("/register", {
            "email": "iris@example.com",
            "password": "strongpassword123!",
            "confirm_password": "strongpassword123!",
        })
        # Immediate resend should be rate-limited
        response = self.client.post("/verify/resend", {"email": "iris@example.com"}, follow=True)
        # Should show a warning (rate limit message)
        messages_text = " ".join(str(m) for m in response.context["messages"])
        self.assertIn("wait", messages_text.lower())
