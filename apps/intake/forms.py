"""Forms para o app intake."""

from django import forms
from django.core.validators import FileExtensionValidator


class CaseUploadForm(forms.Form):
    """Formulário de upload de PDF de encaminhamento."""

    pdf_file = forms.FileField(
        label="Encaminhamento (PDF)",
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
        widget=forms.ClearableFileInput(
            attrs={
                "accept": ".pdf",
                "class": "d-none",
                "id": "file-input",
            }
        ),
    )
    agency_record_number = forms.CharField(
        label="Número do Registro",
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Ex: 2026-0428-001",
            }
        ),
    )
