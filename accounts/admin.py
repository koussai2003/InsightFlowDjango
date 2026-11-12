"""Django admin registration for accounts app."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import SecurityRequest, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Permissions", {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "role"),
        }),
    )
    list_display = ("email", "role", "is_active", "is_staff", "date_joined")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email",)
    ordering = ("email",)
    # Remove username references from base class.
    filter_horizontal = ("groups", "user_permissions")


@admin.register(SecurityRequest)
class SecurityRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "action", "created_at", "attempts", "old_verified")
    list_filter = ("action",)
    readonly_fields = ("code_hash", "new_email_code_hash", "created_at")
    raw_id_fields = ("user",)
