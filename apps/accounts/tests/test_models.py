"""Tests for accounts models."""

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    """Tests for the User model."""

    def test_create_user_with_role(self) -> None:
        """User can be created and assigned a role via M2M."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="nir@example.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="nir")

        user.roles.add(role)

        assert user.roles.count() == 1
        assert user.roles.first() == role
        assert role.name == "nir"

    def test_user_without_roles(self) -> None:
        """User without any roles does not crash."""
        user = User.objects.create_user(username="no@role.com", password="testpass123")

        assert user.roles.count() == 0
        # Should not raise
        list(user.roles.all())

    def test_user_account_status_default(self) -> None:
        """Default account_status is 'active'."""
        user = User.objects.create_user(username="active@test.com", password="testpass123")

        assert user.account_status == "active"

    def test_user_is_account_active_property(self) -> None:
        """is_account_active returns True when status is active and is_active is True."""
        user = User.objects.create_user(username="prop@test.com", password="testpass123")

        assert user.is_account_active is True

        user.account_status = "blocked"
        user.save()
        assert user.is_account_active is False

    def test_user_can_have_multiple_roles(self) -> None:
        """User can be assigned multiple roles."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="multi@role.com", password="testpass123")
        role_nir, _ = Role.objects.get_or_create(name="nir")
        role_doctor, _ = Role.objects.get_or_create(name="doctor")

        user.roles.add(role_nir, role_doctor)

        assert user.roles.count() == 2
        assert set(user.roles.values_list("name", flat=True)) == {"nir", "doctor"}


@pytest.mark.django_db
class TestRoleModel:
    """Tests for the Role model."""

    def test_create_role(self) -> None:
        """Role can be created with a name."""
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name="doctor")
        assert role.name == "doctor"
        assert str(role) == "doctor"

    def test_role_name_unique(self) -> None:
        """Role names must be unique."""
        from apps.accounts.models import Role

        Role.objects.create(name="test_unique_role")

        with pytest.raises(Exception):
            Role.objects.create(name="test_unique_role")
