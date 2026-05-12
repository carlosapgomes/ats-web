"""Seed admin user with all roles — idempotent management command.

Creates a superuser with username 'admin' and the given password,
assigning all 5 roles (nir, doctor, scheduler, manager, admin).
Safe to run multiple times — skips if user already exists.

Usage:
    uv run python manage.py seed_admin --settings=config.settings.dev
    uv run python manage.py seed_admin --password=secret --settings=config.settings.prod
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.accounts.models import Role

User = get_user_model()

ALL_ROLES = ["nir", "doctor", "scheduler", "manager", "admin"]


class Command(BaseCommand):
    help = "Create admin superuser with all roles (idempotent)"

    def add_arguments(self, parser):  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--username",
            default="admin",
            help="Username for the admin user (default: admin)",
        )
        parser.add_argument(
            "--password",
            default="admin",
            help="Password for the admin user (default: admin)",
        )
        parser.add_argument(
            "--email",
            default="admin@hospital.org",
            help="Email for the admin user (default: admin@hospital.org)",
        )

    def handle(self, *args: object, **options: object) -> None:
        username = str(options["username"])
        password = str(options["password"])
        email = str(options["email"])

        # Ensure roles exist
        roles = []
        for role_name in ALL_ROLES:
            role, created = Role.objects.get_or_create(name=role_name)
            roles.append(role)
            if created:
                self.stdout.write(f"  Created role: {role_name}")

        # Create or update user
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_superuser": True,
                "is_staff": True,
                "is_active": True,
            },
        )

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"  Created user: {username}"))
        else:
            # Update password and email if user exists
            user.set_password(password)
            user.email = email
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True
            user.save()
            self.stdout.write(f"  User already exists, updated: {username}")

        # Assign all roles
        for role in roles:
            user.roles.add(role)

        self.stdout.write(self.style.SUCCESS(f"  Assigned {len(roles)} roles to {username}"))
        self.stdout.write(self.style.SUCCESS(f"  Done. Login: {username} / {password}"))
