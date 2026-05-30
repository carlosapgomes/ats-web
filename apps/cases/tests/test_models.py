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


class TestOriginUnitDisplay:
    """Testes do método Case.get_origin_unit_display."""

    def test_returns_empty_when_no_structured_data(self, user) -> None:
        case = Case.objects.create(created_by=user)
        assert case.get_origin_unit_display() == ""
        assert case.get_origin_unit_display(compact=False) == ""

    def test_returns_empty_when_no_origin_context(self, user) -> None:
        case = Case.objects.create(
            created_by=user,
            structured_data={"patient": {"name": "Teste"}},
        )
        assert case.get_origin_unit_display() == ""

    def test_compact_mode_hospital_and_unit(self, user) -> None:
        case = Case.objects.create(
            created_by=user,
            structured_data={
                "origin_context": {
                    "city": "São Paulo",
                    "state_uf": "SP",
                    "hospital": "Santa Casa",
                    "unit": "UTI Adulto",
                }
            },
        )
        result = case.get_origin_unit_display(compact=True)
        assert result == "Santa Casa · UTI Adulto"

    def test_compact_mode_skips_duplicate_unit(self, user) -> None:
        """Quando unit == hospital, não repete."""
        case = Case.objects.create(
            created_by=user,
            structured_data={
                "origin_context": {
                    "hospital": "Hospital X",
                    "unit": "Hospital X",
                }
            },
        )
        result = case.get_origin_unit_display(compact=True)
        assert result == "Hospital X"

    def test_compact_mode_hospital_only(self, user) -> None:
        case = Case.objects.create(
            created_by=user,
            structured_data={
                "origin_context": {
                    "hospital": "Hospital das Clínicas",
                }
            },
        )
        result = case.get_origin_unit_display(compact=True)
        assert result == "Hospital das Clínicas"

    def test_compact_mode_unit_only(self, user) -> None:
        case = Case.objects.create(
            created_by=user,
            structured_data={
                "origin_context": {
                    "unit": "Pronto Socorro",
                }
            },
        )
        result = case.get_origin_unit_display(compact=True)
        assert result == "Pronto Socorro"

    def test_full_mode_with_all_fields(self, user) -> None:
        case = Case.objects.create(
            created_by=user,
            structured_data={
                "origin_context": {
                    "city": "Campinas",
                    "state_uf": "SP",
                    "hospital": "HC Unicamp",
                    "unit": "Gastrocentro",
                }
            },
        )
        result = case.get_origin_unit_display(compact=False)
        assert result == "Campinas (SP) · HC Unicamp · Gastrocentro"

    def test_full_mode_city_without_uf(self, user) -> None:
        case = Case.objects.create(
            created_by=user,
            structured_data={
                "origin_context": {
                    "city": "Rio de Janeiro",
                    "hospital": "Hospital Municipal",
                }
            },
        )
        result = case.get_origin_unit_display(compact=False)
        assert result == "Rio de Janeiro · Hospital Municipal"

    def test_handles_none_values_in_origin_context(self, user) -> None:
        case = Case.objects.create(
            created_by=user,
            structured_data={
                "origin_context": {
                    "city": None,
                    "state_uf": None,
                    "hospital": "  Hospital Teste  ",
                    "unit": None,
                }
            },
        )
        result = case.get_origin_unit_display()
        assert result == "Hospital Teste"
