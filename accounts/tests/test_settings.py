"""
Tests: account settings (password change, email change, account deletion).

Covers:
- Password change requires correct code (wrong code → no change)
- Password change: new password must match confirmation
- Delete account: requires correct code + typing DELETE
- Delete: last administrator cannot delete their account
- Email change: requires both codes (old + new email)
- All sessions invalidated after a sensitive change
- Code expiry (10 min)
- Max 5 attempts lockout
- 60-second rate limit on requests
- Wrong code never modifies the account
"""
import datetime

from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.models import Session
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from accounts.models import Role, SecurityRequest, User
from accounts.sessions import invalidate_all_sessions

from .base import AccountsTestCase


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class SettingsTests(AccountsTestCase):

    # ------------------------------------------------------------------
    # Password change
    # ------------------------------------------------------------------
    def test_password_change_wrong_code_no_change(self):
        user = self.make_user(email="pwchange@example.com")
        self.sign_in("pwchange@example.com")
        self.make_security_request(user, action="password", code="123456")
        old_hash = User.objects.get(pk=user.pk).password
        self.client.post("/settings/verify", {
            "action": "password",
            "code": "000000",  # wrong
            "new_password": "newpassword456!",
            "confirm_password": "newpassword456!",
        })
        user.refresh_from_db()
        self.assertEqual(user.password, old_hash, "Password must not change on wrong code")

    def test_password_change_correct_code(self):
        user = self.make_user(email="pwok@example.com")
        self.sign_in("pwok@example.com")
        self.make_security_request(user, action="password", code="654321")
        response = self.client.post("/settings/verify", {
            "action": "password",
            "code": "654321",
            "new_password": "newpassword456!",
            "confirm_password": "newpassword456!",
        }, follow=True)
        self.assertRedirects(response, "/login")
        user.refresh_from_db()
        self.assertTrue(user.check_password("newpassword456!"))

    def test_password_mismatch_on_verify_rejected(self):
        user = self.make_user(email="pwmatch@example.com")
        self.sign_in("pwmatch@example.com")
        self.make_security_request(user, action="password", code="123456")
        old_hash = User.objects.get(pk=user.pk).password
        self.client.post("/settings/verify", {
            "action": "password",
            "code": "123456",
            "new_password": "newpassword456!",
            "confirm_password": "DIFFERENT!",
        })
        user.refresh_from_db()
        self.assertEqual(user.password, old_hash)

    # ------------------------------------------------------------------
    # Account deletion
    # ------------------------------------------------------------------
    def test_delete_requires_DELETE_confirmation(self):
        user = self.make_user(email="del@example.com")
        self.sign_in("del@example.com")
        self.make_security_request(user, action="delete", code="123456")
        self.client.post("/settings/verify", {
            "action": "delete",
            "code": "123456",
            "delete_confirmation": "NOPE",  # wrong confirmation
        })
        self.assertTrue(User.objects.filter(pk=user.pk).exists(), "Account must not be deleted without DELETE")

    def test_delete_correct_code_and_confirmation(self):
        user = self.make_user(email="del2@example.com", role=Role.DATA_SCIENTIST)
        self.sign_in("del2@example.com")
        self.make_security_request(user, action="delete", code="123456")
        response = self.client.post("/settings/verify", {
            "action": "delete",
            "code": "123456",
            "delete_confirmation": "DELETE",
        }, follow=True)
        self.assertFalse(User.objects.filter(email="del2@example.com").exists(), "Account should be deleted")
        self.assertRedirects(response, "/login")

    def test_last_admin_cannot_delete(self):
        admin = self.make_user(email="lastadmin@example.com", role=Role.ADMINISTRATOR)
        self.sign_in("lastadmin@example.com")
        # Try to initiate deletion (blocked at request step)
        response = self.client.post("/settings/request", {
            "action": "delete",
            "current_password": "validpassword123!",
        }, follow=True)
        content = response.content.decode()
        self.assertIn("Assign another administrator", content)
        self.assertTrue(User.objects.filter(pk=admin.pk).exists())

    def test_last_admin_delete_blocked_at_verify_too(self):
        """Even if a SecurityRequest exists, last admin is blocked at verify."""
        admin = self.make_user(email="lastadmin2@example.com", role=Role.ADMINISTRATOR)
        self.sign_in("lastadmin2@example.com")
        self.make_security_request(admin, action="delete", code="123456")
        self.client.post("/settings/verify", {
            "action": "delete",
            "code": "123456",
            "delete_confirmation": "DELETE",
        })
        self.assertTrue(User.objects.filter(pk=admin.pk).exists())

    # ------------------------------------------------------------------
    # Email change
    # ------------------------------------------------------------------
    def test_email_change_requires_both_codes(self):
        user = self.make_user(email="emailchange@example.com")
        self.sign_in("emailchange@example.com")
        self.make_security_request(
            user, action="email",
            new_email="newemail@example.com",
            code="111111",
            new_email_code="222222",
        )
        # Submit only the current-email code (missing new_email_code)
        self.client.post("/settings/verify", {
            "action": "email",
            "code": "111111",
            "new_email_code": "",  # missing
        })
        user.refresh_from_db()
        self.assertEqual(user.email, "emailchange@example.com", "Email must not change without both codes")

    def test_email_change_both_correct_codes(self):
        user = self.make_user(email="emailok@example.com")
        self.sign_in("emailok@example.com")
        self.make_security_request(
            user, action="email",
            new_email="oknewemail@example.com",
            code="111111",
            new_email_code="222222",
        )
        response = self.client.post("/settings/verify", {
            "action": "email",
            "code": "111111",
            "new_email_code": "222222",
        }, follow=True)
        self.assertRedirects(response, "/login")
        user.refresh_from_db()
        self.assertEqual(user.email, "oknewemail@example.com")

    def test_email_change_wrong_new_email_code(self):
        user = self.make_user(email="emailwrong@example.com")
        self.sign_in("emailwrong@example.com")
        self.make_security_request(
            user, action="email",
            new_email="wrongnew@example.com",
            code="111111",
            new_email_code="222222",
        )
        self.client.post("/settings/verify", {
            "action": "email",
            "code": "111111",
            "new_email_code": "000000",  # wrong
        })
        user.refresh_from_db()
        self.assertEqual(user.email, "emailwrong@example.com")

    # ------------------------------------------------------------------
    # Session invalidation
    # ------------------------------------------------------------------
    def test_all_sessions_invalidated_after_password_change(self):
        user = self.make_user(email="sessiontest@example.com")
        self.sign_in("sessiontest@example.com")
        self.assertIn(SESSION_KEY, self.client.session)
        self.make_security_request(user, action="password", code="123456")
        self.client.post("/settings/verify", {
            "action": "password",
            "code": "123456",
            "new_password": "newpassword456!",
            "confirm_password": "newpassword456!",
        })
        # After the change, the session should be gone → redirected to /login
        self.assertNotIn(SESSION_KEY, self.client.session)

    # ------------------------------------------------------------------
    # Code expiry
    # ------------------------------------------------------------------
    def test_expired_code_rejected(self):
        user = self.make_user(email="expired@example.com")
        self.sign_in("expired@example.com")
        sr = self.make_security_request(user, action="password", code="123456")
        # Artificially age the request to 11 minutes ago
        sr.created_at = timezone.now() - datetime.timedelta(minutes=11)
        sr.save(update_fields=["created_at"])
        old_hash = User.objects.get(pk=user.pk).password
        self.client.post("/settings/verify", {
            "action": "password",
            "code": "123456",
            "new_password": "newpassword456!",
            "confirm_password": "newpassword456!",
        })
        user.refresh_from_db()
        self.assertEqual(user.password, old_hash, "Expired code must not change the account")

    # ------------------------------------------------------------------
    # Max attempts lockout
    # ------------------------------------------------------------------
    def test_max_attempts_lockout(self):
        user = self.make_user(email="lockout@example.com")
        self.sign_in("lockout@example.com")
        sr = self.make_security_request(user, action="password", code="123456")
        sr.attempts = 5
        sr.save(update_fields=["attempts"])
        old_hash = User.objects.get(pk=user.pk).password
        # Even with correct code, locked out
        self.client.post("/settings/verify", {
            "action": "password",
            "code": "123456",
            "new_password": "newpassword456!",
            "confirm_password": "newpassword456!",
        })
        user.refresh_from_db()
        self.assertEqual(user.password, old_hash, "Locked-out request must not change account")

    # ------------------------------------------------------------------
    # 60-second rate limit
    # ------------------------------------------------------------------
    def test_60_second_rate_limit_on_request(self):
        user = self.make_user(email="ratelimit@example.com")
        self.sign_in("ratelimit@example.com")
        # Create an existing recent request
        sr = self.make_security_request(user, action="password", code="123456")
        # Immediately try another request (within 60s)
        response = self.client.post("/settings/request", {
            "action": "password",
            "current_password": "validpassword123!",
            "new_password": "anotherpassword123!",
            "confirm_password": "anotherpassword123!",
        }, follow=True)
        content = response.content.decode()
        self.assertIn("wait", content.lower(), "Rate limit message expected")

    # ------------------------------------------------------------------
    # Wrong code never modifies the account (combined check)
    # ------------------------------------------------------------------
    def test_wrong_code_never_modifies_account(self):
        user = self.make_user(email="nochange@example.com")
        self.sign_in("nochange@example.com")
        original_email = user.email
        original_pw_hash = user.password
        # Try password change with wrong code
        self.make_security_request(user, action="password", code="123456")
        self.client.post("/settings/verify", {
            "action": "password",
            "code": "000000",
            "new_password": "newpassword456!",
            "confirm_password": "newpassword456!",
        })
        user.refresh_from_db()
        self.assertEqual(user.email, original_email)
        self.assertEqual(user.password, original_pw_hash)
