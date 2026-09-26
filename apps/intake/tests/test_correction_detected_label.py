"""Label do conjunto detectado no card de correção (ADR-0011 decisão 4).

Pina a regra anti-duplicação de ``_correction_detected_label`` (R1-R3 do Slice
003): base contida em pacote presente não é listada separadamente, pacotes
distintos restantes juntam-se com ``" e "`` e as demais identidades com
``" + "`` — o card nunca exibe uma combinação impossível como
``EDA + EDA + Dilatação`` (caso real de 2026-09-26).
"""

from __future__ import annotations

import pytest

from apps.cases.models import ProcedureType
from apps.intake.views import _correction_detected_label


def _label(*detected: str) -> str:
    """Label do card para um payload que carrega ``detected_procedures``."""
    return _correction_detected_label({"detected_procedures": list(detected)})


# ── R1/R2 — conjuntos pinados ────────────────────────────────────────────


@pytest.mark.parametrize(
    ("detected", "expected"),
    [
        # Base + pacote que já contém a base → base absorvida (caso real 26/09).
        (
            (ProcedureType.EDA, ProcedureType.EDA_DILATION),
            "EDA + Dilatação",
        ),
        # Pacote sozinho permanece o próprio label.
        ((ProcedureType.EDA_DILATION,), "EDA + Dilatação"),
        # Singleton canônico.
        ((ProcedureType.EDA,), "EDA"),
        # Sem cobertura mas sem base duplicada: dois pacotes juntam-se com " e ".
        (
            (ProcedureType.EDA, ProcedureType.EDA_CAPSULE, ProcedureType.EDA_DILATION),
            "EDA + Cápsula e EDA + Dilatação",
        ),
        # Base do reto absorvida pelo pacote; um único pacote, sem " e ".
        (
            (ProcedureType.COLONOSCOPY, ProcedureType.RECTOSIGMOIDOSCOPY_DILATION),
            "Colonoscopia + Retossigmoidoscopia + Dilatação",
        ),
        # Base reto + pacote argon → absorção simétrica.
        (
            (ProcedureType.RECTOSIGMOIDOSCOPY, ProcedureType.RECTOSIGMOIDOSCOPY_ARGON),
            "Retossigmoidoscopia + Argônio",
        ),
        # Dois pacotes distintos → " e " (nenhum absorve o outro).
        (
            (ProcedureType.EDA_GASTROSTOMY, ProcedureType.EDA_CAPSULE),
            "EDA + Gastrostomia (GTT) e EDA + Cápsula",
        ),
        # Ordem canônica preservada entre os segmentos.
        (
            (ProcedureType.COLONOSCOPY, ProcedureType.EDA_DILATION),
            "EDA + Dilatação + Colonoscopia",
        ),
        # Par válido continua sendo rotulado pelas identidades, sem chave interna.
        ((ProcedureType.EDA, ProcedureType.COLONOSCOPY), "EDA + Colonoscopia"),
        ((ProcedureType.EDA, ProcedureType.CPRE), "EDA + CPRE"),
    ],
)
def test_detected_set_label_never_renders_impossible_combination(detected: tuple[str, ...], expected: str) -> None:
    """R1/R2: absorção de base, ``+`` entre identidades e ``e`` entre pacotes."""
    assert _label(*detected) == expected


def test_detected_set_with_unknown_identity_keeps_raw_code_fallback() -> None:
    """Valor fora do catálogo segue exibido como hoje (código cru, sem exceção)."""
    assert _label("unknown_value") == "unknown_value"
    assert _label(ProcedureType.EDA, "unknown_value") == "EDA + unknown_value"


def test_detected_set_without_known_coverage_keeps_every_identity() -> None:
    """Conjunto sem cobertura não é reduzido: cada identidade segue visível."""
    assert _label(ProcedureType.EDA_CAPSULE, ProcedureType.EDA_DILATION) == "EDA + Cápsula e EDA + Dilatação"


# ── R3 — função total (nunca levanta) ────────────────────────────────────


def test_label_falls_back_to_legacy_key_without_detected_set() -> None:
    """Payload sem ``detected_procedures`` usa a chave legada, como hoje."""
    assert _correction_detected_label({"detected_exam_type": "mixed"}) == "Solicitação mista (EDA + Colonoscopia)"
    assert _correction_detected_label({"exam_type": ProcedureType.COLONOSCOPY}) == "Colonoscopia"
    assert _correction_detected_label({"detected_procedures": []}) == "—"
    assert _correction_detected_label({}) == "—"


def test_label_never_raises_for_malformed_detected_types() -> None:
    """R3: a projeção de card é total — payloads estranhos não levantam."""
    assert _correction_detected_label({"detected_procedures": ProcedureType.EDA}) == "—"
    assert _correction_detected_label({"detected_procedures": [None]}) == "None"
    assert _correction_detected_label({"detected_procedures": [12345]}) == "12345"
