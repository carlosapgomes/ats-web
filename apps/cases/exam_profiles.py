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

Design D4 (catálogo ampliado): as dez identidades atômicas resolvem o profile
clínico da família pelo ``profile_key`` do catálogo. O fallback silencioso para
EDA permanece apenas em ``get_exam_profile`` (adapters/presenters de artefatos
legados 1.1/2.0/3.0); writers novos usam ``require_exam_profile``, que falha
fechado.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from apps.cases.procedures import PROCEDURE_CATALOG


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
    # Descrição clínica do requisito de imagem quando ``accepted_imaging`` não
    # é vazio: usada apenas no ``reason_text`` da pendência de imagem (D7/D8),
    # para que o motivo exibido ao NIR/médico corresponda ao perfil real.
    imaging_requirement_label: str = ""


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
    imaging_requirement_label="TC ou RM de abdome/abdome superior com laudo de conclusao/achado",
)

# D7: CPRE exige USG abdominal/abdome superior/hepatobiliar, TC/RM de
# abdome/abdome superior ou CPRM hepatobiliar; nunca herda corpo estranho.
CPRE_PROFILE = ExamProfile(
    exam_type="cpre",
    label="CPRE",
    allows_foreign_body_exception=False,
    allowed_priority_signal_codes=frozenset({"pediatric"}),
    # Aliases de solicitação (nome completo + sigla) usados pela detecção de
    # escopo (Slice 004, R2). Fonte única: ``scope_detection`` compõe o padrão
    # de ocorrência a partir daqui.
    scope_aliases=(
        "cpre",
        "colangiopancreatografia endoscopica retrograda",
        "colangiopancreatografia retrograda endoscopica",
    ),
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
    # Descrição clínica do requisito de imagem aceito (D7): o perfil é a fonte
    # única das diferenças clínicas; a policy apenas a apresenta no motivo.
    imaging_requirement_label=(
        "USG de abdome/abdome superior/hepatobiliar, TC ou RM de abdome/abdome superior "
        "ou CPRM hepatobiliar, com laudo de conclusao/achado"
    ),
)

_PROFILES_BY_KEY: dict[str, ExamProfile] = {
    "eda": EDA_PROFILE,
    "colonoscopy": COLONOSCOPY_PROFILE,
    "echoendoscopy": ECHOENDOSCOPY_PROFILE,
    "cpre": CPRE_PROFILE,
}

# Catálogo completo resolvido por ``profile_key`` (design D4): as dez
# identidades atômicas apontam para o profile clínico da família. A label é a
# da IDENTIDADE (design D4 — textos determinísticos persistidos pela policy e
# apresentação usam a label canônica, ex.: ``EDA + Cápsula``), enquanto
# ``exam_type`` permanece a chave da família e mantém a dispatch clínica
# exatamente como está (pacotes aplicam as regras do profile de EDA).
_PROFILES_BY_EXAM_TYPE: dict[str, ExamProfile] = {
    definition.code: replace(
        _PROFILES_BY_KEY[definition.profile_key],
        label=definition.label,
    )
    for definition in PROCEDURE_CATALOG
}


def get_exam_profile(exam_type: str | None) -> ExamProfile:
    """Resolve o perfil de procedimento para um tipo de exame (leitura).

    Tipo desconhecido/ausente cai em EDA por compatibilidade — o fallback existe
    SOMENTE para adapters/presenters de artefatos legados (1.1/2.0/3.0).
    Writers novos usam :func:`require_exam_profile`, que falha fechado.
    """
    normalized = (exam_type or "").strip().lower()
    return _PROFILES_BY_EXAM_TYPE.get(normalized, EDA_PROFILE)


def require_exam_profile(exam_type: str) -> ExamProfile:
    """Resolve o perfil de um writer novo, falhando fechado (design D4).

    Código fora do catálogo levanta ``ValueError`` — um writer 4.0 nunca cai
    silenciosamente no profile de EDA.
    """
    normalized = (exam_type or "").strip().lower()
    profile = _PROFILES_BY_EXAM_TYPE.get(normalized)
    if profile is None:
        raise ValueError(f"Procedimento sem profile clínico: {exam_type!r}.")
    return profile
