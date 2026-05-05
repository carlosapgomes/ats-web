"""Shared fixtures for cases tests."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user(db):
    """Cria um usuário ativo para testes."""
    return User.objects.create_user(username="testuser", password="testpass")
