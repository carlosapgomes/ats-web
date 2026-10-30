"""Persistência da identidade local do paciente (Slice 2, PI-01/PI-02).

Nomes/CNS sintéticos (PI-13).
"""

from __future__ import annotations

import pytest

from apps.cases.models import Case

NAME = "Maria Clara Souza Teste"
CNS = "700123456789012"

_HEADER_TEXT = (
    "RELATORIO DE OCORRENCIAS\n"
    "Governo do Estado da Bahia\n"
    "Secretaria da Saude do Estado\n"
    "Codigo: 12345\n"
    f"{NAME} - Idade: 45a.  - Sexo Feminino\n"
    "Paciente:\n"
    "Abertura: 01/01/2025\n"
    f"CNS: {CNS}\n"
    "Nome Social:\n"
    "Central. Reg.:\n"
    "Unid. Origem: Hospital Central\n"
    "Motivo da Solicitacao: EDA diagnostica\n"
    "Resumo Clinico: Paciente de 45 anos, sem comorbidades.\n"
    + "Texto de preenchimento para atingir o minimo de caracteres exigido. "
    * 20
)


@pytest.mark.django_db
class TestExtractionPersistsIdentity:
    def test_do_extraction_persists_local_identity_and_preserves_text(self, user, monkeypatch) -> None:
        from apps.intake.tasks import _do_extraction

        monkeypatch.setattr("apps.intake.pdf_utils.extract_pdf_text", lambda _path: _HEADER_TEXT)

        case = Case.objects.create(created_by=user)
        case.pdf_file = "pdfs/2026/05/test.pdf"
        case.start_processing(user=user)
        case.save()
        case = Case.objects.get(case_id=case.case_id)

        _do_extraction(case)

        reloaded = Case.objects.get(case_id=case.case_id)
        assert reloaded.patient_identity_name == NAME
        assert reloaded.patient_identity_cns == CNS
        assert reloaded.patient_identity_social_name == ""
        assert reloaded.patient_identity_status == "extracted"
        # Texto fonte preservado (PI-02): identidade continua no original local.
        assert NAME in reloaded.extracted_text
        assert reloaded.patient_name == NAME


@pytest.mark.django_db
class TestPatientNamePrecedence:
    def test_local_identity_wins_over_llm_structured_data(self, user) -> None:
        case = Case.objects.create(
            created_by=user,
            patient_identity_name=NAME,
            patient_identity_status="extracted",
            structured_data={"patient": {"name": "Nome Devolvido Pelo Modelo"}},
        )
        assert case.patient_name == NAME

    def test_fallback_to_structured_data_for_historical_cases(self, user) -> None:
        case = Case.objects.create(
            created_by=user,
            structured_data={"patient": {"name": "Paciente Historico"}},
        )
        assert case.patient_name == "Paciente Historico"
