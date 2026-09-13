"""Policy 3.0 procedure-aware — facade determinística por procedimento (D8).

O contrato 3.0 avalia cada procedimento reconciliado e devolve um payload com
``failed_requirements[]`` completo, preservando ``reason_code``/``reason_text``
do motivo primário (compatibilidade com presenter, correção NIR e dashboard).

Este módulo é o seam procedure-aware: resolve o perfil do procedimento, delega
a avaliação determinística compartilhada e mantém a ordem estável das
categorias. A categoria ``imaging`` (imagem abdominal especializada e seu
verificador determinístico) é ativada pelos slices verticais de Ecoendoscopia e
CPRE; no Slice 001 o comportamento de EDA/Colonoscopia permanece inalterado
(R5).
"""

from __future__ import annotations

from apps.cases.exam_profiles import get_exam_profile
from apps.pipeline.policy.eda_preop_policy import REQUIREMENT_CATEGORIES, evaluate_preop_policy


def evaluate_procedure_policy(*, structured_data: dict[str, object], procedure_type: str) -> dict[str, object]:
    """Avalia critérios determinísticos de um procedimento reconciliado (D8).

    Args:
        structured_data: projeção 1.1 do procedimento (adapta 1.1/2.0/3.0).
        procedure_type: um dos quatro tipos do catálogo.

    Returns:
        Payload determinístico com ``decision``, ``reason_code`` primário,
        ``reason_text``, ``evidence_spans``, ``pediatric_flag`` e
        ``failed_requirements[]`` em ordem estável.
    """
    profile = get_exam_profile(procedure_type)
    return evaluate_preop_policy(structured_data=structured_data, exam_type=profile.exam_type)


__all__ = ["REQUIREMENT_CATEGORIES", "evaluate_procedure_policy"]
