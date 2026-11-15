from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Project, Membership, Invitation, Notification, Dataset

@admin.register(User)
class InsightFlowUserAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "role", "is_staff", "is_active")
    fieldsets = ((None, {"fields": ("email", "password")}), ("Profile", {"fields": ("first_name", "last_name", "role", "avatar")}), ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}))
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)
    search_fields = ("email",)
    filter_horizontal = ("groups", "user_permissions")

for model in (Project, Membership, Invitation, Notification, Dataset): admin.site.register(model)
