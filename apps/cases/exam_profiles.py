"""Exam profiles — diferenças reais entre procedimentos suportados.

Fonte única para diferenças de policy/presenter por procedimento: labels,
aliases de solicitação, exceções permitidas, sinais prioritários permitidos e
requisito adicional de imagem (design D7). Regras clínicas comuns permanecem
em funções compartilhadas na policy — o perfil contém somente diferenças.

Design D7: ``accepted_imaging`` declara, de forma puramente declarativa, o
conjunto ``(modalidade, sítio anatômico)`` que satisfaz o requisito adicional
de imagem de Ecoendoscopia/CPRE. A *ativação* da hard rule especializada e do
verificador determinístico de evidência ocorre nos slices verticais próprios
(Slice 002/004); no Slice 001 o comportamento de EDA/Colonoscopia permanece
exatamente inalterado (R5).
"""

from __future__ import annotations

from dataclasses import dataclass, field


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
    # Pares (modality, anatomical_site) aceitos para a imagem abdominal
    # adicional (design D6/D7). Vazio = sem requisito de imagem adicional.
    accepted_imaging: tuple[tuple[str, str], ...] = field(default_factory=tuple)


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

# D7: Ecoendoscopia exige TC/RM de abdome/abdome superior; nunca herda a
# exceção de corpo estranho. Aliases de detecção entram no Slice 002.
ECHOENDOSCOPY_PROFILE = ExamProfile(
    exam_type="echoendoscopy",
    label="Ecoendoscopia",
    allows_foreign_body_exception=False,
    allowed_priority_signal_codes=frozenset({"pediatric"}),
    scope_aliases=(),
    canonical_procedure="Ecoendoscopia",
    accepted_imaging=(
        ("ct", "abdomen"),
        ("ct", "upper_abdomen"),
        ("mri", "abdomen"),
        ("mri", "upper_abdomen"),
    ),
)

# D7: CPRE exige USG abdominal/abdome superior/hepatobiliar, TC/RM de
# abdome/abdome superior ou CPRM hepatobiliar; nunca herda corpo estranho.
CPRE_PROFILE = ExamProfile(
    exam_type="cpre",
    label="CPRE",
    allows_foreign_body_exception=False,
    allowed_priority_signal_codes=frozenset({"pediatric"}),
    scope_aliases=(),
    canonical_procedure="CPRE",
    accepted_imaging=(
        ("ultrasound", "abdomen"),
        ("ultrasound", "upper_abdomen"),
        ("ultrasound", "hepatobiliary"),
        ("ct", "abdomen"),
        ("ct", "upper_abdomen"),
        ("mri", "abdomen"),
        ("mri", "upper_abdomen"),
        ("mrcp", "hepatobiliary"),
    ),
)

_PROFILES_BY_EXAM_TYPE: dict[str, ExamProfile] = {
    profile.exam_type: profile for profile in (EDA_PROFILE, COLONOSCOPY_PROFILE, ECHOENDOSCOPY_PROFILE, CPRE_PROFILE)
}


def get_exam_profile(exam_type: str | None) -> ExamProfile:
    """Resolve o perfil de procedimento para um tipo de exame.

    Tipo desconhecido/ausente cai em EDA por compatibilidade (casos históricos
    são EDA e o default do modelo é ``eda``).
    """
    normalized = (exam_type or "").strip().lower()
    return _PROFILES_BY_EXAM_TYPE.get(normalized, EDA_PROFILE)
