"""
Accounts forms.

All passwords use Django's built-in validators (MinimumLengthValidator is set
to 12 characters in settings). Extra length checks are enforced here too so
that form validation errors are shown to the user before the validator runs.
"""
from django import forms
from django.contrib.auth import authenticate, password_validation
from django.core.exceptions import ValidationError

from .models import Role, User


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
class RegistrationForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    password = forms.CharField(
        label="Password",
        min_length=12,
        max_length=128,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Use at least 12 characters.",
    )
    confirm_password = forms.CharField(
        label="Confirm password",
        max_length=128,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already registered.")
        return email

    def clean_password(self):
        pw = self.cleaned_data["password"]
        # Run Django's configured password validators.
        password_validation.validate_password(pw)
        return pw

    def clean(self):
        cleaned = super().clean()
        pw = cleaned.get("password")
        confirm = cleaned.get("confirm_password")
        if pw and confirm and pw != confirm:
            self.add_error("confirm_password", "Passwords must match.")
        return cleaned


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
class LoginForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    password = forms.CharField(
        label="Password",
        max_length=128,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        self._user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get("email", "").lower().strip()
        password = cleaned.get("password", "")
        if email and password:
            user = authenticate(self.request, username=email, password=password)
            if user is None:
                # Distinguish unverified from wrong credentials.
                try:
                    candidate = User.objects.get(email=email)
                except User.DoesNotExist:
                    candidate = None
                if candidate and not candidate.is_active:
                    raise ValidationError(
                        "Confirm your email before signing in. "
                        "Check your inbox or resend the verification email."
                    )
                raise ValidationError("Incorrect email or password.")
            self._user = user
        return cleaned

    def get_user(self):
        return self._user


# ---------------------------------------------------------------------------
# Security request (step 1 — initiate a change)
# ---------------------------------------------------------------------------
class SecurityRequestForm(forms.Form):
    ACTION_CHOICES = [
        ("email", "Change email"),
        ("password", "Change password"),
        ("delete", "Delete account"),
    ]
    action = forms.ChoiceField(choices=ACTION_CHOICES, widget=forms.HiddenInput)
    current_password = forms.CharField(
        label="Current password",
        max_length=128,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    new_email = forms.EmailField(
        label="New email",
        required=False,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    new_password = forms.CharField(
        label="New password",
        required=False,
        min_length=12,
        max_length=128,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    confirm_password = forms.CharField(
        label="Confirm new password",
        required=False,
        max_length=128,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean(self):
        cleaned = super().clean()
        action = cleaned.get("action")
        if action == "email":
            if not cleaned.get("new_email"):
                self.add_error("new_email", "Enter your new email address.")
        elif action == "password":
            pw = cleaned.get("new_password")
            confirm = cleaned.get("confirm_password")
            if not pw:
                self.add_error("new_password", "Enter a new password.")
            if not confirm:
                self.add_error("confirm_password", "Confirm your new password.")
            if pw and confirm and pw != confirm:
                self.add_error("confirm_password", "New passwords must match.")
            if pw:
                try:
                    password_validation.validate_password(pw)
                except ValidationError as e:
                    self.add_error("new_password", e)
        return cleaned


# ---------------------------------------------------------------------------
# Security verify (step 2 — submit the code and complete the change)
# ---------------------------------------------------------------------------
class SecurityVerifyForm(forms.Form):
    code = forms.CharField(
        label="Verification code (current email)",
        min_length=6,
        max_length=6,
        widget=forms.TextInput(
            attrs={"inputmode": "numeric", "autocomplete": "one-time-code"}
        ),
    )
    new_email_code = forms.CharField(
        label="Verification code (new email)",
        required=False,
        min_length=6,
        max_length=6,
        widget=forms.TextInput(attrs={"inputmode": "numeric"}),
    )
    new_password = forms.CharField(
        label="New password",
        required=False,
        min_length=12,
        max_length=128,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    confirm_password = forms.CharField(
        label="Confirm new password",
        required=False,
        max_length=128,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    delete_confirmation = forms.CharField(
        label='Type "DELETE" to confirm',
        required=False,
        max_length=10,
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )

    def clean_code(self):
        return self.cleaned_data["code"].strip()

    def clean_new_email_code(self):
        return self.cleaned_data.get("new_email_code", "").strip()


# ---------------------------------------------------------------------------
# Role change (admin page)
# ---------------------------------------------------------------------------
class RoleChangeForm(forms.Form):
    role = forms.ChoiceField(choices=Role.choices)

    def clean_role(self):
        return self.cleaned_data["role"]
