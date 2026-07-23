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
- **Notificacoes operacionais**: todas in-app, sem SMS/push. **Emails transacionais de conta** (reset de senha, convite de cadastro) sao enviados via AWS SES SMTP (sincrono) conforme ADR-0002; nunca para notificacoes operacionais de caso. URL do link (publica/interna) selecionada por papel do usuario.
- **Auditoria**: `CaseEvent` append-only — unica fonte de verdade sobre historico.
- **Cleanup**: marcar caso como `CLEANED` — sai das filas, so aparece na auditoria.

### Estrutura de Apps

```text
config/          # settings (base/dev/prod), urls, wsgi, asgi
apps/accounts/   # User, Role, auth views, password reset, profile/password change, intranet guard middleware, email services (invitation)
apps/cases/      # Case (FSM 17 estados), CaseEvent (auditoria)
apps/llm/        # PromptTemplate (versionado, 1 ativo por nome)
apps/pipeline/   # Pipeline LLM: client, services, policy engine, orchestrator, tasks
apps/pipeline/schemas/  # Pydantic v2 DTOs: llm1.py (StructuredData), llm2.py (Suggestion)
apps/intake/     # NIR: upload PDF, meus casos, detalhe + timeline
apps/doctor/     # Médico: fila, decisão, presenter de relatório (7 blocos)
apps/scheduler/  # Agendador: fila, confirmação/desmarcação
apps/dashboard/  # Dashboard gerencial: métricas, sumários, tabela de casos
apps/admin_ui/   # Interface admin: gestão de usuários e prompts
templates/       # base.html (tema hospitalar), login, switch-role, perfil, password reset/change, intake/, doctor/
static/          # css/app.css (paleta hospitalar), js/upload.js, js/password-toggle.js
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
- **Case**: FSM 17 estados, 30+ campos (PDF, LLM artifacts, decisao medica, agendamento). Vínculo opcional de reenvio corrigido: `corrects_case` (self-FK) + `correction_reason`/`correction_created_by`/`correction_created_at`.
- **CaseEvent**: auditoria append-only (~40 tipos de evento)
- **CaseCommunicationMessage**: thread operacional append-only vinculada a um `Case` (comunicação entre NIR/médico/scheduler para esclarecimentos; NÃO substitui decisão/agendamento/eventos estruturados). Suporta `message_type="user"` (manual, com autor) e `message_type="system"` (projeção automática de `CaseEvent`, sem autor) via `source_event` OneToOne idempotente + `system_event_type`.
- **UserNotification**: notificação in-app user-scoped criada por menções explícitas (`@role`/`@username`) em `CaseCommunicationMessage`; badge SSR + inbox “Minhas notificações” + polling Vanilla JS do badge
- **PromptTemplate**: versionado, apenas 1 ativo por nome

## Regras Nao Negociaveis

- **Sem framework JS** (React, Vue, Angular, etc.). Apenas Vanilla JS.
- **Sem pre-processador CSS** (Sass, Less). Apenas Bootstrap 5.3 + CSS puro.
- **Sem Django REST Framework** — projeto e SSR puro.
- Todas as dependencias via `uv` + `pyproject.toml`.
- Toda mudanca relevante deve deixar evidencia no Git (spec/task/commit).
- FSM com 17 estados preservados — rastreabilidade completa de quem fez o que e quando.
- `case_messages` (entidade legada de mensagens de sistema) NAO existe neste projeto — `CaseEvent` cobre toda a rastreabilidade de estados/decisões. Comunicação operacional entre humanos vive em `CaseCommunicationMessage` e não substitui eventos estruturados.
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
- **Emails transacionais (ADR-0002)**: reset de senha usa views/token nativos do Django com rate limit
  por IP/email e anti-enumeração. Convite de cadastro (criação administrativa) envia email automático
  com link de reset; a URL base é pública (`PUBLIC_APP_BASE_URL`) quando o usuário tem qualquer papel
  `doctor`/`manager`/`admin`, e interna (`INTERNAL_APP_BASE_URL`) quando só tem `nir`/`scheduler`.
  Envio síncrono; falha SMTP não apaga o usuário criado.
- **Reenvio corrigido explícito**: o NIR pode partir de um caso anterior e criar um novo `Case` vinculado
  via `corrects_case`, com motivo obrigatório. O novo caso NÃO herda PDF, anexos, eventos, decisões ou
  dados extraídos do anterior; o anterior não é reaberto nem muda de status. Eventos
  `CASE_CORRECTION_CREATED` (novo) e `CASE_MARKED_SUPERSEDED` (original) registram a relação. Visível
  para NIR (cards no detalhe + badge na busca de encerrados) e médico (card na decisão com motivo do
  NIR + aviso de não-herança de documentos). Quando o vínculo explícito aponta para o mesmo caso do
  prior-case lookup, o card genérico é suprimido para evitar duplicidade visual.
- **Comunicação operacional por caso**: thread append-only (`CaseCommunicationMessage`) vinculada a
  exatamente um `Case`, para esclarecimentos/coordenação entre NIR/médico/scheduler. Serviço único
  `post_case_communication_message` valida papel permitido (`nir`/`doctor`/`scheduler`/`manager`/`admin`),
  blank/spaces, limite de 2000 chars e bloqueia post em caso `CLEANED`. Endpoint POST único
  `/cases/<id>/communication/` com redirect seguro (`url_has_allowed_host_and_scheme`). Partial único
  `_communication_thread.html` reutilizado em 4 telas. Cada post gera evento auditável
  `CASE_COMMUNICATION_MESSAGE_POSTED` (payload enxuto com `message_id`/`author_role`/`body_preview`).
  NÃO substitui decisão médica, motivo de negativa, observação de decisão, agendamento, intercorrência
  estruturada, supressão de anexo nem reenvio corrigido. **Menções explícitas** (`@nir`/`@doctor`/`@scheduler`/`@manager`/`@admin` e `@username` ativo) criam
  `UserNotification` para destinatários elegíveis (exclui autor, deduplica, ignora inativos/blocked);
  payload do evento `CASE_COMMUNICATION_MESSAGE_POSTED` inclui `mentioned_roles`/`mentioned_usernames`/`notification_count`.
  Badge SSR no header via `get_unread_notification_count()` (helper único/DRY) + endpoint `GET /notifications/unread-count/`
  (`@require_GET`) + polling Vanilla JS (`static/js/notifications.js`, 45s, respeita `document.visibilityState`,
  backoff em erro). Página “Minhas notificações” com abrir/marcar lida/marcar todas + redirect seguro por papel/status.
  Sem autocomplete, aliases avançados, marcação AJAX, push/SMS/email operacional, WebSocket/SSE ou polling da thread.
- **Mensagens sistêmicas de workflow**: eventos estruturados selecionados projetam automaticamente uma `CaseCommunicationMessage` (`message_type="system"`) na thread do caso via serviço central `create_system_communication_notice_for_event` + signal `CaseEvent.post_save` (`create_case_event_system_notice`). Formatadores por `event_type` (DRY, dispatch dict) em `apps/cases/services.py`. 10 eventos projetados: `CASE_ATTACHMENT_SUPPRESSED`, `CASE_ATTACHMENT_SUPPLEMENT_ADDED`, `CASE_CORRECTION_CREATED`, `CASE_MARKED_SUPERSEDED`, `POST_SCHEDULE_ISSUE_OPENED`, `POST_SCHEDULE_ISSUE_RESPONDED`, `POST_ACCEPTANCE_ISSUE_OPENED`, `POST_ACCEPTANCE_ISSUE_RESPONDED`, `POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED`, `CASE_ADMINISTRATIVELY_CLOSED`. `POST_SCHEDULE_ISSUE_ACKNOWLEDGED` omitido (payload vazio, ruído). `CASE_COMMUNICATION_MESSAGE_POSTED` guardado contra loop. Renderização distinta: “Sistema” + badge SISTEMA no partial `_communication_thread.html`. **Sistêmicas são apenas contexto**: não criam `UserNotification`, não mexem no badge, não exigem leitura/resolução e `@` no corpo não aciona parser de menções. Idempotência por `source_event` OneToOne. Sem backfill, inbox/filtro/edição/deleção de sistêmicas. FSM e workflows estruturados inalterados. Formatador de `POST_SCHEDULE_ISSUE_RESPONDED` é projeção pura do payload (não consulta `Case.appointment_at` — decisão D10).
- **Intercorrência pós-aceitação (dois modos)**: permite ao NIR comunicar mudanças operacionais em casos já aceitos e encerrados (`CLEANED`). Dois contextos: **(a) `scheduled`** — fluxo agendado com ações sobre agenda (cancelar/reagendar/manter/negar), transições FSM `CLEANED → WAIT_APPT → WAIT_R1_CLEANUP_THUMBS → CLEANED`, lock `scheduler_confirm`; **(b) `operational_notice`** — fluxos sem agenda (`immediate`/`pre_icu`/`ward_icu_backup`/`pediatric_em`), CHD apenas confirma ciência, caso permanece `CLEANED` e campos `appointment_*` são imutáveis. Motivos: `death`, `clinical_condition`, `transport_unavailable`, `external_regulation`, `reschedule_request`, `patient_absconded` (evasão), `accepted_elsewhere` (transferência externa), `origin_cancelled` (cancelado pela origem), `other`. Ciclos identificados por `post_acceptance_issue_cycle_id` (UUID) e `post_acceptance_issue_context`. Eventos `POST_ACCEPTANCE_ISSUE_OPENED`/`RESPONDED`/`ACKNOWLEDGED` com `cycle_id`/`context`/`admission_flow` no payload. Serviços: `open_post_acceptance_issue`, `respond_scheduled_post_acceptance_issue`, `acknowledge_scheduled_post_acceptance_issue`, `acknowledge_operational_post_acceptance_issue`. Queries: `unacknowledged_operational_notice_qs()` (notices iniciais duráveis), `unacknowledged_operational_issue_qs()` (issues operacionais abertas). Deduplicação: notice inicial é suprimido quando há issue operacional ativa; após ACK da issue, notice inicial não reaparece. Card CHD específico exibe motivo, mensagem e CTA único "Confirmar ciência" — sem ações de agenda. Badge do scheduler soma `WAIT_APPT` + notices iniciais + issues operacionais. NIR acessa pela busca/detalhe de casos encerrados.

## State do Sistema

- **Fase atual**: Fase 3 (débitos técnicos) — capacity de anexos clínicos entregue
- **Changes concluídos**:
  - `openspec/archive/bootstrap-django-ats-core/` (7 slices, Fase 0)
  - `openspec/archive/intake-nir/` (6 slices, Fase 1)
  - `openspec/archive/pipeline-llm/` (7 slices, Fase 2)
  - `openspec/archive/ui-alinhamento-mocks/` (3 slices, Fase 2b)
  - `openspec/archive/align-llm-contract-and-doctor-routing/` (7 slices)
  - `openspec/archive/post-schedule-intercurrence/` (5 slices + follow-ups)
  - `openspec/archive/post-acceptance-intercurrence/` (3 slices + hardenings — notices operacionais iniciais duráveis até ACK; intercorrência pós-aceitação nos modos `scheduled` e `operational_notice`; ciclos UUID auditáveis; fila/badge CHD deduplicados; ACK operacional sem alterar FSM ou campos `appointment_*`; compatibilidade com eventos e storage legados preservada).
  - `openspec/archive/consolidate-duplicated-test-fixtures/` (1 slice)
  - `openspec/archive/align-uuid-route-parameter-annotations/` (1 slice)
  - `openspec/archive/release-lock-on-successful-handoff/` (1 slice)
  - `openspec/archive/case-attachments-initial-upload/` (4 slices — anexos clínicos PDF/JPEG/PNG no upload NIR, supressão auditável e anexos complementares antes da decisão médica). Limitação aceita L1: lote de anexos complementares sem atomicidade transacional de batch — ver `design.md`.
  - `openspec/archive/fix-prior-case-lookup-after-closure/` (1 slice — correção de bug: prior-case lookup agora usa campos estáveis de decisão `doctor_decision`/`appointment_status` + `*_decided_at`, não status FSM transitório; negativas recentes continuam encontradas mesmo após o caso avançar para `CLEANED`)
  - `openspec/archive/corrected-case-resubmission-linkage/` (2 slices — fluxo NIR de reenvio corrigido explícito: novo `Case` vinculado via `corrects_case` + motivo obrigatório, sem herdar/reabrir o anterior; eventos `CASE_CORRECTION_CREATED`/`CASE_MARKED_SUPERSEDED`; visibilidade NIR e médico com deduplicação vs. prior-case lookup). Deploy runbook em `docs/deploy/corrected-case-resubmission-linkage.md`.
  - `openspec/archive/case-operational-communication-mvp/` (2 slices — thread operacional append-only por caso `CaseCommunicationMessage` para esclarecimentos entre NIR/médico/scheduler; serviço `post_case_communication_message` com validações + endpoint POST `/cases/<id>/communication/` com redirect seguro + partial reutilizado em 4 telas + evento auditável `CASE_COMMUNICATION_MESSAGE_POSTED`. Sem notificações/polling/HTMX/WebSocket; FSM inalterada).
  - `openspec/archive/case-communication-mentions-notifications/` (2 slices + 2 hardening pós-revisão — menções `@role`/`@username` em `CaseCommunicationMessage` criam `UserNotification` (UUID PK, indexes, unique constraint); parser + `create_case_communication_notifications` (exclui autor, deduplica, ignora inativos/blocked) + badge SSR via helper DRY `get_unread_notification_count()` + inbox “Minhas notificações” com redirect seguro por papel/status + endpoint `GET /notifications/unread-count/` (`@require_GET`) + polling Vanilla JS (`fetch()`, 45s, `document.visibilityState`, backoff). Sem autocomplete/aliases/push/SMS/email/WebSocket/SSE/marcação AJAX/polling de thread).
  - `openspec/archive/workflow-system-notices-in-case-communication/` (2 slices + 2 hardening pós-revisão — eventos estruturados selecionados projetam `CaseCommunicationMessage` sistêmica (`message_type="system"`) na thread via serviço central `create_system_communication_notice_for_event` + signal `CaseEvent.post_save` + formatadores por `event_type` (DRY); 7 eventos (`CASE_ATTACHMENT_SUPPRESSED`/`CASE_ATTACHMENT_SUPPLEMENT_ADDED`/`CASE_CORRECTION_CREATED`/`CASE_MARKED_SUPERSEDED`/`POST_SCHEDULE_ISSUE_OPENED`/`POST_SCHEDULE_ISSUE_RESPONDED`/`CASE_ADMINISTRATIVELY_CLOSED`), `POST_SCHEDULE_ISSUE_ACKNOWLEDGED` omitido (payload vazio); render “Sistema” + badge SISTEMA; idempotência por `source_event` OneToOne; sem `UserNotification`/badge/read-resolved/backfill/inbox. FSM e workflows estruturados inalterados).
  - `openspec/archive/prioritize-queues-by-regulation-days/` (2 slices — extrai deterministicamente “Dias em tela: N” do PDF de regulação em `Case.regulation_days_on_screen` (`PositiveIntegerField`, nullable, indexed) via parser puro `extract_regulation_days_on_screen` (maior ocorrência, `None` se ausente); persistência em `_do_extraction` + migration `0010` com backfill idempotente (`elidable=True`) de `extracted_text` existente; filas `WAIT_DOCTOR` e `WAIT_APPT` ordenadas por `F("regulation_days_on_screen").desc(nulls_last=True), "created_at"` + badge “Dias em tela: N” nos cards (apenas `WAIT_APPT`/`WAIT_DOCTOR`, não na vinda imediata); vinda imediata do agendador permanece no topo absoluto. FSM/locks/workflows estruturados inalterados; sem LLM, sem score composto, sem somar dias desde upload).
  - `openspec/archive/dashboard-metrics-search-ux/` (4 slices + 2 correções pós-revisão + micro-fix — polimento UX do dashboard: duração média legível (`N min`/`X h YY min`) + labels visíveis de data; métricas diárias por data selecionada `metrics_date` (padrão hoje, inválida cai silenciosamente) + card “Aguardando por etapa” rotulado ATUAL; busca server-side por nome (`structured_data.patient.name`) e registro (`agency_record_number`), case-insensitive, mínimo 3 caracteres, compondo com status/datas/attention/metrics_date e paginação; migration `cases.0011` com `pg_trgm` + índices GIN trigram efetivamente usados pela query (`Lower()` + `__contains`, Bitmap Index Scan); busca dinâmica progressiva via partial `_case_list.html` + header `X-ATS-Partial: case-list` + Vanilla JS (debounce 400 ms, `AbortController`, fallback de submit tradicional). Sem DRF/JSON/SPA/WS/SSE; FSM e permissões inalteradas). Limitação aceita L1: busca não é accent-insensitive (ver `design.md`).
- **Change merged em main (não arquivado)**: `transactional-emails-auth-flows` (Slices 000–003 concluídos e validados em produção; Slice 004 hardening será implementado direto em main)
- **Apps criados**: `apps/accounts/`, `apps/cases/`, `apps/llm/`, `apps/intake/`, `apps/pipeline/`,
  `apps/doctor/`, `apps/scheduler/`, `apps/dashboard/`, `apps/admin_ui/`
- **Testes**: 2187 passando, quality gate verde (ruff + mypy + pytest)
- **Templates**: base.html com tema hospitalar, login, switch-role, perfil, password reset/change,
  intake (home, my_cases, case_detail), doctor (queue, decision)
- **Documentacao de dominio**: `docs/DOMAIN_ANALYSIS.md`
- **Investigações**: `docs/investigations/2026-05-18-nir-to-doctor-flow-review.md`
- **ADR ativas**: ADR-0001 (arquitetura Django SSR), ADR-0002 (emails transacionais de conta/autenticação)
- **Dívida técnica**: `django-fsm` deprecated → `viewflow.fsm` (não urgente); observabilidade de logs do gunicorn / falha SMTP (candidato a change de hardening)

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
