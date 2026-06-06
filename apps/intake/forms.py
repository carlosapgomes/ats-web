"""Forms para o app intake."""

from django import forms

from apps.cases.services import (
    POST_SCHEDULE_ISSUE_REASONS,
    POST_SCHEDULE_ISSUE_REASONS_MESSAGE_OPTIONAL,
)


class CaseUploadForm(forms.Form):
    """Formulário de upload de PDFs de encaminhamento.

    A validação e processamento dos arquivos é feita via
    ``services.process_uploaded_files`` usando ``request.FILES.getlist()``
    diretamente, já que o ``FileField`` do Django não suporta seleção
    múltipla de arquivos de forma nativa.
    """

    # The ``pdf_files`` field is intentionally omitted from the Form class.
    # Files are read via ``request.FILES.getlist("pdf_files")`` in the view
    # and validated/processed by ``apps.intake.services.process_uploaded_files``.
    # This avoids Django's single-file Field limitations for multi-upload.

    pass


REASON_CHOICES = [
    ("", "---"),
    ("death", "Paciente faleceu"),
    ("clinical_condition", "Paciente sem condição clínica de transporte"),
    ("transport_unavailable", "Transporte indisponível pela unidade de origem"),
    ("external_regulation", "Exame realizado pela regulação estadual em outro serviço"),
    ("reschedule_request", "Solicitação de reagendamento pela unidade de origem"),
    ("other", "Outro"),
]


class PostScheduleIssueForm(forms.Form):
    """Formulário NIR para abrir intercorrência pós-agendamento.

    Valida motivo oficial e mensagem condicional conforme regras de negócio.
    """

    reason = forms.ChoiceField(
        choices=REASON_CHOICES,
        label="Motivo",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    message = forms.CharField(
        label="Mensagem",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Descreva o motivo da intercorrência (obrigatório para o motivo selecionado)",
            }
        ),
    )

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        if cleaned_data is None:
            cleaned_data = {}
        reason = cleaned_data.get("reason")
        message = cleaned_data.get("message", "")

        if not reason:
            self.add_error("reason", "Selecione um motivo para a intercorrência.")
        elif reason not in POST_SCHEDULE_ISSUE_REASONS:
            self.add_error("reason", f"Motivo inválido: {reason}")
        elif reason not in POST_SCHEDULE_ISSUE_REASONS_MESSAGE_OPTIONAL and not (message or "").strip():
            self.add_error("message", "Mensagem é obrigatória para o motivo selecionado.")

        return cleaned_data
