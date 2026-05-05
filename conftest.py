"""Root-level pytest fixtures shared across all apps."""

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user_password() -> str:
    """Default test password."""
    return "testpass123!"


@pytest.fixture
def user_with_single_role(db: None, user_password: str):  # type: ignore[no-untyped-def]
    from apps.accounts.models import Role

    role = Role.objects.create(name="admin")
    user = User.objects.create_user(
        username="testuser",
        password=user_password,
    )
    user.roles.add(role)
    return user


@pytest.fixture
def user_with_multiple_roles(db: None, user_password: str):  # type: ignore[no-untyped-def]
    from apps.accounts.models import Role

    roles = Role.objects.bulk_create([Role(name="doctor"), Role(name="manager")])
    user = User.objects.create_user(
        username="multiuser",
        password=user_password,
    )
    user.roles.add(*roles)
    return user


@pytest.fixture
def authenticated_client(client, user_with_single_role, user_password):  # type: ignore[no-untyped-def]
    client.login(username=user_with_single_role.username, password=user_password)
    return client
