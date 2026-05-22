# Design: Upload Múltiplo NIR com Extração PDF Assíncrona

## D1. Arquitetura alvo

```text
NIR /cases/ POST multipart com N PDFs
  ↓
View valida lote e arquivos
  ↓
Para cada PDF válido:
  - cria Case
  - salva pdf_file
  - transiciona NEW → R1_ACK_PROCESSING
  - registra eventos de aceite do upload
  - enqueue_pdf_extraction(case_id) na fila "pdf"
  ↓
Redirect para Meus Casos / tela de status
  ↓
pdf_worker (django-q2 cluster "pdf")
  - executa execute_pdf_extraction(case_id)
  - valida idempotência e status
  - transiciona R1_ACK_PROCESSING → EXTRACTING
  - extrai texto do PDF
  - remove marca d'água e extrai registro
  - salva extracted_text, agency_record_number, agency_record_extracted_at
  - transiciona EXTRACTING → LLM_STRUCT
  - enqueue_pipeline(case_id) na fila "llm"
  ↓
llm_worker (django-q2 cluster "llm")
  - executa pipeline LLM existente
```

## D2. Upload múltiplo

### Form

Substituir/adaptar `CaseUploadForm` para aceitar múltiplos arquivos. Como `forms.FileField` não modela bem múltiplos arquivos em todas as versões do Django, preferir uma abordagem explícita:

- widget com `multiple`;
- validação de cada `UploadedFile` em serviço/função própria;
- uso de `request.FILES.getlist("pdf_files")` ou nome equivalente.

Nome recomendado do campo: `pdf_files`.

### Limites

Configurar constantes em settings com defaults seguros:

```python
INTAKE_MAX_FILES_PER_BATCH = 30
INTAKE_MAX_UPLOAD_BYTES_PER_FILE = 20 * 1024 * 1024
INTAKE_MAX_UPLOAD_BYTES_PER_BATCH = 600 * 1024 * 1024
```

Os nomes exatos podem variar, mas devem ficar centralizados e testáveis.

### UX

`static/js/upload.js` deve:

- aceitar seleção múltipla e drag & drop múltiplo;
- listar arquivos selecionados;
- validar extensão/tipo e tamanho por arquivo;
- exibir total do lote;
- habilitar submit se houver ao menos 1 arquivo válido;
- não depender de framework JS.

A validação client-side é apenas conveniência. A validação server-side é obrigatória.

## D3. Serviço de criação de casos de upload

Evitar lógica extensa na view. Criar serviço pequeno, preferencialmente em `apps/intake/services.py`:

```python
def create_case_from_uploaded_pdf(*, user, uploaded_file) -> Case:
    ...
```

Responsabilidades:

1. Criar `Case(created_by=user)`.
2. Salvar `pdf_file`.
3. Transicionar `start_processing(user=user)` para `R1_ACK_PROCESSING`.
4. Registrar eventos já existentes da FSM.
5. Enfileirar extração PDF.
6. Retornar `Case`.

Se a validação do arquivo falhar antes de criar o caso, não criar `Case`.

## D4. Task de extração PDF

Criar `apps/intake/tasks.py`:

```python
def enqueue_pdf_extraction(case_id: uuid.UUID) -> None:
    async_task(
        "apps.intake.tasks.execute_pdf_extraction",
        str(case_id),
        q_options={"cluster": "pdf", "task_name": f"pdf:{case_id}"},
    )


def execute_pdf_extraction(case_id_str: str) -> None:
    ...
```

### Responsabilidades da task

1. Buscar o `Case`.
2. Se o caso já está após `LLM_STRUCT`, não reprocessar e registrar/retornar idempotentemente.
3. Se `pdf_file` ausente, marcar falha controlada.
4. Transicionar para `EXTRACTING` quando iniciar.
5. Extrair texto usando `extract_pdf_text`.
6. Aplicar `strip_watermark_and_extract_record`.
7. Salvar `extracted_text`, `agency_record_number`, `agency_record_extracted_at`.
8. Transicionar para `LLM_STRUCT` com `extraction_complete(success=True, user=None ou system)`.
9. Enfileirar pipeline LLM via `enqueue_pipeline(case.case_id)`.
10. Em exceção, registrar `CaseEvent` e transicionar para `FAILED` usando transição FSM apropriada.

### Idempotência

A task deve ser segura para retry:

- Se `status in {LLM_STRUCT, LLM_SUGGEST, R2_POST_WIDGET, WAIT_DOCTOR, ...}`, não extrair novamente.
- Se `extracted_text` existe e status é `LLM_STRUCT`, não enfileirar LLM duplicado sem checagem.
- Evitar múltiplos enqueues LLM para o mesmo caso quando possível. Se não houver garantia forte no `django-q2`, registrar o risco e proteger no início da pipeline LLM pelo status esperado.

## D5. Ajuste da pipeline LLM para cluster `llm`

Alterar `apps/pipeline/tasks.py`:

```python
def enqueue_pipeline(case_id: uuid.UUID) -> None:
    async_task(
        "apps.pipeline.tasks.execute_pipeline",
        str(case_id),
        q_options={"cluster": "llm", "task_name": f"llm:{case_id}"},
    )
```

A pipeline deve continuar validando status esperado no orchestrator. Se necessário, adicionar guarda para não executar caso ainda não esteja em `LLM_STRUCT`.

## D6. Configuração `django-q2`

Configurar `ALT_CLUSTERS` em `config/settings/base.py` e sobrescrever valores de produção em `prod.py` se necessário.

Exemplo conceitual:

```python
Q_CLUSTER = {
    "name": "ats",
    "cluster_name": "llm",
    "workers": 1,
    "timeout": 900,
    "retry": 1200,
    "save_limit": 250,
    "queue_limit": 100,
    "catch_up": False,
    "poll": 1.0,
    "orm": "default",
    "ALT_CLUSTERS": {
        "pdf": {
            "workers": 2,
            "timeout": 180,
            "retry": 300,
            "save_limit": 500,
            "queue_limit": 500,
            "catch_up": False,
            "poll": 1.0,
            "orm": "default",
        },
        "llm": {
            "workers": 1,
            "timeout": 900,
            "retry": 1200,
            "save_limit": 500,
            "queue_limit": 200,
            "catch_up": False,
            "poll": 2.0,
            "orm": "default",
        },
    },
}
```

Produção pode começar com:

- PDF: 2–4 workers;
- LLM: 1–2 workers.

A concorrência LLM deve ser conservadora por rate limit/custo.

## D7. Docker Compose

### Desenvolvimento

Adicionar serviço `pdf_worker` em `docker-compose.dev.yml`:

```yaml
pdf_worker:
  command: uv run python manage.py qcluster --settings=config.settings.dev
  environment:
    Q_CLUSTER_NAME: pdf
```

Garantir que `worker` atual rode como cluster `llm`:

```yaml
worker:
  environment:
    Q_CLUSTER_NAME: llm
```

### Produção

Adicionar `pdf_worker` e garantir volume de media compartilhado:

```yaml
web:
  volumes:
    - media_prod:/app/media

pdf_worker:
  volumes:
    - media_prod:/app/media

worker:
  volumes:
    - media_prod:/app/media  # opcional hoje, útil para inspeção/futuro

volumes:
  media_prod:
```

Em desenvolvimento, o bind mount `.:/app` já tende a compartilhar `media/`, mas a configuração deve ser explícita se houver divergência de `MEDIA_ROOT`.

## D8. UI de acompanhamento

Após upload em lote, redirecionar preferencialmente para `intake:my_cases` ou para uma seção da home com mensagem:

```text
30 encaminhamentos recebidos. O processamento continuará em background.
```

A lista de casos já deve mostrar estados como `R1_ACK_PROCESSING`, `EXTRACTING`, `LLM_STRUCT`, etc. Se o polling HTMX já existir em `my_cases`, reaproveitar. Caso contrário, manter refresh manual/UX simples neste change.

## D9. Auditoria e eventos

Usar eventos existentes da FSM sempre que possível. Adicionar eventos explícitos somente se necessário para distinguir:

- lote aceito;
- extração enfileirada;
- extração iniciada;
- extração falhou;
- extração ignorada por idempotência.

Não criar novo modelo de batch neste change, a menos que a implementação de UX exija. Para MVP, `Case` por arquivo é suficiente.

## D10. Plano de Slices

1. `slice-001-q2-clusters-and-compose.md` — configurar clusters `pdf`/`llm`, compose e enqueue LLM no cluster correto.
2. `slice-002-pdf-extraction-task.md` — criar task assíncrona de extração PDF, idempotente, com FSM e testes.
3. `slice-003-multi-upload-backend.md` — view/form/service para upload múltiplo criando vários casos e enfileirando extração.
4. `slice-004-multi-upload-ui.md` — template/JS para seleção múltipla, preview e feedback.
5. `slice-005-operational-hardening-and-quality.md` — limites, docs, testes de lote maior, quality gate e relatório final.

## Gates Globais

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

Cada slice deve criar relatório temporário com snippets antes/depois e informar `REPORT_PATH`.
