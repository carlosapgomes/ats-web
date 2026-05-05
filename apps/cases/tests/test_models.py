"""Testes unitários do modelo Case."""

from __future__ import annotations

import pytest
from django.db import IntegrityError

from apps.cases.models import Case, CaseStatus


class TestCaseModel:
    def test_create_case_default_status(self, user) -> None:
        """Novo caso deve ter status NEW por padrão."""
        case = Case.objects.create(created_by=user)
        assert case.status == CaseStatus.NEW

    def test_case_has_uuid_pk(self, user) -> None:
        """PK deve ser UUID gerado automaticamente."""
        case = Case.objects.create(created_by=user)
        assert case.case_id is not None
        # UUID tem 36 caracteres com hífens
        assert len(str(case.case_id)) == 36

    def test_case_created_by_required(self, db) -> None:
        """created_by é obrigatório — deve falhar sem ele."""
        with pytest.raises(IntegrityError):
            Case.objects.create()

    def test_case_str_representation(self, user) -> None:
        """__str__ deve retornar formato esperado."""
        case = Case.objects.create(created_by=user)
        expected = f"Case {case.case_id} [NEW]"
        assert str(case) == expected

    def test_case_created_at_set_automatically(self, user) -> None:
        """created_at e updated_at devem ser preenchidos automaticamente."""
        case = Case.objects.create(created_by=user)
        assert case.created_at is not None
        assert case.updated_at is not None
