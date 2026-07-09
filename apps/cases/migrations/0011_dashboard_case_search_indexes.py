"""Cria índices GIN trigram para busca server-side no dashboard.

Habilita pg_trgm e cria índices funcionais para:
- lower(agency_record_number) com gin_trgm_ops
- lower((structured_data #>> '{patient,name}')) com gin_trgm_ops

Usa CREATE INDEX CONCURRENTLY com atomic=False para reduzir lock
em produção.
"""

from django.db import migrations


class Migration(migrations.Migration):
    """Cria índices de busca trigram para o dashboard."""

    atomic = False

    dependencies = [
        ("cases", "0010_add_regulation_days_on_screen"),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS pg_trgm",
            reverse_sql="",
        ),
        migrations.RunSQL(
            sql="""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS cases_case_arn_trgm_idx
            ON cases_case USING gin (lower(agency_record_number) gin_trgm_ops)
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS cases_case_arn_trgm_idx
            """,
        ),
        migrations.RunSQL(
            sql="""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS cases_case_patient_name_trgm_idx
            ON cases_case USING gin (lower((structured_data #>> '{patient,name}')) gin_trgm_ops)
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS cases_case_patient_name_trgm_idx
            """,
        ),
    ]
