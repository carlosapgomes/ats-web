# Identidade local do paciente extraída programaticamente (PI-01/PI-02).

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cases", "0021_alter_caseprocedure_procedure_type_catalog_expanded"),
    ]

    operations = [
        migrations.AddField(
            model_name="case",
            name="patient_identity_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="case",
            name="patient_identity_social_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="case",
            name="patient_identity_cns",
            field=models.CharField(blank=True, max_length=15),
        ),
        migrations.AddField(
            model_name="case",
            name="patient_identity_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("extracted", "Extracted"),
                    ("absent", "Absent"),
                    ("ambiguous", "Ambiguous"),
                    ("failed", "Failed"),
                ],
                max_length=20,
            ),
        ),
    ]
