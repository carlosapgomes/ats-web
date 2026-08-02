"""Unit tests for the canonical priority signal resolver and badge projection.

Covers R1 (persisted field default), R2 (versioned canonical contract),
R3 (pure resolver for the six codes with negations/context) and R4
(badge projection tolerant to malformed payloads).
"""

from __future__ import annotations

import pytest

from apps.cases.priority_signals import (
    CANONICAL_ORDER,
    build_priority_signal_badges,
    resolve_priority_signals,
)


def _structured(**overrides: object) -> dict[str, object]:
    """Default LLM1-shaped payload; overrides replace top-level keys."""
    payload: dict[str, object] = {
        "patient": {"name": "Paciente", "age": 35, "sex": "M"},
        "eda": {
            "indication_category": "other",
            "is_pediatric": False,
            "foreign_body_suspected": False,
            "requested_procedure": {"name": "EDA", "subtype": "standard"},
        },
        "preop_screening": {"rulebook_signals": {"eda_subtype": "standard"}},
    }
    payload.update(overrides)
    return payload


def _resolve(
    structured_data: dict[str, object] | None = None,
    source_text: str = "",
) -> list[dict[str, object]]:
    return resolve_priority_signals(
        structured_data=structured_data or _structured(),
        source_text=source_text,
    )


def _codes(
    structured_data: dict[str, object] | None = None,
    source_text: str = "",
) -> list[str]:
    return [str(s["code"]) for s in _resolve(structured_data, source_text)]


@pytest.mark.django_db
class TestPrioritySignalsField:
    """R1 — Case.priority_signals: default list independente por instância."""

    def test_default_is_independent_empty_list_per_instance(self, user, case_factory) -> None:
        from apps.cases.models import Case

        c1 = case_factory(user)
        c2 = case_factory(user)
        assert c1.priority_signals == []
        assert c2.priority_signals == []
        c1.priority_signals = [{"code": "pediatric", "category": "special_population", "detail": "", "version": 1}]
        c1.save()
        # refresh_from_db conflita com django-fsm (status protected); re-busca.
        assert Case.objects.get(pk=c1.pk).priority_signals != []
        assert Case.objects.get(pk=c2.pk).priority_signals == []

    def test_old_fixture_without_field_defaults_to_empty(self, user, case_factory) -> None:
        case = case_factory(user)
        assert case.priority_signals == []


class TestResolvePrioritySignals:
    """R3 — resolvedor puro, conservador e deduplicado."""

    # ── Pediatria ─────────────────────────────────────────────────────

    def test_pediatric_age_15_is_signal(self) -> None:
        signals = _resolve(_structured(patient={"name": "X", "age": 15, "sex": "M"}))
        assert [s["code"] for s in signals] == ["pediatric"]
        assert signals[0]["detail"] == "15 anos"

    def test_pediatric_age_16_is_not_signal(self) -> None:
        assert _codes(_structured(patient={"name": "X", "age": 16, "sex": "M"})) == []

    def test_pediatric_fallback_flag_without_age(self) -> None:
        payload = _structured(patient={"name": "X", "age": None, "sex": "M"})
        eda = payload["eda"]
        assert isinstance(eda, dict)
        eda["is_pediatric"] = True
        signals = _resolve(payload)
        assert [s["code"] for s in signals] == ["pediatric"]
        assert signals[0]["detail"] == ""

    # ── Corpo estranho ────────────────────────────────────────────────

    def test_foreign_body_from_requested_subtype(self) -> None:
        payload = _structured()
        eda = payload["eda"]
        assert isinstance(eda, dict)
        requested = eda["requested_procedure"]
        assert isinstance(requested, dict)
        requested["subtype"] = "foreign_body"
        rulebook = payload["preop_screening"]
        assert isinstance(rulebook, dict)
        rulebook_signals = rulebook["rulebook_signals"]
        assert isinstance(rulebook_signals, dict)
        rulebook_signals["eda_subtype"] = "foreign_body"
        assert _codes(payload) == ["foreign_body"]

    def test_foreign_body_from_rulebook_subtype_only(self) -> None:
        payload = _structured()
        rulebook = payload["preop_screening"]
        assert isinstance(rulebook, dict)
        rulebook_signals = rulebook["rulebook_signals"]
        assert isinstance(rulebook_signals, dict)
        rulebook_signals["eda_subtype"] = "foreign_body"
        assert _codes(payload) == ["foreign_body"]

    def test_foreign_body_from_indication_category(self) -> None:
        payload = _structured()
        eda = payload["eda"]
        assert isinstance(eda, dict)
        eda["indication_category"] = "foreign_body"
        assert _codes(payload) == ["foreign_body"]

    def test_foreign_body_from_suspected_flag(self) -> None:
        payload = _structured()
        eda = payload["eda"]
        assert isinstance(eda, dict)
        eda["foreign_body_suspected"] = True
        assert _codes(payload) == ["foreign_body"]

    @pytest.mark.parametrize(
        "negated_text",
        [
            "Sem corpo estranho no esôfago.",
            "Corpo estranho descartado na avaliação.",
            "Nega ingestão de corpo estranho.",
            "Não há corpo estranho.",
        ],
    )
    def test_foreign_body_textual_negation(self, negated_text: str) -> None:
        assert _codes(source_text=negated_text) == []

    def test_foreign_body_textual_positive(self) -> None:
        assert _codes(source_text="Suspeita de corpo estranho em esôfago.") == ["foreign_body"]

    def test_structured_foreign_body_prevails_over_textual_negation(self) -> None:
        """Sinal estruturado positivo (solicitação atual) prevalece sobre
        fallback textual negado (menção histórica)."""
        payload = _structured()
        eda = payload["eda"]
        assert isinstance(eda, dict)
        requested = eda["requested_procedure"]
        assert isinstance(requested, dict)
        requested["subtype"] = "foreign_body"
        rulebook = payload["preop_screening"]
        assert isinstance(rulebook, dict)
        rulebook_signals = rulebook["rulebook_signals"]
        assert isinstance(rulebook_signals, dict)
        rulebook_signals["eda_subtype"] = "foreign_body"
        assert _codes(payload, source_text="Relatório anterior: sem corpo estranho.") == ["foreign_body"]

    # ── Históricos/negações não geram sinal (D1) ────────────────────

    @pytest.mark.parametrize(
        "historical_text",
        [
            "Ecoendoscopia realizada em 2023.",
            "Sem indicação de ecoendoscopia.",
            "Dilatação esofágica prévia em 2022.",
            "Sem indicação de dilatação esofágica.",
            "Retirada de corpo estranho realizada em 2022.",
        ],
    )
    def test_historical_or_negated_mentions_do_not_signal(self, historical_text: str) -> None:
        assert _codes(source_text=historical_text) == []

    # ── Corpo estranho misto histórico + atual (D2) ──────────────────

    @pytest.mark.parametrize(
        "mixed_text",
        [
            "Corpo estranho descartado em 2022. Suspeita atual de corpo estranho no esôfago.",
            "Suspeita atual de corpo estranho no esôfago. Corpo estranho descartado em 2022.",
        ],
    )
    def test_foreign_body_mixed_historical_and_current_keeps_signal(self, mixed_text: str) -> None:
        assert _codes(source_text=mixed_text) == ["foreign_body"]

    def test_foreign_body_historical_clause_does_not_cancel_current_request(self) -> None:
        text = "Retirada de corpo estranho realizada em 2022. Suspeita atual de corpo estranho no esôfago."
        assert _codes(source_text=text) == ["foreign_body"]

    # ── Boundaries (D3) ──────────────────────────────────────────────

    @pytest.mark.parametrize(
        "substring_text",
        ["microecoendoscopia", "predilatacao esofagica"],
    )
    def test_substring_inside_larger_word_is_not_signal(self, substring_text: str) -> None:
        assert _codes(source_text=substring_text) == []

    def test_echoendoscopy_historical_clause_does_not_cancel_current_request(self) -> None:
        text = "Ecoendoscopia realizada em 2023. Solicito nova ecoendoscopia para controle."
        assert _codes(source_text=text) == ["echoendoscopy"]

    def test_dilation_historical_clause_does_not_cancel_current_request(self) -> None:
        text = "Dilatação esofágica prévia em 2022. Indicação atual de dilatação esofágica."
        assert _codes(source_text=text) == ["esophageal_dilation"]

    def test_echoendoscopy_not_indicada_is_not_signal(self) -> None:
        assert _codes(source_text="Ecoendoscopia não indicada neste caso.") == []

    # ── Segunda correção: negações diretas (C8) ──────────────────────

    @pytest.mark.parametrize(
        "negated_text",
        [
            "Não solicito ecoendoscopia.",
            "Nega indicação de ecoendoscopia.",
            "Não solicito dilatação esofágica.",
            "Nega corpo estranho.",
            "Não foi identificado corpo estranho.",
            "Ausência de corpo estranho.",
            "Sem evidência de corpo estranho.",
        ],
    )
    def test_direct_negations_do_not_signal(self, negated_text: str) -> None:
        assert _codes(source_text=negated_text) == []

    # ── Segunda correção: históricos/contexto emprestado (C9/C10) ────

    @pytest.mark.parametrize(
        "historical_text",
        [
            "Exame de ecoendoscopia foi realizado em 2023.",
            "Procedimento de dilatação esofágica foi realizado em 2022.",
            "Histórico de corpo estranho em 2022.",
            "Solicito colonoscopia e registro de ecoendoscopia no histórico.",
        ],
    )
    def test_historical_or_borrowed_context_does_not_signal(self, historical_text: str) -> None:
        assert _codes(source_text=historical_text) == []

    # ── Segunda correção: positivos ancorados e coexistência (C10) ───

    @pytest.mark.parametrize(
        "positive_text",
        [
            "Solicito ecoendoscopia.",
            "Solicito eco-endoscopia.",
            "Indicada ultrassonografia endoscópica.",
            "Exame: ultrassom endoscópico.",
            "Motivo da Solicitação: ecoendoscopia.",
            "Ecoendoscopia solicitada.",
            "Dilatação esofágica indicada.",
            "Solicito dilatação do esôfago.",
            "Indicação de dilatação de esôfago.",
            "Procedimento: dilatação esofágica.",
        ],
    )
    def test_positive_request_phrases_still_signal(self, positive_text: str) -> None:
        assert _codes(source_text=positive_text) != []

    def test_coexistence_echoendoscopy_and_dilation(self) -> None:
        assert _codes(source_text="Solicito EDA com ecoendoscopia e dilatação esofágica.") == [
            "echoendoscopy",
            "esophageal_dilation",
        ]

    # ── Segunda correção: ocorrência atual distinta sobrevive (C9/C11) ──

    def test_negated_occurrence_does_not_cancel_distinct_current(self) -> None:
        assert _codes(source_text="Nega corpo estranho. Suspeita atual de corpo estranho.") == ["foreign_body"]

    def test_historical_occurrence_does_not_cancel_distinct_current(self) -> None:
        assert _codes(source_text="Histórico de corpo estranho. Suspeita atual de corpo estranho.") == ["foreign_body"]

    def test_historical_echo_does_not_cancel_current_request(self) -> None:
        assert _codes(source_text="Ecoendoscopia foi realizada em 2023. Solicito nova ecoendoscopia.") == [
            "echoendoscopy"
        ]

    # ── Segunda correção: estruturado positivo prevalece (C12) ────────

    def test_structured_foreign_body_prevails_over_direct_negation(self) -> None:
        payload = _structured()
        eda = payload["eda"]
        assert isinstance(eda, dict)
        requested = eda["requested_procedure"]
        assert isinstance(requested, dict)
        requested["subtype"] = "foreign_body"
        rulebook = payload["preop_screening"]
        assert isinstance(rulebook, dict)
        rulebook_signals = rulebook["rulebook_signals"]
        assert isinstance(rulebook_signals, dict)
        rulebook_signals["eda_subtype"] = "foreign_body"
        assert _codes(payload, source_text="Nega corpo estranho.") == ["foreign_body"]

    def test_structured_echoendoscopy_prevails_over_historical(self) -> None:
        payload = _structured()
        eda = payload["eda"]
        assert isinstance(eda, dict)
        requested = eda["requested_procedure"]
        assert isinstance(requested, dict)
        requested["subtype"] = "echoendoscopy"
        rulebook = payload["preop_screening"]
        assert isinstance(rulebook, dict)
        rulebook_signals = rulebook["rulebook_signals"]
        assert isinstance(rulebook_signals, dict)
        rulebook_signals["eda_subtype"] = "echoendoscopy"
        assert _codes(payload, source_text="Ecoendoscopia foi realizada em 2023.") == ["echoendoscopy"]

    # ── Terceira correção: EUS negado/histórico (C15) ─────────────────

    @pytest.mark.parametrize(
        "negated_eus_text",
        [
            "Não solicito EUS.",
            "Nega indicação de EUS.",
            "Sem indicação de EUS.",
            "Exame de EUS já realizado em 2023.",
        ],
    )
    def test_negated_or_historical_eus_does_not_signal(self, negated_eus_text: str) -> None:
        assert _codes(source_text=negated_eus_text) == []

    # ── Terceira correção: solicitação mista atual (C16) ──────────────

    @pytest.mark.parametrize(
        ("mixed_text", "expected_codes"),
        [
            ("Solicito colonoscopia e ecoendoscopia.", ["echoendoscopy"]),
            ("Solicito CPRE e ecoendoscopia.", ["echoendoscopy"]),
            ("Solicito colonoscopia e dilatação esofágica.", ["esophageal_dilation"]),
            ("Solicito CPRE e EUS.", ["echoendoscopy"]),
        ],
    )
    def test_current_mixed_request_keeps_supported_signal(self, mixed_text: str, expected_codes: list[str]) -> None:
        assert _codes(source_text=mixed_text) == expected_codes

    # ── Terceira correção: equivalentes explícitos (C17) ──────────────

    @pytest.mark.parametrize(
        "explicit_text",
        [
            "Não há indicação de ecoendoscopia.",
            "Não há evidência de corpo estranho.",
            "Nega a indicação de ecoendoscopia.",
            "Ausência de indicação de ecoendoscopia.",
            "Exame de ecoendoscopia já realizado em 2023.",
            "Procedimento de dilatação esofágica já realizado em 2022.",
            "Corpo estranho não identificado.",
        ],
    )
    def test_direct_equivalents_do_not_signal(self, explicit_text: str) -> None:
        assert _codes(source_text=explicit_text) == []

    # ── Terceira correção: caracterizações (C15/C16/C18) ──────────────

    def test_mixed_historical_request_stays_empty(self) -> None:
        assert _codes(source_text="Solicito CPRE e registro de EUS no histórico.") == []

    def test_negated_eus_clause_does_not_cancel_distinct_current_eus(self) -> None:
        assert _codes(source_text="Não solicito EUS. Solicito EUS agora.") == ["echoendoscopy"]

    def test_historical_eus_clause_does_not_cancel_distinct_current_eus(self) -> None:
        assert _codes(source_text="Exame de EUS já realizado. Solicito novo EUS.") == ["echoendoscopy"]

    def test_structured_echoendoscopy_prevails_over_negated_eus_text(self) -> None:
        payload = _structured()
        eda = payload["eda"]
        assert isinstance(eda, dict)
        requested = eda["requested_procedure"]
        assert isinstance(requested, dict)
        requested["subtype"] = "echoendoscopy"
        rulebook = payload["preop_screening"]
        assert isinstance(rulebook, dict)
        rulebook_signals = rulebook["rulebook_signals"]
        assert isinstance(rulebook_signals, dict)
        rulebook_signals["eda_subtype"] = "echoendoscopy"
        assert _codes(payload, source_text="Não solicito EUS.") == ["echoendoscopy"]

    def test_negated_mixed_list_does_not_signal(self) -> None:
        assert _codes(source_text="Não solicito CPRE e EUS.") == []
        assert _codes(source_text="Não solicito EUS e gastrostomia.") == []

    @pytest.mark.parametrize(
        "positive_eus_text",
        [
            "Encaminhamento para EUS.",
            "Solicitação de EUS.",
            "Solicitação: EUS.",
            "Procedimento de EUS indicado.",
            "Exame: EUS.",
            "EUS solicitado.",
            "EUS realizado em 2022 e EUS solicitado agora.",
        ],
    )
    def test_eus_current_request_forms_still_signal(self, positive_eus_text: str) -> None:
        assert _codes(source_text=positive_eus_text) == ["echoendoscopy"]

    # ── Quarta correção: negação/histórico abrangem a lista fechada (C20–C22) ──

    @pytest.mark.parametrize(
        "negated_mixed_text",
        [
            "Nega indicação de CPRE e EUS.",
            "Nega a indicação de colonoscopia e ecoendoscopia.",
            "Sem indicação de CPRE e EUS.",
            "Não há indicação de CPRE e EUS.",
            "Ausência de indicação de colonoscopia e ecoendoscopia.",
        ],
    )
    def test_negation_spans_mixed_list_does_not_signal(self, negated_mixed_text: str) -> None:
        assert _codes(source_text=negated_mixed_text) == []

    @pytest.mark.parametrize(
        "negated_mixed_text",
        [
            "Sem indicação de colonoscopia e ecoendoscopia.",
            "Não há indicação de CPRE e dilatação esofágica.",
            "Ausência de indicação de colonoscopia e gastrostomia.",
        ],
    )
    def test_negation_spans_mixed_list_other_signal_types(self, negated_mixed_text: str) -> None:
        assert _codes(source_text=negated_mixed_text) == []

    @pytest.mark.parametrize(
        "historical_mixed_text",
        [
            "Histórico de solicitação de EUS.",
            "Histórico de solicitação de ecoendoscopia.",
            "Histórico de solicitação de dilatação esofágica.",
            "Histórico de solicitação de CPRE e EUS.",
            "Histórico de indicação de colonoscopia e ecoendoscopia.",
            "Histórico de encaminhamento para CPRE e dilatação esofágica.",
        ],
    )
    def test_history_wrapping_request_stem_does_not_signal(self, historical_mixed_text: str) -> None:
        assert _codes(source_text=historical_mixed_text) == []

    def test_negated_mixed_list_does_not_cancel_distinct_current_request(self) -> None:
        assert _codes(source_text="Nega indicação de CPRE e EUS. Solicito EUS agora.") == ["echoendoscopy"]

    def test_historical_mixed_list_does_not_cancel_distinct_current_request(self) -> None:
        assert _codes(source_text="Histórico de solicitação de CPRE e EUS. Solicito EUS agora.") == ["echoendoscopy"]

    @pytest.mark.parametrize(
        "negated_fb_text",
        [
            "Nega indicação de CPRE e corpo estranho.",
            "Sem indicação de colonoscopia e corpo estranho.",
        ],
    )
    def test_foreign_body_negation_in_recognized_list_does_not_alert(self, negated_fb_text: str) -> None:
        assert _codes(source_text=negated_fb_text) == []

    # ── Ingestão cáustica ─────────────────────────────────────────────

    def test_caustic_positive_with_time_detail(self) -> None:
        signals = _resolve(source_text="Paciente ingeriu soda cáustica há 3 semanas.")
        assert [s["code"] for s in signals] == ["caustic_ingestion"]
        assert signals[0]["detail"] == "há 3 semanas"

    @pytest.mark.parametrize(
        "negated_text",
        [
            "Paciente nega ingestão de cáustico.",
            "Sem ingestão de corrosivos.",
            "Não ingeriu soda cáustica.",
            "Contato com soda cáustica, sem ingestão.",
        ],
    )
    def test_caustic_negation(self, negated_text: str) -> None:
        assert _codes(source_text=negated_text) == []

    # ── Ecoendoscopia ─────────────────────────────────────────────────

    def test_echoendoscopy_from_subtype(self) -> None:
        payload = _structured()
        eda = payload["eda"]
        assert isinstance(eda, dict)
        requested = eda["requested_procedure"]
        assert isinstance(requested, dict)
        requested["subtype"] = "echoendoscopy"
        rulebook = payload["preop_screening"]
        assert isinstance(rulebook, dict)
        rulebook_signals = rulebook["rulebook_signals"]
        assert isinstance(rulebook_signals, dict)
        rulebook_signals["eda_subtype"] = "echoendoscopy"
        assert _codes(payload) == ["echoendoscopy"]

    @pytest.mark.parametrize(
        "term",
        [
            "Solicito ecoendoscopia.",
            "Solicito eco-endoscopia.",
            "Indicada ultrassonografia endoscópica.",
            "Exame: ultrassom endoscópico.",
        ],
    )
    def test_echoendoscopy_full_terms(self, term: str) -> None:
        assert _codes(source_text=term) == ["echoendoscopy"]

    def test_eus_contextual_positive(self) -> None:
        assert _codes(source_text="Solicito EUS para avaliar lesão.") == ["echoendoscopy"]

    def test_eus_isolated_is_not_signal(self) -> None:
        assert _codes(source_text="EUS") == []
        assert _codes(source_text="Paciente realizou EUS em 2024.") == []

    # ── Dilatação esofágica ───────────────────────────────────────────

    def test_esophageal_dilation_from_subtype(self) -> None:
        payload = _structured()
        eda = payload["eda"]
        assert isinstance(eda, dict)
        requested = eda["requested_procedure"]
        assert isinstance(requested, dict)
        requested["subtype"] = "esophageal_dilation"
        rulebook = payload["preop_screening"]
        assert isinstance(rulebook, dict)
        rulebook_signals = rulebook["rulebook_signals"]
        assert isinstance(rulebook_signals, dict)
        rulebook_signals["eda_subtype"] = "esophageal_dilation"
        assert _codes(payload) == ["esophageal_dilation"]

    @pytest.mark.parametrize(
        "term",
        [
            "Dilatação esofágica indicada.",
            "Solicito dilatação do esôfago.",
            "Indicação de dilatação de esôfago.",
        ],
    )
    def test_esophageal_dilation_terms(self, term: str) -> None:
        assert _codes(source_text=term) == ["esophageal_dilation"]

    def test_generic_dilatacao_word_is_not_signal(self) -> None:
        assert _codes(source_text="Solicito dilatação.") == []

    # ── Gastrostomia ──────────────────────────────────────────────────

    def test_gastrostomy_from_subtype(self) -> None:
        payload = _structured()
        eda = payload["eda"]
        assert isinstance(eda, dict)
        requested = eda["requested_procedure"]
        assert isinstance(requested, dict)
        requested["subtype"] = "gastrostomy"
        rulebook = payload["preop_screening"]
        assert isinstance(rulebook, dict)
        rulebook_signals = rulebook["rulebook_signals"]
        assert isinstance(rulebook_signals, dict)
        rulebook_signals["eda_subtype"] = "gastrostomy"
        assert _codes(payload) == ["gastrostomy"]

    @pytest.mark.parametrize(
        "term",
        [
            "Solicito gastrostomia.",
            "Indicado GTT.",
            "Programar PEG.",
        ],
    )
    def test_gastrostomy_terms_with_procedural_context(self, term: str) -> None:
        assert _codes(source_text=term) == ["gastrostomy"]

    def test_gastrostomy_historical_is_not_signal(self) -> None:
        assert _codes(source_text="Paciente com gastrostomia prévia.") == []

    # ── Coexistência, ordem e deduplicação ────────────────────────────

    def test_coexistence_and_canonical_order(self) -> None:
        payload = _structured(patient={"name": "X", "age": 10, "sex": "F"})
        eda = payload["eda"]
        assert isinstance(eda, dict)
        eda["is_pediatric"] = True
        requested = eda["requested_procedure"]
        assert isinstance(requested, dict)
        requested["subtype"] = "foreign_body"
        rulebook = payload["preop_screening"]
        assert isinstance(rulebook, dict)
        rulebook_signals = rulebook["rulebook_signals"]
        assert isinstance(rulebook_signals, dict)
        rulebook_signals["eda_subtype"] = "foreign_body"
        codes = _codes(
            payload,
            source_text="Solicito EDA com ecoendoscopia e gastrostomia. Ingestão de soda cáustica há 2 dias.",
        )
        assert codes == ["foreign_body", "caustic_ingestion", "pediatric", "echoendoscopy", "gastrostomy"]
        assert codes == [c for c in CANONICAL_ORDER if c in codes]

    def test_deduplication_by_code(self) -> None:
        payload = _structured()
        eda = payload["eda"]
        assert isinstance(eda, dict)
        eda["indication_category"] = "foreign_body"
        eda["foreign_body_suspected"] = True
        requested = eda["requested_procedure"]
        assert isinstance(requested, dict)
        requested["subtype"] = "foreign_body"
        rulebook = payload["preop_screening"]
        assert isinstance(rulebook, dict)
        rulebook_signals = rulebook["rulebook_signals"]
        assert isinstance(rulebook_signals, dict)
        rulebook_signals["eda_subtype"] = "foreign_body"
        assert _codes(payload, source_text="Suspeita de corpo estranho.") == ["foreign_body"]

    def test_persisted_format_version_and_category(self) -> None:
        signals = _resolve(source_text="Paciente ingeriu soda cáustica.")
        assert signals[0] == {
            "code": "caustic_ingestion",
            "category": "clinical_alert",
            "detail": "",
            "version": 1,
        }


class TestBuildPrioritySignalBadges:
    """R4 — projeção tolerante a payload malformado, ordem canônica, mesma ênfase."""

    def test_ignores_non_list_payload(self) -> None:
        assert build_priority_signal_badges(None) == []
        assert build_priority_signal_badges("x") == []
        assert build_priority_signal_badges({}) == []
        assert build_priority_signal_badges(42) == []

    def test_ignores_non_dict_items_and_unknown_codes(self) -> None:
        payload: list[object] = [
            "nope",
            {"code": "unknown_code", "version": 1},
            {"code": "foreign_body", "version": 1},
            42,
        ]
        badges = build_priority_signal_badges(payload)
        assert [b["code"] for b in badges] == ["foreign_body"]

    def test_ignores_incompatible_version(self) -> None:
        payload: list[object] = [
            {"code": "pediatric", "version": 1},
            {"code": "gastrostomy", "version": 99},
        ]
        badges = build_priority_signal_badges(payload)
        assert [b["code"] for b in badges] == ["pediatric"]

    def test_dedup_and_canonical_order(self) -> None:
        payload: list[object] = [
            {"code": "gastrostomy", "version": 1},
            {"code": "foreign_body", "version": 1},
            {"code": "gastrostomy", "version": 1},
        ]
        badges = build_priority_signal_badges(payload)
        assert [b["code"] for b in badges] == ["foreign_body", "gastrostomy"]

    def test_foreign_body_and_caustic_same_emphasis_and_css(self) -> None:
        payload: list[object] = [
            {"code": "foreign_body", "version": 1},
            {"code": "caustic_ingestion", "version": 1},
        ]
        badges = build_priority_signal_badges(payload)
        fb = next(b for b in badges if b["code"] == "foreign_body")
        ci = next(b for b in badges if b["code"] == "caustic_ingestion")
        assert fb["emphasis"] == ci["emphasis"] == "warning"
        assert fb["css_class"] == ci["css_class"]

    def test_labels_include_detail_when_safe(self) -> None:
        payload: list[object] = [
            {"code": "caustic_ingestion", "version": 1, "detail": "há 3 semanas"},
            {"code": "pediatric", "version": 1, "detail": "10 anos"},
        ]
        badges = build_priority_signal_badges(payload)
        labels = {b["code"]: b["label"] for b in badges}
        assert "10 anos" in labels["pediatric"]
        assert "há 3 semanas" in labels["caustic_ingestion"]
        for badge in badges:
            assert isinstance(badge["label"], str)
            assert isinstance(badge["css_class"], str)
            assert isinstance(badge["emphasis"], str)
            assert badge["css_class"]
