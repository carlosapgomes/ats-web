import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
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
    regulation_days_on_screen = models.PositiveIntegerField(null=True, blank=True, db_index=True)

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
    doctor_observation = models.CharField(max_length=500, blank=True)
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

    # Post-schedule intercurrence (post_schedule_issue)
    post_schedule_issue_status = models.CharField(max_length=20, blank=True, default="")
    post_schedule_issue_reason = models.CharField(max_length=50, blank=True)
    post_schedule_issue_message = models.TextField(blank=True)
    post_schedule_issue_opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="post_schedule_issues_opened",
    )
    post_schedule_issue_opened_at = models.DateTimeField(null=True, blank=True)
    post_schedule_issue_response_action = models.CharField(max_length=30, blank=True)
    post_schedule_issue_response_message = models.TextField(blank=True)
    post_schedule_issue_responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="post_schedule_issues_responded",
    )
    post_schedule_issue_responded_at = models.DateTimeField(null=True, blank=True)

    # Corrected resubmission linkage
    corrects_case = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="corrected_by_cases",
    )
    correction_reason = models.TextField(blank=True)
    correction_created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="case_corrections_created",
    )
    correction_created_at = models.DateTimeField(null=True, blank=True)

    # Lock / Lease fields
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cases_locked",
    )
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_until = models.DateTimeField(null=True, blank=True, db_index=True)
    lock_token = models.UUIDField(null=True, blank=True)
    lock_context = models.CharField(max_length=40, blank=True)
    lock_role = models.CharField(max_length=30, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["status", "locked_until"]),
            models.Index(fields=["agency_record_number", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Case {self.case_id} [{self.status}]"

    @property
    def patient_name(self) -> str:
        sd = self.structured_data
        if isinstance(sd, dict):
            patient = sd.get("patient", {})
            if isinstance(patient, dict):
                name = patient.get("name")
                if name:
                    return str(name)
        return "Paciente"

    @property
    def patient_age(self) -> str:
        sd = self.structured_data
        if isinstance(sd, dict):
            patient = sd.get("patient", {})
            if isinstance(patient, dict):
                age = patient.get("age", "")
                return str(age) if age else ""
        return ""

    @property
    def patient_gender(self) -> str:
        sd = self.structured_data
        if isinstance(sd, dict):
            patient = sd.get("patient", {})
            if isinstance(patient, dict):
                sex = patient.get("sex")
                if isinstance(sex, str) and sex.strip():
                    return sex.strip()
                gender = patient.get("gender")
                if isinstance(gender, str) and gender.strip():
                    return gender.strip()
        return ""

    @property
    def diagnosis(self) -> str:
        if self.summary_text:
            return self.summary_text
        sd = self.structured_data
        if isinstance(sd, dict):
            eda = sd.get("eda", {})
            if isinstance(eda, dict):
                indication = eda.get("indication_category", "")
                if indication:
                    return str(indication)
        return ""

    @property
    def has_doctor_observation(self) -> bool:
        return bool(self.doctor_observation.strip())

    @property
    def doctor_display(self) -> str:
        """Exibe o médico responsável com nome e registro profissional.

        Formato: 'Nome — CRM 12345' ou apenas 'Nome' quando não há registro.
        Retorna '' quando não há médico atribuído.
        """
        if not self.doctor:
            return ""
        registration = self.doctor.professional_registration_display
        if registration:
            return f"{self.doctor.display_name} — {registration}"
        return self.doctor.display_name

    @property
    def scheduler_display(self) -> str:
        """Exibe o agendador responsável com nome e registro profissional.

        Formato: 'Nome — COREN 12345' ou apenas 'Nome' quando não há registro.
        Retorna '' quando não há agendador atribuído.
        """
        if not self.scheduler:
            return ""
        registration = self.scheduler.professional_registration_display
        if registration:
            return f"{self.scheduler.display_name} — {registration}"
        return self.scheduler.display_name

    def get_origin_unit_display(self, compact: bool = True) -> str:
        """Extrai e formata a unidade de origem do structured_data.

        Retorna string vazia se structured_data ou origin_context
        estiverem ausentes/vazios.

        Modo compacto (cards): ``🏥 {hospital} · {unit}``
        Modo completo (detalhes): ``{city} ({state_uf}) · {hospital} · {unit}``
        """
        sd = self.structured_data
        if not isinstance(sd, dict):
            return ""

        origin = sd.get("origin_context")
        if not isinstance(origin, dict):
            return ""

        city = (origin.get("city") or "").strip()
        uf = (origin.get("state_uf") or "").strip()
        hospital = (origin.get("hospital") or "").strip()
        unit = (origin.get("unit") or "").strip()

        if compact:
            compact_parts: list[str] = []
            if hospital:
                compact_parts.append(hospital)
            if unit and unit != hospital:
                compact_parts.append(unit)
            return " · ".join(compact_parts) if compact_parts else ""

        full_parts: list[str] = []
        if city:
            label = f"{city} ({uf})" if uf else city
            full_parts.append(label)
        if hospital:
            full_parts.append(hospital)
        if unit and unit != hospital:
            full_parts.append(unit)
        return " · ".join(full_parts) if full_parts else ""

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
            payload={"decision": decision, "has_doctor_observation": self.has_doctor_observation},
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
            CaseStatus.WAIT_APPT,
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

    @transition(field=status, source=CaseStatus.CLEANED, target=CaseStatus.WAIT_APPT)
    def open_post_schedule_issue(self, user=None):
        pass

    @transition(
        field=status,
        source=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        target=CaseStatus.CLEANED,
    )
    def post_schedule_issue_acknowledged(self, user=None):
        self._record_event("POST_SCHEDULE_ISSUE_ACKNOWLEDGED", user=user)

    @transition(
        field=status,
        source=[
            CaseStatus.NEW,
            CaseStatus.R1_ACK_PROCESSING,
            CaseStatus.EXTRACTING,
            CaseStatus.LLM_STRUCT,
            CaseStatus.LLM_SUGGEST,
            CaseStatus.R2_POST_WIDGET,
            CaseStatus.WAIT_DOCTOR,
            CaseStatus.DOCTOR_ACCEPTED,
            CaseStatus.DOCTOR_DENIED,
            CaseStatus.R3_POST_REQUEST,
            CaseStatus.WAIT_APPT,
            CaseStatus.APPT_CONFIRMED,
            CaseStatus.APPT_DENIED,
            CaseStatus.FAILED,
            CaseStatus.R1_FINAL_REPLY_POSTED,
            CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            CaseStatus.CLEANUP_RUNNING,
        ],
        target=CaseStatus.CLEANED,
    )
    def administratively_close(self, *, user=None, payload=None):
        """Transição excepcional para encerramento administrativo.

        Disponível de qualquer estado não CLEANED. Move o caso para CLEANED
        sem passar pelos eventos normais de cleanup.
        """
        self._record_event("CASE_ADMINISTRATIVELY_CLOSED", user=user, payload=payload or {})

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


def case_attachment_upload_to(instance: "CaseAttachment", filename: str) -> str:
    """Gera caminho seguro: case_attachments/<case_id>/<attachment_id>.<ext>

    Usa UUID do anexo em vez do nome original para evitar colisão e path traversal.
    A extensão é extraída do content-type para consistência.
    """
    ext = _extension_for_content_type(instance.content_type)
    return os.path.join(
        "case_attachments",
        str(instance.case_id),
        f"{instance.attachment_id}{ext}",
    )


CONTENT_TYPE_EXTENSION_MAP: dict[str, str] = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


ACCEPTED_ATTACHMENT_CONTENT_TYPES = set(CONTENT_TYPE_EXTENSION_MAP.keys())

ACCEPTED_ATTACHMENT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


def _extension_for_content_type(content_type: str) -> str:
    return CONTENT_TYPE_EXTENSION_MAP.get(content_type, ".bin")


class CaseAttachment(models.Model):
    """Anexo clínico vinculado a um Case.

    Anexos são documentos complementares enviados pelo NIR junto com o
    relatório principal (Case.pdf_file) ou posteriormente como complemento.
    Não são processados pelo pipeline LLM — servem como evidência humana
    para o médico.
    """

    attachment_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to=case_attachment_upload_to)
    original_filename = models.CharField(max_length=255)
    stored_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64, db_index=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="case_attachments_uploaded",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Suppression fields (auditable removal of wrong attachments)
    is_suppressed = models.BooleanField(default=False, db_index=True)
    suppressed_at = models.DateTimeField(null=True, blank=True)
    suppressed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="case_attachments_suppressed",
    )
    suppression_reason = models.TextField(blank=True)

    # Upload phase fields
    upload_phase = models.CharField(max_length=20, default="initial")  # initial | supplemental
    uploaded_when_case_status = models.CharField(max_length=30, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["case", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"CaseAttachment {self.attachment_id} [{self.original_filename}]"


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


class CaseCommunicationMessage(models.Model):
    """Mensagem de comunicação operacional vinculada a um Case.

    Append-only no MVP. A mensagem pertence sempre a exatamente um Case
    e carrega um snapshot do papel ativo do autor no momento do post.

    Suporta dois tipos:
    - user: mensagem manual com autor e papel definidos (via serviço).
    - system: mensagem sistêmica automática, sem autor, referenciando CaseEvent.

    Mensagens sistêmicas aparecem apenas na thread do caso e NÃO geram
    UserNotification, badge ou estado de lida/resolvida.
    """

    message_type = models.CharField(max_length=20, default="user")
    """user (manual) ou system (automática)."""

    message_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="communication_messages")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="case_communication_messages",
    )
    author_role = models.CharField(max_length=30, blank=True)
    body = models.TextField()
    source_event = models.OneToOneField(
        CaseEvent,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="communication_notice",
    )
    system_event_type = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["case", "created_at"])]

    def __str__(self) -> str:
        if self.message_type == "system":
            return f"CaseCommunicationMessage {self.message_id} [system: {self.system_event_type}]"
        return f"CaseCommunicationMessage {self.message_id} [{self.author_role}]"

    def clean(self) -> None:
        """Valida integridade dos campos antes de salvar.

        - Mensagens manuais (message_type='user') exigem author e author_role.
        - message_type deve ser 'user' ou 'system'.
        """
        if self.message_type == "user":
            if self.author is None:
                raise ValidationError("Mensagens manuais (message_type='user') exigem author.")
            if not self.author_role:
                raise ValidationError("Mensagens manuais (message_type='user') exigem author_role.")
        if self.message_type not in ("user", "system"):
            raise ValidationError(f"message_type inválido: '{self.message_type}'. Use 'user' ou 'system'.")
