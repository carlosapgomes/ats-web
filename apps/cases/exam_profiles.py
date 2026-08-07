"""Exam profiles — diferenças reais entre procedimentos suportados (Slice 003).

Fonte única para diferenças de policy/presenter por procedimento: labels,
aliases de solicitação, exceções permitidas e sinais prioritários permitidos.
Regras clínicas comuns permanecem em funções compartilhadas na policy — o
perfil contém somente diferenças.

Slice 007: os nomes de prompts administráveis saíram do perfil (dispatch v2
usa somente os quatro nomes neutros ``exam_llm{1,2}_{system,user}``). Os perfis
continuam fornecendo policy/presenter (``allows_foreign_body_exception``,
``scope_aliases``, ``canonical_procedure``) consumidos pelo pipeline v2 e
pelos adapters/presenters históricos 1.1.

Sem framework prematuro: apenas os perfis EDA e Colonoscopia existem. CPRE não
é escopo deste change (YAGNI).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExamProfile:
    """Diferenças operacionais de um tipo de exame suportado."""

    exam_type: str
    label: str
    # Exceção de corpo estranho é exclusiva de EDA (R4 / ADR-0003).
    allows_foreign_body_exception: bool
    # Sinais prioritários persistidos permitidos (R7 / design D9).
    allowed_priority_signal_codes: frozenset[str]
    # Aliases de solicitação aprovados para detecção de escopo (R3 / D7).
    scope_aliases: tuple[str, ...]
    # Nome canônico do procedimento para presenters (R6).
    canonical_procedure: str


EDA_PROFILE = ExamProfile(
    exam_type="eda",
    label="EDA",
    allows_foreign_body_exception=True,
    allowed_priority_signal_codes=frozenset(
        {
            "foreign_body",
            "caustic_ingestion",
            "pediatric",
            "echoendoscopy",
            "esophageal_dilation",
            "gastrostomy",
        }
    ),
    scope_aliases=(
        "endoscopia digestiva alta",
        "videoendoscopia digestiva alta",
        "endoscopia digestiva superior",
    ),
    canonical_procedure="EDA",
)

COLONOSCOPY_PROFILE = ExamProfile(
    exam_type="colonoscopy",
    label="Colonoscopia",
    allows_foreign_body_exception=False,
    allowed_priority_signal_codes=frozenset({"pediatric"}),
    scope_aliases=(
        "colonoscopia",
        "colonoscopia diagnostica",
        "colonoscopia terapeutica",
        "endoscopia digestiva baixa",
        "endoscopia digestiva baixa - colonoscopia",
        "videocolonoendoscopia",
    ),
    canonical_procedure="Colonoscopia",
)

_PROFILES_BY_EXAM_TYPE: dict[str, ExamProfile] = {
    profile.exam_type: profile for profile in (EDA_PROFILE, COLONOSCOPY_PROFILE)
}


def get_exam_profile(exam_type: str | None) -> ExamProfile:
    """Resolve o perfil de procedimento para um tipo de exame.

    Tipo desconhecido/ausente cai em EDA por compatibilidade (casos históricos
    são EDA e o default do modelo é ``eda``).
    """
    normalized = (exam_type or "").strip().lower()
    return _PROFILES_BY_EXAM_TYPE.get(normalized, EDA_PROFILE)
