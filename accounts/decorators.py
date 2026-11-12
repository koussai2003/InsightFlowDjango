"""
Role-based access decorators.

Usage:
    @role_required(Role.ADMINISTRATOR)
    def my_view(request): ...

Returns 403 if the authenticated user does not have one of the given roles.
Wraps login_required so unauthenticated users are redirected to /login.
"""
import functools

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import Role


def role_required(*roles):
    """Decorator factory: allow only users whose role is in *roles*."""

    def decorator(view_func):
        @login_required
        @functools.wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
