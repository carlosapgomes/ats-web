import uuid

from django.conf import settings
from django.db import models
from django_fsm import FSMField, transition


class ReturnState:
    """Target callable for django-fsm that resolves the target from the
    return value of the transition method."""

    def get_state(self, instance, transition, result, args, kwargs) -> str:
        return result


class CaseStatus(models.TextChoices):
    """Todos os 17 estados do caso, preservados do legado."""

    NEW = "NEW", "New"
    R1_ACK_PROCESSING = "R1_ACK_PROCESSING", "R1 Ack Processing"
    EXTRACTING = "EXTRACTING", "Extracting"
    LLM_STRUCT = "LLM_STRUCT", "LLM Struct"
    LLM_SUGGEST = "LLM_SUGGEST", "LLM Suggest"
    R2_POST_WIDGET = "R2_POST_WIDGET", "R2 Post Widget"
    WAIT_DOCTOR = "WAIT_DOCTOR", "Wait Doctor"
    DOCTOR_DENIED = "DOCTOR_DENIED", "Doctor Denied"
    DOCTOR_ACCEPTED = "DOCTOR_ACCEPTED", "Doctor Accepted"
    R3_POST_REQUEST = "R3_POST_REQUEST", "R3 Post Request"
    WAIT_APPT = "WAIT_APPT", "Wait Appointment"
    APPT_CONFIRMED = "APPT_CONFIRMED", "Appointment Confirmed"
    APPT_DENIED = "APPT_DENIED", "Appointment Denied"
    FAILED = "FAILED", "Failed"
    R1_FINAL_REPLY_POSTED = "R1_FINAL_REPLY_POSTED", "R1 Final Reply Posted"
    WAIT_R1_CLEANUP_THUMBS = "WAIT_R1_CLEANUP_THUMBS", "Wait R1 Cleanup"
    CLEANUP_RUNNING = "CLEANUP_RUNNING", "Cleanup Running"
    CLEANED = "CLEANED", "Cleaned"


class Case(models.Model):
    """Caso de triagem EDA — entidade central do sistema."""

    case_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # FSM Status
    status = FSMField(
        max_length=30,
        choices=CaseStatus.choices,
        default=CaseStatus.NEW,
        protected=True,
    )

    # Origin / PDF
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cases_created",
    )
    pdf_file = models.FileField(upload_to="pdfs/%Y/%m/", blank=True, null=True)
    extracted_text = models.TextField(blank=True)
    agency_record_number = models.CharField(max_length=20, blank=True)
    agency_record_extracted_at = models.DateTimeField(null=True, blank=True)

    # LLM artifacts
    structured_data = models.JSONField(blank=True, null=True)
    summary_text = models.TextField(blank=True)
    suggested_action = models.JSONField(blank=True, null=True)

    # Doctor decision
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cases_decided",
    )
    doctor_decision = models.CharField(max_length=10, blank=True)
    doctor_support_flag = models.CharField(max_length=20, blank=True, default="none")
    doctor_admission_flow = models.CharField(max_length=15, blank=True)
    doctor_reason = models.TextField(blank=True)
    doctor_decided_at = models.DateTimeField(null=True, blank=True)

    # Scheduler decision
    scheduler = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cases_scheduled",
    )
    appointment_status = models.CharField(max_length=15, blank=True)
    appointment_at = models.DateTimeField(null=True, blank=True)
    appointment_location = models.TextField(blank=True)
    appointment_instructions = models.TextField(blank=True)
    appointment_reason = models.TextField(blank=True)
    appointment_decided_at = models.DateTimeField(null=True, blank=True)

    # Closure
    final_reply_posted_at = models.DateTimeField(null=True, blank=True)
    cleanup_triggered_at = models.DateTimeField(null=True, blank=True)
    cleanup_completed_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["agency_record_number", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Case {self.case_id} [{self.status}]"

    # ── FSM Transitions ──────────────────────────────────────────────────

    @transition(field=status, source=CaseStatus.NEW, target=CaseStatus.R1_ACK_PROCESSING)
    def start_processing(self, user=None):
        self._record_event("CASE_START_PROCESSING", user=user)

    @transition(field=status, source=CaseStatus.R1_ACK_PROCESSING, target=CaseStatus.EXTRACTING)
    def start_extraction(self, user=None):
        self._record_event("CASE_START_EXTRACTION", user=user)

    @transition(
        field=status,
        source=CaseStatus.EXTRACTING,
        target=ReturnState(),
    )
    def extraction_complete(self, success: bool, user=None):
        if not success:
            self._record_event("CASE_EXTRACTION_FAILED", user=user)
        else:
            self._record_event("CASE_EXTRACTION_OK", user=user)
        return CaseStatus.FAILED if not success else CaseStatus.LLM_STRUCT

    @transition(
        field=status,
        source=CaseStatus.LLM_STRUCT,
        target=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
    )
    def scope_gate_bypass(self, *, reason_code: str = "", user=None):
        """Bypass LLM2 for scope-gated cases (non-EDA / unknown exam type).

        Transitions directly to WAIT_R1_CLEANUP_THUMBS so the NIR can
        confirm receipt — the case never enters the doctor queue.
        """
        self._record_event(
            "SCOPE_GATE_BYPASS",
            user=user,
            payload={"reason_code": reason_code},
        )

    @transition(
        field=status,
        source=CaseStatus.LLM_STRUCT,
        target=ReturnState(),
    )
    def llm1_complete(self, success: bool, user=None):
        self._record_event(
            "LLM1_OK" if success else "LLM1_FAILED",
            user=user,
        )
        return CaseStatus.FAILED if not success else CaseStatus.LLM_SUGGEST

    @transition(
        field=status,
        source=CaseStatus.LLM_SUGGEST,
        target=ReturnState(),
    )
    def llm2_complete(self, success: bool, user=None):
        self._record_event(
            "LLM2_OK" if success else "LLM2_FAILED",
            user=user,
        )
        return CaseStatus.FAILED if not success else CaseStatus.R2_POST_WIDGET

    @transition(
        field=status,
        source=CaseStatus.R2_POST_WIDGET,
        target=CaseStatus.WAIT_DOCTOR,
    )
    def ready_for_doctor(self, user=None):
        self._record_event("CASE_READY_FOR_DOCTOR", user=user)

    @transition(
        field=status,
        source=CaseStatus.WAIT_DOCTOR,
        target=ReturnState(),
    )
    def doctor_decide(self, decision: str, user=None):
        self._record_event(
            f"DOCTOR_{decision.upper()}",
            user=user,
            payload={"decision": decision},
        )
        return CaseStatus.DOCTOR_DENIED if decision == "deny" else CaseStatus.DOCTOR_ACCEPTED

    @transition(
        field=status,
        source=CaseStatus.DOCTOR_ACCEPTED,
        target=CaseStatus.R3_POST_REQUEST,
    )
    def ready_for_scheduler(self, user=None):
        self._record_event("CASE_READY_FOR_SCHEDULER", user=user)

    @transition(
        field=status,
        source=CaseStatus.R3_POST_REQUEST,
        target=CaseStatus.WAIT_APPT,
    )
    def scheduler_request_posted(self, user=None):
        self._record_event("SCHEDULER_REQUEST_POSTED", user=user)

    @transition(
        field=status,
        source=CaseStatus.WAIT_APPT,
        target=ReturnState(),
    )
    def scheduler_decide(self, appointment_status: str, user=None):
        self._record_event(
            f"APPT_{appointment_status.upper()}",
            user=user,
            payload={"appointment_status": appointment_status},
        )
        return CaseStatus.APPT_DENIED if appointment_status == "denied" else CaseStatus.APPT_CONFIRMED

    @transition(
        field=status,
        source=[
            CaseStatus.DOCTOR_DENIED,
            CaseStatus.DOCTOR_ACCEPTED,
            CaseStatus.APPT_CONFIRMED,
            CaseStatus.APPT_DENIED,
            CaseStatus.FAILED,
            CaseStatus.R1_FINAL_REPLY_POSTED,
        ],
        target=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
    )
    def final_reply_posted(self, user=None):
        self._record_event("FINAL_REPLY_POSTED", user=user)

    @transition(
        field=status,
        source=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        target=CaseStatus.CLEANUP_RUNNING,
    )
    def cleanup_triggered(self, user=None):
        self._record_event("CLEANUP_TRIGGERED", user=user)

    @transition(
        field=status,
        source=CaseStatus.CLEANUP_RUNNING,
        target=CaseStatus.CLEANED,
    )
    def cleanup_completed(self, user=None):
        self._record_event("CLEANUP_COMPLETED", user=user)

    def _record_event(
        self,
        event_type: str,
        *,
        user=None,
        payload: dict[str, object] | None = None,
    ) -> None:
        """Cria CaseEvent. Chamado via signal após save()."""
        self._pending_event = {
            "event_type": event_type,
            "actor": user,
            "actor_type": "human" if user else "system",
            "payload": payload or {},
        }


class CaseEvent(models.Model):
    """Trilha de auditoria append-only. Única fonte de verdade."""

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="events")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    actor_type = models.CharField(max_length=10)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    event_type = models.CharField(max_length=80, db_index=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["case", "timestamp"]),
            models.Index(fields=["event_type", "timestamp"]),
        ]

    def __str__(self) -> str:
        return f"CaseEvent {self.event_type} @ {self.timestamp}"


class SupervisorSummary(models.Model):
    """Resumo periódico para supervisão de casos."""

    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    patients_received = models.PositiveIntegerField(default=0)
    reports_processed = models.PositiveIntegerField(default=0)
    cases_evaluated = models.PositiveIntegerField(default=0)
    accepted_scheduled = models.PositiveIntegerField(default=0)
    immediate_admission = models.PositiveIntegerField(default=0)
    refused = models.PositiveIntegerField(default=0)
    in_progress = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=10,
        choices=[("pending", "Pending"), ("sent", "Sent")],
        default="sent",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("window_start", "window_end")]
        ordering = ["-window_end"]

    def __str__(self) -> str:
        return f"SupervisorSummary {self.window_start} – {self.window_end} [{self.status}]"
