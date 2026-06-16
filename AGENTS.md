# AGENTS.md

## 1. Stack e Versoes

### Linguagens
- **Backend:** Python 3.13+
- **Frontend:** Vanilla JS (ES6+), Vanilla HTML

### Framework & Libraries
- **Django** 5.2+ (framework web, SSR — sem API REST/SPA)
- **django-fsm** (maquina de estados finitos para modelos)
- **django-q2** (fila de tarefas assincronas)
- **Bootstrap** 5.3 (framework CSS, via CDN ou static)

### Gerenciamento de Pacotes
- **uv** (resolucao de dependencias e virtualenv — substitui pip/poetry)

### Ferramentas de Qualidade
- **pytest** (testes — com pytest-django)
- **ruff** (lint + formatter — substitui flake8, isort, black)
- **mypy** (type checking estatico com django-stubs)

### Banco de Dados
- **PostgreSQL** 17+ (extensao unaccent habilitada) — versão atual nos containers: 17.9
- **Docker Compose** com arquivos separados por ambiente (dev, test, prod) via Docker rootless
- **docker-compose.yml**: definição base do serviço PostgreSQL (imagem, healthcheck, init.sql com unaccent)
- **docker-compose.dev.yml** (name: ats-web-dev): porta de host configurável por `POSTGRES_HOST_PORT` (default 5432), volume persistente `pgdata_dev`
- **docker-compose.test.yml** (name: ats-web-test): porta de host configurável por `POSTGRES_TEST_HOST_PORT` (default 5433), tmpfs para dados efêmeros
- **docker-compose.prod.yml** (name: ats-web-prod): porta de host configurável por `POSTGRES_HOST_PORT` (default 15432) ligada a `POSTGRES_HOST_BIND` (default 127.0.0.1), volume `pgdata_prod`

### Constraints do Stack
- Frontend **sem** framework JS (React, Vue, etc.). Apenas Vanilla JS.
- Frontend **sem** pre-processador CSS (Sass, Less). Apenas Bootstrap 5.3 + CSS customizado.
- Templates Django para renderizacao server-side.
- Nao usar Django REST Framework — o projeto e SSR puro.
- Todas as dependencias gerenciadas via `uv` (pyproject.toml).

## 2. Comandos de Validacao (Quality Gate)

- Lint + formatter: `uv run ruff check . && uv run ruff format --check .`
- Type check: `uv run mypy .`
- Testes: `uv run pytest`
- Verificacao basica: `git status --short`

## 3. Comandos Essenciais (Operacao Local)

### Setup inicial

```bash
# 1. Subir todos os serviços (db + web + worker)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 2. Rodar migrations (primeira vez)
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec web \
  uv run python manage.py migrate --settings=config.settings.dev

# 3. Criar usuário admin com todos os papéis (idempotente)
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec web \
  uv run python manage.py seed_admin --settings=config.settings.dev

# 4. Criar prompts LLM iniciais (idempotente)
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec web \
  uv run python manage.py seed_prompts --settings=config.settings.dev
```

### Operacao basica

```bash
# Subir
DDEV="docker compose -f docker-compose.yml -f docker-compose.dev.yml"
$DDEV up -d

# Logs
$DDEV logs -f web
$DDEV logs -f worker

# Parar
$DDEV down

# Migrations
$DDEV exec web uv run python manage.py migrate --settings=config.settings.dev

# Django management commands
$DDEV exec web uv run python manage.py <command> --settings=config.settings.dev

# Status dos serviços
$DDEV ps
```

### Ambiente de testes

```bash
# Subir banco de teste (porta ${POSTGRES_TEST_HOST_PORT:-5433}, dados efêmeros)
docker compose -f docker-compose.yml -f docker-compose.test.yml up -d

# Rodar testes
uv run pytest

# Derrubar e limpar dados de teste
docker compose -f docker-compose.yml -f docker-compose.test.yml down -v
```

### Servidor de desenvolvimento

```bash
# Tudo roda em Docker:
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
# Web: http://localhost:8080
# Worker: django-q2 processa pipeline automaticamente
# Código editado no host reflete instantaneamente (volume mount)
```

### Quality gate completo

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## 4. Arquitetura e Constraints

- **Monolito Django** com templates SSR. Nao ha API REST nem SPA.
- Definir boundaries explicitos por modulo (Django app) e manter dependencias unidirecionais.
- Cada Django app deve ser autocontida: models, views, templates, static, tests.
- Logica de negocio em `services.py` ou `models.py` — nunca em views ou templates.
- Estados de modelo gerenciados via **django-fsm**; transicoes centralizadas no model.
- Tarefas assincronas via **django-q2** (pipeline LLM, resumo periodico, cleanup).
- Frontend: HTML nos templates Django, estilos com **Bootstrap 5.3** + CSS customizado em `/static/css/`, JS vanilla em `/static/js/`.
- Queries complexas em QuerySets customizados; evitar ORM implicito em views.
- **Multi-role**: admin atribui multiplos papeis por usuario; usuario escolhe papel ativo ao logar e pode trocar via avatar/perfil. Apenas 1 papel ativo por vez, armazenado na sessao.
- **Intranet guard**: papéis `nir` e `scheduler` so acessam de dentro da intranet do hospital. Range de IPs configuravel via env var `INTRANET_IP_RANGE` (formato CIDR). Middleware bloqueia requests externos para esses papeis.
- **PDF storage**: filesystem local (`MEDIA_ROOT`). Sem S3/object storage.
- **Notificacoes**: todas in-app (dentro do aplicativo). Sem email, SMS ou push.
- **Acesso externo**: via tunel Cloudflare com SSL. Header `CF-Connecting-IP` para IP real do cliente.
- **Auditoria**: `CaseEvent` append-only como unica fonte de verdade sobre historico de casos.
- **Cleanup**: marcar caso como `CLEANED`. Caso sai das filas operacionais e so aparece na auditoria.
- **FSM**: todos os 17 estados preservados para rastreabilidade completa.

## 5. Politica de Testes

### Infraestrutura de Testes

- **Banco de dados de teste isolado**: PostgreSQL em container dedicado (`ats-web-test`), porta de host configurável por `POSTGRES_TEST_HOST_PORT` (default 5433), dados efêmeros via tmpfs.
- **Settings de teste**: `config/settings.test` — banco `ats_web_test`, hashers rápidos (MD5), DEBUG=False.
- **pytest**: configurado com `--reuse-db` para acelerar execuções repetidas. O banco persiste entre rodadas e é descartado apenas com `down -v`.
- **CI/CD futuro**: usar `docker compose -f docker-compose.yml -f docker-compose.test.yml` para isolar completamente o ambiente de testes.

### Metodologia

- TDD obrigatorio: RED (teste falha) -> GREEN (minimo para passar) -> REFACTOR (limpeza sem quebrar).
- Nao iniciar implementacao sem primeiro teste falhando para o comportamento-alvo.
- Priorizar testes unitarios; usar integracao para contratos e fluxos.
- Ao tocar legado sem testes, adicionar ao menos um teste de caracterizacao.
- No REFACTOR, reforcar clean code: nomes claros, funcoes coesas, baixo acoplamento e remocao de codigo morto.

## 6. Stop Rule (CRUCIAL)

- Implementar uma task slice vertical por vez (end-to-end).
- Nao quebrar o trabalho em slice horizontal por camada sem entrega de fluxo completo.
- Planejar slices enxutos: tocar poucos arquivos (ideal <= 5) e so o necessario para entregar valor.
- Se precisar ampliar escopo de arquivos, registrar justificativa em tasks/design antes de codar.
- Cada slice deve incluir handoff + prompt pronto para implementador LLM com contexto zero.
- O slice deve explicitar criterios de sucesso e gates de autoavaliacao antes da implementacao.
- Antes de codar o change: design.md e obrigatorio, exceto QUICK de bugfix simples e reversivel.
- Rodar comandos de validacao da secao 2.
- Atualizar tasks/specs com o status do slice.
- Fazer commit com mensagem rastreavel e dar push para branch remota.
- Gerar relatorio detalhado do slice com snippets antes/depois e salvar em markdown temporario.
- Informar REPORT_PATH para avaliacao do planner.
- PARAR e pedir confirmacao explicita para o proximo slice.
- Nao iniciar o proximo slice sem confirmacao explicita do usuario.

## 7. Definition of Done (DoD)

- [ ] Build/check sem erros
- [ ] Testes relevantes passando
- [ ] Lint/type-check sem erros relevantes
- [ ] Specs/docs atualizadas quando necessario
- [ ] Commit com mensagem clara e rastreavel
- [ ] Push realizado para branch remota
- [ ] Relatorio do slice gerado em markdown temporario com snippets antes/depois
- [ ] REPORT_PATH informado para avaliacao do planner

## 8. Anti-patterns Proibidos

- Nao criar classes/funcoes God object com responsabilidades demais.
- Nao deixar TODO/FIXME sem issue ou plano.
- Nao acoplar regras de negocio em camada de apresentacao.
- Nao executar slices horizontais por camada sem valor end-to-end.

## 9. Prompt de Reentrada

```text
Read AGENTS.md and PROJECT_CONTEXT.md first.
Implement ONLY the next incomplete slice from tasks/spec.
Use vertical slicing (end-to-end); avoid horizontal slicing by layer.
Keep the slice lean: touch only the minimum files needed (ideal <= 5).
Follow TDD cycle: RED (failing test) -> GREEN (minimal pass) -> REFACTOR (clean safely).
In REFACTOR, enforce clean code (clarity, cohesion, low coupling, no dead code).
If the active change is not a simple QUICK bugfix, require design.md before implementation.
Assume the implementer is an LLM with zero context: include handoff, prompt, success criteria and self-eval gates in the slice file.
Run section 2 validation commands and update artifacts for the completed slice.
Create a detailed implementation report with before/after snippets in a temporary markdown file.
Reply with REPORT_PATH=<temp-markdown-path> for planner review.
Commit and push the current branch.
STOP and ask for explicit confirmation before starting the next slice.
```

<!-- generated-by: agents-md-generator -->
