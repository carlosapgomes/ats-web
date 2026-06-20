# ats-web

Sistema de triagem automatizada para EDA (Endoscopia Digestiva Alta) — reimplantação web Django.

## Documentação

- `AGENTS.md` — regras, stack, comandos, política de testes
- `PROJECT_CONTEXT.md` — contexto executivo do sistema
- `ROADMAP.md` — fases de implementação
- `docs/DOMAIN_ANALYSIS.md` — análise de domínio completa
- `docs/adr/` — decisões arquiteturais

## Stack

Python 3.13+ · Django 5.2+ · PostgreSQL 17+ · Bootstrap 5.3 · Vanilla JS · uv

## Ambiente de Desenvolvimento

> Tudo roda em Docker. Não é necessário instalar Python ou uv no host.

### Primeira vez (bootstrap completo)

```bash
# 1. Subir todos os serviços (db + web + worker)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 2. Rodar migrations (cria tabelas + seed dos 5 papéis)
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec web \
  uv run python manage.py migrate --settings=config.settings.dev

# 3. Criar usuário admin com todos os papéis (idempotente)
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec web \
  uv run python manage.py seed_admin --settings=config.settings.dev

# 4. Criar prompts LLM iniciais (idempotente)
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec web \
  uv run python manage.py seed_prompts --settings=config.settings.dev

# 5. Acessar http://localhost:8080 (login: admin / admin)
```

> Os comandos `seed_admin` e `seed_prompts` são idempotentes — podem ser executados
> múltiplas vezes sem efeitos colaterais.

### Comandos do dia-a-dia

```bash
# Subir
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Logs do web
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f web

# Logs do worker LLM (pipeline django-q2)
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f worker

# Logs do pdf_worker (extração assíncrona de PDF)
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f pdf_worker

# Parar
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
```

O diretório do projeto é montado como volume no container (`.` → `/app`), então
edições no host refletem imediatamente no servidor (auto-reload).

A porta do PostgreSQL no host é configurável por `POSTGRES_HOST_PORT`
(default: `5432` em desenvolvimento). Exemplo para evitar conflito com outro
PostgreSQL local:

```bash
POSTGRES_HOST_PORT=15432 docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

A URL interna dos containers continua usando `db:5432`; apenas a porta publicada
no host muda.

### Ambiente de Testes

```bash
# Subir banco de teste (porta ${POSTGRES_TEST_HOST_PORT:-5433}, dados efêmeros)
docker compose -f docker-compose.yml -f docker-compose.test.yml up -d

# Rodar testes (no host, com uv)
uv run pytest

# Derrubar e limpar dados
docker compose -f docker-compose.yml -f docker-compose.test.yml down -v
```

### Produção

```bash
# Subir todos os serviços (db + web + worker)
# Requer: DJANGO_SECRET_KEY, POSTGRES_PASSWORD no .env ou env vars
# Web fica ligada ao host ${WEB_HOST_BIND:-127.0.0.1}:${WEB_HOST_PORT:-8000}
# PostgreSQL fica ligado ao host ${POSTGRES_HOST_BIND:-127.0.0.1}:${POSTGRES_HOST_PORT:-15432}
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Rodar migrations
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web \
  uv run python manage.py migrate --settings=config.settings.prod

# Coletar estáticos
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web \
  uv run python manage.py collectstatic --noinput --settings=config.settings.prod
```

## Upload Múltiplo com Extração PDF Assíncrona

O sistema suporta upload simultâneo de múltiplos PDFs com processamento
em background via `django-q2`.

### Arquitetura de Workers

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   web (SSR)      │     │  pdf_worker     │     │  worker (LLM)   │
│ Upload múltiplo  │ ──► │ Extração PDF    │ ──► │ Pipeline LLM    │
│ Cria Cases       │     │ FSM → LLM_STRUCT│     │ Sugestão/Decisão│
│ Enfileira extração│     │ Enfileira LLM   │     │                  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
       │                      │                        │
       └──────────────────────┴────────────────────────┘
                         MEDIA_ROOT compartilhado
```

- **web**: recebe upload, valida arquivos, cria `Case`, enfileira extração — não extrai PDF.
- **pdf_worker** (cluster `pdf`): extrai texto do PDF, avança FSM, enfileira pipeline LLM.
- **worker** (cluster `llm`): executa pipeline LLM (estruturação + sugestão + policy).

### Limites (centralizados em `config/settings/base.py`)

| Config | Default | Descrição |
|--------|---------|-----------|
| `INTAKE_MAX_FILES_PER_BATCH` | 30 | Máximo de arquivos por submissão |
| `INTAKE_MAX_UPLOAD_BYTES_PER_FILE` | 20 MB | Tamanho máximo por arquivo |
| `INTAKE_MAX_UPLOAD_BYTES_PER_BATCH` | 600 MB | Tamanho máximo total do lote |
| `INTAKE_MAX_ATTACHMENTS_PER_CASE` | 10 | Máximo de anexos clínicos por caso |
| `INTAKE_MAX_ATTACHMENT_BYTES_PER_FILE` | 20 MB | Tamanho máximo por anexo (PDF/JPEG/PNG) |
| `INTAKE_MAX_ATTACHMENT_BYTES_PER_CASE` | 200 MB | Tamanho máximo total de anexos por caso |

### Barreira de Aceitação — Relatório de Regulação

Após a extração do texto do PDF, o sistema aplica uma barreira determinística
para verificar se o documento é um relatório de regulação do sistema baiano
(*Central Estadual de Regulação*).

**Critérios (todos obrigatórios para aceite):**

1. **Texto mínimo**: texto limpo com ≥ `INTAKE_REGULATION_MIN_TEXT_CHARS` (500 chars).
2. **Header**: contém "RELATÓRIO DE OCORRÊNCIAS" (normalização de acentos/caixa).
3. **Sinal institucional**: contém ao menos 1 dos seguintes:
   - "Central Estadual de Regulação"
   - "Secretaria da Saúde do Estado"
   - "Governo do Estado da Bahia"
4. **Seções operacionais**: contém ≥ `INTAKE_REGULATION_MIN_OPERATIONAL_SECTIONS` (3) entre:
   - Código:, Abertura:, Unid. Origem, Unidade de Origem, Motivo da Solicitação,
     Complemento da Solicitação, Resumo Clínico, Dias em tela, Data Adm. Unid.

**Comportamento para PDFs barrados:**

- O texto extraído é preservado para auditoria.
- O número de registro por fallback (timestamp) é removido — evita falsa evidência.
- `suggested_action` é configurado com `decision=manual_review_required`,
  `reason_code=invalid_regulation_report` e mensagem clara para o NIR.
- **Não** é enfileirada tarefa de pipeline LLM (economia de custo).
- O caso transiciona via FSM para `WAIT_R1_CLEANUP_THUMBS` (revisão manual NIR).
- Eventos `REGULATION_REPORT_GATE_FAILED`, `SCOPE_GATE_BYPASS` e `FINAL_REPLY_POSTED`
  são registrados para rastreabilidade.

**Diferença entre barreira de regulação e scope gate EDA:**

| Aspecto | Barreira de Regulação | Scope Gate EDA |
|---------|----------------------|----------------|
| **O que valida** | Formato do documento (é relatório de regulação?) | Escopo do exame (é EDA?) |
| **Onde executa** | Worker de extração, pós-texto, pré-LLM | Pipeline LLM, pós-LLM1 |
| **Consequência** | Bloqueia pipeline LLM inteiro | Bloqueia fila médica (non_eda/unknown) |
| **Destino** | `WAIT_R1_CLEANUP_THUMBS` | `WAIT_R1_CLEANUP_THUMBS` |

Relatórios de regulação válidos (ex.: colonoscopia) passam pela barreira e
seguem para o scope gate EDA existente, que decide o roteamento médico.

**Limitações conhecidas:**

- A barreira não implementa OCR — PDFs escanados sem camada de texto
  falham por texto insuficiente.
- A barreira reconhece apenas relatórios com a assinatura textual do
  sistema baiano. Relatórios de regulação de outros estados/emissores
  podem ser rejeitados.
- Relatórios de regulação de formato significativamente diferente do
  padrão observado podem precisar de ajuste nos critérios.

**Configurações (em `config/settings/base.py`):**

| Config | Default | Descrição |
|--------|---------|-----------|
| `INTAKE_REGULATION_MIN_TEXT_CHARS` | 500 | Tamanho mínimo do texto extraído |
| `INTAKE_REGULATION_MIN_OPERATIONAL_SECTIONS` | 3 | Mínimo de seções operacionais |

### Garantias operacionais

- `retry > timeout` em todos os clusters — evita reexecução indevida de tasks longas.
- Tasks de extração PDF são idempotentes: verificam FSM antes de agir.
- Falha de um PDF não afeta os demais do lote.

### Operação em Produção

- `web`, `pdf_worker` e `worker` compartilham o volume `media_prod` para acesso aos PDFs.
- Escala atual em `config/settings/prod.py` (cluster interno `ALT_CLUSTERS`):
  - **pdf_worker**: 6 workers (extração PDF é CPU/IO bound via PyMuPDF).
  - **worker (LLM)**: 3 workers (pipeline é I/O bound — espera a API OpenAI).
- **Alerta de custo LLM**: monitore o número de tasks enfileiradas no cluster `llm`.
  A capacidade real depende do tempo médio de resposta da LLM e dos rate limits
  do provedor. Ajuste os workers gradualmente com monitoramento de custo,
  latência, falhas por rate limit e tamanho da fila `llm`.
- **Tuning de workers**: os counts ficam em `config/settings/prod.py`
  (`Q_CLUSTER["ALT_CLUSTERS"]["pdf"]["workers"]` e `[...]["llm"]["workers"]`).
  Aumentá-los escala o paralelismo dentro de um mesmo container. Cada processo
  abre uma conexão Postgres; com `CONN_MAX_AGE=600` e health checks, o total fica
  bem abaixo do limite padrão de 100 conexões (~12 hoje: 6 pdf + 3 llm + 3 gunicorn).
  Se um container não der conta, o próximo passo é escalar containers via
  `deploy.replicas` (override do compose), pois todos os containers do mesmo
  `Q_CLUSTER_NAME` compartilham a fila via Postgres. Veja "Medindo gargalo" abaixo.
- **Volume de media**: em produção, `media_prod` (definido em `docker-compose.prod.yml`)
  deve usar um driver de volume com backup periódico.

### Workers no Compose

**Dev** (`docker-compose.dev.yml`):
- `worker`: `Q_CLUSTER_NAME=llm` — 1 worker.
- `pdf_worker`: `Q_CLUSTER_NAME=pdf` — 2 workers.

**Prod** (`docker-compose.prod.yml`):
- `worker`: `Q_CLUSTER_NAME=llm` — 3 workers.
- `pdf_worker`: `Q_CLUSTER_NAME=pdf` — 6 workers.
- Ambos montam `media_prod:/app/media`.

### Verificações Operacionais

```bash
# Verificar workers ativos
$DDEV ps

# Logs do pdf_worker
$DDEV logs -f pdf_worker

# Ver tasks pendentes na fila ORM do django-q2 (tabela OrmQ)
docker exec -it ats-web-dev-db-1 psql -U ats_web -d ats_web_dev \
  -c "SELECT key, COUNT(*) FROM django_q_ormq WHERE key IN ('pdf', 'llm') GROUP BY key;"

# Ver histórico de tasks já processadas por cluster (tabela Task)
docker exec -it ats-web-dev-db-1 psql -U ats_web -d ats_web_dev \
  -c "SELECT cluster, success, COUNT(*) FROM django_q_task GROUP BY cluster, success ORDER BY cluster, success;"
```

#### Medindo gargalo (decidir se precisa escalar workers)

Durante uma alimentação em lote real, compare tasks em execução vs. na fila.
Se `running` estiver sempre no máximo configurado (6 para `pdf`, 3 para `llm`)
e `queued` crescer, há gargalo de workers:

```bash
# running = tasks pegas por algum worker; queued = tasks esperando
$DPROD exec web uv run python -c "
import django, os
os.environ['DJANGO_SETTINGS_MODULE']='config.settings.prod'
django.setup()
from django_q.models import Task
from django.utils import timezone
from datetime import timedelta
running = Task.objects.filter(started__isnull=False, stopped__isnull=True).count()
queued = Task.objects.filter(started__isnull=True).count()
done_1h = Task.objects.filter(stopped__gte=timezone.now()-timedelta(hours=1)).count()
print(f'running: {running}, queued: {queued}, done last 1h: {done_1h}')
"
```

Se `queued` crescer com `running` saturado, aumentar `workers` em
`config/settings/prod.py` (mais paralelismo no mesmo container) ou adicionar
`deploy.replicas` no compose (mais containers). Se `queued` fica baixo e
`running` raramente satura, o gargalo é outro (ex.: rate limit da OpenAI),
e aumentar workers não vai ajudar.

## Quality Gate

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Arquitetura Docker

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   web (:8000)    │  │    worker       │  │  pdf_worker     │  │ db (host var)   │
│─────────────────│  │─────────────────│  │─────────────────│  │─────────────────│
│ Dev:  runserver │  │ django-q2 LLM   │  │ django-q2 PDF   │  │ PostgreSQL 17   │
│ Prod: gunicorn  │  │ qcluster        │  │ qcluster        │  │ + unaccent      │
│ Vol: . → /app   │  │ Vol: . → /app   │  │ Vol: . → /app   │  │ Dev: persist    │
│                  │  │ Q_CLUSTER_NAME  │  │ Q_CLUSTER_NAME  │  │ Test: tmpfs     │
│                  │  │ = llm           │  │ = pdf           │  │                  │
└─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘
       rede interna Docker (ats-web-dev / ats-web-prod)
```
