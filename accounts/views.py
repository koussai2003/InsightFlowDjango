"""
Accounts views.

URL map (see accounts/urls.py):
  /register                 register
  /verify/<uid>/<token>/    verify_link      (email link)
  /verify                   verify_code      (6-digit code form)
  /verify/resend            verify_resend
  /login                    login_view
  /logout                   logout_view
  /                         home
  /workspaces/preparation   workspace_preparation
  /workspaces/review        workspace_review
  /manage/accounts          manage_accounts
  /manage/accounts/<pk>/role  change_role
  /settings                 settings_view
  /settings/request         settings_request
  /settings/verify          settings_verify
"""
import logging

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_POST

from .decorators import role_required
from .emails import (
    send_new_email_code,
    send_security_code,
    send_verification_email,
)
from .forms import (
    LoginForm,
    RegistrationForm,
    RoleChangeForm,
    SecurityRequestForm,
    SecurityVerifyForm,
)
from .models import Role, SecurityRequest, User
from .sessions import invalidate_all_sessions

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _add_form_errors(request, form):
    """Push all form errors into the Django messages framework."""
    for field_errors in form.errors.values():
        for error in field_errors:
            messages.error(request, error)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]
        code = SecurityRequest.generate_code()
        user = User.objects.create_user(
            email=email,
            password=password,
            is_active=False,  # inactive until email verified
            role=Role.DATA_SCIENTIST,  # always; never from form input
        )
        # Store a SecurityRequest to hold the signup code hash.
        SecurityRequest.objects.create(
            user=user,
            action=SecurityRequest.ACTION_EMAIL,  # repurposed: signup verification
            code_hash=SecurityRequest.hash_code(code),
        )
        send_verification_email(user, code, request)
        messages.success(
            request,
            "Account created! Check your inbox to verify your email. "
            "You can also enter the 6-digit code from the email below.",
        )
        return redirect(f"/verify?email={email}")

    return render(request, "accounts/register.html", {"form": form})


# ---------------------------------------------------------------------------
# Email verification — link (GET)
# ---------------------------------------------------------------------------
def verify_link(request, uidb64, token):
    """Handle the signed link emailed after registration."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (ValueError, TypeError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save(update_fields=["is_active"])
        # Clean up the signup SecurityRequest if present.
        SecurityRequest.objects.filter(user=user).delete()
        messages.success(request, "Email verified! You can now sign in.")
        return redirect("login")

    messages.error(request, "The verification link is invalid or has expired. Request a new one.")
    return redirect(f"/verify?email=")


# ---------------------------------------------------------------------------
# Email verification — 6-digit code (GET / POST)
# ---------------------------------------------------------------------------
def verify_code(request):
    """Let a user submit the 6-digit code from their registration email."""
    if request.user.is_authenticated:
        return redirect("home")

    email = request.GET.get("email", "")

    if request.method == "POST":
        email = request.POST.get("email", "").lower().strip()
        code = request.POST.get("code", "").strip()

        try:
            user = User.objects.get(email=email, is_active=False)
            sr = SecurityRequest.objects.get(user=user)
        except (User.DoesNotExist, SecurityRequest.DoesNotExist):
            messages.error(request, "No pending verification found for this email.")
            return render(request, "accounts/verify.html", {"email": email})

        if sr.is_expired() or sr.is_locked():
            messages.error(request, "The code has expired or too many attempts were made. Request a new verification email.")
            return render(request, "accounts/verify.html", {"email": email})

        sr.attempts += 1
        sr.save(update_fields=["attempts"])

        if not sr.code_matches(code):
            remaining = max(0, 5 - sr.attempts)
            messages.error(request, f"Incorrect code. {remaining} attempt(s) remaining.")
            return render(request, "accounts/verify.html", {"email": email})

        user.is_active = True
        user.save(update_fields=["is_active"])
        sr.delete()
        messages.success(request, "Email verified! You can now sign in.")
        return redirect("login")

    return render(request, "accounts/verify.html", {"email": email})


# ---------------------------------------------------------------------------
# Resend verification email
# ---------------------------------------------------------------------------
@require_POST
def verify_resend(request):
    email = request.POST.get("email", "").lower().strip()
    try:
        user = User.objects.get(email=email, is_active=False)
        sr = SecurityRequest.objects.get(user=user)
    except (User.DoesNotExist, SecurityRequest.DoesNotExist):
        # Don't reveal whether the account exists.
        messages.info(request, "If that email is registered and unverified, a new code has been sent.")
        return redirect(f"/verify?email={email}")

    # 60-second rate limit on SecurityRequest.created_at
    elapsed = (timezone.now() - sr.created_at).total_seconds()
    if elapsed < 60:
        messages.warning(request, "Please wait a moment before requesting another email.")
        return redirect(f"/verify?email={email}")

    code = SecurityRequest.generate_code()
    sr.code_hash = SecurityRequest.hash_code(code)
    sr.created_at = timezone.now()
    sr.attempts = 0
    sr.save(update_fields=["code_hash", "created_at", "attempts"])
    send_verification_email(user, code, request)
    messages.info(request, "A new verification email has been sent.")
    return redirect(f"/verify?email={email}")


# ---------------------------------------------------------------------------
# Login / logout
# ---------------------------------------------------------------------------
def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = LoginForm(request.POST or None, request=request)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        request.session.set_expiry(3600)
        next_url = request.POST.get("next") or request.GET.get("next") or "/"
        return redirect(next_url)

    return render(request, "accounts/login.html", {"form": form})


@require_POST
@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


# ---------------------------------------------------------------------------
# Home — redirect by role
# ---------------------------------------------------------------------------
@login_required
def home(request):
    role = request.user.role
    if role == Role.ADMINISTRATOR:
        return redirect("manage_accounts")
    if role == Role.REVIEWER:
        return redirect("workspace_review")
    return redirect("workspace_preparation")


# ---------------------------------------------------------------------------
# Workspaces (placeholder pages)
# ---------------------------------------------------------------------------
@role_required(Role.DATA_SCIENTIST)
def workspace_preparation(request):
    return render(request, "workspaces/preparation.html")


@role_required(Role.REVIEWER)
def workspace_review(request):
    return render(request, "workspaces/review.html")


# ---------------------------------------------------------------------------
# Admin: account list + role change
# ---------------------------------------------------------------------------
@role_required(Role.ADMINISTRATOR)
def manage_accounts(request):
    users = User.objects.all().order_by("email")
    return render(request, "accounts/manage_accounts.html", {"users": users})


@require_POST
@role_required(Role.ADMINISTRATOR)
def change_role(request, pk):
    target = get_object_or_404(User, pk=pk)
    form = RoleChangeForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Invalid role selection.")
        return redirect("manage_accounts")

    new_role = form.cleaned_data["role"]

    if target == request.user and new_role != Role.ADMINISTRATOR:
        messages.error(request, "Ask another administrator to change your role.")
        return redirect("manage_accounts")

    target.role = new_role
    target.save(update_fields=["role"])
    messages.success(request, f"Role updated for {target.email}.")
    return redirect("manage_accounts")


# ---------------------------------------------------------------------------
# Account settings — landing page
# ---------------------------------------------------------------------------
@login_required
def settings_view(request):
    return render(request, "accounts/settings.html", {"user": request.user})


# ---------------------------------------------------------------------------
# Settings — step 1: request a change (send verification code)
# ---------------------------------------------------------------------------
@login_required
def settings_request(request):
    action = request.POST.get("action") if request.method == "POST" else request.GET.get("action", "")
    if action not in ("email", "password", "delete"):
        return redirect("settings")

    # Build form with the hidden action field pre-filled.
    initial = {"action": action}
    form = SecurityRequestForm(request.POST or None, initial=initial)

    if request.method == "POST" and form.is_valid():
        current_password = form.cleaned_data["current_password"]

        # Verify current password.
        if not request.user.check_password(current_password):
            messages.error(request, "Current password is incorrect.")
            return render(request, "accounts/settings_request.html", {"form": form, "action": action})

        # 60-second rate limit.
        try:
            existing = SecurityRequest.objects.get(user=request.user)
            elapsed = (timezone.now() - existing.created_at).total_seconds()
            if elapsed < 60:
                messages.warning(request, "Please wait one minute before requesting another code.")
                return render(request, "accounts/settings_request.html", {"form": form, "action": action})
        except SecurityRequest.DoesNotExist:
            pass

        # Last-admin guard for deletion.
        if action == "delete":
            if (
                request.user.role == Role.ADMINISTRATOR
                and User.objects.filter(role=Role.ADMINISTRATOR).count() <= 1
            ):
                messages.error(request, "Assign another administrator before deleting your account.")
                return render(request, "accounts/settings_request.html", {"form": form, "action": action})

        new_email = form.cleaned_data.get("new_email", "").lower() if action == "email" else None
        if new_email and new_email == request.user.email.lower():
            messages.error(request, "Enter a different email address.")
            return render(request, "accounts/settings_request.html", {"form": form, "action": action})

        # Generate code(s).
        code = SecurityRequest.generate_code()
        code_hash = SecurityRequest.hash_code(code)
        new_email_code = SecurityRequest.generate_code() if action == "email" else None
        new_email_code_hash = SecurityRequest.hash_code(new_email_code) if new_email_code else None

        # Upsert SecurityRequest.
        SecurityRequest.objects.update_or_create(
            user=request.user,
            defaults={
                "action": action,
                "new_email": new_email,
                "code_hash": code_hash,
                "new_email_code_hash": new_email_code_hash,
                "created_at": timezone.now(),
                "attempts": 0,
                "old_verified": False,
            },
        )

        # Send email(s).
        send_security_code(request.user, code, action)
        if action == "email" and new_email and new_email_code:
            send_new_email_code(new_email, new_email_code)

        label = {
            "email": "both your current and new email addresses",
            "password": "your current email",
            "delete": "your current email",
        }[action]
        messages.success(request, f"Verification code(s) sent to {label}. Enter them below within 10 minutes.")
        return redirect(f"/settings/verify?action={action}")

    return render(request, "accounts/settings_request.html", {"form": form, "action": action})


# ---------------------------------------------------------------------------
# Settings — step 2: verify the code and apply the change
# ---------------------------------------------------------------------------
@login_required
def settings_verify(request):
    action = request.POST.get("action") if request.method == "POST" else request.GET.get("action", "")
    if action not in ("email", "password", "delete"):
        return redirect("settings")

    form = SecurityVerifyForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            try:
                sr = SecurityRequest.objects.select_for_update().get(user=request.user)
            except SecurityRequest.DoesNotExist:
                messages.error(request, "No pending change found. Start again.")
                return redirect("settings")

            # Expiry / lockout check.
            if sr.is_expired():
                sr.delete()
                messages.error(request, "The verification code has expired. Start again.")
                return redirect("settings")

            if sr.is_locked():
                sr.delete()
                messages.error(request, "Too many incorrect attempts. Start again.")
                return redirect("settings")

            # Action-specific validations (before consuming an attempt).
            if sr.action == "delete":
                if form.cleaned_data.get("delete_confirmation") != "DELETE":
                    messages.error(request, 'Type DELETE (all caps) to confirm deletion.')
                    return render(request, "accounts/settings_verify.html", {"form": form, "action": action, "sr": sr})

            if sr.action == "password":
                pw = form.cleaned_data.get("new_password")
                confirm = form.cleaned_data.get("confirm_password")
                if not pw or pw != confirm:
                    messages.error(request, "New passwords must match.")
                    return render(request, "accounts/settings_verify.html", {"form": form, "action": action, "sr": sr})

            # Consume one attempt immediately (before code check).
            sr.attempts += 1
            sr.save(update_fields=["attempts"])

            # Verify code.
            code = form.cleaned_data["code"]
            if not sr.code_matches(code):
                remaining = max(0, 5 - sr.attempts)
                messages.error(request, f"Incorrect code. {remaining} attempt(s) remaining.")
                return render(request, "accounts/settings_verify.html", {"form": form, "action": action, "sr": sr})

            # Email change: requires both codes.
            if sr.action == "email":
                new_email_code = form.cleaned_data.get("new_email_code", "")
                if not new_email_code:
                    messages.error(request, "Enter both verification codes.")
                    return render(request, "accounts/settings_verify.html", {"form": form, "action": action, "sr": sr})
                if not sr.new_email_code_matches(new_email_code):
                    messages.error(request, "The new-email code is incorrect.")
                    return render(request, "accounts/settings_verify.html", {"form": form, "action": action, "sr": sr})

            # Last-admin guard for deletion (re-check inside transaction).
            if sr.action == "delete":
                if (
                    request.user.role == Role.ADMINISTRATOR
                    and User.objects.filter(role=Role.ADMINISTRATOR).count() <= 1
                ):
                    sr.delete()
                    messages.error(request, "Assign another administrator before deleting your account.")
                    return redirect("settings")

            # Apply the change.
            user = request.user
            if sr.action == "password":
                new_password = form.cleaned_data["new_password"]
                user.set_password(new_password)
                user.save()
            elif sr.action == "email":
                user.email = sr.new_email.lower()
                user.save(update_fields=["email"])
            elif sr.action == "delete":
                # Invalidate sessions first, then delete.
                invalidate_all_sessions(user)
                sr.delete()
                user.delete()
                logout(request)
                messages.success(request, "Your account has been permanently deleted.")
                return redirect("login")

            # For password / email: invalidate all sessions (including current).
            sr.delete()
            invalidate_all_sessions(user)
            logout(request)
            messages.success(request, "Account updated. Please sign in again.")
            return redirect("login")

    return render(request, "accounts/settings_verify.html", {"form": form, "action": action})
