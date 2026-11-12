"""
Tests for management command: promote_admin.

Covers:
- Promotes existing verified user to administrator
- Errors if user does not exist
- Errors if user is not verified (is_active=False)
- Warns if user is already an administrator
"""
from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from accounts.models import Role, User
from .base import AccountsTestCase


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PromoteAdminCommandTests(AccountsTestCase):

    def test_promote_verified_user_success(self):
        user = self.make_user(email="scientist@example.com", role=Role.DATA_SCIENTIST, active=True)
        out = StringIO()
        call_command("promote_admin", "scientist@example.com", stdout=out)
        user.refresh_from_db()
        self.assertEqual(user.role, Role.ADMINISTRATOR)
        self.assertIn("Administrator role assigned", out.getvalue())

    def test_promote_case_insensitive(self):
        user = self.make_user(email="case@example.com", role=Role.DATA_SCIENTIST, active=True)
        out = StringIO()
        call_command("promote_admin", "CaSe@ExAmPlE.cOm", stdout=out)
        user.refresh_from_db()
        self.assertEqual(user.role, Role.ADMINISTRATOR)

    def test_promote_nonexistent_user_fails(self):
        with self.assertRaises(CommandError) as ctx:
            call_command("promote_admin", "nonexistent@example.com")
        self.assertIn("No account found", str(ctx.exception))

    def test_promote_unverified_user_fails(self):
        self.make_user(email="unverified@example.com", role=Role.DATA_SCIENTIST, active=False)
        with self.assertRaises(CommandError) as ctx:
            call_command("promote_admin", "unverified@example.com")
        self.assertIn("has not been verified", str(ctx.exception))

    def test_promote_already_admin_warns(self):
        self.make_user(email="alreadyadmin@example.com", role=Role.ADMINISTRATOR, active=True)
        out = StringIO()
        call_command("promote_admin", "alreadyadmin@example.com", stdout=out)
        self.assertIn("already an administrator", out.getvalue())
