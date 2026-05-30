"""Admin registration for accounts models."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Role, User


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(User)
class UserAdmin(BaseUserAdmin):  # type: ignore[type-arg]
    list_display = ("username", "email", "account_status", "is_active")
    list_filter = ("account_status", "is_active", "roles")
    fieldsets = (BaseUserAdmin.fieldsets or ()) + (  # type: ignore[operator]
        ("Profissional", {"fields": ("professional_council", "professional_council_number")}),
        ("ATS Custom", {"fields": ("roles", "account_status")}),
    )
