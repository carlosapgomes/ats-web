# Slice 3: Upload de PDF + Criação do Caso

> **Status**: TODO
> **Depende de**: Slice 2 (app intake + decorator)
> **Change**: `openspec/changes/intake-nir/`

---

## Leitura Obrigatória Antes de Implementar

1. `AGENTS.md` — regras do projeto
2. `docs/DOMAIN_ANALYSIS.md` — seção 3 (FSM), seção 4.1 (fluxo NIR intake), seção 9 (telas)
3. `apps/cases/models.py` — modelo Case, FSM transitions, CaseStatus
4. `demo-reference/nir/dashboard.html` — upload zone com drag & drop

---

## Handoff para Implementador (LLM com contexto zero)

### Contexto

Você está em `/home/carlos/projects/ats-web/`. Slices 1-2 da Fase 1 concluídos.
App `apps/intake/` existe com decorator `role_required`. Tema hospitalar no CSS.

### Sua Tarefa

1. Criar view e form de upload de PDF
2. No POST: salvar PDF, criar Case (status NEW), transicionar para R1_ACK_PROCESSING → EXTRACTING
3. Extrair texto do PDF com PyMuPDF (`pymupdf` / `fitz`)
4. Armazenar texto extraído em `case.extracted_text`
5. Preencher `agency_record_number` a partir do campo do formulário
6. Template com drag & drop no estilo demo-reference

### Dependência nova

```bash
uv add pymupdf
```

### Arquivos a Criar/Modificar (idealmente <= 6)

```
apps/intake/forms.py              # Criar (CaseUploadForm)
apps/intake/views.py              # MODIFICAR: adicionar upload_view
apps/intake/urls.py               # MODIFICAR: adicionar URL upload
templates/intake/intake_home.html # REESCREVER com upload zone + lista
templates/intake/upload_success.html # Criar (confirmação pós-upload)
apps/intake/tests/test_upload.py  # Criar
static/js/upload.js               # Criar (drag & drop vanilla JS)
```

### Detalhes Técnicos

#### apps/intake/forms.py

```python
from django import forms

class CaseUploadForm(forms.Form):
    pdf_file = forms.FileField(
        label="Encaminhamento (PDF)",
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf", "class": "d-none"}),
    )
    agency_record_number = forms.CharField(
        label="Número do Registro",
        max_length=20,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ex: 2026-0428-001",
        }),
    )
```

#### apps/intake/views.py — upload_view

```python
@login_required
@role_required("nir")
def upload_view(request):
    if request.method == "POST":
        form = CaseUploadForm(request.POST, request.FILES)
        if form.is_valid():
            case = Case.objects.create(
                created_by=request.user,
                agency_record_number=form.cleaned_data["agency_record_number"],
            )
            # Salvar PDF
            case.pdf_file = form.cleaned_data["pdf_file"]
            case.save()

            # FSM: NEW → R1_ACK_PROCESSING → EXTRACTING
            case.start_processing(user=request.user)
            case.save()
            case.start_extraction(user=request.user)
            case.save()

            # Extrair texto do PDF
            extracted = extract_pdf_text(case.pdf_file.path)
            case.extracted_text = extracted
            case.agency_record_extracted_at = timezone.now()
            case.save()

            return redirect("intake:case_detail", case_id=case.case_id)
    else:
        form = CaseUploadForm()

    # Mostrar casos recentes também
    recent_cases = Case.objects.filter(
        created_by=request.user
    ).exclude(status="CLEANED").order_by("-created_at")[:10]

    return render(request, "intake/intake_home.html", {
        "form": form,
        "recent_cases": recent_cases,
    })
```

#### Extração de texto — função helper

Criar em `apps/intake/pdf_utils.py`:

```python
import fitz  # PyMuPDF

def extract_pdf_text(pdf_path: str) -> str:
    """Extrai texto de todas as páginas do PDF."""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text.strip()
```

#### Template — upload zone (Vanilla JS)

Usar o padrão do `demo-reference/nir/dashboard.html`:
- Div com borda dashed para drag & drop
- Input file hidden, triggerado por click na div
- JS vanilla: dragover, dragleave, drop, change events
- Preview do arquivo selecionado
- Validação client-side: apenas PDF, até 20MB

**NÃO usar** nenhuma lib JS. Vanilla JS apenas em `static/js/upload.js`.

#### config/settings/base.py

Verificar se `MEDIA_ROOT` e `MEDIA_URL` estão configurados (já estão do bootstrap).
Adicionar config de tamanho máximo de upload se necessário:

```python
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024   # 20 MB
```

### TDD — Testes a Escrever PRIMEIRO

#### apps/intake/tests/test_upload.py

Criar um PDF de teste simples no fixture (usar PyMuPDF para gerar).

1. `test_upload_page_renders`: GET /cases/ → 200 com form de upload
2. `test_upload_creates_case`: POST com PDF + registro → Case criado no banco
3. `test_upload_sets_created_by`: case.created_by == request.user
4. `test_upload_saves_pdf_file`: case.pdf_file existe no MEDIA_ROOT
5. `test_upload_transitions_to_extracting`: case.status == EXTRACTING após upload
6. `test_upload_extracts_text`: case.extracted_text contém texto do PDF
7. `test_upload_sets_agency_record_number`: case.agency_record_number pego do form
8. `test_upload_rejects_non_pdf`: POST com .txt → form inválido
9. `test_upload_requires_nir_role`: doctor → redirect/blocked
10. `test_upload_requires_login`: sem login → redirect /login/
11. `test_upload_generates_case_created_event`: CaseEvent CASE_CREATED gerado
12. `test_upload_generates_processing_events`: CaseEvents para start_processing + start_extraction + CASE_EXTRACTION_OK

### Critérios de Sucesso

```bash
uv add pymupdf
uv run python manage.py check --settings=config.settings.dev
uv run pytest -v
# Esperado: todos passando

# Smoke test:
uv run python manage.py runserver --settings=config.settings.dev
# 1. Logar como nir
# 2. /cases/ mostra upload zone
# 3. Fazer upload de PDF
# 4. Ver caso criado com texto extraído
```

### Relatório

Gere `/tmp/slice-intake-003-report.md`.
Informe `REPORT_PATH=/tmp/slice-intake-003-report.md`.
