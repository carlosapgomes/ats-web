"""Testes de auditoria — CaseEvent e signals."""

from __future__ import annotations

from apps.cases.models import Case, CaseEvent, CaseStatus


class TestAuditCreate:
    def test_create_case_generates_case_created_event(self, user) -> None:
        """Criar caso deve gerar evento CASE_CREATED automaticamente."""
        case = Case.objects.create(created_by=user)
        events = CaseEvent.objects.filter(case=case)
        assert events.count() == 1
        event = events.first()
        assert event is not None
        assert event.event_type == "CASE_CREATED"
        assert event.actor == user
        assert event.actor_type == "human"

    def test_event_actor_is_set_to_created_by(self, user) -> None:
        """Actor do evento de criação deve ser o created_by."""
        case = Case.objects.create(created_by=user)
        event = CaseEvent.objects.get(case=case)
        assert event.actor == user


class TestAuditTransitions:
    def test_transition_generates_event(self, user) -> None:
        """Cada transição deve gerar um CaseEvent com tipo correto."""
        case = Case.objects.create(created_by=user)
        case.start_processing(user=user)
        case.save()

        events = CaseEvent.objects.filter(case=case).order_by("timestamp")
        assert events.count() == 2  # CASE_CREATED + CASE_START_PROCESSING
        assert events[1].event_type == "CASE_START_PROCESSING"

    def test_event_records_actor(self, user) -> None:
        """Evento deve registrar quem executou a transição."""
        case = Case.objects.create(created_by=user)
        case.start_processing(user=user)
        case.save()

        event = CaseEvent.objects.filter(case=case, event_type="CASE_START_PROCESSING").first()
        assert event is not None
        assert event.actor == user
        assert event.actor_type == "human"

    def test_event_payload_captured(self, user, advance_to) -> None:
        """Evento deve capturar payload quando fornecido."""
        case = Case.objects.create(created_by=user)
        advance_to(case, CaseStatus.WAIT_DOCTOR)

        case.doctor_decide(decision="accept", user=user)
        case.save()

        event = CaseEvent.objects.filter(case=case, event_type="DOCTOR_ACCEPT").first()
        assert event is not None
        assert event.payload == {"decision": "accept"}

    def test_extraction_success_generates_event(self, user) -> None:
        """EXTRACTING → LLM_STRUCT deve gerar CASE_EXTRACTION_OK."""
        case = Case.objects.create(created_by=user)
        case.start_processing(user=user)
        case.save()
        case.start_extraction(user=user)
        case.save()
        case.extraction_complete(success=True, user=user)
        case.save()

        event = CaseEvent.objects.filter(case=case, event_type="CASE_EXTRACTION_OK").first()
        assert event is not None
        assert event.actor == user


class TestAuditOrdering:
    def test_events_ordered_by_timestamp(self, user) -> None:
        """Eventos devem ficar em ordem cronológica."""
        case = Case.objects.create(created_by=user)
        case.start_processing(user=user)
        case.save()
        case.start_extraction(user=user)
        case.save()

        events = list(CaseEvent.objects.filter(case=case).order_by("timestamp"))
        types = [e.event_type for e in events]
        assert types == [
            "CASE_CREATED",
            "CASE_START_PROCESSING",
            "CASE_START_EXTRACTION",
        ]


class TestAuditFullLifecycle:
    def test_full_lifecycle_events(self, user) -> None:
        """Percorrer fluxo completo NEW → CLEANED e verificar todos os eventos."""
        case = Case.objects.create(created_by=user)

        # Pipeline de processamento
        case.start_processing(user=user)
        case.save()
        case.start_extraction(user=user)
        case.save()
        case.extraction_complete(success=True, user=user)
        case.save()
        case.llm1_complete(success=True, user=user)
        case.save()
        case.llm2_complete(success=True, user=user)
        case.save()
        case.ready_for_doctor(user=user)
        case.save()

        # Decisão médica
        case.doctor_decide(decision="accept", user=user)
        case.save()
        case.ready_for_scheduler(user=user)
        case.save()
        case.scheduler_request_posted(user=user)
        case.save()
        case.scheduler_decide(appointment_status="confirmed", user=user)
        case.save()

        # Fechamento
        case.final_reply_posted(user=user)
        case.save()
        case.cleanup_triggered(user=user)
        case.save()
        case.cleanup_completed(user=user)
        case.save()

        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.CLEANED

        events = list(CaseEvent.objects.filter(case=case).order_by("timestamp"))
        event_types = [e.event_type for e in events]

        expected = [
            "CASE_CREATED",
            "CASE_START_PROCESSING",
            "CASE_START_EXTRACTION",
            "CASE_EXTRACTION_OK",
            "LLM1_OK",
            "LLM2_OK",
            "CASE_READY_FOR_DOCTOR",
            "DOCTOR_ACCEPT",
            "CASE_READY_FOR_SCHEDULER",
            "SCHEDULER_REQUEST_POSTED",
            "APPT_CONFIRMED",
            "FINAL_REPLY_POSTED",
            "CLEANUP_TRIGGERED",
            "CLEANUP_COMPLETED",
        ]
        assert event_types == expected
