"""Slice 011-C — Cutover físico: precheck fail-closed e remoção da coluna ponte.

Antes de remover o índice composto e a coluna, um ``RunPython`` fail-closed
valida no banco histórico que TODO caso possui 1–2 rows ``CaseProcedure``
válidas (tipos ``eda|colonoscopy``, sem duplicata por caso/tipo e ao menos uma
row declarada pelo NIR). Qualquer violação aborta a migration com erro
explícito (identificador do caso incluído) ANTES de qualquer mudança de schema.

Forward determinístico (R2): remove somente ``cases_status_exam_type_idx`` e
``Case.exam_type``; preserva Case, CaseProcedure, CaseEvent, JSON 1.1/2.0,
PDF, anexos, decisões e agenda. Sem reverse migration silenciosa: rollback
para imagem antiga pertence à bridge documentada no Slice 012 (ADR-0004 D9).
"""

from django.db import migrations

_VALID_PROCEDURE_TYPES = {"eda", "colonoscopy"}


def validate_case_procedures_for_cutover(apps, schema_editor):
    """Fail-closed (R1): exige 1–2 rows CaseProcedure válidas por Case.

    Não inventa EDA e não lê JSON/texto para reparar: qualquer ausência, tipo
    inválido, duplicata ou conjunto sem declaração NIR aborta a migration.
    """
    Case = apps.get_model("cases", "Case")
    CaseProcedure = apps.get_model("cases", "CaseProcedure")
    db_alias = schema_editor.connection.alias

    case_ids = Case.objects.using(db_alias).values_list("case_id", flat=True)
    for case_id in case_ids.iterator(chunk_size=500):
        rows = list(
            CaseProcedure.objects.using(db_alias)
            .filter(case_id=case_id)
            .order_by("procedure_type")
        )
        if not rows:
            raise RuntimeError(
                f"Cutover bloqueado: Case {case_id} não possui rows CaseProcedure; "
                "não é possível remover Case.exam_type sem projeção declarada."
            )
        if len(rows) > 2:
            raise RuntimeError(
                f"Cutover bloqueado: Case {case_id} possui {len(rows)} rows "
                "CaseProcedure (máximo 2: EDA e Colonoscopia)."
            )
        seen: set[str] = set()
        for row in rows:
            if row.procedure_type not in _VALID_PROCEDURE_TYPES:
                raise RuntimeError(
                    f"Cutover bloqueado: Case {case_id} possui tipo inválido "
                    f"{row.procedure_type!r}; aceitos: eda|colonoscopy."
                )
            if row.procedure_type in seen:
                raise RuntimeError(
                    f"Cutover bloqueado: Case {case_id} possui duplicata "
                    f"{row.procedure_type!r} por caso/tipo."
                )
            seen.add(row.procedure_type)
        if not any(row.declared_by_nir for row in rows):
            raise RuntimeError(
                f"Cutover bloqueado: Case {case_id} não possui row declarada pelo "
                "NIR (declared_by_nir=True)."
            )


class Migration(migrations.Migration):
    dependencies = [
        ("cases", "0015_caseprocedure"),
    ]

    operations = [
        migrations.RunPython(
            code=validate_case_procedures_for_cutover,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RemoveIndex(
            model_name="case",
            name="cases_status_exam_type_idx",
        ),
        migrations.RemoveField(
            model_name="case",
            name="exam_type",
        ),
    ]
