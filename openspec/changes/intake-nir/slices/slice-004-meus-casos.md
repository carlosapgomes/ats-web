# Slice 4: Meus Casos — Lista com Filtros

> **Status**: DONE ✅
> **Depende de**: Slice 3 (upload funcionando)
> **Change**: `openspec/changes/intake-nir/`

---

## Leitura Obrigatória Antes de Implementar

1. `AGENTS.md` — regras do projeto
2. `docs/DOMAIN_ANALYSIS.md` — seção 9 (telas), seção 3.1 (estados do caso)
3. `demo-reference/nir/dashboard.html` — layout de cards de casos
4. `apps/cases/models.py` — CaseStatus choices

---

## Handoff para Implementador (LLM com contexto zero)

### Contexto

Slice 3 implementado: upload de PDF cria caso com texto extraído.
Agora precisamos da lista de "Meus Casos" com cards no estilo demo-reference.

### Sua Tarefa

1. Criar view `my_cases` que lista casos do NIR logado (excluindo CLEANED)
2. Filtros por status e busca por número de registro
3. Cards de caso no estilo `demo-reference/nir/dashboard.html`
4. Status badges com cores por estado

### Arquivos a Criar/Modificar (idealmente <= 5)

```
apps/intake/views.py               # MODIFICAR: adicionar my_cases view
apps/intake/urls.py                 # MODIFICAR: adicionar URL my-cases/
templates/intake/intake_home.html   # MODIFICAR: integrar lista de casos
templates/intake/my_cases.html      # Criar (se separar da home)
apps/intake/tests/test_my_cases.py  # Criar
```

### Detalhes Técnicos

#### View my_cases

```python
STATUS_LABELS = {
    "NEW": "Novo",
    "R1_ACK_PROCESSING": "Processando",
    "EXTRACTING": "Extraindo dados",
    "LLM_STRUCT": "Análise IA (estrutura)",
    "LLM_SUGGEST": "Análise IA (sugestão)",
    "R2_POST_WIDGET": "Preparando avaliação",
    "WAIT_DOCTOR": "Aguardando médico",
    "DOCTOR_ACCEPTED": "Aceito pelo médico",
    "DOCTOR_DENIED": "Recusado pelo médico",
    "R3_POST_REQUEST": "Preparando agendamento",
    "WAIT_APPT": "Aguardando agendamento",
    "APPT_CONFIRMED": "Agendamento confirmado",
    "APPT_DENIED": "Agendamento negado",
    "FAILED": "Falha no processamento",
    "R1_FINAL_REPLY_POSTED": "Resultado enviado",
    "WAIT_R1_CLEANUP_THUMBS": "Aguardando confirmação",
    "CLEANUP_RUNNING": "Em limpeza",
    "CLEANED": "Concluído",
}

STATUS_CSS_CLASS = {
    "NEW": "status-pending",
    "R1_ACK_PROCESSING": "status-progress",
    "EXTRACTING": "status-progress",
    "LLM_STRUCT": "status-progress",
    "LLM_SUGGEST": "status-progress",
    "R2_POST_WIDGET": "status-progress",
    "WAIT_DOCTOR": "status-progress",
    "DOCTOR_ACCEPTED": "status-accepted",
    "DOCTOR_DENIED": "status-denied",
    "R3_POST_REQUEST": "status-progress",
    "WAIT_APPT": "status-progress",
    "APPT_CONFIRMED": "status-done",
    "APPT_DENIED": "status-denied",
    "FAILED": "status-denied",
    "WAIT_R1_CLEANUP_THUMBS": "status-pending",
    "CLEANUP_RUNNING": "status-pending",
    "CLEANED": "status-done",
}

@login_required
@role_required("nir")
def my_cases(request):
    qs = Case.objects.filter(
        created_by=request.user,
    ).exclude(status="CLEANED").order_by("-created_at")

    # Filtro por status
    status_filter = request.GET.get("status", "")
    if status_filter:
        qs = qs.filter(status=status_filter)

    # Busca por registro
    search = request.GET.get("q", "")
    if search:
        qs = qs.filter(agency_record_number__icontains=search)

    return render(request, "intake/my_cases.html", {
        "cases": qs,
        "status_filter": status_filter,
        "search": search,
        "status_labels": STATUS_LABELS,
        "status_css": STATUS_CSS_CLASS,
    })
```

#### Template — Cards de caso

Seguir o padrão do `demo-reference/nir/dashboard.html`:
- Cada caso em um `.case-card.card.p-3`
- Row com colunas: nome/registro | data + info | status badge | botão "Ver detalhes"
- Status badge com classe CSS dinâmica (`.status-progress`, `.status-done`, `.status-denied`)
- Header da página com título "Meus Casos" + contador

#### Navegação

Adicionar nav pills no `intake_home.html` e `my_cases.html`:
- "Novo Encaminhamento" (link para upload/home)
- "Meus Casos" (link para my_cases)

### TDD — Testes

1. `test_my_cases_shows_only_user_cases`: NIR vê apenas seus próprios casos
2. `test_my_cases_excludes_cleaned`: casos CLEANED não aparecem
3. `test_my_cases_filter_by_status`: filtro `?status=WAIT_DOCTOR` funciona
4. `test_my_cases_search_by_record`: busca por número de registro funciona
5. `test_my_cases_order_by_newest`: casos ordenados por created_at desc
6. `test_my_cases_shows_status_label`: HTML contém label em português
7. `test_my_cases_requires_nir_role`: doctor → blocked

### Critérios de Sucesso

```bash
uv run pytest -v
# Smoke: logar como NIR, ver lista com filtros, cards com badges coloridos
```

### Relatório

Gere `/tmp/slice-intake-004-report.md`.
Informe `REPORT_PATH=/tmp/slice-intake-004-report.md`.
