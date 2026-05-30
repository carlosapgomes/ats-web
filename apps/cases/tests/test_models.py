"""Testes unitários do modelo Case."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.cases.models import Case, CaseStatus

User = get_user_model()


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


class TestPatientProperties:
    """Testes das properties patient_name, patient_age, patient_gender, diagnosis."""

    def test_patient_name_from_structured_data(self, user) -> None:
        case = Case.objects.create(
            created_by=user,
            structured_data={"patient": {"name": "João Silva"}},
        )
        assert case.patient_name == "João Silva"

    def test_patient_name_returns_paciente_when_no_data(self, user) -> None:
        case = Case.objects.create(created_by=user)
        assert case.patient_name == "Paciente"

    def test_patient_name_returns_paciente_when_name_empty(self, user) -> None:
        case = Case.objects.create(
            created_by=user,
            structured_data={"patient": {"name": ""}},
        )
        assert case.patient_name == "Paciente"

    def test_patient_age_from_structured_data(self, user) -> None:
        case = Case.objects.create(
            created_by=user,
            structured_data={"patient": {"age": 45}},
        )
        assert case.patient_age == "45"

    def test_patient_age_empty_when_no_data(self, user) -> None:
        case = Case.objects.create(created_by=user)
        assert case.patient_age == ""

    def test_patient_gender_sex_from_structured_data(self, user) -> None:
        case = Case.objects.create(
            created_by=user,
            structured_data={"patient": {"sex": "Feminino"}},
        )
        assert case.patient_gender == "Feminino"

    def test_patient_gender_falls_back_to_gender(self, user) -> None:
        case = Case.objects.create(
            created_by=user,
            structured_data={"patient": {"gender": "Masculino"}},
        )
        assert case.patient_gender == "Masculino"

    def test_patient_gender_empty_when_no_data(self, user) -> None:
        case = Case.objects.create(created_by=user)
        assert case.patient_gender == ""

    def test_diagnosis_uses_summary_text_first(self, user) -> None:
        case = Case.objects.create(
            created_by=user,
            summary_text="Paciente com indicação de EDA",
            structured_data={"eda": {"indication_category": "Diagnóstico"}},
        )
        assert case.diagnosis == "Paciente com indicação de EDA"

    def test_diagnosis_falls_back_to_indication(self, user) -> None:
        case = Case.objects.create(
            created_by=user,
            structured_data={"eda": {"indication_category": "Triagem"}},
        )
        assert case.diagnosis == "Triagem"

    def test_diagnosis_empty_when_no_data(self, user) -> None:
        case = Case.objects.create(created_by=user)
        assert case.diagnosis == ""


class TestDoctorDisplay:
    """Testes da property Case.doctor_display."""

    def test_doctor_display_with_registration(self, user) -> None:
        """doctor_display retorna 'Nome — CRM 12345' quando médico tem registro."""
        from apps.accounts.models import ProfessionalCouncil

        doctor_user = User.objects.create_user(
            username="dra.maria",
            password="pass123",
            first_name="Maria",
            last_name="Silva",
        )
        doctor_user.professional_council = ProfessionalCouncil.CRM
        doctor_user.professional_council_number = "12345"
        doctor_user.save()

        case = Case.objects.create(created_by=user, doctor=doctor_user)
        assert case.doctor_display == "Maria Silva — CRM 12345"

    def test_doctor_display_without_registration(self, user) -> None:
        """doctor_display retorna 'Nome' quando médico não tem registro."""
        doctor_user = User.objects.create_user(
            username="dr.joao",
            password="pass123",
            first_name="João",
            last_name="Souza",
        )
        case = Case.objects.create(created_by=user, doctor=doctor_user)
        assert case.doctor_display == "João Souza"

    def test_doctor_display_returns_empty_when_no_doctor(self, user) -> None:
        """doctor_display retorna '' quando case.doctor is None."""
        case = Case.objects.create(created_by=user)
        assert case.doctor_display == ""

    def test_doctor_display_fallback_to_username(self, user) -> None:
        """doctor_display usa username quando first/last name estão vazios."""
        doctor_user = User.objects.create_user(username="dra.ana", password="pass123")
        doctor_user.professional_council = "CRM"
        doctor_user.professional_council_number = "54321"
        doctor_user.save()

        case = Case.objects.create(created_by=user, doctor=doctor_user)
        assert case.doctor_display == "dra.ana — CRM 54321"
