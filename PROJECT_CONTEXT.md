# PROJECT_CONTEXT.md

## Proposito

Resumo executivo para retomada rapida apos pausas e para onboarding de novos contribuidores.

## Fontes Autoritativas

- `AGENTS.md` — regras, stack, comandos, politica de testes
- `docs/DOMAIN_ANALYSIS.md` — analise completa de dominio
- `docs/adr/` — decisoes arquiteturais
- `openspec/changes/` — changes ativos com proposals, designs e slices
- Em caso de conflito: artefatos mais recentes no Git prevalecem.

## Objetivo do Sistema

Sistema de **triagem automatizada para EDA** (Endoscopia Digestiva Alta).
Operadores NIR enviam PDFs de relatorios medicos, o sistema processa via pipeline
LLM, apresenta ao medico para decisao, encaminha ao agendador, e retorna o
resultado ao NIR. Monolito Django SSR, sem API REST e sem SPA.

Projeto **greenfield** — reimplantacao de sistema legado (`augmented-triage-system`)
que operava via salas Matrix. A interface Matrix desaparece completamente;
e substituida por filas de trabalho web com formularios.

## Fluxo Operacional

```text
[NIR] Upload PDF
  -> Sistema: extrair texto + LLM1 (extracao estruturada) + LLM2 (sugestao)
  -> Sistema: Policy Engine (reconciliation deterministica)
  -> [Medico] Visualiza caso + sugestao -> Decide (accept/deny)
     |-> Aceita (scheduled): [Agendador] confirma/desmarca -> Resultado -> [NIR]
     |-> Aceita (immediate): notifica agendador (info only) -> Resultado -> [NIR]
     |-> Nega: Resultado -> [NIR]
  -> [NIR] confirma recebimento -> Caso fechado (CLEANED)
```

## Papéis e Permissoes

| Papel | Fila principal | Restricao de rede |
| ------- | --------------- | ------------------- |
| `nir` | Upload + meus casos + resultado final | **Intranet only** |
| `doctor` | Fila medica + decisao | Qualquer lugar |
| `scheduler` | Fila agendamento + notif. vinda imediata | **Intranet only** |
| `manager` | Dashboard + metricas + todos os casos | Qualquer lugar |
| `admin` | Tudo + gestao usuarios + gestao prompts | Qualquer lugar |

**Multi-role**: admin atribui multiplos papeis por usuario. Usuario escolhe
papel ativo ao logar e pode trocar via avatar/perfil. Apenas 1 papel ativo
por vez, armazenado na sessao Django.

**Intranet guard**: middleware valida IP contra `INTRANET_IP_RANGE` (CIDR,
env var) para papeis `nir` e `scheduler`. Acesso externo via tunel Cloudflare
com SSL.

## Arquitetura de Alto Nivel

- **Monolito Django 5.2+** com templates SSR.
- **PostgreSQL 17+** como banco de dados principal.
- **django-fsm** para maquina de estados (17 estados preservados).
- **django-q2** para tarefas assincronas (pipeline LLM, resumo periodico).
- **Frontend**: Templates Django + Bootstrap 5.3 (CDN) + Vanilla JS + Vanilla HTML.
- **uv** como gerenciador de pacotes e virtualenv.
- **PDF storage**: filesystem local (`MEDIA_ROOT`).
- **Notificacoes**: todas in-app, sem email/SMS/push.
- **Auditoria**: `CaseEvent` append-only — unica fonte de verdade sobre historico.
- **Cleanup**: marcar caso como `CLEANED` — sai das filas, so aparece na auditoria.

### Estrutura de Apps

```text
config/          # settings (base/dev/prod), urls, wsgi, asgi
apps/accounts/   # User, Role, auth views, intranet guard middleware
apps/cases/      # Case (FSM 17 estados), CaseEvent (auditoria)
apps/llm/        # PromptTemplate (versionado, 1 ativo por nome)
apps/pipeline/   # Pipeline LLM: client, services, policy engine, orchestrator, tasks
apps/pipeline/schemas/  # Pydantic v2 DTOs: llm1.py (StructuredData), llm2.py (Suggestion)
apps/intake/     # NIR: upload PDF, meus casos, detalhe + timeline
apps/doctor/     # Médico: fila, decisão, presenter de relatório (7 blocos)
apps/scheduler/  # Agendador: fila, confirmação/desmarcação
apps/dashboard/  # Dashboard gerencial: métricas, sumários, tabela de casos
apps/admin_ui/   # Interface admin: gestão de usuários e prompts
templates/       # base.html (tema hospitalar), login, switch-role, intake/, doctor/
static/          # css/app.css (paleta hospitalar), js/upload.js
```

### Stack resumido

| Camada | Tecnologia | Versao |
| -------- | ----------- | -------- |
| Backend | Python | 3.13+ |
| Framework | Django | 5.2+ |
| Estados | django-fsm | latest |
| Filas | django-q2 | latest |
| Banco | PostgreSQL | 17+ |
| CSS | Bootstrap | 5.3 |
| JS | Vanilla | ES6+ |
| Empacotador | uv | latest |
| Testes | pytest | latest |
| Lint | ruff | latest |
| Types | mypy | latest |

## Entidades Principais

- **User** (AbstractUser): multi-role via M2M(Role), `account_status`, papel ativo na sessao
- **Role**: nir, doctor, scheduler, manager, admin
- **Case**: FSM 17 estados, 30+ campos (PDF, LLM artifacts, decisao medica, agendamento)
- **CaseEvent**: auditoria append-only (~40 tipos de evento)
- **PromptTemplate**: versionado, apenas 1 ativo por nome

## Regras Nao Negociaveis

- **Sem framework JS** (React, Vue, Angular, etc.). Apenas Vanilla JS.
- **Sem pre-processador CSS** (Sass, Less). Apenas Bootstrap 5.3 + CSS puro.
- **Sem Django REST Framework** — projeto e SSR puro.
- Todas as dependencias via `uv` + `pyproject.toml`.
- Toda mudanca relevante deve deixar evidencia no Git (spec/task/commit).
- FSM com 17 estados preservados — rastreabilidade completa de quem fez o que e quando.
- `case_messages` NAO existe neste projeto — `CaseEvent` cobre toda a rastreabilidade.
- Templates textuais e parsers de Matrix nao existem — formularios HTML substituem.
- Reactions/thumbs-up nao existem — botao "Confirmar Recebimento" substitui.

## Contratos e Validações

- **Prompts canônicos**: nomes legados `llm1_system`, `llm1_user`, `llm2_system`, `llm2_user` são definitivos.
  `seed_prompts` cria versões ativas com defaults portados do legado. Fallback de código usa os mesmos defaults.
- **Validação Pydantic v2**: schemas `apps/pipeline/schemas/llm1.py` (StructuredData) e `llm2.py` (Suggestion)
  validam rigidamente as respostas LLM. Respostas fora do contrato geram falha explícita de pipeline com
  `CaseEvent` de auditoria.
- **Scope gate**: casos `non_eda` ou `unknown` (exame fora do escopo EDA) vão direto para
  `WAIT_R1_CLEANUP_THUMBS` com resultado de revisão manual obrigatória — **não entram na fila médica**.
- **Presenter médico**: `apps/doctor/presenters.py` gera relatório técnico equivalente ao legado em 7 blocos:
  Resumo clínico, Achados críticos, Pendências críticas, Decisão sugerida, Suporte recomendado,
  ASA estimado e Motivo objetivo.
- **Role guard**: todas as views médicas exigem `@role_required('doctor')` com papel ativo `doctor`.
  Manager com role `doctor` ativo também acessa.

## State do Sistema

- **Fase atual**: Fase 3 CONCLUÍDA — débitos técnicos planejados
- **Changes concluídos**:
  - `openspec/archive/bootstrap-django-ats-core/` (7 slices, Fase 0)
  - `openspec/archive/intake-nir/` (6 slices, Fase 1)
  - `openspec/archive/pipeline-llm/` (7 slices, Fase 2)
  - `openspec/archive/ui-alinhamento-mocks/` (3 slices, Fase 2b)
  - `openspec/archive/align-llm-contract-and-doctor-routing/` (7 slices)
  - `openspec/archive/post-schedule-intercurrence/` (5 slices + follow-ups)
- **Changes ativos**:
  - `openspec/changes/release-lock-on-successful-handoff/`
  - `openspec/changes/consolidate-duplicated-test-fixtures/`
  - `openspec/changes/align-uuid-route-parameter-annotations/`
- **Apps criados**: `apps/accounts/`, `apps/cases/`, `apps/llm/`, `apps/intake/`, `apps/pipeline/`,
  `apps/doctor/`, `apps/scheduler/`, `apps/dashboard/`, `apps/admin_ui/`
- **Testes**: 605 passando, quality gate verde
- **Templates**: base.html com tema hospitalar, login, switch-role, intake (home, my_cases, case_detail),
  doctor (queue, decision)
- **Documentacao de dominio**: `docs/DOMAIN_ANALYSIS.md`
- **Investigações**: `docs/investigations/2026-05-18-nir-to-doctor-flow-review.md`
- **ADR ativa**: `docs/adr/ADR-0001-arquitetura-django-web-ssr-ats-triagem-eda.md`
- **Dívida técnica**: `django-fsm` deprecated → `viewflow.fsm` (não urgente)

## Quality Bar

- Quality gate completo: `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest`
- TDD obrigatorio: RED -> GREEN -> REFACTOR.
- Mudancas com risco medio/alto devem ter plano de rollback.
- Design.md obrigatorio antes de implementar (exceto QUICK bugfix).

## Projeto Legado (referencia only)

- Repositorio: `../augmented-triage-system/`
- Usado apenas como referencia funcional e comportamental
- Sem migracao de codigo, sem migracao de dados
- Documentacao em `docs/DOMAIN_ANALYSIS.md` captura o que foi extraido do legado
