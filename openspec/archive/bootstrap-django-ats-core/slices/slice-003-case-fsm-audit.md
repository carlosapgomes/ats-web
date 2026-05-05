# Slice 3: Modelo Case + CaseEvent + FSM (17 estados)

> **Status**: TODO
> **Depende de**: Slice 2
> **Change**: `openspec/changes/bootstrap-django-ats-core/`

---

## Leitura Obrigatória Antes de Implementar

Antes de escrever qualquer código, leia estes arquivos na ordem:

1. `AGENTS.md` — regras do projeto, stack, comandos de validação, política de testes
2. `docs/adr/ADR-0001-arquitetura-django-web-ssr-ats-triagem-eda.md` — decisão arquitetural aceita
3. `docs/DOMAIN_ANALYSIS.md` — análise completa de domínio (entidades, estados, transições, eventos, permissões, telas)

Estes documentos dão o contexto de **por que** cada modelo, estado e regra existe.
Sem lê-los, você não terá contexto do domínio clínico (triagem EDA, políticas de pré-operatório, fluxo NIR-médico-agendador).

---

## Handoff para Implementador (LLM com contexto zero)

### Contexto

Você está em `/home/carlos/projects/ats-web/`, um projeto Django greenfield.
Os **Slices 1 e 2** já foram executados:
- Estrutura base Django funcional (`config/`, `manage.py`, `pyproject.toml`)
- App `accounts` com `User` (multi-role M2M) e `Role`
- Login/logout com seleção de papel ativo na sessão

Leia `AGENTS.md` para regras do projeto.

### Sua Tarefa

Criar o app `cases` com o modelo `Case` (FSM de 17 estados via django-fsm)
e `CaseEvent` (auditoria append-only). Cada transição de estado deve registrar
automaticamente um evento de auditoria.

### Arquivos a Criar/Modificar (idealmente <= 6)

```
apps/cases/__init__.py
apps/cases/models.py       # CaseStatus, Case, CaseEvent + FSM transitions
apps/cases/admin.py        # admin registration
apps/cases/apps.py         # AppConfig
config/settings/base.py    # adicionar "apps.cases" em INSTALLED_APPS
```

### Detalhes Técnicos

#### apps/cases/models.py

```python
import uuid
from django.conf import settings
from django.db import models
from django_fsm import FSMField, transition


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
        null=True, blank=True,
        related_name="cases_decided",
    )
    doctor_decision = models.CharField(max_length=10, blank=True)  # accept/deny
    doctor_support_flag = models.CharField(max_length=20, blank=True, default="none")
    doctor_admission_flow = models.CharField(max_length=15, blank=True)  # scheduled/immediate
    doctor_reason = models.TextField(blank=True)
    doctor_decided_at = models.DateTimeField(null=True, blank=True)

    # Scheduler decision
    scheduler = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="cases_scheduled",
    )
    appointment_status = models.CharField(max_length=15, blank=True)  # confirmed/denied
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

    # --- FSM Transitions ---
    # Seguem o grafo exato do legado (ver DOMAIN_ANALYSIS.md seção 3.2)

    @transition(field=status, source=CaseStatus.NEW, target=CaseStatus.R1_ACK_PROCESSING)
    def start_processing(self, user=None):
        self._record_event("CASE_START_PROCESSING", user=user)

    @transition(field=status, source=CaseStatus.R1_ACK_PROCESSING, target=CaseStatus.EXTRACTING)
    def start_extraction(self, user=None):
        self._record_event("CASE_START_EXTRACTION", user=user)

    @transition(
        field=status,
        source=CaseStatus.EXTRACTING,
        target=[CaseStatus.LLM_STRUCT, CaseStatus.FAILED],
    )
    def extraction_complete(self, success: bool, user=None):
        if not success:
            self._record_event("CASE_EXTRACTION_FAILED", user=user)

    @transition(
        field=status,
        source=CaseStatus.LLM_STRUCT,
        target=[CaseStatus.LLM_SUGGEST, CaseStatus.FAILED],
    )
    def llm1_complete(self, success: bool, user=None):
        self._record_event(
            "LLM1_OK" if success else "LLM1_FAILED",
            user=user,
        )

    @transition(
        field=status,
        source=CaseStatus.LLM_SUGGEST,
        target=[CaseStatus.R2_POST_WIDGET, CaseStatus.FAILED],
    )
    def llm2_complete(self, success: bool, user=None):
        self._record_event(
            "LLM2_OK" if success else "LLM2_FAILED",
            user=user,
        )

    @transition(field=status, source=CaseStatus.R2_POST_WIDGET, target=CaseStatus.WAIT_DOCTOR)
    def ready_for_doctor(self, user=None):
        self._record_event("CASE_READY_FOR_DOCTOR", user=user)

    @transition(
        field=status,
        source=CaseStatus.WAIT_DOCTOR,
        target=[CaseStatus.DOCTOR_ACCEPTED, CaseStatus.DOCTOR_DENIED],
    )
    def doctor_decide(self, decision: str, user=None):
        self._record_event(
            f"DOCTOR_{decision.upper()}",
            user=user,
            payload={"decision": decision},
        )

    @transition(field=status, source=CaseStatus.DOCTOR_ACCEPTED, target=CaseStatus.R3_POST_REQUEST)
    def ready_for_scheduler(self, user=None):
        self._record_event("CASE_READY_FOR_SCHEDULER", user=user)

    @transition(field=status, source=CaseStatus.R3_POST_REQUEST, target=CaseStatus.WAIT_APPT)
    def scheduler_request_posted(self, user=None):
        self._record_event("SCHEDULER_REQUEST_POSTED", user=user)

    @transition(
        field=status,
        source=CaseStatus.WAIT_APPT,
        target=[CaseStatus.APPT_CONFIRMED, CaseStatus.APPT_DENIED],
    )
    def scheduler_decide(self, appointment_status: str, user=None):
        self._record_event(
            f"APPT_{appointment_status.upper()}",
            user=user,
            payload={"appointment_status": appointment_status},
        )

    @transition(
        field=status,
        source=[
            CaseStatus.DOCTOR_DENIED,
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

    @transition(field=status, source=CaseStatus.CLEANUP_RUNNING, target=CaseStatus.CLEANED)
    def cleanup_completed(self, user=None):
        self._record_event("CLEANUP_COMPLETED", user=user)

    def _record_event(
        self,
        event_type: str,
        *,
        user=None,
        payload: dict | None = None,
    ) -> None:
        """Cria CaseEvent. Chamado via signal após save() — ver abaixo."""
        # Evento é criado via post_save signal para garantir que o caso foi salvo.
        # Guardamos os dados para o signal usar.
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
    actor_type = models.CharField(max_length=10)  # system, bot, human
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
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
```

#### Auditoria automática via signal

Criar `apps/cases/signals.py`:

```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Case, CaseEvent


@receiver(post_save, sender=Case)
def record_case_event(sender, instance: Case, created: bool, **kwargs):
    """Registra evento pendente após save do Case."""
    if created:
        CaseEvent.objects.create(
            case=instance,
            event_type="CASE_CREATED",
            actor=instance.created_by,
            actor_type="human",
            payload={"status": instance.status},
        )
        return

    pending = getattr(instance, "_pending_event", None)
    if pending:
        CaseEvent.objects.create(
            case=instance,
            event_type=pending["event_type"],
            actor=pending["actor"],
            actor_type=pending["actor_type"],
            payload=pending["payload"],
        )
        instance._pending_event = None
```

Registrar signal em `apps/cases/apps.py`:

```python
class CasesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cases"

    def ready(self):
        import apps.cases.signals  # noqa: F401
```

### TDD — Testes a Escrever PRIMEIRO

Criar `apps/cases/tests/` com:

1. **test_models.py**:
   - `test_create_case_default_status`: novo caso tem status NEW
   - `test_case_has_uuid_pk`: PK é UUID
   - `test_case_created_by_required`: created_by é obrigatório
   - `test_case_str_representation`: __str__ retorna formato esperado

2. **test_fsm.py** (CRÍTICO — testa o coração do sistema):
   - `test_transition_new_to_r1_ack`: NEW → R1_ACK_PROCESSING
   - `test_transition_r1_ack_to_extracting`: R1_ACK_PROCESSING → EXTRACTING
   - `test_transition_extracting_to_llm_struct_success`: EXTRACTING → LLM_STRUCT
   - `test_transition_extracting_to_failed`: EXTRACTING → FAILED
   - `test_transition_llm_struct_to_llm_suggest`: LLM_STRUCT → LLM_SUGGEST
   - `test_transition_llm_suggest_to_r2_post_widget`: LLM_SUGGEST → R2_POST_WIDGET
   - `test_transition_r2_post_widget_to_wait_doctor`: R2_POST_WIDGET → WAIT_DOCTOR
   - `test_transition_wait_doctor_to_accepted`: WAIT_DOCTOR → DOCTOR_ACCEPTED
   - `test_transition_wait_doctor_to_denied`: WAIT_DOCTOR → DOCTOR_DENIED
   - `test_transition_accepted_to_r3_post_request`: DOCTOR_ACCEPTED → R3_POST_REQUEST
   - `test_transition_r3_to_wait_appt`: R3_POST_REQUEST → WAIT_APPT
   - `test_transition_wait_appt_to_confirmed`: WAIT_APPT → APPT_CONFIRMED
   - `test_transition_wait_appt_to_denied`: WAIT_APPT → APPT_DENIED
   - `test_transition_denied_to_wait_cleanup`: DOCTOR_DENIED → WAIT_R1_CLEANUP_THUMBS
   - `test_transition_confirmed_to_wait_cleanup`: APPT_CONFIRMED → WAIT_R1_CLEANUP_THUMBS
   - `test_transition_wait_cleanup_to_running`: WAIT_R1_CLEANUP_THUMBS → CLEANUP_RUNNING
   - `test_transition_running_to_cleaned`: CLEANUP_RUNNING → CLEANED
   - `test_invalid_transition_raises`: NEW → WAIT_DOCTOR (direto) levanta TransitionNotAllowed

3. **test_audit.py**:
   - `test_create_case_generates_case_created_event`: criar caso gera evento CASE_CREATED
   - `test_transition_generates_event`: cada transição gera evento com tipo correto
   - `test_event_records_actor`: evento registra quem executou
   - `test_event_payload_captured`: evento captura payload quando fornecido
   - `test_events_ordered_by_timestamp`: eventos ficam em ordem cronológica
   - `test_full_lifecycle_events`: percorrer fluxo completo e verificar todos os eventos

### Critérios de Sucesso (Self-Eval Gates)

```bash
# Gate 1: migrations
uv run python manage.py makemigrations cases --settings=config.settings.dev
uv run python manage.py migrate --settings=config.settings.dev

# Gate 2: Django check
uv run python manage.py check --settings=config.settings.dev

# Gate 3: testes FSM (o mais importante)
uv run pytest apps/cases/tests/ -v
# Esperado: TODOS passando — FSM é o coração do sistema

# Gate 4: teste de cobertura do ciclo de vida completo
uv run pytest apps/cases/tests/test_audit.py::test_full_lifecycle_events -v
# Esperado: passa com eventos do fluxo NEW → ... → CLEANED
```

### Relatório

Gere `/tmp/slice-003-report.md`.Informe `REPORT_PATH=/tmp/slice-003-report.md`.
