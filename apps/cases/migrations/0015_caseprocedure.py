"""Slice 001 — CaseProcedure: projeção normalizada + backfill conservador D3.

Decisões (design D1/D3):
- ``CreateModel`` com unique constraint ``(case, procedure_type)`` e os três
  índices dimensionais fechados (declarado/detectado/autorizado) — criados
  ANTES de qualquer consumer de fila migrar.
- Backfill cria EXATAMENTE uma row declarada por caso a partir de
  ``Case.exam_type`` atual; não reprocessa, não altera status/eventos/PDF/JSON/
  agenda e não infere `not_detected`.
- Tabela fechada: os 18 estados de ``CaseStatus`` (4 → pending, 9 → detected,
  5 condicionais com marcador downstream → detected, sem marcador → pending).
  Marcador downstream: doctor_decision em {accept, deny}, appointment_status
  preenchido ou evento LLM2_OK/LLM2_FAILED/CASE_READY_FOR_DOCTOR/DOCTOR_ACCEPT/
  DOCTOR_DENY/CASE_READY_FOR_SCHEDULER. LLM1_OK isolado NÃO basta.
- ``doctor_disposition`` também fechada: accept → approved (razão vazia),
  deny → denied (cópia exata de doctor_reason), qualquer outro → pending.
- Forward e reverse determinísticos; reverse apaga as rows (a tabela é
  removida pelo reverse do CreateModel).
"""

from django.db import migrations, models

# ── Tabela fechada D3 ──────────────────────────────────────────────────────

_PENDING_STATUSES = {"NEW", "R1_ACK_PROCESSING", "EXTRACTING", "LLM_STRUCT"}
_DETECTED_STATUSES = {
    "LLM_SUGGEST",
    "R2_POST_WIDGET",
    "WAIT_DOCTOR",
    "DOCTOR_DENIED",
    "DOCTOR_ACCEPTED",
    "R3_POST_REQUEST",
    "WAIT_APPT",
    "APPT_CONFIRMED",
    "APPT_DENIED",
}
_CONDITIONAL_STATUSES = {
    "FAILED",
    "R1_FINAL_REPLY_POSTED",
    "WAIT_R1_CLEANUP_THUMBS",
    "CLEANUP_RUNNING",
    "CLEANED",
}

_DOWNSTREAM_MARKER_EVENTS = {
    "LLM2_OK",
    "LLM2_FAILED",
    "CASE_READY_FOR_DOCTOR",
    "DOCTOR_ACCEPT",
    "DOCTOR_DENY",
    "CASE_READY_FOR_SCHEDULER",
}


def backfill_case_procedures(apps, schema_editor):
    """Cria exatamente uma row declarada por caso, conforme tabela D3.

    Não lê texto clínico, não reprocessa e não altera nenhum campo/evento do
    caso. Idempotente por natureza (uma row por (case, procedure_type)); em
    banco já migrado com rows existentes, poderia duplicar — por isso este
    backfill roda apenas na primeira aplicação da migration (forward).
    """
    Case = apps.get_model("cases", "Case")
    CaseEvent = apps.get_model("cases", "CaseEvent")
    CaseProcedure = apps.get_model("cases", "CaseProcedure")
    db_alias = schema_editor.connection.alias

    marker_case_ids = set(
        CaseEvent.objects.using(db_alias)
        .filter(event_type__in=_DOWNSTREAM_MARKER_EVENTS)
        .values_list("case_id", flat=True)
    )

    cases = Case.objects.using(db_alias).all().iterator(chunk_size=500)
    for case in cases:
        status = str(case.status)
        if status in _PENDING_STATUSES:
            detection = "pending"
        elif status in _DETECTED_STATUSES:
            detection = "detected"
        elif status in _CONDITIONAL_STATUSES:
            has_marker = (
                case.doctor_decision in ("accept", "deny")
                or bool(case.appointment_status)
                or case.case_id in marker_case_ids
            )
            detection = "detected" if has_marker else "pending"
        else:
            # Tabela fechada cobre os 18 estados; qualquer valor inesperado
            # permanece conservador (pending), nunca inferindo detecção.
            detection = "pending"

        if case.doctor_decision == "accept":
            disposition, reason = "approved", ""
        elif case.doctor_decision == "deny":
            disposition, reason = "denied", case.doctor_reason or ""
        else:
            disposition, reason = "pending", ""

        CaseProcedure.objects.using(db_alias).create(
            case_id=case.case_id,
            procedure_type=case.exam_type,
            declared_by_nir=True,
            detection_status=detection,
            doctor_disposition=disposition,
            doctor_reason=reason,
        )


def reverse_backfill_case_procedures(apps, schema_editor):
    """Reverse determinístico: remove as rows criadas pelo backfill.

    O reverse do ``CreateModel`` derruba a tabela em seguida; apagar as rows
    primeiro mantém a reversão explícita e testável sem depender de DDL.
    """
    CaseProcedure = apps.get_model("cases", "CaseProcedure")
    db_alias = schema_editor.connection.alias
    CaseProcedure.objects.using(db_alias).all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("cases", "0014_case_exam_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="CaseProcedure",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("procedure_type", models.CharField(max_length=20, choices=[("eda", "EDA"), ("colonoscopy", "Colonoscopia")])),
                ("declared_by_nir", models.BooleanField(default=False)),
                (
                    "detection_status",
                    models.CharField(
                        choices=[("pending", "Pendente"), ("detected", "Detectado"), ("not_detected", "Não detectado")],
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "doctor_disposition",
                    models.CharField(
                        choices=[("pending", "Pendente"), ("approved", "Aprovado"), ("denied", "Negado")],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("doctor_reason", models.TextField(blank=True)),
                (
                    "case",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="procedures",
                        to="cases.case",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=["case", "procedure_type"], name="uniq_case_procedure_type"),
                ],
                "indexes": [
                    models.Index(fields=["procedure_type", "declared_by_nir", "case"], name="proc_declared_idx"),
                    models.Index(fields=["procedure_type", "detection_status", "case"], name="proc_detection_idx"),
                    models.Index(fields=["procedure_type", "doctor_disposition", "case"], name="proc_disposition_idx"),
                ],
            },
        ),
        migrations.RunPython(
            code=backfill_case_procedures,
            reverse_code=reverse_backfill_case_procedures,
        ),
    ]
