"""S1 — artefato LLM nao persistivel termina em falha auditada ou job failure.

Contrato: slices/slice-001-persistable-output-and-auditable-failure.md (R1–R6).
Fixtures 100% sinteticas; nenhum acesso a producao ou LLM real.

Fase RED: estes testes comportamentais devem FALHAR contra o baseline
(adulteracao orfa observada em 5074806: save rejeitado + handler que regrava
a instancia contaminada + erro secundario engolido + task com success falso).
"""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest

from apps.cases.models import Case, CaseEvent, CaseStatus
from apps.pipeline.llm import RecordingLlmClient
from apps.pipeline.orchestrator import run_pipeline

# Marcador clinico sintetico: NUNCA pode aparecer em evento/log (R3/R6).
MARKER = "SINTETICO-MARCADOR-NUL-987654"
# Caractere NUL real (o que o PostgreSQL rejeita em JSONB/texto).
NUL = "\x00"


def _reload(case: Case) -> Case:
    return Case.objects.get(case_id=case.case_id)


def _to_llm_struct(case: Case, user: Any) -> Case:
    case.start_processing(user=user)
    case.save()
    case.start_extraction(user=user)
    case.save()
    case.extraction_complete(success=True, user=user)
    case.save()
    return case


def _make_case(
    user: Any,
    *,
    extracted_text: str = "Paciente com dispepsia. Solicito EDA.",
    declared: tuple[str, ...] = ("eda",),
) -> Case:
    from apps.cases.procedures import set_declared_procedures

    case = Case.objects.create(
        created_by=user,
        agency_record_number="12345",
        extracted_text=extracted_text,
    )
    set_declared_procedures(case=case, procedure_types=declared, actor=user)
    return _to_llm_struct(case, user)


def _min_exam_ok() -> dict[str, str]:
    return {
        "hb_numeric_present": "yes",
        "platelets_numeric_present": "yes",
        "tp_inr_rni_numeric_present": "yes",
        "ttpa_present": "yes",
        "urea_present": "yes",
        "creatinine_present": "yes",
    }


def _llm1_v2(
    *,
    procedures: list[dict[str, Any]],
    one_liner: str = "EDA eletiva indicada.",
) -> str:
    return json.dumps(
        {
            "schema_version": "4.0",
            "language": "pt-BR",
            "agency_record_number": "12345",
            "patient": {"name": "Paciente", "age": 35, "sex": "F", "document_id": None},
            "common_preop": {
                "labs": {"hb_g_dl": 13.0, "platelets_per_mm3": 200000, "inr": 1.0, "source_text_hint": None},
                "ecg": {"report_present": "unknown", "abnormal_flag": "unknown", "source_text_hint": None},
                "asa": {"bucket": "I-II", "source_text_hint": None},
                "cardiovascular_risk": {"level": "low", "source_text_hint": None},
                "rulebook_signals": {
                    "eda_subtype": "standard",
                    "minimum_exam_evidence": _min_exam_ok(),
                    "conditional_exam_requirements": {},
                    "clinical_flags": {},
                },
                "comorbidities_described": [],
                "medications_described": [],
                "evidence_spans": [],
            },
            "requested_procedures": procedures,
            "policy_precheck": {
                "excluded_from_eda_flow": False,
                "exclusion_reason": None,
                "labs_required": True,
                "labs_pass": "yes",
                "labs_failed_items": [],
                "ecg_required": False,
                "ecg_present": "unknown",
                "pediatric_flag": False,
                "notes": None,
            },
            "summary": {"one_liner": one_liner, "bullet_points": ["Ponto 1", "Ponto 2", "Ponto 3"]},
            "extraction_quality": {"confidence": "alta", "missing_fields": [], "notes": None},
            "origin_context": {
                "city": None,
                "hospital": None,
                "unit": None,
                "state_uf": None,
                "source_text_hint": None,
            },
            "transfusion": {"had_transfusion": "no"},
            "tracked_exams": [],
        }
    )


def _eda_procedure(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "procedure_type": "eda",
        "name": "EDA",
        "urgency": "eletivo",
        "indication_category": "dyspepsia",
        "subtype": "standard",
        "evidence_spans": [{"field_path": "p.0", "excerpt": "Solicito EDA"}],
    }
    item.update(overrides)
    return item


def _llm2_v2(case_id: str, *, procedure_type: str = "eda", rationale_details: list[str] | None = None) -> str:
    # O contrato exige >= 2 detalhes em rationale.details.
    return json.dumps(
        {
            "schema_version": "4.0",
            "language": "pt-BR",
            "case_id": case_id,
            "agency_record_number": "12345",
            "procedure_recommendations": [
                {
                    "procedure_type": procedure_type,
                    "suggestion": "accept",
                    "support_recommendation": "none",
                    "rationale": {
                        "short_reason": "Criterios atendidos.",
                        "details": rationale_details or ["Sem contraindicacao relevante.", "Exames compativeis."],
                        "missing_info_questions": [],
                    },
                    "policy_alignment": {
                        "excluded_request": False,
                        "labs_ok": "yes",
                        "ecg_ok": "yes",
                        "pediatric_flag": False,
                        "notes": None,
                    },
                    "confidence": "alta",
                }
            ],
            "global_support_recommendation": "none",
            "summary": None,
        }
    )


def _failed_event(case: Case) -> CaseEvent:
    return CaseEvent.objects.filter(case=case, event_type="PIPELINE_FAILED").latest("timestamp")


def _payload_text(payload: Any) -> str:
    return json.dumps(payload or {}, ensure_ascii=False, default=str)


class TestPersistabilityHelperUnit:
    """R1: guard recursivo puro (sem banco); positivo/negativo + literal."""

    def test_nested_nul_detected_with_structural_path(self) -> None:
        from apps.pipeline.persistability import LlmOutputNotPersistableError, assert_persistable

        value = {
            "summary": {"one_liner": "limpo"},
            "requested_procedures": [{"name": f"EDA {NUL}", "deep": {"k": ["ok", f"x{NUL}"]}}],
        }
        try:
            assert_persistable(value, stage="llm1", path="structured_data")
        except LlmOutputNotPersistableError as exc:
            assert exc.error_code == "llm_output_not_persistable"
            assert exc.stage == "llm1"
            # P1-B: caminho puramente estrutural — nenhum texto de chave.
            assert exc.path == "structured_data[key][0][key]"
            assert NUL not in str(exc)
            assert NUL not in exc.path
            assert "requested_procedures" not in exc.path
            assert "name" not in exc.path
        else:
            raise AssertionError("NUL aninhado deveria ser rejeitado")

    def test_nul_in_dict_key_rejected_without_key_text(self) -> None:
        from apps.pipeline.persistability import LlmOutputNotPersistableError, assert_persistable

        evil_key = f"chave clinica {MARKER}{NUL}"
        with pytest.raises(LlmOutputNotPersistableError) as exc_info:
            assert_persistable({evil_key: "valor"}, stage="llm2")
        exc = exc_info.value
        # P1-B: a chave rejeitada (com NUL) nao contamina o diagnostico —
        # caso contrario o proprio payload de falha seria rejeitado pelo
        # PostgreSQL e o texto clinico vazaria para logs.
        assert exc.path == "output[key]"
        assert NUL not in exc.path
        assert NUL not in str(exc)
        assert MARKER not in exc.path
        assert MARKER not in str(exc)
        assert evil_key not in exc.path
        assert evil_key not in str(exc)

    def test_clean_dict_key_text_never_enters_diagnostic_path(self) -> None:
        from apps.pipeline.persistability import LlmOutputNotPersistableError, assert_persistable

        clinical_key = f"campo com texto clinico {MARKER}"
        with pytest.raises(LlmOutputNotPersistableError) as exc_info:
            assert_persistable({clinical_key: f"valor{NUL}"}, stage="llm1", path="structured_data")
        exc = exc_info.value
        assert exc.path == "structured_data[key]"
        assert MARKER not in exc.path
        assert MARKER not in str(exc)
        assert clinical_key not in exc.path
        assert clinical_key not in str(exc)

    def test_clean_and_literal_structures_pass_unmodified(self) -> None:
        from apps.pipeline.persistability import assert_persistable

        literal = "texto com literal barra-u-0000: \\u0000 intacto"
        value: dict[str, Any] = {"a": [literal, 42, None, True], "b": {"c": literal}}
        assert_persistable(value, stage="llm1")
        assert_persistable(literal, stage="llm1")
        assert value["a"][0] == literal

    def test_stage_helpers_route_llm1_and_llm2(self) -> None:
        from apps.pipeline.persistability import (
            LlmOutputNotPersistableError,
            assert_llm1_persistable,
            assert_llm2_persistable,
        )

        with pytest.raises(LlmOutputNotPersistableError) as exc1:
            assert_llm1_persistable(structured_data={"k": f"v{NUL}"}, summary_text="ok")
        assert exc1.value.stage == "llm1"
        with pytest.raises(LlmOutputNotPersistableError) as exc2:
            assert_llm2_persistable(procedure_recommendations=[{"rationale": f"r{NUL}"}])
        assert exc2.value.stage == "llm2"
        # Válidos passam.
        assert_llm1_persistable(structured_data={"k": "v"}, summary_text="ok")
        assert_llm2_persistable(procedure_recommendations=[{"rationale": "r"}])


@pytest.mark.django_db
class TestNulRejectedBeforeWrites:
    """R1/R2: NUL decodificado rejeitado antes de writes; dois estagios."""

    def test_nul_in_llm1_fails_audited_without_llm2_or_doctor(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="s1_nul1", password="pw")
        case = _make_case(user)
        contaminated = _llm1_v2(
            procedures=[_eda_procedure(name=f"EDA {MARKER}{NUL} aninhado")],
        )
        client = RecordingLlmClient(responses=[contaminated, _llm2_v2(str(case.case_id))])

        run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")

        case = _reload(case)
        assert case.status == CaseStatus.FAILED
        failed = _failed_event(case)
        assert failed.payload.get("error_code") == "llm_output_not_persistable"
        assert failed.payload.get("stage") == "llm1"
        # Nenhum write indevido: LLM2 nunca roda, medico nunca ve o caso.
        assert len(client.calls) == 1
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_READY_FOR_DOCTOR").exists()
        assert MARKER not in _payload_text(failed.payload)

    def test_nul_in_llm2_keeps_valid_llm1_artifacts(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="s1_nul2", password="pw")
        case = _make_case(user)
        client = RecordingLlmClient(
            responses=[
                _llm1_v2(procedures=[_eda_procedure()]),
                _llm2_v2(str(case.case_id), rationale_details=["Detalhe limpo.", f"Detalhe {MARKER}{NUL}"]),
            ]
        )

        run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")

        case = _reload(case)
        assert case.status == CaseStatus.FAILED
        assert case.status != CaseStatus.WAIT_DOCTOR
        failed = _failed_event(case)
        assert failed.payload.get("error_code") == "llm_output_not_persistable"
        assert failed.payload.get("stage") == "llm2"
        # Artefatos validos anteriores preservados e auditaveis.
        assert isinstance(case.structured_data, dict)
        assert CaseEvent.objects.filter(case=case, event_type="LLM1_OK").exists()
        assert MARKER not in _payload_text(failed.payload)
        assert MARKER not in _payload_text(case.structured_data)

    def test_nul_key_in_llm1_recovers_to_audited_failed(
        self, django_user_model, caplog: pytest.LogCaptureFixture
    ) -> None:
        """P1-B/R3: chave com NUL termina em FAILED auditavel com payload seguro.

        A camada de servico pode rejeitar a chave antes do guard (erro de
        validacao sanitizado); em ambos os ramos o desfecho persiste via
        handler limpo — o que antes falharia de novo no PostgreSQL.
        """
        user = django_user_model.objects.create_user(username="s1_nulkey", password="pw")
        case = _make_case(user)
        evil_item = _eda_procedure()
        evil_item[f"campo clinico {MARKER}{NUL}"] = "valor"
        contaminated = _llm1_v2(procedures=[evil_item])
        client = RecordingLlmClient(responses=[contaminated, _llm2_v2(str(case.case_id))])

        with caplog.at_level(logging.ERROR, logger="apps.pipeline.orchestrator"):
            run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")

        case = _reload(case)
        assert case.status == CaseStatus.FAILED
        failed = _failed_event(case)
        # Guard (llm_output_not_persistable) ou validacao sanitizada do
        # servico: ambos codigos tecnicos, nunca texto clinico/DB.
        assert failed.payload.get("error_code") in ("llm_output_not_persistable", "Llm1V4ValidationError")
        # Nem NUL nem texto clinico da chave vazam para payload ou log.
        assert NUL not in _payload_text(failed.payload)
        assert MARKER not in _payload_text(failed.payload)
        assert MARKER not in caplog.text
        assert NUL not in caplog.text

    def test_guard_nul_key_error_flows_through_clean_handler(self, django_user_model) -> None:
        """P1-B: diagnostico do guard (chave com NUL) persiste via handler limpo.

        Composicao deterministica: o erro do guard alimenta diretamente o
        handler real com writes reais — prova que caminho/mensagem seguros
        atravessam PIPELINE_FAILED/FAILED no PostgreSQL.
        """
        from apps.pipeline.orchestrator import _record_pipeline_failure
        from apps.pipeline.persistability import assert_llm1_persistable

        user = django_user_model.objects.create_user(username="s1_nulkey2", password="pw")
        case = _make_case(user)
        assert case.status == CaseStatus.LLM_STRUCT

        with pytest.raises(Exception) as guard_exc:
            assert_llm1_persistable(
                structured_data={f"campo clinico {MARKER}{NUL}": "valor"},
                summary_text="resumo limpo",
            )
        guard_error = guard_exc.value

        _record_pipeline_failure(case_id=case.case_id, error=guard_error)

        case = _reload(case)
        assert case.status == CaseStatus.FAILED
        failed = _failed_event(case)
        assert failed.payload.get("error_code") == "llm_output_not_persistable"
        assert failed.payload.get("stage") == "llm1"
        assert NUL not in _payload_text(failed.payload)
        assert MARKER not in _payload_text(failed.payload)


@pytest.mark.django_db
class TestSaveFailureHasCleanAuditableOutcome:
    """R3: falha real de save gera FAILED auditavel com instancia limpa."""

    def test_generic_persistence_failure_uses_safe_payload(self, django_user_model, monkeypatch) -> None:
        from django.db import DatabaseError

        user = django_user_model.objects.create_user(username="s1_r3", password="pw")
        case = _make_case(user)
        client = RecordingLlmClient(responses=[_llm1_v2(procedures=[_eda_procedure()]), _llm2_v2(str(case.case_id))])

        real_save = Case.save
        calls = {"n": 0}

        def _flaky_save(self, *args: Any, **kwargs: Any) -> None:
            calls["n"] += 1
            if calls["n"] == 1:
                # Simula CONTEXT clinico do driver (texto recusado no erro).
                raise DatabaseError(f"save recusado; CONTEXT recusado: {MARKER} detalhe sigiloso")
            return real_save(self, *args, **kwargs)

        monkeypatch.setattr(Case, "save", _flaky_save)

        run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")

        case = _reload(case)
        assert case.status == CaseStatus.FAILED
        failed = _failed_event(case)
        assert MARKER not in _payload_text(failed.payload)
        assert MARKER not in _payload_text(failed.payload.get("message", ""))
        # Timeline SSR atual reconhece o rotulo de falha (sem ampliar UX).
        from apps.intake.views import EVENT_LABELS

        assert EVENT_LABELS.get("PIPELINE_FAILED")

    def test_postgres_rejects_nul_in_jsonb(self, django_user_model) -> None:
        """Caracteriza o mecanismo do incidente: NUL nao persiste em JSONB."""
        from django.db import DatabaseError

        user = django_user_model.objects.create_user(username="s1_r3b", password="pw")
        case = _make_case(user)
        case.structured_data = {"chave": f"texto {NUL} invalido"}
        with pytest.raises(DatabaseError):
            case.save()

    def test_real_rejected_save_recovers_to_audited_failed(self, django_user_model) -> None:
        """R3 (evidencia vinculada P1-A): rejeicao REAL do PostgreSQL → FAILED auditado.

        A rejeicao e autentica (sem monkeypatch no save que falha): um save
        contaminado e rejeitado pelo banco, e o handler real recupera com
        instancia limpa e writes reais. Distingue-se do fault-injection
        acima, onde a falha do primeiro save e simulada.
        """
        from django.db import DatabaseError, transaction

        from apps.pipeline.orchestrator import _record_pipeline_failure

        user = django_user_model.objects.create_user(username="s1_r3c", password="pw")
        case = _make_case(user)
        assert case.status == CaseStatus.LLM_STRUCT

        contaminated = Case.objects.get(case_id=case.case_id)
        contaminated.structured_data = {"chave": f"texto {MARKER}{NUL} rejeitado"}
        with pytest.raises(DatabaseError) as exc_info:
            with transaction.atomic():
                contaminated.save()
        real_error = exc_info.value
        # A instancia contaminada e descartada; o handler usa reload limpo.
        del contaminated

        _record_pipeline_failure(case_id=case.case_id, error=real_error)

        case = _reload(case)
        assert case.status == CaseStatus.FAILED
        failed = _failed_event(case)
        assert NUL not in _payload_text(failed.payload)
        assert MARKER not in _payload_text(failed.payload)
        assert CaseEvent.objects.filter(case=case, event_type="LLM1_FAILED").exists()

    def test_secondary_failure_rolls_back_partial_outcome(self, django_user_model, monkeypatch) -> None:
        """P1-A: falha no segundo save reverte o evento parcial e propaga.

        Evento + desfecho FSM confirmam juntos numa transacao curta; se a
        transicao/save falhar, nenhum PIPELINE_FAILED parcial permanece e a
        excecao secundaria sai (sem sucesso falso).
        """
        from django.db import DatabaseError

        user = django_user_model.objects.create_user(username="s1_r3d", password="pw")
        case = _make_case(user)

        real_save = Case.save
        calls = {"n": 0}

        def _second_save_fails(self, *args: Any, **kwargs: Any) -> None:
            calls["n"] += 1
            if calls["n"] == 2:
                raise DatabaseError("banco indisponivel na transicao")
            return real_save(self, *args, **kwargs)

        monkeypatch.setattr(Case, "save", _second_save_fails)

        from apps.pipeline.orchestrator import _record_pipeline_failure

        with pytest.raises(DatabaseError):
            _record_pipeline_failure(case_id=case.case_id, error=ValueError("falha original"))

        case = _reload(case)
        assert case.status == CaseStatus.LLM_STRUCT
        assert not CaseEvent.objects.filter(case=case, event_type="PIPELINE_FAILED").exists()


@pytest.mark.django_db
class TestConcurrentAdvanceNeverRegresses:
    """P1-A: avanco concorrente confirmado antes do handler nunca e sobrescrito.

    Simula a corrida de forma deterministica: outro ator avanca o estado
    persistido (LLM_STRUCT → WAIT_DOCTOR via pipeline valido) antes da
    entrega tardia da falha. O handler le o estado persistido sob row lock
    e registra conflito auditado sem regressao — nunca salva FAILED por cima
    de WAIT_DOCTOR nem reescreve artefatos. A checagem in-memory de
    TransitionNotAllowed, sozinha, nao detectaria essa corrida.
    """

    def test_late_failure_after_doctor_advance_keeps_wait_doctor(self, django_user_model) -> None:
        from apps.pipeline.orchestrator import _record_pipeline_failure

        user = django_user_model.objects.create_user(username="s1_race", password="pw")
        case = _make_case(user)
        client = RecordingLlmClient(responses=[_llm1_v2(procedures=[_eda_procedure()]), _llm2_v2(str(case.case_id))])
        run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")
        case = _reload(case)
        assert case.status == CaseStatus.WAIT_DOCTOR
        before_types = sorted(e.event_type for e in CaseEvent.objects.filter(case=case))
        before_action = json.dumps(case.suggested_action or {}, sort_keys=True, default=str)
        before_structured = json.dumps(case.structured_data or {}, sort_keys=True, default=str)

        # Falha tardia (ex.: excecao de outro ramo) entregue apos o avanco.
        with pytest.raises(ValueError, match="falha tardia"):
            _record_pipeline_failure(case_id=case.case_id, error=ValueError("falha tardia"))

        case = _reload(case)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert json.dumps(case.suggested_action or {}, sort_keys=True, default=str) == before_action
        assert json.dumps(case.structured_data or {}, sort_keys=True, default=str) == before_structured
        for event_type in before_types:
            assert event_type in sorted(e.event_type for e in CaseEvent.objects.filter(case=case))
        conflict = _failed_event(case)
        assert conflict.payload.get("persisted_status") == CaseStatus.WAIT_DOCTOR
        assert conflict.payload.get("stage_conflict") is True


@pytest.mark.django_db(transaction=True)
class TestFailureBoundarySerializesCompetitor:
    """P1-A: lock da fronteira serializa avanco concorrente (PostgreSQL real).

    Dois atores em conexoes separadas, ordenados por eventos (sem sleep): o
    handler adquire o row lock e pausa no primeiro save; o competidor tenta
    `select_for_update(nowait=True)` e DEVE ser bloqueado — prova que o lock
    e mantido durante evento+transicao. Apos o commit, o competidor le o
    desfecho (FAILED) em vez de intercalar um write.
    """

    def test_competing_advance_blocks_until_handler_commits(self, django_user_model, monkeypatch) -> None:
        import threading

        from django.db import connection
        from django.db.models.query import QuerySet
        from django.db.utils import OperationalError

        from apps.pipeline.orchestrator import _record_pipeline_failure

        user = django_user_model.objects.create_user(username="s1_lockrace", password="pw")
        case = _make_case(user)
        case_id = case.case_id
        assert Case.objects.get(case_id=case_id).status == CaseStatus.LLM_STRUCT

        h_locked = threading.Event()
        h_saving = threading.Event()
        c_attempted = threading.Event()
        h_done = threading.Event()
        c_done = threading.Event()
        guard = threading.Lock()
        state = {"h_ident": None, "blocked": None, "competitor_seen": None, "handler_error": None}
        save_calls = {"n": 0}

        real_select_for_update = QuerySet.select_for_update
        real_save = Case.save

        def _spy_select_for_update(self, *args: Any, **kwargs: Any):
            if kwargs.get("nowait"):
                return real_select_for_update(self, *args, **kwargs)
            watched = real_select_for_update(self, *args, **kwargs)
            with guard:
                if state["h_ident"] is None:
                    state["h_ident"] = threading.get_ident()
            h_locked.set()
            return watched

        def _spy_save(self, *args: Any, **kwargs: Any):
            with guard:
                is_handler = state["h_ident"] is not None and threading.get_ident() == state["h_ident"]
                if is_handler:
                    save_calls["n"] += 1
                    first = save_calls["n"] == 1
                else:
                    first = False
            if first:
                h_saving.set()
                assert c_attempted.wait(timeout=30), "competidor nao tentou com lock mantido"
            return real_save(self, *args, **kwargs)

        monkeypatch.setattr(QuerySet, "select_for_update", _spy_select_for_update)
        monkeypatch.setattr(Case, "save", _spy_save)

        def _run_handler() -> None:
            try:
                _record_pipeline_failure(case_id=case_id, error=ValueError("falha concorrente"))
            except Exception as exc:  # noqa: BLE001 - registrada e asseverada no fio principal
                state["handler_error"] = exc
            finally:
                try:
                    connection.close()
                finally:
                    h_done.set()

        def _run_competitor() -> None:
            from django.db import transaction

            try:
                assert h_saving.wait(timeout=30), "handler nao alcancou o save"
                try:
                    with transaction.atomic():
                        list(Case.objects.select_for_update(nowait=True).filter(case_id=case_id))
                except OperationalError:
                    state["blocked"] = True
                else:
                    state["blocked"] = False
                finally:
                    c_attempted.set()
                assert h_done.wait(timeout=30), "handler nao concluiu"
                with transaction.atomic():
                    seen = Case.objects.select_for_update().get(case_id=case_id)
                state["competitor_seen"] = seen.status
            finally:
                try:
                    connection.close()
                finally:
                    c_done.set()

        handler_thread = threading.Thread(target=_run_handler, daemon=True)
        handler_thread.start()
        try:
            assert h_locked.wait(timeout=30), "handler nao adquiriu o lock"
            competitor_thread = threading.Thread(target=_run_competitor, daemon=True)
            competitor_thread.start()
            try:
                assert c_done.wait(timeout=60), "competidor nao concluiu"
            finally:
                competitor_thread.join(timeout=30)
        finally:
            handler_thread.join(timeout=30)

        assert state["handler_error"] is None
        assert state["blocked"] is True, "competidor deveria bloquear com o lock do handler mantido"
        assert state["competitor_seen"] == CaseStatus.FAILED
        final = Case.objects.get(case_id=case_id)
        assert final.status == CaseStatus.FAILED
        assert CaseEvent.objects.filter(case=final, event_type="PIPELINE_FAILED").exists()
        assert CaseEvent.objects.filter(case=final, event_type="LLM1_FAILED").exists()


@pytest.mark.django_db
class TestSecondaryFailurePropagates:
    """R4: se o desfecho de erro nao persiste, excecao sai (sem sucesso falso)."""

    def test_failure_recording_error_reaches_worker_boundary(self, django_user_model, monkeypatch) -> None:
        from django.db import DatabaseError

        user = django_user_model.objects.create_user(username="s1_r4", password="pw")
        case = _make_case(user)
        client = RecordingLlmClient(responses=["nao json"])

        def _always_fail_save(self, *args: Any, **kwargs: Any) -> None:
            raise DatabaseError("banco indisponivel")

        monkeypatch.setattr(Case, "save", _always_fail_save)

        from apps.pipeline.tasks import execute_pipeline

        with pytest.raises(DatabaseError):
            run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")
        with pytest.raises(DatabaseError):
            execute_pipeline(str(case.case_id))


@pytest.mark.django_db
class TestAdvancedStateNeverRegresses:
    """R5: estado avancado nao regride; historico nao e reescrito."""

    @pytest.mark.parametrize("target", ["wait_doctor", "cleaned"])
    def test_stale_failure_keeps_advanced_state(self, django_user_model, target: str) -> None:
        user = django_user_model.objects.create_user(username=f"s1_r5_{target}", password="pw")
        case = _make_case(user)
        client = RecordingLlmClient(responses=[_llm1_v2(procedures=[_eda_procedure()]), _llm2_v2(str(case.case_id))])
        run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")
        case = _reload(case)
        assert case.status == CaseStatus.WAIT_DOCTOR
        if target == "cleaned":
            case.administratively_close(user=user, payload={"reason": "sintetico"})
            case.save()
            case = _reload(case)
            assert case.status == CaseStatus.CLEANED
        before_types = sorted(e.event_type for e in CaseEvent.objects.filter(case=case))
        before_action = json.dumps(case.suggested_action or {}, sort_keys=True, default=str)

        stale_client = RecordingLlmClient(
            responses=[_llm1_v2(procedures=[_eda_procedure()]), _llm2_v2(str(case.case_id))]
        )
        with pytest.raises(Exception):
            run_pipeline(case.case_id, llm_client=stale_client, llm1_system_prompt="sp1", llm1_user_template="ut1")

        case = _reload(case)
        assert case.status == CaseStatus(target.upper())
        after_types = sorted(e.event_type for e in CaseEvent.objects.filter(case=case))
        for event_type in before_types:
            assert event_type in after_types
        assert json.dumps(case.suggested_action or {}, sort_keys=True, default=str) == before_action


@pytest.mark.django_db
class TestSafeErrorLogs:
    """R6: logs de erro nao despejam marcador clinico; sem retry LLM novo."""

    def test_nul_failure_logs_without_clinical_marker(
        self, django_user_model, caplog: pytest.LogCaptureFixture
    ) -> None:
        user = django_user_model.objects.create_user(username="s1_r6", password="pw")
        case = _make_case(user)
        contaminated = _llm1_v2(procedures=[_eda_procedure(name=f"EDA {MARKER}{NUL}")])
        client = RecordingLlmClient(responses=[contaminated])

        with caplog.at_level(logging.ERROR, logger="apps.pipeline.orchestrator"):
            run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")

        assert MARKER not in caplog.text
        # Sem retry LLM novo: exatamente 1 chamada fisica.
        assert len(client.calls) == 1

    def test_schema_validation_failure_hides_raw_values(
        self, django_user_model, caplog: pytest.LogCaptureFixture
    ) -> None:
        """R3/R6: mensagem de validacao pydantic carrega input cru; suprimir."""
        user = django_user_model.objects.create_user(username="s1_r6b", password="pw")
        case = _make_case(user)
        # details como string: pydantic relata input_value com o marcador.
        bad_llm2 = json.dumps(
            {
                "schema_version": "4.0",
                "language": "pt-BR",
                "case_id": str(case.case_id),
                "agency_record_number": "12345",
                "procedure_recommendations": [
                    {
                        "procedure_type": "eda",
                        "suggestion": "accept",
                        "support_recommendation": "none",
                        "rationale": {
                            "short_reason": "Criterios atendidos.",
                            "details": f"texto cru {MARKER}",
                            "missing_info_questions": [],
                        },
                        "policy_alignment": {
                            "excluded_request": False,
                            "labs_ok": "yes",
                            "ecg_ok": "yes",
                            "pediatric_flag": False,
                            "notes": None,
                        },
                        "confidence": "alta",
                    }
                ],
                "global_support_recommendation": "none",
                "summary": None,
            }
        )
        client = RecordingLlmClient(responses=[_llm1_v2(procedures=[_eda_procedure()]), bad_llm2])

        with caplog.at_level(logging.ERROR, logger="apps.pipeline.orchestrator"):
            run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")

        case = _reload(case)
        assert case.status == CaseStatus.FAILED
        failed = _failed_event(case)
        assert MARKER not in _payload_text(failed.payload)
        assert MARKER not in caplog.text


@pytest.mark.django_db
class TestFailedTimelineRendersSsr:
    """Runtime/SSR: detalhe autorizado reconhece o rotulo de falha (R3)."""

    def test_nir_case_detail_shows_failure_label(self, django_user_model, client) -> None:
        from django.contrib.auth import get_user_model

        from apps.accounts.models import Role

        user_model = get_user_model()
        user = user_model.objects.create_user(username="s1_ssr_nir", password="pw")
        role, _ = Role.objects.get_or_create(name="nir")
        user.roles.add(role)
        client.force_login(user)
        session = client.session
        session["active_role"] = "nir"
        session.save()

        case = _make_case(user)
        contaminated = _llm1_v2(procedures=[_eda_procedure(name=f"EDA {NUL}")])
        llm_client = RecordingLlmClient(responses=[contaminated])
        run_pipeline(case.case_id, llm_client=llm_client, llm1_system_prompt="sp1", llm1_user_template="ut1")
        case = _reload(case)
        assert case.status == CaseStatus.FAILED

        from django.urls import reverse

        response = client.get(reverse("intake:case_detail", args=[str(case.case_id)]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Falha no processamento" in content
