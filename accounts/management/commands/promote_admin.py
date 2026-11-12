"""
Management command: promote_admin

Usage:
    python manage.py promote_admin <email>

Promotes an existing, verified (is_active=True) user to the administrator role.
Exits with a clear error message if the user does not exist or is not verified.
"""
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Role, User


class Command(BaseCommand):
    help = "Promote an existing verified user to the administrator role."

    def add_arguments(self, parser):
        parser.add_argument("email", type=str, help="Email address of the user to promote.")

    def handle(self, *args, **options):
        email = options["email"].lower().strip()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise CommandError(f"No account found for '{email}'. Register first.")

        if not user.is_active:
            raise CommandError(
                f"The account '{email}' has not been verified. "
                "Ask the user to verify their email first."
            )

        if user.role == Role.ADMINISTRATOR:
            self.stdout.write(self.style.WARNING(f"'{email}' is already an administrator."))
            return

        user.role = Role.ADMINISTRATOR
        user.save(update_fields=["role"])
        self.stdout.write(self.style.SUCCESS(f"Administrator role assigned to '{email}'."))
