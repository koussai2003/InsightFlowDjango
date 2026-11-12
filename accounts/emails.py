"""
Email helpers for accounts.

send_verification_email   — registration email (link + 6-digit code).
send_security_code        — 6-digit code for account changes.
send_new_email_code       — 6-digit code sent to the prospective new email.
"""
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def _uid_b64(user):
    return urlsafe_base64_encode(force_bytes(user.pk))


def send_verification_email(user, code: str, request=None):
    """Send registration email with a verification link and a 6-digit code."""
    uid = _uid_b64(user)
    token = default_token_generator.make_token(user)
    if request:
        base = request.build_absolute_uri("/")
    else:
        from django.conf import settings

        base = getattr(settings, "APP_PUBLIC_URL", "http://localhost:8000/")
    link = f"{base.rstrip('/')}/verify/{uid}/{token}/"
    send_mail(
        subject="Verify your InsightFlow account",
        message=(
            f"Hello,\n\n"
            f"Click the link below to verify your email address and activate your account:\n"
            f"{link}\n\n"
            f"Or enter this 6-digit code on the verification page:\n{code}\n\n"
            f"The code expires in 10 minutes.\n\n"
            f"If you did not create an InsightFlow account, ignore this email.\n"
        ),
        from_email=None,  # uses DEFAULT_FROM_EMAIL
        recipient_list=[user.email],
        fail_silently=False,
    )


def send_security_code(user, code: str, action: str):
    """Send a 6-digit security code to the user's current email."""
    action_labels = {
        "email": "email address change",
        "password": "password change",
        "delete": "account deletion",
    }
    label = action_labels.get(action, "account change")
    send_mail(
        subject=f"InsightFlow – verification code for {label}",
        message=(
            f"Hello,\n\n"
            f"Your InsightFlow verification code for {label} is:\n\n"
            f"    {code}\n\n"
            f"This code expires in 10 minutes. Maximum 5 attempts allowed.\n"
            f"If you did not request this, change your password immediately.\n"
        ),
        from_email=None,
        recipient_list=[user.email],
        fail_silently=False,
    )


def send_new_email_code(new_email: str, code: str):
    """Send a 6-digit code to the prospective new email address."""
    send_mail(
        subject="InsightFlow – verify your new email address",
        message=(
            f"Hello,\n\n"
            f"This code confirms that {new_email} will become your new InsightFlow email:\n\n"
            f"    {code}\n\n"
            f"This code expires in 10 minutes.\n"
            f"If you did not request this, ignore this email.\n"
        ),
        from_email=None,
        recipient_list=[new_email],
        fail_silently=False,
    )
