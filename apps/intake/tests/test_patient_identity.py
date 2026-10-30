"""Tests for deterministic patient identity extraction and masking (PI-01..PI-09).

All names/CNS below are synthetic fixtures (PI-13); no real sample data.
"""

from __future__ import annotations

import pytest

from apps.intake.patient_identity import (
    PatientIdentity,
    PatientIdentityLeakError,
    assert_no_identity_leaks,
    extract_patient_identity,
    mask_identity_in_value,
    mask_patient_identity,
)

NAME = "Maria Clara Souza Teste"
SOCIAL = "Mariana Souza Teste"
CNS = "700123456789012"

HEADER = (
    "RELATÓRIO DE OCORRÊNCIAS\n"
    "1234567\n"
    f"{NAME} - Idade: 45a.  - Sexo Feminino - Raça/Cor Parda\n"
    "Paciente:\n"
    "Abertura:\n"
    "01/05/2026\n"
    f"CNS: {CNS}\n"
    "Nome Social:\n"
    "Central. Reg.:\n"
    "Motivo da Solicitação:\n"
    "Endoscopia Digestiva Alta - EDA\n"
    "Resumo Clínico:\n"
    f"Paciente {NAME} relata dispepsia há 3 meses.\n"
)


class TestExtractPatientIdentity:
    def test_name_before_paciente_label_with_age_suffix(self) -> None:
        identity = extract_patient_identity(HEADER)
        assert identity.name == NAME
        assert identity.status == "extracted"

    def test_name_after_paciente_label(self) -> None:
        identity = extract_patient_identity(f"Paciente: {NAME}\nResumo Clínico: dispepsia.\n")
        assert identity.name == NAME
        assert identity.status == "extracted"

    def test_repeated_headers_same_name(self) -> None:
        identity = extract_patient_identity(HEADER + "\n" + HEADER)
        assert identity.name == NAME
        assert identity.status == "extracted"

    def test_divergent_headers_are_ambiguous(self) -> None:
        other = HEADER.replace(NAME, "Outra Pessoa Teste")
        identity = extract_patient_identity(HEADER + "\n" + other)
        assert identity.status == "ambiguous"

    def test_paciente_label_without_parseable_name_is_ambiguous(self) -> None:
        identity = extract_patient_identity("4915486\nPaciente:\nAbertura:\n01/05/2026\n")
        assert identity.name is None
        assert identity.status == "ambiguous"

    def test_text_without_header_is_absent_not_error(self) -> None:
        identity = extract_patient_identity("Solicito EDA para avaliação de dispepsia.")
        assert identity.name is None
        assert identity.cns is None
        assert identity.status == "absent"

    def test_cns_numeric_15_digits(self) -> None:
        assert extract_patient_identity(HEADER).cns == CNS

    def test_cns_nao_cadastrado_is_absent(self) -> None:
        identity = extract_patient_identity(HEADER.replace(CNS, "não cadastrado"))
        assert identity.cns is None
        assert identity.status == "extracted"

    def test_cns_empty_is_absent(self) -> None:
        assert extract_patient_identity("CNS:\nPaciente: " + NAME).cns is None

    def test_divergent_cns_is_ambiguous(self) -> None:
        text = HEADER + "\nCNS: 700999988887777\n"
        assert extract_patient_identity(text).status == "ambiguous"

    def test_social_inline(self) -> None:
        identity = extract_patient_identity(f"Nome Social: {SOCIAL}\nCentral. Reg.:\n")
        assert identity.social_name == SOCIAL

    def test_social_next_line_validated(self) -> None:
        identity = extract_patient_identity(f"Nome Social:\n{SOCIAL}\nCentral. Reg.:\n")
        assert identity.social_name == SOCIAL

    def test_social_empty_before_central_label(self) -> None:
        assert extract_patient_identity(HEADER).social_name is None

    def test_social_empty_before_watermark_token(self) -> None:
        assert extract_patient_identity("Nome Social:\n65823\nCentral. Reg.:\n").social_name is None

    def test_social_not_consumed_from_later_clinical_text(self) -> None:
        text = "Nome Social:\nCentral. Reg.:\nNome Social:\nPaciente relata dor epigástrica intensa.\n"
        assert extract_patient_identity(text).social_name is None


class TestMaskPatientIdentity:
    def test_masks_header_and_narrative_repetitions(self) -> None:
        masked = mask_patient_identity(HEADER + "\n" + HEADER, extract_patient_identity(HEADER))
        assert NAME not in masked
        assert masked.count("[NOME_REMOVIDO]") == 4  # 2 headers + 2 narratives
        assert "Idade: 45a." in masked
        assert "Sexo Feminino" in masked
        assert "dispepsia" in masked

    def test_masks_case_and_accent_variants(self) -> None:
        identity = PatientIdentity(name=NAME, social_name=None, cns=None, status="extracted")
        masked = mask_patient_identity("maria clara souza teste e MARIA CLARA SOUZA TESTE", identity)
        assert masked == "[NOME_REMOVIDO] e [NOME_REMOVIDO]"

    def test_masks_social_and_cns(self) -> None:
        identity = PatientIdentity(name=NAME, social_name=SOCIAL, cns=CNS, status="extracted")
        masked = mask_patient_identity(f"{SOCIAL} / {NAME} / CNS {CNS}", identity)
        assert masked == "[NOME_SOCIAL_REMOVIDO] / [NOME_REMOVIDO] / CNS [CNS_REMOVIDO]"

    def test_cns_does_not_consume_longer_number(self) -> None:
        identity = PatientIdentity(name=None, social_name=None, cns=CNS, status="extracted")
        assert mask_patient_identity(f"protocolo {CNS}9 fim", identity) == f"protocolo {CNS}9 fim"
        assert mask_patient_identity(f"cns {CNS} fim", identity) == "cns [CNS_REMOVIDO] fim"

    def test_short_name_does_not_cut_other_words(self) -> None:
        identity = PatientIdentity(name="Ana Souza", social_name=None, cns=None, status="extracted")
        masked = mask_patient_identity("Anabela Souza e Ana Souza", identity)
        assert masked == "Anabela Souza e [NOME_REMOVIDO]"

    def test_absent_identity_is_noop(self) -> None:
        identity = extract_patient_identity("Solicito EDA.")
        assert mask_patient_identity("Solicito EDA.", identity) == "Solicito EDA."

    def test_mask_identity_in_value_recurses(self) -> None:
        identity = PatientIdentity(name=NAME, social_name=None, cns=CNS, status="extracted")
        value = {"patient": {"name": NAME, "age": 45}, "notes": [f"CNS {CNS}", "ok"]}
        assert mask_identity_in_value(value, identity) == {
            "patient": {"name": "[NOME_REMOVIDO]", "age": 45},
            "notes": ["CNS [CNS_REMOVIDO]", "ok"],
        }

    def test_leak_guard(self) -> None:
        identity = PatientIdentity(name=NAME, social_name=None, cns=CNS, status="extracted")
        assert_no_identity_leaks(mask_patient_identity(HEADER, identity), identity)
        with pytest.raises(PatientIdentityLeakError):
            assert_no_identity_leaks(HEADER, identity)
