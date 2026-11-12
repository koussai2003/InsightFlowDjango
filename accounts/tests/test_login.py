"""
Tests: login and logout.

Covers:
- Correct credentials + verified user → session created
- Unverified user blocked with clear message
- Wrong password → 401-equivalent (re-renders form)
- Session expires within 1 hour
- Logout flushes session
- Anonymous access to protected pages → redirect to /login
"""
from django.contrib.auth import SESSION_KEY
from django.test import override_settings

from accounts.models import Role

from .base import AccountsTestCase


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class LoginTests(AccountsTestCase):

    def test_login_success(self):
        user = self.make_user(email="login@example.com")
        response = self.sign_in("login@example.com")
        self.assertIn(SESSION_KEY, self.client.session, "Session must be created after login")

    def test_login_unverified_blocked(self):
        self.make_user(email="unverified@example.com", active=False)
        self.sign_in("unverified@example.com")
        self.assertNotIn(SESSION_KEY, self.client.session, "No session for unverified user")

    def test_login_unverified_message(self):
        self.make_user(email="unverified2@example.com", active=False)
        response = self.client.post("/login", {
            "email": "unverified2@example.com",
            "password": "validpassword123!",
        })
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Confirm your email", content)

    def test_login_wrong_password(self):
        self.make_user(email="wrongpw@example.com")
        response = self.client.post("/login", {
            "email": "wrongpw@example.com",
            "password": "wrongpassword999!",
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_login_nonexistent_user(self):
        response = self.client.post("/login", {
            "email": "ghost@example.com",
            "password": "doesntmatter123!",
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_logout_clears_session(self):
        self.make_user(email="logout@example.com")
        self.sign_in("logout@example.com")
        self.assertIn(SESSION_KEY, self.client.session)
        self.client.post("/logout")
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_anonymous_home_redirects_to_login(self):
        response = self.client.get("/")
        self.assertRedirects(response, "/login?next=/", fetch_redirect_response=False)

    def test_anonymous_workspace_redirects_to_login(self):
        response = self.client.get("/workspaces/preparation")
        self.assertRedirects(response, "/login?next=/workspaces/preparation", fetch_redirect_response=False)

    def test_session_expiry_set(self):
        self.make_user(email="expiry@example.com")
        self.sign_in("expiry@example.com")
        # Django's SESSION_COOKIE_AGE is 3600; get_expiry_age() returns that
        expiry = self.client.session.get_expiry_age()
        self.assertLessEqual(expiry, 3600)
        self.assertGreater(expiry, 0)

    def test_login_redirects_data_scientist_to_preparation(self):
        self.make_user(email="ds@example.com", role=Role.DATA_SCIENTIST)
        response = self.sign_in("ds@example.com")
        self.assertRedirects(response, "/workspaces/preparation")

    def test_login_redirects_reviewer_to_review(self):
        self.make_user(email="rev@example.com", role=Role.REVIEWER)
        response = self.sign_in("rev@example.com")
        self.assertRedirects(response, "/workspaces/review")

    def test_login_redirects_admin_to_manage_accounts(self):
        self.make_user(email="adm@example.com", role=Role.ADMINISTRATOR)
        response = self.sign_in("adm@example.com")
        self.assertRedirects(response, "/manage/accounts")
