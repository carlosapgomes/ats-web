"""Forms para o app intake."""

from django import forms


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
