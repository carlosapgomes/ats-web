"""Policy 3.0 procedure-aware — facade determinística por procedimento (D8).

O contrato 3.0 avalia cada procedimento reconciliado e devolve um payload com
``failed_requirements[]`` completo, preservando ``reason_code``/``reason_text``
do motivo primário (compatibilidade com presenter, correção NIR e dashboard).

Este módulo é o seam procedure-aware: resolve o perfil do procedimento, delega
a avaliação determinística compartilhada e mantém a ordem estável das
categorias. A categoria ``imaging`` é ativada pelos slices verticais de
Ecoendoscopia e CPRE e recebe exclusivamente a evidência aprovada pelo
verificador determinístico (design D6); sem isso, o comportamento de
EDA/Colonoscopia permanece inalterado (R5).
"""

from __future__ import annotations

from apps.pipeline.policy.eda_preop_policy import (
    REQUIREMENT_CATEGORIES,
    VerifiedImaging,
    evaluate_preop_policy,
)


def evaluate_procedure_policy(
    *,
    structured_data: dict[str, object],
    procedure_type: str,
    verified_imaging: VerifiedImaging | None = None,
) -> dict[str, object]:
    """Avalia critérios determinísticos de um procedimento reconciliado (D8).

    Args:
        structured_data: projeção 1.1 do procedimento (adapta 1.1/2.0/3.0).
        procedure_type: uma das dez identidades atômicas do catálogo. O código
            ORIGINAL é repassado à policy — o profile é resolvido por
            ``profile_key`` (pacotes reutilizam as regras da família) e a label
            persistida nos textos determinísticos é a da IDENTIDADE (D4).
        verified_imaging: outcomes do verificador determinístico de imagem
            (design D6). A policy consome SOMENTE evidência aprovada; perfis
            EDA/Colonoscopia ignoram o parâmetro e não mudam de comportamento.

    Returns:
        Payload determinístico com ``decision``, ``reason_code`` primário,
        ``reason_text``, ``evidence_spans``, ``pediatric_flag`` e
        ``failed_requirements[]`` em ordem estável.
    """
    return evaluate_preop_policy(
        structured_data=structured_data,
        exam_type=procedure_type,
        verified_imaging=verified_imaging,
    )


__all__ = ["REQUIREMENT_CATEGORIES", "VerifiedImaging", "evaluate_procedure_policy"]
