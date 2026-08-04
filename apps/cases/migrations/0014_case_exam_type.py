"""Slice 002 — Case.exam_type com backfill EDA e índice composto (status, exam_type).

Decisões:
- Backfill integral para EDA sem consultar artefatos clínicos (sem leitura de
  PDF/JSON/texto) e sem reprocessar: AddField com default histórico + RunPython
  explícito e idempotente (elidable) que força EDA em todas as linhas.
- Nenhum status/decisão/evento histórico é alterado.
- O default ``eda`` é mantido no modelo final para compatibilidade de fixtures
  (custo de remoção desproporcional: dezenas de fixtures/tests criam Case sem
  tipo); novos uploads exigem tipo explícito no serviço/views.
"""

from django.db import migrations, models


def backfill_exam_type_eda(apps, schema_editor):
    """Força exam_type='eda' em todos os casos existentes, sem ler artefatos.

    Idempotente e sem efeitos colaterais (não cria eventos, não muda FSM,
    não reprocessa). Cobre inclusive casos legados scope-gated.
    """
    Case = apps.get_model("cases", "Case")
    db_alias = schema_editor.connection.alias
    Case.objects.using(db_alias).update(exam_type="eda")


class Migration(migrations.Migration):
    dependencies = [
        ("cases", "0013_case_priority_signals"),
    ]

    operations = [
        migrations.AddField(
            model_name="case",
            name="exam_type",
            field=models.CharField(
                choices=[("eda", "EDA"), ("colonoscopy", "Colonoscopia")],
                default="eda",
                max_length=20,
            ),
        ),
        migrations.RunPython(
            code=backfill_exam_type_eda,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
        migrations.AddIndex(
            model_name="case",
            index=models.Index(
                fields=["status", "exam_type"],
                name="cases_status_exam_type_idx",
            ),
        ),
    ]
