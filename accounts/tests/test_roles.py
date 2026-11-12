"""
Tests: role-based access control.

Covers:
- data_scientist: 200 on /workspaces/preparation, 403 on /workspaces/review and /manage/accounts
- reviewer: 200 on /workspaces/review, 403 on /workspaces/preparation and /manage/accounts
- administrator: 200 on /manage/accounts, 403 on both workspaces
- Anonymous: 302 → /login on all protected pages
- Admin cannot demote themselves (self-role-change rejected)
- Role change for another user succeeds
- Non-admin cannot POST to change_role endpoint
"""
from django.test import override_settings

from accounts.models import Role, User

from .base import AccountsTestCase


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RoleAccessTests(AccountsTestCase):

    def _check_access(self, role, expected):
        """Login as *role* and assert expected status codes for three routes."""
        email = f"{role}@example.com"
        self.make_user(email=email, role=role)
        self.sign_in(email)
        prep_status, review_status, admin_status = expected
        self.assertEqual(self.client.get("/workspaces/preparation").status_code, prep_status,
                         f"prep for {role}")
        self.assertEqual(self.client.get("/workspaces/review").status_code, review_status,
                         f"review for {role}")
        self.assertEqual(self.client.get("/manage/accounts").status_code, admin_status,
                         f"admin for {role}")
        self.client.post("/logout")

    def test_data_scientist_access(self):
        self._check_access(Role.DATA_SCIENTIST, (200, 403, 403))

    def test_reviewer_access(self):
        self._check_access(Role.REVIEWER, (403, 200, 403))

    def test_administrator_access(self):
        self._check_access(Role.ADMINISTRATOR, (403, 403, 200))

    def test_anonymous_gets_redirect(self):
        for path in ["/workspaces/preparation", "/workspaces/review", "/manage/accounts"]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302, f"Anonymous {path} should redirect")
            self.assertIn("/login", response["Location"])

    def test_admin_cannot_demote_themselves(self):
        admin = self.make_user(email="selfdemote@example.com", role=Role.ADMINISTRATOR)
        self.sign_in("selfdemote@example.com")
        response = self.client.post(
            f"/manage/accounts/{admin.pk}/role",
            {"role": Role.REVIEWER},
            follow=True,
        )
        admin.refresh_from_db()
        self.assertEqual(admin.role, Role.ADMINISTRATOR, "Admin role must not change to reviewer via self-demotion")
        content = response.content.decode()
        self.assertIn("Ask another administrator", content)

    def test_admin_can_change_other_user_role(self):
        admin = self.make_user(email="changer@example.com", role=Role.ADMINISTRATOR)
        target = self.make_user(email="target@example.com", role=Role.DATA_SCIENTIST)
        self.sign_in("changer@example.com")
        self.client.post(f"/manage/accounts/{target.pk}/role", {"role": Role.REVIEWER})
        target.refresh_from_db()
        self.assertEqual(target.role, Role.REVIEWER)

    def test_non_admin_cannot_change_role(self):
        self.make_user(email="notadmin@example.com", role=Role.DATA_SCIENTIST)
        target = self.make_user(email="victim@example.com", role=Role.DATA_SCIENTIST)
        self.sign_in("notadmin@example.com")
        response = self.client.post(
            f"/manage/accounts/{target.pk}/role", {"role": Role.ADMINISTRATOR}
        )
        self.assertEqual(response.status_code, 403)
        target.refresh_from_db()
        self.assertEqual(target.role, Role.DATA_SCIENTIST)

    def test_all_roles_can_be_assigned(self):
        admin = self.make_user(email="roler@example.com", role=Role.ADMINISTRATOR)
        target = self.make_user(email="rolee@example.com", role=Role.DATA_SCIENTIST)
        self.sign_in("roler@example.com")
        for role in [Role.REVIEWER, Role.ADMINISTRATOR, Role.DATA_SCIENTIST]:
            self.client.post(f"/manage/accounts/{target.pk}/role", {"role": role})
            target.refresh_from_db()
            self.assertEqual(target.role, role, f"Role should be {role}")
