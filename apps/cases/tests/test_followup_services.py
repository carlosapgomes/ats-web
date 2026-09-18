"""Testes do serviço de follow-up de desfecho (registro do supervisor)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext

from apps.cases.followup import (
    LEGACY_UNMAPPED_REASON,
    ProcedureOutcomeInput,
    current_follow_ups,
    get_current_follow_up,
    is_unmapped_legacy_follow_up,
    project_non_performance_reason,
    record_case_follow_up,
    unmapped_legacy_follow_up_ids,
)
from apps.cases.models import (
    CURRENT_FOLLOWUP_NON_PERFORMANCE_REASON_CHOICES,
    CURRENT_FOLLOWUP_NON_PERFORMANCE_REASON_VALUES,
    Case,
    CaseEvent,
    CaseFollowUp,
    CaseProcedure,
    DoctorDisposition,
    FollowUpNonPerformanceReason,
    FollowUpResourceShortageDetail,
    ProcedureFollowUp,
)

pytestmark = pytest.mark.django_db

# Catálogo oficial da ficha de suspensão (design D1): ordem e labels exatos.
# É a expectativa literal que pina a constante usada pelo form e pelo service.
_OFFICIAL_CATALOG: tuple[tuple[str, str], ...] = (
    ("missing_exam_consent", "Ausência do preenchimento do TCLE para realização de exame"),
    ("missing_anesthesia_consent", "Ausência do preenchimento do TCLE anestésico"),
    ("clinical_conditions", "Condições clínicas desfavoráveis"),
    ("scheduling_error", "Erro na programação do procedimento"),
    ("missing_gastroenterologist", "Falta de médico gastroenterologista"),
    ("missing_anesthesiologist", "Falta de anestesiologista"),
    ("missing_equipment", "Falta de equipamentos"),
    ("missing_tests", "Falta de exames"),
    ("missing_blood_products", "Falta de hemoderivados"),
    ("fasting_not_observed", "Falta de jejum"),
    ("missing_material_opme", "Falta de material/OPME"),
    ("missing_icu_bed", "Falta de vaga na UTI"),
    ("inadequate_prep", "Preparo inadequado"),
    ("difficult_intubation", "Intubação difícil"),
    ("medical_plan_changed", "Mudança de conduta médica"),
    ("patient_no_show", "Não comparecimento do paciente"),
    ("patient_death", "Paciente foi a óbito"),
    ("emergency_priority", "Prioridade para urgência"),
    ("time_exceeded", "Tempo excedido"),
    ("transferred_other_hospital", "Transferência para outro hospital"),
    ("patient_delay", "Atraso do paciente"),
    ("divergent_report", "Relatório divergente"),
    ("patient_refusal", "Recusa do paciente"),
    ("other", "Outras causas"),
)
_OFFICIAL_REASON_IDS = [value for value, _label in _OFFICIAL_CATALOG]

# ── Helpers ──────────────────────────────────────────────────────────────


def _case_with_procedures(
    case_factory: Callable[..., Case],
    user: Any,
    types: tuple[str, ...] = ("eda",),
) -> Case:
    """Caso elegível com rows declaradas e autorizadas (universo do follow-up)."""
    case = case_factory(user)
    for procedure_type in types:
        CaseProcedure.objects.create(
            case=case,
            procedure_type=procedure_type,
            doctor_disposition=DoctorDisposition.APPROVED,
        )
    return case


def _procedure_ids(case: Case) -> list[int]:
    return list(case.procedures.order_by("id").values_list("id", flat=True))


def _outcome(case: Case, *, performed: bool = True, reason: str = "", detail: str = "", other: str = ""):
    procedure_id = _procedure_ids(case)[0]
    return ProcedureOutcomeInput(
        procedure_id=procedure_id,
        performed=performed,
        non_performance_reason=reason,
        resource_shortage_detail=detail,
        other_reason=other,
    )


# ── R1: catálogo oficial × eras persistidas ───────────────────────────────


class TestCatalogoOficial:
    """R1 — catálogo atual é a fonte única das choices de entrada.

    O model state continua reconhecendo os códigos legados persistidos; apenas
    as 24 choices atuais ordenadas podem ser gravadas (design D1/D2).
    """

    def test_current_choices_seguem_ordem_e_labels_oficiais(self) -> None:
        assert CURRENT_FOLLOWUP_NON_PERFORMANCE_REASON_CHOICES == _OFFICIAL_CATALOG

    def test_current_values_derivam_das_choices(self) -> None:
        assert CURRENT_FOLLOWUP_NON_PERFORMANCE_REASON_VALUES == frozenset(_OFFICIAL_REASON_IDS)
        assert len(CURRENT_FOLLOWUP_NON_PERFORMANCE_REASON_VALUES) == 24

    def test_model_state_reconhece_eram_legada_e_atual(self) -> None:
        persisted = set(FollowUpNonPerformanceReason.values)
        assert set(CURRENT_FOLLOWUP_NON_PERFORMANCE_REASON_VALUES) <= persisted
        assert persisted == set(CURRENT_FOLLOWUP_NON_PERFORMANCE_REASON_VALUES) | {
            "absenteeism",
            "resource_shortage",
        }

    def test_codigos_preservados_de_inadequate_prep_e_other(self) -> None:
        assert FollowUpNonPerformanceReason.INADEQUATE_PREP.value == "inadequate_prep"
        assert FollowUpNonPerformanceReason.OTHER.value == "other"

    def test_nenhum_codigo_excede_o_max_length_do_field(self) -> None:
        field = ProcedureFollowUp._meta.get_field("non_performance_reason")
        max_length = field.max_length
        assert max_length is not None
        assert max(len(value) for value in FollowUpNonPerformanceReason.values) <= max_length


# ── R1 (Slice 002): projeção pura das causas legadas ─────────────────────


class TestProjecaoCausasLegadas:
    """R1 — a projeção de leitura é a fonte única das eras no Histórico.

    Pina os quatro mapeamentos confirmados pelo owner e o pass-through das
    causas atuais (design D5). Estado persistido fora deles vira a categoria
    técnica ``legacy_unmapped`` (fail-closed): nunca uma equivalência nova.
    """

    @pytest.mark.parametrize(
        ("reason", "detail", "expected"),
        [
            ("absenteeism", "", "patient_no_show"),
            ("resource_shortage", "emergency_occupied", "emergency_priority"),
            ("resource_shortage", "insufficient_time", "time_exceeded"),
            ("resource_shortage", "equipment_unavailable", "missing_equipment"),
        ],
        ids=["absenteeism", "emergency_occupied", "insufficient_time", "equipment_unavailable"],
    )
    def test_legacy_reason_projection(self, reason: str, detail: str, expected: str) -> None:
        assert (
            project_non_performance_reason(
                non_performance_reason=reason,
                resource_shortage_detail=detail,
            )
            == expected
        )

    @pytest.mark.parametrize("reason", _OFFICIAL_REASON_IDS, ids=_OFFICIAL_REASON_IDS)
    def test_current_reason_passa_sem_mudanca(self, reason: str) -> None:
        assert project_non_performance_reason(non_performance_reason=reason) == reason

    @pytest.mark.parametrize("reason", ["patient_no_show", "other"], ids=["patient_no_show", "other"])
    def test_current_reason_com_detalhe_nao_vazio_vira_legacy_unmapped(self, reason: str) -> None:
        """Regressão: causa atual exige detalhe vazio (design D5).

        Uma causa do catálogo oficial persistida com detalhe não vazio não é
        lida como a causa atual — cai em ``legacy_unmapped`` e a decisão do
        preflight (``is_unmapped_legacy_follow_up``) a sinaliza (R7).
        """
        assert (
            project_non_performance_reason(
                non_performance_reason=reason,
                resource_shortage_detail="emergency_occupied",
            )
            == LEGACY_UNMAPPED_REASON
        )
        assert is_unmapped_legacy_follow_up(
            non_performance_reason=reason,
            resource_shortage_detail="emergency_occupied",
        )

    @pytest.mark.parametrize(
        ("reason", "detail"),
        [
            ("resource_shortage", ""),
            ("resource_shortage", "submotivo_desconhecido"),
            ("absenteeism", "detalhe_inesperado"),
            ("causa_desconhecida", ""),
            ("", ""),
        ],
        ids=[
            "resource-shortage-sem-detalhe",
            "resource-shortage-detalhe-desconhecido",
            "absenteeism-com-detalhe",
            "causa-desconhecida",
            "causa-vazia",
        ],
    )
    def test_legacy_unmapped_fail_closed(self, reason: str, detail: str) -> None:
        assert (
            project_non_performance_reason(
                non_performance_reason=reason,
                resource_shortage_detail=detail,
            )
            == LEGACY_UNMAPPED_REASON
        )
        assert LEGACY_UNMAPPED_REASON not in CURRENT_FOLLOWUP_NON_PERFORMANCE_REASON_VALUES
        assert LEGACY_UNMAPPED_REASON not in FollowUpNonPerformanceReason.values

    def test_projecao_e_pura_sem_consultar_banco(self) -> None:
        """A projeção não faz writes nem leituras: só transforma os dois campos."""
        with CaptureQueriesContext(connection) as ctx:
            assert (
                project_non_performance_reason(
                    non_performance_reason="resource_shortage",
                    resource_shortage_detail="equipment_unavailable",
                )
                == "missing_equipment"
            )
        assert len(ctx) == 0


# ── R7 (Slice 002): preflight fail-closed de legados não mapeados ─────────


class TestPreflightLegadoNaoMapeado:
    """R7 — o preflight lista exatamente as rows que a projeção não lê.

    Substitui o conjunto ``Q`` paralelo do slice: o preflight delega à projeção
    (``is_unmapped_legacy_follow_up``), então um par fora dos mapeamentos —
    como ``absenteeism`` com detalhe não vazio — bloqueia o rollout, enquanto
    as combinações confirmadas liberam.
    """

    def _legacy_follow_up(self, case: Case, user: Any, *, reason: str, detail: str = "") -> ProcedureFollowUp:
        follow_up = CaseFollowUp.objects.create(
            case=case,
            version=case.follow_ups.count() + 1,
            patient_admitted=False,
            recorded_by=user,
        )
        return ProcedureFollowUp.objects.create(
            follow_up=follow_up,
            procedure=case.procedures.get(),
            performed=False,
            non_performance_reason=reason,
            resource_shortage_detail=detail,
        )

    def test_dataset_mapeado_libera_rollout(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        self._legacy_follow_up(case, user, reason="absenteeism")
        self._legacy_follow_up(case, user, reason="resource_shortage", detail="emergency_occupied")

        assert unmapped_legacy_follow_up_ids() == []

    def test_resource_shortage_com_detalhe_desconhecido_bloqueia(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        row = self._legacy_follow_up(case, user, reason="resource_shortage", detail="detalhe_desconhecido")

        assert unmapped_legacy_follow_up_ids() == [row.pk]

    def test_causa_fora_do_catalogo_bloqueia(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        row = self._legacy_follow_up(case, user, reason="causa_fora_do_catalogo")

        assert unmapped_legacy_follow_up_ids() == [row.pk]

    def test_absenteeism_com_detalhe_nao_vazio_bloqueia(self) -> None:
        """Row sintética: o par só não persiste porque o check 0017 o proíbe.

        A decisão do preflight é a mesma usada sobre rows persistidas, então a
        combinação fora do mapeamento é sinalizada (exit 1) mesmo sem poder
        existir no banco.
        """
        synthetic = ProcedureFollowUp(
            non_performance_reason="absenteeism",
            resource_shortage_detail="emergency_occupied",
        )

        assert is_unmapped_legacy_follow_up(
            non_performance_reason=synthetic.non_performance_reason,
            resource_shortage_detail=synthetic.resource_shortage_detail,
        )

    def test_realizado_nao_entra_no_preflight(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        follow_up = CaseFollowUp.objects.create(case=case, version=1, patient_admitted=False, recorded_by=user)
        ProcedureFollowUp.objects.create(
            follow_up=follow_up,
            procedure=case.procedures.get(),
            performed=True,
        )

        assert unmapped_legacy_follow_up_ids() == []


# ── R2: causas oficiais, `other` e códigos legados ────────────────────────


class TestCausasOficiais:
    """R2 — somente o catálogo atual grava; legados e submotivos são rejeitados."""

    def _assert_nada_gravado(self, case: Case) -> None:
        assert not CaseFollowUp.objects.filter(case=case).exists()
        assert not CaseEvent.objects.filter(case=case, event_type__startswith="FOLLOWUP").exists()

    @pytest.mark.parametrize(
        "reason",
        [value for value in _OFFICIAL_REASON_IDS if value != "other"],
        ids=[value for value in _OFFICIAL_REASON_IDS if value != "other"],
    )
    def test_official_reason_gravada_sem_submotivo_nem_texto(self, user, case_factory, reason: str) -> None:
        case = _case_with_procedures(case_factory, user)
        follow_up = record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=False,
            procedure_outcomes=[_outcome(case, performed=False, reason=reason)],
        )

        row = ProcedureFollowUp.objects.get(follow_up=follow_up)
        assert row.performed is False
        assert row.non_performance_reason == reason
        assert row.resource_shortage_detail == ""
        assert row.other_reason == ""

        (payload,) = CaseEvent.objects.get(case=case, event_type="FOLLOWUP_RECORDED").payload["outcomes"]
        assert payload["non_performance_reason"] == reason
        assert payload["resource_shortage_detail"] == ""
        assert payload["other_reason"] == ""

    @pytest.mark.parametrize("reason", ["absenteeism", "resource_shortage"])
    def test_legacy_reason_rejeitada_sem_persistencia(self, user, case_factory, reason: str) -> None:
        case = _case_with_procedures(case_factory, user)
        with pytest.raises(ValueError, match="Informe a causa do procedimento não realizado."):
            record_case_follow_up(
                case=case,
                performed_by=user,
                patient_admitted=False,
                procedure_outcomes=[_outcome(case, performed=False, reason=reason)],
            )
        self._assert_nada_gravado(case)

    def test_legacy_resource_shortage_com_submotivo_rejeitado(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        with pytest.raises(ValueError, match="Informe a causa do procedimento não realizado."):
            record_case_follow_up(
                case=case,
                performed_by=user,
                patient_admitted=False,
                procedure_outcomes=[
                    _outcome(case, performed=False, reason="resource_shortage", detail="emergency_occupied")
                ],
            )
        self._assert_nada_gravado(case)

    @pytest.mark.parametrize(
        "detail",
        list(FollowUpResourceShortageDetail.values),
        ids=list(FollowUpResourceShortageDetail.values),
    )
    def test_submotivo_rejeitado_com_causa_oficial(self, user, case_factory, detail: str) -> None:
        case = _case_with_procedures(case_factory, user)
        with pytest.raises(ValueError, match="Submotivo de falta de recursos não é aceito em novas gravações."):
            record_case_follow_up(
                case=case,
                performed_by=user,
                patient_admitted=False,
                procedure_outcomes=[_outcome(case, performed=False, reason="missing_equipment", detail=detail)],
            )
        self._assert_nada_gravado(case)

    @pytest.mark.parametrize("reason", ["", "causa_inexistente", "ABSENTEEISM"])
    def test_causa_vazia_desconhecida_ou_fora_do_catalogo_rejeitada(self, user, case_factory, reason: str) -> None:
        case = _case_with_procedures(case_factory, user)
        with pytest.raises(ValueError, match="Informe a causa do procedimento não realizado."):
            record_case_follow_up(
                case=case,
                performed_by=user,
                patient_admitted=False,
                procedure_outcomes=[_outcome(case, performed=False, reason=reason)],
            )
        self._assert_nada_gravado(case)


# ── R1: registro inicial ─────────────────────────────────────────────────


class TestRegistroInicial:
    def test_cria_versao1_outcomes_e_evento(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user, types=("eda", "colonoscopy"))
        eda_id, col_id = _procedure_ids(case)

        follow_up = record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=True,
            procedure_outcomes=[
                ProcedureOutcomeInput(procedure_id=eda_id, performed=True),
                ProcedureOutcomeInput(
                    procedure_id=col_id,
                    performed=False,
                    non_performance_reason="missing_equipment",
                ),
            ],
        )

        assert follow_up.version == 1
        assert follow_up.patient_admitted is True
        assert follow_up.recorded_by == user

        eda_row = ProcedureFollowUp.objects.get(follow_up=follow_up, procedure_id=eda_id)
        assert eda_row.performed is True
        assert eda_row.non_performance_reason == ""

        col_row = ProcedureFollowUp.objects.get(follow_up=follow_up, procedure_id=col_id)
        assert col_row.performed is False
        assert col_row.non_performance_reason == "missing_equipment"
        assert col_row.resource_shortage_detail == ""

        event = CaseEvent.objects.get(case=case, event_type="FOLLOWUP_RECORDED")
        assert event.actor == user
        assert event.actor_type == "human"
        assert event.payload["version"] == 1
        assert event.payload["patient_admitted"] is True
        assert len(event.payload["outcomes"]) == 2

    def test_causa_oficial_e_outras_causas_sao_gravados(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=False,
            procedure_outcomes=[
                _outcome(case, performed=False, reason="patient_no_show"),
            ],
        )
        case2 = _case_with_procedures(case_factory, user)
        record_case_follow_up(
            case=case2,
            performed_by=user,
            patient_admitted=False,
            procedure_outcomes=[
                _outcome(case2, performed=False, reason="other", other="Paciente em jejum incompleto"),
            ],
        )
        row = ProcedureFollowUp.objects.get(follow_up__case=case)
        assert row.non_performance_reason == "patient_no_show"
        row2 = ProcedureFollowUp.objects.get(follow_up__case=case2)
        assert row2.non_performance_reason == "other"
        assert row2.other_reason == "Paciente em jejum incompleto"


# ── R2: versionamento e evento de atualização ────────────────────────────


class TestVersionamento:
    def test_atualizacao_cria_versao2_preserva_v1_e_evento(self, user, case_factory) -> None:
        from django.contrib.auth import get_user_model

        other_user = get_user_model().objects.create_user(username="segundo", password="x")
        case = _case_with_procedures(case_factory, user)

        record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=False,
            procedure_outcomes=[_outcome(case, performed=True)],
        )
        record_case_follow_up(
            case=case,
            performed_by=other_user,
            patient_admitted=True,
            procedure_outcomes=[_outcome(case, performed=False, reason="patient_no_show")],
        )

        assert CaseFollowUp.objects.filter(case=case).count() == 2
        v1 = CaseFollowUp.objects.get(case=case, version=1)
        v2 = CaseFollowUp.objects.get(case=case, version=2)
        assert v1.recorded_by == user
        assert v1.patient_admitted is False
        assert v1.procedure_outcomes.get().performed is True
        assert v2.recorded_by == other_user
        assert v2.patient_admitted is True

        current = get_current_follow_up(case)
        assert current == v2

        updated_event = CaseEvent.objects.filter(case=case, event_type="FOLLOWUP_UPDATED")
        assert updated_event.count() == 1
        assert updated_event.get().payload["version"] == 2
        assert CaseEvent.objects.filter(case=case, event_type="FOLLOWUP_RECORDED").count() == 1

    def test_get_current_sem_followup_retorna_none(self, user, case_factory) -> None:
        case = case_factory(user)
        assert get_current_follow_up(case) is None


# ── R2b: current_follow_ups() — versão corrente por caso (histórico do supervisor) ──


class TestCurrentFollowUps:
    """``current_follow_ups()`` entrega 1 row por caso, na versão máxima (R1)."""

    def test_current_follow_ups_uma_linha_por_caso_na_versao_maxima(self, user, case_factory) -> None:
        case_a = _case_with_procedures(case_factory, user)
        case_b = _case_with_procedures(case_factory, user)
        sem_followup = case_factory(user)

        record_case_follow_up(
            case=case_a,
            performed_by=user,
            patient_admitted=False,
            procedure_outcomes=[_outcome(case_a, performed=True)],
        )
        record_case_follow_up(
            case=case_b,
            performed_by=user,
            patient_admitted=False,
            procedure_outcomes=[_outcome(case_b, performed=True)],
        )
        record_case_follow_up(
            case=case_b,
            performed_by=user,
            patient_admitted=True,
            procedure_outcomes=[_outcome(case_b, performed=False, reason="patient_no_show")],
        )

        rows = list(current_follow_ups())
        by_case = {row.case_id: row for row in rows}
        assert set(by_case) == {case_a.case_id, case_b.case_id}
        assert sem_followup.case_id not in by_case
        assert by_case[case_a.case_id].version == 1
        assert by_case[case_b.case_id].version == 2
        assert by_case[case_b.case_id].patient_admitted is True

    def test_current_follow_ups_preloads_caso_autor_e_desfechos_sem_n1(self, user, case_factory) -> None:
        """select_related + prefetch: acesso a case/recorded_by/outcomes não gera N+1."""
        case = _case_with_procedures(case_factory, user, types=("eda", "colonoscopy"))
        eda_id, col_id = _procedure_ids(case)
        record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=False,
            procedure_outcomes=[
                ProcedureOutcomeInput(procedure_id=eda_id, performed=True),
                ProcedureOutcomeInput(
                    procedure_id=col_id,
                    performed=False,
                    non_performance_reason="missing_equipment",
                ),
            ],
        )

        with CaptureQueriesContext(connection) as ctx:
            rows = list(current_follow_ups())
            for follow_up in rows:
                follow_up.case.agency_record_number
                assert follow_up.recorded_by is not None
                follow_up.recorded_by.username
                for outcome in follow_up.procedure_outcomes.all():
                    outcome.procedure.procedure_type
        # Principal + prefetch de desfechos + prefetch dos procedimentos.
        assert len(ctx) == 3


# ── R3: validações ───────────────────────────────────────────────────────


class TestValidacoes:
    def _assert_rejeitado(self, case, user, outcomes) -> None:
        with pytest.raises(ValueError):
            record_case_follow_up(
                case=case,
                performed_by=user,
                patient_admitted=False,
                procedure_outcomes=outcomes,
            )
        assert not CaseFollowUp.objects.filter(case=case).exists()
        assert not CaseEvent.objects.filter(case=case, event_type__startswith="FOLLOWUP").exists()

    def test_cobertura_todos_os_procedimentos(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user, types=("eda", "colonoscopy"))
        col_id = _procedure_ids(case)[1]
        self._assert_rejeitado(
            case,
            user,
            [ProcedureOutcomeInput(procedure_id=col_id, performed=True)],
        )

    @pytest.mark.parametrize(
        ("case_types", "outcomes", "expected_message"),
        [
            pytest.param(
                (),
                lambda case: [],
                "Caso não possui procedimentos autorizados para pós-procedimento.",
                id="sem-procedimentos-autorizados",
            ),
            pytest.param(
                ("eda",),
                lambda case: [_outcome(case, performed=True), _outcome(case, performed=True)],
                "Procedimento duplicado no pós-procedimento.",
                id="procedimento-duplicado",
            ),
            pytest.param(
                ("eda", "colonoscopy"),
                lambda case: [ProcedureOutcomeInput(procedure_id=_procedure_ids(case)[1], performed=True)],
                "O pós-procedimento deve cobrir todos os procedimentos autorizados do caso.",
                id="cobertura-incompleta",
            ),
        ],
    )
    def test_mensagens_de_validacao_usam_pos_procedimento(
        self,
        user,
        case_factory,
        case_types: tuple[str, ...],
        outcomes: Callable[[Case], list[Any]],
        expected_message: str,
    ) -> None:
        """ValueErrors de estrutura usam "pós-procedimento" (D1), nunca "follow-up".

        São exatamente as mensagens que ``followup_form`` renderiza como erro
        de formulário (``add_error(None, str(exc))`` em views.py), então o
        termo visível precisa ser o novo; o anglicismo não pode regredir.
        """
        case = _case_with_procedures(case_factory, user, types=case_types)
        with pytest.raises(ValueError) as exc:
            record_case_follow_up(
                case=case,
                performed_by=user,
                patient_admitted=False,
                procedure_outcomes=outcomes(case),
            )
        assert str(exc.value) == expected_message
        assert not CaseFollowUp.objects.filter(case=case).exists()
        assert not CaseEvent.objects.filter(case=case, event_type__startswith="FOLLOWUP").exists()

    def test_procedimento_estranho_rejeitado(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        outro = _case_with_procedures(case_factory, user)
        self._assert_rejeitado(case, user, [_outcome(outro, performed=True)])

    def test_nao_realizado_sem_motivo_rejeitado(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        self._assert_rejeitado(case, user, [_outcome(case, performed=False)])

    def test_outras_causas_sem_texto_rejeitado(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        self._assert_rejeitado(case, user, [_outcome(case, performed=False, reason="other")])

    def test_texto_de_outras_causas_com_causa_diferente_rejeitado(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        self._assert_rejeitado(
            case,
            user,
            [_outcome(case, performed=False, reason="patient_no_show", other="x")],
        )

    def test_performed_normaliza_campos_de_motivo(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=False,
            procedure_outcomes=[
                _outcome(case, performed=True, reason="patient_no_show", detail="emergency_occupied", other="lixo"),
            ],
        )
        row = ProcedureFollowUp.objects.get(follow_up__case=case)
        assert row.non_performance_reason == ""
        assert row.resource_shortage_detail == ""
        assert row.other_reason == ""


# ── R4: constraints de integridade ───────────────────────────────────────


class TestConstraints:
    def _make_follow_up(self, case: Case, version: int) -> CaseFollowUp:
        return CaseFollowUp.objects.create(case=case, version=version, patient_admitted=False)

    def test_unique_case_version(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=False,
            procedure_outcomes=[_outcome(case, performed=True)],
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                CaseFollowUp.objects.create(case=case, version=1, patient_admitted=False)

    def test_unique_followup_procedure(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        follow_up = record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=False,
            procedure_outcomes=[_outcome(case, performed=True)],
        )
        procedure = case.procedures.get()
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProcedureFollowUp.objects.create(follow_up=follow_up, procedure=procedure, performed=True)

    def test_check_nao_realizado_exige_motivo(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        follow_up = self._make_follow_up(case, version=1)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProcedureFollowUp.objects.create(
                    follow_up=follow_up,
                    procedure=case.procedures.get(),
                    performed=False,
                    non_performance_reason="",
                )

    def test_check_realizado_nao_carrega_motivo(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        follow_up = self._make_follow_up(case, version=1)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProcedureFollowUp.objects.create(
                    follow_up=follow_up,
                    procedure=case.procedures.get(),
                    performed=True,
                    non_performance_reason="patient_no_show",
                )

    def test_check_submotivo_exigido_quando_falta_de_recursos(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        follow_up = self._make_follow_up(case, version=1)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProcedureFollowUp.objects.create(
                    follow_up=follow_up,
                    procedure=case.procedures.get(),
                    performed=False,
                    non_performance_reason="resource_shortage",
                    resource_shortage_detail="",
                )

    def test_check_submotivo_proibido_sem_falta_de_recursos(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        follow_up = self._make_follow_up(case, version=1)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProcedureFollowUp.objects.create(
                    follow_up=follow_up,
                    procedure=case.procedures.get(),
                    performed=False,
                    non_performance_reason="patient_no_show",
                    resource_shortage_detail="emergency_occupied",
                )

    def test_check_texto_exigido_quando_outras_causas(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        follow_up = self._make_follow_up(case, version=1)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProcedureFollowUp.objects.create(
                    follow_up=follow_up,
                    procedure=case.procedures.get(),
                    performed=False,
                    non_performance_reason="other",
                    other_reason="",
                )

    def test_check_texto_proibido_sem_outras_causas(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        follow_up = self._make_follow_up(case, version=1)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProcedureFollowUp.objects.create(
                    follow_up=follow_up,
                    procedure=case.procedures.get(),
                    performed=False,
                    non_performance_reason="patient_no_show",
                    other_reason="texto indevido",
                )


# ── Causa "Preparo inadequado" (follow-up-inadequate-prep-reason) ───────


class TestPreparoInadequado:
    """Causa nova do conjunto fechado: gravável sem submotivo/texto e espelhada."""

    def test_preparo_inadequado_gravado_e_espelhado(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        follow_up = record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=False,
            procedure_outcomes=[
                _outcome(case, performed=False, reason="inadequate_prep"),
            ],
        )
        row = ProcedureFollowUp.objects.get(follow_up=follow_up)
        assert row.performed is False
        assert row.non_performance_reason == "inadequate_prep"
        assert row.resource_shortage_detail == ""
        assert row.other_reason == ""

        event = CaseEvent.objects.get(case=case, event_type="FOLLOWUP_RECORDED")
        (outcome_payload,) = event.payload["outcomes"]
        assert outcome_payload["performed"] is False
        assert outcome_payload["non_performance_reason"] == "inadequate_prep"
        assert outcome_payload["resource_shortage_detail"] == ""
        assert outcome_payload["other_reason"] == ""

    def test_preparo_inadequado_com_submotivo_ou_texto_rejeitado(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        with pytest.raises(
            ValueError,
            match="Submotivo de falta de recursos não é aceito em novas gravações.",
        ):
            record_case_follow_up(
                case=case,
                performed_by=user,
                patient_admitted=False,
                procedure_outcomes=[
                    _outcome(case, performed=False, reason="inadequate_prep", detail="emergency_occupied"),
                ],
            )
        assert not CaseFollowUp.objects.filter(case=case).exists()

        with pytest.raises(
            ValueError,
            match="Texto de outras causas só deve ser informado quando a causa é 'Outras causas'.",
        ):
            record_case_follow_up(
                case=case,
                performed_by=user,
                patient_admitted=False,
                procedure_outcomes=[
                    _outcome(case, performed=False, reason="inadequate_prep", other="jejum incompleto"),
                ],
            )
        assert not CaseFollowUp.objects.filter(case=case).exists()
        assert not CaseEvent.objects.filter(case=case, event_type__startswith="FOLLOWUP").exists()


# ── Cobertura restrita às rows autorizadas (ADR-0007 / R1) ───────────────


def _row(case: Case, procedure_type: str, disposition: str) -> CaseProcedure:
    """Row ``CaseProcedure`` com disposição médica explícita (dimensão de decisão)."""
    return CaseProcedure.objects.create(
        case=case,
        procedure_type=procedure_type,
        doctor_disposition=disposition,
    )


class TestCoberturaRestritaAutorizadas:
    """O universo do follow-up é o subconjunto ``doctor_disposition == approved``."""

    def _assert_rejeitado(self, case: Case, user: Any, outcomes: list[ProcedureOutcomeInput]) -> None:
        with pytest.raises(ValueError):
            record_case_follow_up(
                case=case,
                performed_by=user,
                patient_admitted=False,
                procedure_outcomes=outcomes,
            )
        assert not CaseFollowUp.objects.filter(case=case).exists()
        assert not CaseEvent.objects.filter(case=case, event_type__startswith="FOLLOWUP").exists()

    def test_troca_aceita_sem_desfecho_da_row_negada(self, user, case_factory) -> None:
        """Troca (EDA negada + Ecoendoscopia autorizada): só a autorizada é coberta."""
        case = case_factory(user)
        _row(case, "eda", DoctorDisposition.DENIED)
        autorizada = _row(case, "echoendoscopy", DoctorDisposition.APPROVED)

        follow_up = record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=True,
            procedure_outcomes=[ProcedureOutcomeInput(procedure_id=autorizada.id, performed=True)],
        )

        assert follow_up.version == 1
        assert [row.procedure_id for row in follow_up.procedure_outcomes.all()] == [autorizada.id]
        event = CaseEvent.objects.get(case=case, event_type="FOLLOWUP_RECORDED")
        assert [payload["procedure_id"] for payload in event.payload["outcomes"]] == [autorizada.id]
        assert event.payload["outcomes"][0]["procedure_type"] == "echoendoscopy"

    def test_aprovacao_parcial_aceita_sem_desfecho_da_row_negada(self, user, case_factory) -> None:
        """Aprovação parcial (EDA aprovada + Colonoscopia negada): só a EDA é coberta."""
        case = case_factory(user)
        autorizada = _row(case, "eda", DoctorDisposition.APPROVED)
        _row(case, "colonoscopy", DoctorDisposition.DENIED)

        follow_up = record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=False,
            procedure_outcomes=[
                ProcedureOutcomeInput(
                    procedure_id=autorizada.id,
                    performed=False,
                    non_performance_reason="patient_no_show",
                )
            ],
        )

        assert [row.procedure_id for row in follow_up.procedure_outcomes.all()] == [autorizada.id]

    def test_desfecho_para_row_negada_rejeitado(self, user, case_factory) -> None:
        """Desfecho informado para row negada é rejeitado (fail-closed)."""
        case = case_factory(user)
        autorizada = _row(case, "eda", DoctorDisposition.APPROVED)
        negada = _row(case, "colonoscopy", DoctorDisposition.DENIED)

        self._assert_rejeitado(
            case,
            user,
            [
                ProcedureOutcomeInput(procedure_id=autorizada.id, performed=True),
                ProcedureOutcomeInput(procedure_id=negada.id, performed=True),
            ],
        )

    def test_desfecho_para_row_pendente_rejeitado(self, user, case_factory) -> None:
        """Desfecho para row ainda pendente (não autorizada) é rejeitado."""
        case = case_factory(user)
        autorizada = _row(case, "eda", DoctorDisposition.APPROVED)
        pendente = _row(case, "colonoscopy", DoctorDisposition.PENDING)

        self._assert_rejeitado(
            case,
            user,
            [
                ProcedureOutcomeInput(procedure_id=autorizada.id, performed=True),
                ProcedureOutcomeInput(procedure_id=pendente.id, performed=True),
            ],
        )

    def test_caso_sem_rows_autorizadas_rejeitado(self, user, case_factory) -> None:
        """Sem rows autorizadas (defensivo): erro explícito, nada gravado."""
        case = case_factory(user)
        _row(case, "eda", DoctorDisposition.DENIED)

        with pytest.raises(ValueError, match="Caso não possui procedimentos autorizados para pós-procedimento."):
            record_case_follow_up(
                case=case,
                performed_by=user,
                patient_admitted=False,
                procedure_outcomes=[],
            )
        assert not CaseFollowUp.objects.filter(case=case).exists()
        assert not CaseEvent.objects.filter(case=case, event_type__startswith="FOLLOWUP").exists()
