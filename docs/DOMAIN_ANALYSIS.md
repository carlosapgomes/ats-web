# Domain Analysis — ATS Web (Django Reimplementation)

> Análise independente do projeto legado `augmented-triage-system` para
> extrair entidades de domínio, estados, transições, eventos, side effects,
> permissões e telas necessárias para a reimplementação em Django web (PWA).

---

## Sumário

1. [Visão Geral do Sistema](#1-visão-geral-do-sistema)
2. [Entidades de Domínio](#2-entidades-de-domínio)
3. [Máquina de Estados do Caso](#3-máquina-de-estados-do-caso)
4. [Fluxo Operacional Completo](#4-fluxo-operacional-completo)
5. [Eventos Auditáveis](#5-eventos-auditáveis)
6. [Políticas Clínicas (Decision Engine)](#6-políticas-clínicas-decision-engine)
7. [Permissões e Papéis](#7-permissões-e-papéis)
8. [Side Effects e Tarefas Assíncronas](#8-side-effects-e-tarefas-assíncronas)
9. [Telas/Páginas Necessárias](#9-telaspáginas-necessárias)
10. [Ponderações e Discordâncias do Plano Original](#10-ponderações-e-discordâncias-do-plano-original)
11. [Mapeamento Legado → Django](#11-mapeamento-legado--django)

---

## 1. Visão Geral do Sistema

O sistema legado é um **sistema de triagem automatizada para EDA** (Endoscopia
Digestiva Alta) que opera via salas Matrix. O fluxo é:

1. Um **NIR** envia um PDF de relatório médico numa sala Matrix (Room 1).
2. O sistema extrai o texto, roda LLM1 (extração estruturada) e LLM2 (sugestão).
3. O resultado é apresentado a um **médico** (Room 2) para decisão.
4. Se aceito com agendamento, vai para o **agendador** (Room 3).
5. O resultado final volta para o NIR (Room 1).
6. Após confirmação (👍), mensagens são redactadas (cleanup).
7. Supervisores acompanham via dashboard (monitoring/Room 4).

### Conceitos "Room" → "Filas/Páginas Web"

No legado, "Room" = sala Matrix. No Django web, isso se traduz em **filas
de trabalho por papel**, com telas dedicadas. O conceito de Room desaparece
completamente — é substituído por views/templates Django.

---

## 2. Entidades de Domínio

### 2.1 Case (Caso)

Entidade central. Representa um relatório médico em processamento.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `case_id` | UUID | PK |
| `status` | CaseStatus (FSM) | Estado atual na máquina de estados |
| `agency_record_number` | str | Número de registro (5+ dígitos) extraído do PDF |
| `room1_origin_room_id` | str | **Não relevante no Django** — era sala Matrix |
| `room1_origin_event_id` | str | **Não relevante no Django** — era evento Matrix |
| `room1_sender_user_id` | str | **Adaptar**: FK para User (NIR) |
| `pdf_mxc_url` | str | **Adaptar**: caminho do arquivo no storage local/S3 |
| `extracted_text` | text | Texto extraído do PDF |
| `structured_data_json` | JSON | Saída do LLM1 (extração estruturada) |
| `summary_text` | text | Resumo legível do LLM1 |
| `suggested_action_json` | JSON | Saída do LLM2 (sugestão + policy reconciliation) |
| `doctor_user_id` | FK User | Médico que decidiu |
| `doctor_decision` | `accept` / `deny` | Decisão médica |
| `doctor_support_flag` | `none` / `anesthesist` / `anesthesist_icu` | Necessidade de suporte |
| `doctor_admission_flow` | `scheduled` / `immediate` | Fluxo de admissão |
| `doctor_reason` | text | Motivo (quando deny) |
| `doctor_decided_at` | datetime | Timestamp da decisão |
| `scheduler_user_id` | FK User | Agendador que decidiu |
| `appointment_status` | `confirmed` / `denied` | Status do agendamento |
| `appointment_at` | datetime | Data/hora do agendamento |
| `appointment_location` | text | Local |
| `appointment_instructions` | text | Instruções |
| `appointment_reason` | text | Motivo (quando denied) |
| `appointment_decided_at` | datetime | Timestamp da decisão do agendador |
| `room1_final_reply_event_id` | str | **Adaptar**: referencia ao post do resultado final |
| `room1_final_reply_posted_at` | datetime | Quando o resultado final foi postado |
| `cleanup_triggered_at` | datetime | Quando cleanup foi disparado |
| `cleanup_completed_at` | datetime | Quando cleanup foi concluído |
| `artifact_storage_mode` | str | Modo de armazenamento (default: `full_pdf`) |
| `pdf_sha256` | str | Hash do PDF original |

### 2.2 CaseEvent (Evento de Auditoria)

Registro append-only de tudo que acontece no caso.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | BigInt PK | Auto-incremento |
| `case_id` | FK Case | Caso relacionado |
| `ts` | datetime | Timestamp do evento |
| `actor_type` | `system` / `bot` / `human` | Quem gerou o evento |
| `actor_user_id` | str/UUID | Usuário (quando humano) |
| `event_type` | str | Tipo do evento (ver seção 5) |
| `payload` | JSON | Dados adicionais do evento |

### 2.3 ~~CaseMessage~~ — Removido

**Decisão**: A tabela `case_messages` **não será migrada** para o novo sistema.
No legado ela existia para mapear eventos Matrix a casos. No Django web,
toda ação relevante já fica registrada na trilha de auditoria (`CaseEvent`),
que é suficiente para saber **quem fez o quê e quando**.

As informações que eram tracking de mensagens passam a ser:
- **Eventos de auditoria** (`CaseEvent`): ações do sistema e dos usuários
- **Estado do caso**: o FSM já carrega toda a informação de progresso
- **Notificações**: (futuro) in-app ou email, se necessário

### 2.4 User (Usuário)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | UUID PK | Identificador |
| `email` | str | Email (único) |
| `password_hash` | str | Hash da senha |
| `roles` | M2M Role | Papéis atribuídos (pode ter mais de um) |
| `active_role` | FK Role (nullable) | Papel ativo no momento (apenas 1) |
| `is_active` | bool | Conta ativa |
| `account_status` | `active` / `blocked` / `removed` | Status da conta |

O campo `active_role` é definido no login e pode ser trocado via UI.
Ele é persistido na sessão do Django (session backend).

### 2.5 Role (Papel)

O legado define apenas 2 roles: `admin` e `reader`. No novo sistema,
teremos 5 papéis: `nir`, `doctor`, `scheduler`, `manager`, `admin`.

**Multi-role**: Um usuário pode ter mais de um papel atribuído pelo admin.
Porém, **apenas um papel está ativo por vez**. O usuário escolhe o papel
ativo ao fazer login e pode trocar a qualquer momento clicando em seu
avatar/perfil.

**Restrição de rede (intranet)**:
- `nir` e `scheduler` só podem acessar o sistema de dentro da intranet do hospital.
- `doctor`, `manager` e `admin` podem acessar de qualquer lugar (via túnel Cloudflare com SSL).
- O range de IPs da intranet é configurado via env var (ex: `INTRANET_IP_RANGE=10.0.0.0/8`).
- Middleware Django valida o IP do cliente a cada request para papéis restritos.

### 2.6 PromptTemplate (Template de Prompt)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | UUID PK | |
| `name` | str | Nome do prompt (ex: `llm1_system`, `llm1_user`) |
| `version` | int | Versão (incremental) |
| `content` | text | Conteúdo do prompt |
| `is_active` | bool | Se é a versão ativa |
| `created_at` | datetime | |
| `updated_by_user_id` | FK User | Quem atualizou |

**Constraints**:
- `(name, version)` é único
- Apenas 1 versão ativa por nome (partial unique index)

### 2.7 Job (Fila de Tarefas)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `job_id` | BigInt PK | |
| `case_id` | FK Case (nullable) | Caso relacionado |
| `job_type` | str | Tipo do job |
| `status` | `queued` / ... | Status |
| `attempts` | int | Tentativas |
| `max_attempts` | int | Máximo (default: 5) |
| `last_error` | text | Último erro |
| `payload` | JSON | Dados do job |

**No Django**: Substituído por `django-q2` Task ORM ou tabela customizada.

### 2.8 AuthEvent / AuthToken

Eventos de autenticação (login, logout, falhas). Tokens opacos para sessão.

**No Django**: `django.contrib.auth` + `django.contrib.sessions` cobrem isso.
A tabela `auth_events` pode ser mantida como auditoria customizada.

### 2.9 SupervisorSummaryDispatch

Rastreia envio de resumos periódicos para supervisores.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | BigInt PK | |
| `room_id` | str | **Adaptar**: destino do resumo |
| `window_start` | datetime | Início da janela |
| `window_end` | datetime | Fim da janela |
| `status` | `pending` / `sent` / `failed` | Status |
| `sent_at` | datetime | Quando foi enviado |
| `matrix_event_id` | str | **Adaptar**: referência ao envio |

### 2.10 ReactionCheckpoint

Rastreia reações (👍) do NIR confirmando recebimento. **No Django**, será
adaptado para uma confirmação explícita via botão/clique.

### 2.11 Entidades do LLM (DTOs/Value Objects)

Estes não são modelos persistidos diretamente, mas value objects complexos
que estruturam os dados do caso:

- **Llm1Response**: Extração estruturada completa do PDF
  - Patient (nome, idade, sexo, documento)
  - EDA (indicação, subtipo, labs, ECG, ASA, risco cardiovascular)
  - PreopScreening (tipo de exame, flags clínicos, sinais do rulebook)
  - PolicyPrecheck (pre-checks para reconciliation)
  - Summary (one-liner + bullets)
  - ExtractionQuality (confiança, campos faltantes)
  - OriginContext (hospital, cidade, UF)
  - Transfusion, TrackedExams

- **Llm2Response**: Sugestão de decisão
  - suggestion (`accept` / `deny`)
  - support_recommendation (`none` / `anesthesist` / `anesthesist_icu`)
  - rationale (short_reason + details + missing_info_questions)
  - policy_alignment (labs_ok, ecg_ok, pediatric_flag)
  - confidence

- **EdaPreopDecision**: Resultado determinístico do policy engine
- **EdaPolicyResult**: Resultado da reconciliation com contradições

---

## 3. Máquina de Estados do Caso

### 3.1 Estados (CaseStatus)

```
NEW                        → Caso criado (antes de processar)
R1_ACK_PROCESSING          → NIR: recebido, processando
EXTRACTING                 → Extraindo texto do PDF
LLM_STRUCT                 → LLM1 rodando (extração estruturada)
LLM_SUGGEST                → LLM2 rodando (sugestão)
R2_POST_WIDGET             → Montando apresentação para o médico
WAIT_DOCTOR                → Aguardando decisão médica
DOCTOR_DENIED              → Médico negou
DOCTOR_ACCEPTED            → Médico aceitou
R3_POST_REQUEST            → Montando solicitação de agendamento
WAIT_APPT                  → Aguardando agendamento
APPT_CONFIRMED             → Agendamento confirmado
APPT_DENIED                → Agendamento negado
FAILED                     → Falha no processamento
R1_FINAL_REPLY_POSTED      → [compat] Resposta final postada
WAIT_R1_CLEANUP_THUMBS     → Aguardando confirmação do NIR
CLEANUP_RUNNING            → Cleanup em andamento
CLEANED                    → Caso finalizado e limpo
```

### 3.2 Grafo de Transições

```
NEW ───────────────────────────────────────────────────► R1_ACK_PROCESSING
R1_ACK_PROCESSING ──────────────────────────────────────► EXTRACTING
EXTRACTING ──────────────────────────────────┬──────────► LLM_STRUCT
                                             └──────────► FAILED
LLM_STRUCT ──────────────────────────────────┬──────────► LLM_SUGGEST
                                             └──────────► FAILED
LLM_SUGGEST ─────────────────────────────────┬──────────► R2_POST_WIDGET
                                             └──────────► FAILED
R2_POST_WIDGET ─────────────────────────────────────────► WAIT_DOCTOR
WAIT_DOCTOR ───────────────────────┬────────────────────► DOCTOR_ACCEPTED
                                   └────────────────────► DOCTOR_DENIED
DOCTOR_DENIED ──────────────────────────────────────────► WAIT_R1_CLEANUP_THUMBS
DOCTOR_ACCEPTED ────────────────────────────────────────► R3_POST_REQUEST
R3_POST_REQUEST ───────────────────────────────────────► WAIT_APPT
WAIT_APPT ───────────────────────┬─────────────────────► APPT_CONFIRMED
                                  └─────────────────────► APPT_DENIED
APPT_CONFIRMED ─────────────────────────────────────────► WAIT_R1_CLEANUP_THUMBS
APPT_DENIED ────────────────────────────────────────────► WAIT_R1_CLEANUP_THUMBS
FAILED ─────────────────────────────────────────────────► WAIT_R1_CLEANUP_THUMBS
R1_FINAL_REPLY_POSTED ──────────────────────────────────► WAIT_R1_CLEANUP_THUMBS
WAIT_R1_CLEANUP_THUMBS ─────────────────────────────────► CLEANUP_RUNNING
CLEANUP_RUNNING ─────────────────────────────────────────► CLEANED
CLEANED ────────────────────────────────────────────────► (terminal)
```

### 3.3 Nota sobre "Vinda Imediata" (immediate)

Quando `doctor_decision = accept` e `doctor_admission_flow = immediate`:
- O médico **autoriza a chegada imediata** do paciente — não há agendamento.
- O agendador é **notificado** (recebe uma mensagem informativa), mas **não precisa agir**.
- O resultado (decisão médica + suporte + fluxo) é **imediatamente enviado ao NIR**.
- O caso vai direto para `WAIT_R1_CLEANUP_THUMBS` após a notificação.

**Fluxo comparativo**:

```
accept + scheduled:
  Médico aceita → Agendador agenda (confirma/desmarca) → Resultado → NIR

accept + immediate:
  Médico aceita → Agendador é notificado (info only) → Resultado → NIR
                    └─ sem ação do agendador ──┘
```

### 3.4 Nota sobre "Scope Gated Manual Review"

Quando o LLM1 identifica que o exame **não é EDA** (`non_eda_request` ou
`unknown_exam_type`):
- O caso **não vai para Room 2** (decisão médica).
- Vai diretamente para `WAIT_R1_CLEANUP_THUMBS` com mensagem de revisão manual.
- Isso é um shortcut que pula WAIT_DOCTOR.

### 3.5 Preservação dos 17 Estados

**Decisão**: Manter **todos os 17 estados originais** do legado, sem simplificação.
Cada estado representa um ponto no fluxo que precisa ser rastreável na trilha
de auditoria — é essencial saber **quem fez o quê e quando fez**.

Os estados intermediários de processamento automático (`EXTRACTING`,
`LLM_STRUCT`, `LLM_SUGGEST`, `R2_POST_WIDGET`, `R3_POST_REQUEST`) terão
transições rápidas no Django (muitas síncronas dentro da mesma transação),
mas continuam sendo registrados no FSM e nos eventos de auditoria.

---

## 4. Fluxo Operacional Completo

### 4.1 Fluxo Principal (Happy Path — Agendamento)

```
[NIR] Upload PDF
  │
  ├─► Sistema: extrair texto do PDF
  ├─► Sistema: extrair número de registro
  ├─► Sistema: LLM1 (extração estruturada)
  ├─► Sistema: LLM2 (sugestão)
  ├─► Sistema: Policy Engine (reconciliation)
  │
  ├─► [Médico] Visualiza caso + sugestão
  │     ├─► Aceita (scheduled)
  │     │     └─► [Agendador] Confirma/desmarca
  │     │           ├─► Confirmado → resultado final → [NIR] confirma
  │     │           └─► Negado → resultado final → [NIR] confirma
  │     └─► Nega → resultado final → [NIR] confirma
  │
  └─► Sistema: cleanup (remover dados sensíveis)
```

### 4.2 Fluxo: Vinda Imediata (immediate)

```
[Médico] Aceita (immediate)
  │
  ├─► [Agendador] recebe notificação informativa (SEM ação requerida)
  │
  └─► Resultado final enviado ao [NIR] imediatamente
        └─► [NIR] confirma recebimento → cleanup
```

### 4.3 Fluxo: Scope Gated Manual Review

```
Sistema: detecta que não é EDA
  │
  └─► Mensagem "revisão manual" → [NIR] confirma → cleanup
      (sem passar pelo médico)
```

### 4.4 Fluxo: Falha

```
Sistema: erro no download/extraction/LLM
  │
  └─► Mensagem de falha → [NIR] confirma → cleanup
```

---

## 5. Eventos Auditáveis

Cada ação relevante gera um `CaseEvent`. Os tipos de evento mais importantes:

### 5.1 Intake & Processamento

| Event Type | Actor | Descrição |
|------------|-------|-----------|
| `ROOM1_PDF_ACCEPTED` | system | PDF recebido e aceito |
| `ROOM1_PROCESSING_ACK_POSTED` | bot | Confirmação de processamento |
| `JOB_ENQUEUED_PROCESS_PDF_CASE` | system | Job de processamento enfileirado |
| `LLM1_STRUCTURED_SUMMARY_OK` | system | LLM1 completou com sucesso |
| `LLM1_FAILED` | system | LLM1 falhou |
| `LLM2_SUGGESTION_OK` | system | LLM2 completou com sucesso |
| `LLM2_FAILED` | system | LLM2 falhou |
| `LLM_CONTRADICTION_DETECTED` | system | Policy reconciliation detectou contradição |
| `EDA_SCOPE_GATED_MANUAL_REVIEW` | system | Exame fora de escopo EDA |
| `CASE_STATUS_CHANGED` | system | Mudança de status |

### 5.2 Decisão Médica

| Event Type | Actor | Descrição |
|------------|-------|-----------|
| `ROOM2_WIDGET_POSTED` | bot | Caso apresentado ao médico |
| `ROOM2_CASE_SUMMARY_POSTED` | bot | Resumo postado |
| `ROOM2_CASE_INSTRUCTIONS_POSTED` | bot | Instruções postadas |
| `ROOM2_CASE_TEMPLATE_POSTED` | bot | Template postado |
| `ROOM2_WIDGET_SUBMITTED` | system | Médico submeteu decisão |
| `ROOM2_DECISION_ACK_POSTED` | bot | Confirmação da decisão postada |
| `ROOM2_DECISION_IGNORED_WRONG_STATE` | system | Decisão ignorada (estado errado) |
| `ROOM2_DECISION_DUPLICATE_OR_RACE_IGNORED` | system | Decisão duplicada |

### 5.3 Agendamento

| Event Type | Actor | Descrição |
|------------|-------|-----------|
| `ROOM3_REQUEST_POSTED` | bot | Solicitação de agendamento postada |
| `ROOM3_TEMPLATE_POSTED` | bot | Template postado |
| `ROOM3_APPOINTMENT_CONFIRMED` | system | Agendamento confirmado |
| `ROOM3_APPOINTMENT_DENIED` | system | Agendamento negado |
| `ROOM3_TEMPLATE_PARSE_FAILED` | system | Parser falhou |
| `ROOM3_ACK_POSTED` | bot | Confirmação postada |
| `ROOM3_IMMEDIATE_INFO_POSTED` | bot | Info vinda imediata |
| `ROOM3_IMMEDIATE_ACK_POSTED` | bot | Ack vinda imediata |

### 5.4 Resultado Final

| Event Type | Actor | Descrição |
|------------|-------|-----------|
| `ROOM1_FINAL_REPLY_POSTED` | bot | Resultado final postado para NIR |
| `ROOM1_FINAL_THUMBS_UP_RECEIVED` | human | NIR confirmou com 👍 |
| `ROOM1_FINAL_THUMBS_UP_TRIGGERED_CLEANUP` | system | Cleanup disparado |

### 5.5 Cleanup

| Event Type | Actor | Descrição |
|------------|-------|-----------|
| `MATRIX_EVENT_REDACTED` | system | Mensagem redactada |
| `CLEANUP_COMPLETED` | system | Cleanup finalizado |

### 5.6 Supervisão

| Event Type | Actor | Descrição |
|------------|-------|-----------|
| `PRIOR_CASE_LOOKUP_COMPLETED` | system | Consulta de casos anteriores |

---

## 6. Políticas Clínicas (Decision Engine)

O sistema tem um **engine de regras determinístico** que opera sobre a saída
do LLM1 para tomar decisões de pré-operatório. Isso é crítica para o novo
sistema e deve ser preservado fielmente.

### 6.1 EDA Preop Policy (`evaluate_eda_preop_policy`)

Avalia critérios determinísticos antes da apresentação ao médico:

1. **Foreign Body Exception**: Corpo estranho → bypass de exames mínimos, accept automático
2. **Minimum Exam Check**: Verifica presença de:
   - Hb/Ht, Plaquetas, TP/INR/RNI, TTPa, Ureia, Creatinina
   - Ausência → deny
3. **Threshold Check**:
   - HB < mínimo (7.0 ou 8.0 dependendo do perfil)
   - Plaquetas < mínimo (50K ou 100K)
   - RNI/INR > 1.5
4. **Conditional Exam Gates**:
   - ECG: se >40 anos ou doença cardiovascular
   - RX Tórax: se sintomas respiratórios
   - Ecocardiograma: se risco cardíaco estrutural
5. **Thresholds por perfil** (hepatopatia, cardiopatia, ambos, geral)

### 6.2 EDA Policy Reconciliation (`reconcile_eda_policy`)

Aplica hard rules sobre a saída do LLM2:

1. **Excluded Request**: Força deny se excluído do fluxo EDA
2. **Foreign Body**: Labs e ECG viram "not_required"
3. **Required Labs Missing/Failed**: Força deny
4. **Required ECG Missing**: Força deny
5. Registra contradições explicitamente para auditoria

### 6.3 Support Recommendation Synthesis

Deriva recomendação de suporte baseada em:
- **ASA bucket**: I-II, III ou mais, insufficient_data
- **Cardiovascular risk**: low, moderate_high, unknown
- Mapeamento: moderate_high → `anesthesist_icu`, ASA III+ → `anesthesist`, resto → `none`

### 6.4 Scope Detection

Detecta se o exame é EDA baseado em keywords no texto:
- Gastrostomia (gtt, gastrostomia, gastrostomy)
- Dilatação esofágica
- Corpo estranho
- EDA genérico

Se não for EDA → `manual_review_required` (pula decisão médica).

---

## 7. Permissões e Papéis

### 7.1 Papéis no Legado

O legado tem apenas 2 roles explícitos no banco: `admin` e `reader`.

A separação funcional é feita por **sala Matrix**:
- Quem está em Room 1 → NIR
- Quem está em Room 2 → Médico
- Quem está em Room 3 → Agendador
- Quem está em Room 4 → Supervisor/Manager

### 7.2 Papéis Propostos para o Django

| Papel | Descrição | Permissões |
|-------|-----------|------------|
| `nir` | Operador NIR | Upload PDF, ver resultado final, confirmar recebimento |
| `doctor` | Médico | Ver fila médica, decidir (accept/deny), ver detalhes do caso |
| `scheduler` | Agendador | Ver fila de agendamento, confirmar/desmarcar agendamento, receber notificações de vinda imediata |
| `manager` | Supervisor | Dashboard, ver todos os casos, timeline, métricas |
| `admin` | Administrador | Gerir usuários, gerir prompts, tudo acima |

### 7.3 Access Guard

O legado usa `AccessGuardService` com dois checks:
- `require_admin`: Apenas admin
- `require_audit_read`: Admin ou reader

No Django, isso se traduz em decorators/mixins por view:
- `@role_required('doctor')` para views médicas
- `@role_required('scheduler')` para views do agendador
- `@role_required('manager', 'admin')` para dashboard
- `@role_required('admin')` para admin

### 7.4 Matriz de Permissões por Tela

> Cada usuário enxerga apenas as telas do seu **papel ativo** no momento.
> A troca de papel é feita via avatar/perfil no canto superior da tela.

| Tela | nir | doctor | scheduler | manager | admin |
|------|-----|--------|-----------|---------|-------|
| Upload PDF | ✅ | - | - | - | ✅ |
| Minha fila (NIR) | ✅ | - | - | - | - |
| Fila médica | - | ✅ | - | ✅ | ✅ |
| Decisão médica | - | ✅ | - | - | - |
| Fila agendamento | - | - | ✅ | ✅ | ✅ |
| Agendar/desmarcar | - | - | ✅ | - | - |
| Dashboard | - | - | - | ✅ | ✅ |
| Detalhe do caso | ✅ | ✅ | ✅ | ✅ | ✅ |
| Timeline do caso | ✅ | ✅ | ✅ | ✅ | ✅ |
| Gestão usuários | - | - | - | - | ✅ |
| Gestão prompts | - | - | - | - | ✅ |
| Relatórios/métricas | - | - | - | ✅ | ✅ |

### 7.5 Restrição de Acesso por Rede

O sistema será acessado externamente via **túnel Cloudflare (com SSL)**.
Porém, papéis operacionais (`nir`, `scheduler`) ficam restritos à intranet.

**Mecanismo**:
- Env var `INTRANET_IP_RANGE` define o bloco CIDR permitido (ex: `10.0.0.0/8`).
- Middleware Django verifica o IP do cliente a cada request.
- Se o papel ativo do usuário for `nir` ou `scheduler` e o IP estiver fora do range:
  - Request é bloqueado com HTTP 403.
  - Evento de auditoria é registrado (auth event).
- O IP real é extraído do header `X-Forwarded-For` (Cloudflare) ou do `REMOTE_ADDR`.
- Env var opcional `TRUSTED_PROXY_HEADER` para configurar qual header usar.

**Fluxo de acesso**:

```
NIR/Agendador (intranet):
  Hospital PC → Intranet → Servidor Django (IP interno) ✅

Médico/Supervisor/Admin (externo):
  Qualquer lugar → Cloudflare Tunnel (SSL) → Servidor Django ✅

NIR/Agendador (tentativa externa):
  Qualquer lugar → Cloudflare Tunnel (SSL) → Servidor Django → 403 ❌
```

---

## 8. Side Effects e Tarefas Assíncronas

### 8.1 Job Types do Legado

| Job Type | Descrição | Django-q2 Equivalente |
|----------|-----------|----------------------|
| `process_pdf_case` | Download + extração + LLM1 + LLM2 | `async_task(process_pdf_case, case_id)` |
| `post_room2_widget` | Apresentar caso ao médico | **Não necessário** — renderizar template |
| `post_room3_request` | Solicitar agendamento | **Não necessário** — renderizar template |
| `post_room1_final_denial_triage` | Postar resultado (negação médica) | Notificação ao NIR |
| `post_room1_final_appt` | Postar resultado (agendamento confirmado) | Notificação ao NIR |
| `post_room1_final_appt_denied` | Postar resultado (agendamento negado) | Notificação ao NIR |
| `post_room1_final_immediate` | Postar resultado (vinda imediata) | Notificação ao NIR |
| `post_room1_final_failure` | Postar resultado (falha) | Notificação ao NIR |
| `post_room1_final_scope_manual_review` | Postar resultado (fora de escopo) | Notificação ao NIR |
| `post_immediate_admission_flow` | Postar info vinda imediata | Notificação ao agendador |
| `post_room4_summary` | Resumo periódico | `cron(resumo_periodico)` |
| `execute_cleanup` | Redactar mensagens | `async_task(cleanup_case, case_id)` |

### 8.2 No Django, Jobs "Post Room" Desaparecem

No legado, "post room X" = postar mensagem Matrix. No Django web:
- A informação é renderizada no template quando o usuário acessa a página.
- **Não precisa de job para postar** — é SSR.
- Jobs assíncronos reais: `process_pdf_case`, `execute_cleanup`, `resumo_periodico`.

### 8.3 Processamento de PDF (Pipeline)

```
upload_pdf → extract_text → extract_record_number
                              │
                              ├─► llm1 (structured extraction)
                              │     └─► eda_preop_policy (deterministic gate)
                              │           ├─► scope_gate → manual_review (no LLM2)
                              │           └─► llm2 (suggestion)
                              │                 └─► reconcile_eda_policy
                              │                 └─► synthesize_support_context
                              │
                              └─► store artifacts on Case model
```

### 8.4 Resumo Periódico (Room 4)

O legado usa janelas de tempo com cutoffs configuráveis (ex: 8h, 16h, 0h).
Agrega métricas e posta em Room 4.

No Django: `django-q2` schedule com `cron()` gera o resumo e disponibiliza
via dashboard ou email.

---

## 9. Telas/Páginas Necessárias

### 9.1 Mapeamento Legado → Django

| "Room" Legado | papel | Tela Django | Descrição |
|---------------|-------|-------------|-----------|
| Room 1 | nir | `/cases/upload/` | Upload de PDF |
| Room 1 | nir | `/cases/my-cases/` | Meus casos (lista) |
| Room 1 | nir | `/cases/<id>/result/` | Resultado final + botão confirmar |
| Room 2 | doctor | `/doctor/queue/` | Fila de casos aguardando decisão |
| Room 2 | doctor | `/doctor/cases/<id>/` | Detalhe + formulário de decisão |
| Room 3 | scheduler | `/scheduler/queue/` | Fila de agendamentos |
| Room 3 | scheduler | `/scheduler/cases/<id>/` | Detalhe + formulário de agendamento |
| Room 4 | manager | `/dashboard/` | Dashboard operacional |
| Room 4 | manager | `/cases/<id>/` | Detalhe do caso (timeline) |
| - | admin | `/admin/users/` | Gestão de usuários |
| - | admin | `/admin/prompts/` | Gestão de prompts |

### 9.2 Detalhamento das Telas

#### Tela 1: Login (`/login/`)
- Form email + senha
- Session-based auth (Django padrão)
- Se o usuário tem **múltiplos papéis**: tela de seleção de papel após autenticação
  - Ex: "Escolha com qual papel deseja entrar: [Médico] [Manager]"
- Se o usuário tem **apenas 1 papel**: segue direto para a home do papel
- Validação de IP contra `INTRANET_IP_RANGE` para papéis `nir` e `scheduler`

#### Tela 2: Upload PDF (`/cases/upload/`)
- **Acesso**: nir, admin
- Upload de PDF (drag & drop)
- Criação automática do caso
- Feedback imediato: "Processando..."
- Redireciona para Meus Casos

#### Tela 3: Meus Casos NIR (`/cases/my-cases/`)
- **Acesso**: nir
- Lista de casos criados pelo NIR logado
- Colunas: registro, paciente, status, data, resultado
- Filtros: status, data
- Link para detalhe

#### Tela 4: Fila Médica (`/doctor/queue/`)
- **Acesso**: doctor, manager, admin
- Casos em `WAIT_DOCTOR`
- Cards com: registro, paciente, resumo, sugestão LLM, ASA
- Link para detalhe/decisão
- Badges: pedido de suporte, vinda imediata

#### Tela 5: Decisão Médica (`/doctor/cases/<id>/`)
- **Acesso**: doctor
- Seções:
  - PDF original (viewer inline)
  - Dados estruturados (patient, labs, ECG)
  - Sugestão LLM (accept/deny + rationale)
  - Resultado do policy engine (preop gate)
  - Casos anteriores (prior lookup)
- Formulário de decisão:
  - Decisão: `accept` / `deny`
  - Support flag (se accept): `none` / `anesthesist` / `anesthesist_icu`
  - Admission flow (se accept): `scheduled` / `immediate`
  - Motivo (se deny): texto livre

#### Tela 6: Fila do Agendador (`/scheduler/queue/`)
- **Acesso**: scheduler, manager, admin
- Casos em `WAIT_SCHEDULER` (era WAIT_APPT) — apenas fluxo `scheduled`
- **Notificações de vinda imediata** (fluxo `immediate`) aparecem em seção separada, somente leitura
- Cards com: registro, paciente, médico, suporte, tipo (agendamento / vinda imediata)
- Link para agendamento (quando `scheduled`)

#### Tela 7: Agendamento (`/scheduler/cases/<id>/`)
- **Acesso**: scheduler
- **Comportamento varia por tipo**:
  - **Fluxo `scheduled`**: formulário de agendamento
    - Status: `confirmed` / `denied`
    - Data/hora (se confirmed)
    - Local (se confirmed)
    - Instruções (se confirmed)
    - Motivo (se denied)
  - **Fluxo `immediate`**: tela somente leitura
    - Informação do caso + decisão médica
    - Badges: "Vinda Imediata" / "Suporte: anestesista"
    - Nenhum formulário — agendador apenas toma ciência

#### Tela 8: Resultado Final (`/cases/<id>/result/`)
- **Acesso**: nir (autor do upload)
- Resultado final do caso:
  - Aceito: data/hora, local, instruções, médico, suporte
  - Negado: motivo
  - Vinda imediata: médico, suporte
  - Falha: causa
  - Fora de escopo: explicação
- Botão: "Confirmar recebimento" (equivale ao 👍)
- Após confirmação → caso entra em cleanup

#### Tela 9: Dashboard (`/dashboard/`)
- **Acesso**: manager, admin
- Métricas do dia/período:
  - Pacientes recebidos
  - Relatórios processados
  - Casos avaliados
  - Aceitos (agendamento)
  - Vinda imediata
  - Recusados
  - Em andamento (por etapa)
- Lista de casos com filtros:
  - Por status/etapa
  - Por data
  - Por resultado
- Paginação
- Link para detalhe

#### Tela 10: Detalhe do Caso (`/cases/<id>/`)
- **Acesso**: todos os papéis (com scope por papel)
- Timeline completa do caso (todos os eventos auditáveis)
- Dados do caso
- Decisão médica (se houver)
- Agendamento (se houver)
- Evidence spans (evidências extraídas)

#### Tela 11: Gestão de Usuários (`/admin/users/`)
- **Acesso**: admin
- Lista de usuários
- Criar/editar/desativar
- Atribuir papel

#### Tela 12: Gestão de Prompts (`/admin/prompts/`)
- **Acesso**: admin
- Lista de prompts por nome
- Versões de cada prompt
- Criar nova versão
- Ativar/desativar versão

#### Tela 13: Home/Redirect (`/`)
- Redireciona para a tela adequada ao **papel ativo**:
  - nir → `/cases/my-cases/`
  - doctor → `/doctor/queue/`
  - scheduler → `/scheduler/queue/`
  - manager → `/dashboard/`
  - admin → `/dashboard/`

#### Tela 14: Troca de Papel (`/switch-role/`)
- **Acesso**: qualquer usuário com múltiplos papéis
- Acessível via clique no avatar/perfil (canto superior)
- Mostra cards/botões com os papéis disponíveis
- Ao trocar: atualiza sessão e redireciona para a home do novo papel
- Se o novo papel for `nir`/`scheduler`: valida IP contra intranet

#### Tela 15: Perfil/Avatar (`/profile/`)
- **Acesso**: qualquer usuário autenticado
- Mostra: nome, email, papel ativo, papéis disponíveis
- Badge visual do papel ativo no header (todas as telas)

### 9.3 Telas PWA

Para comportamento PWA:
- `manifest.json` com ícone, nome, tema
- Service Worker para cache de assets estáticos
- Meta tags viewport, theme-color
- Instalável (prompt de instalação)

---

## 10. Ponderações e Discordâncias do Plano Original

### 10.1 ✅ Concordâncias

1. **Sem migração de código/dados** — correto.
2. **Sem FastAPI/Matrix/SQLAlchemy/Alembic** — correto.
3. **Django ORM + PostgreSQL + migrations** — correto.
4. **django-fsm para estados** — excelente escolha, alinha perfeitamente.
5. **django-q2 para assíncrono** — correto.
6. **Auditoria como parte central** — correto e essencial.
7. **Ordem de implementação** — a sequência faz sentido.

### 10.2 Decisões Tomadas

#### D1: Papéis — 5 papéis confirmados ✅

`nir`, `doctor`, `scheduler`, `manager`, `admin`. A separação funcional
que era implícita nas salas Matrix torna-se explícita via roles no Django.

#### D2: "Rooms" são Filas ✅

Cada Room legado vira uma fila/tela no Django. Sem chat bidirecional.
A informação é renderizada via templates SSR.

#### D3: Todos os 17 estados preservados ✅

**Decisão**: Manter os 17 estados sem simplificação. Cada estado é um
ponto rastreável na auditoria — é essencial saber quem fez o quê e quando.
Ver seção 3.5.

#### D4: Jobs "Post Room" Desaparecem ✅

No Django web, a informação é renderizada via template SSR. Jobs reais:
`process_pdf_case` e `resumo_periodico`.

#### D5: Template Parsing Desaparece ✅

Formulários HTML substituem templates textuais Matrix. `doctor_decision_parser`
e `scheduler_parser` desaparecem completamente.

#### D6: Reaction / Thumbs-up → Botão ✅

Botão "Confirmar Recebimento" na tela de resultado.

#### D7: Cleanup = Marcar como fechado ✅

**Decisão**: Cleanup significa simplesmente **marcar o caso como `CLEANED`**.
O caso deixa de aparecer nas filas operacionais e só é visível nas trilhas
de auditoria. Não há redaction de dados — a retenção é gerida pela
marcação de status.

#### D8/D9: case_messages desaparece ✅

**Decisão**: A tabela `case_messages` **não será migrada**. Toda a informação
necessária já está coberta pelos eventos de auditoria (`CaseEvent`), que
registram quem fez o quê e quando. Ver seção 2.3.

#### D10: Prior Case Lookup ✅

Preservar a consulta de casos anteriores do mesmo registro para detectar
negações recentes.

#### D11: LLM Service Abstraction ✅

Manter abstração com injeção de dependência + prompt versionado.

#### D12: PWA Leve ✅

Service Worker mínimo para cache de estáticos. SSR puro.

#### D13: PDF Storage = Local Filesystem ✅

**Decisão**: PDFs são armazenados no **filesystem local** do servidor
(`MEDIA_ROOT`), servidos pelo Django em dev e pelo servidor web em produção.
Sem S3, sem object storage externo.

#### D14: Notificações in-app ✅

**Decisão**: Todas as notificações são **dentro do aplicativo** (in-app).
Sem email, sem SMS, sem push. Quando um novo caso aparece na fila do médico,
por exemplo, ele vê ao acessar sua fila. Futuramente pode-se adicionar
badges de contagem no menu.

#### D15: Multi-role com papel ativo ✅

**Decisão**: O admin pode atribuir **múltiplos papéis** a um usuário.
O usuário escolhe o papel ativo ao logar e pode trocar via avatar/perfil.
Apenas um papel ativo por vez. A troca atualiza a sessão e redireciona.

#### D16: Intranet restriction para NIR e Scheduler ✅

**Decisão**: `nir` e `scheduler` só acessam de dentro da intranet do hospital.
O range de IPs é configurado via env var `INTRANET_IP_RANGE` (formato CIDR).
Middleware bloqueia requests de IPs fora do range para esses papéis.
O sistema é acessado externamente via túnel Cloudflare com SSL por
`doctor`, `manager` e `admin`.

---

## 11. Mapeamento Legado → Django

### 11.1 Apps Django Recomendados

```
ats_web/
├── apps/
│   ├── accounts/         → User, Role, AuthEvent
│   ├── cases/            → Case, CaseStatus (FSM), CaseEvent
│   ├── intake/           → Upload PDF, NIR views
│   ├── doctor/           → Fila médica, decisão
│   ├── scheduler/        → Fila agendamento, confirmação
│   ├── dashboard/        → Dashboard supervisor, métricas
│   ├── llm/              → LLM client, prompt templates, pipeline
│   ├── policy/           → EDA preop policy, reconciliation engine
│   └── admin_panel/      → Gestão usuários, prompts
├── config/               → Settings, URLs, WSGI/ASGI
├── static/               → CSS (Bootstrap 5.3), JS vanilla
├── templates/            → Base templates + per-app
└── manage.py
```

### 11.2 Modelos Django Principais

```python
# accounts/models.py
class Role(Model):
    name: CharField  (nir/doctor/scheduler/manager/admin)

class User(AbstractUser):
    roles: M2M(Role)  # multi-role
    active_role: FK(Role, null)  # selecionado no login / troca via UI
    account_status: CharField  (active/blocked/removed)

# cases/models.py
class Case(Model):
    case_id: UUIDField (PK)
    status: CharField  (FSM via django-fsm - TODOS os 17 estados preservados)
    agency_record_number: CharField
    agency_record_extracted_at: DateTimeField
    pdf_file: FileField  (local filesystem, MEDIA_ROOT)
    extracted_text: TextField
    structured_data: JSONField
    summary_text: TextField
    suggested_action: JSONField
    # doctor fields
    doctor: FK(User, null)
    doctor_decision: CharField  (accept/deny)
    doctor_support_flag: CharField  (none/anesthesist/anesthesist_icu)
    doctor_admission_flow: CharField  (scheduled/immediate)
    doctor_reason: TextField
    doctor_decided_at: DateTimeField
    # scheduler fields
    scheduler: FK(User, null)
    appointment_status: CharField  (confirmed/denied)
    appointment_at: DateTimeField
    appointment_location: TextField
    appointment_instructions: TextField
    appointment_reason: TextField
    appointment_decided_at: DateTimeField
    # closure fields
    final_reply_posted_at: DateTimeField
    cleanup_triggered_at: DateTimeField
    cleanup_completed_at: DateTimeField
    # metadata
    created_by: FK(User)  # NIR
    created_at: DateTimeField
    updated_at: DateTimeField

class CaseEvent(Model):
    case: FK(Case)
    timestamp: DateTimeField  (auto)
    actor_type: CharField  (system/bot/human)
    actor: FK(User, null)
    event_type: CharField  (~40 tipos diferentes)
    payload: JSONField

# llm/models.py
class PromptTemplate(Model):
    id: UUIDField (PK)
    name: CharField
    version: IntegerField
    content: TextField
    is_active: BooleanField
    updated_by: FK(User, null)
    created_at: DateTimeField
    updated_at: DateTimeField
```

> **Nota**: `case_messages` foi removido. `CaseEvent` cobre toda a rastreabilidade.

### 11.3 FSM Transitions (django-fsm) - Todos os 17 estados

```python
class Case(Model):
    status = FSMField(default=CaseStatus.NEW)

    # --- Intake & Processing ---
    @transition(field=status, source=CaseStatus.NEW, target=CaseStatus.R1_ACK_PROCESSING)
    def start_processing(self): ...

    @transition(field=status, source=CaseStatus.R1_ACK_PROCESSING, target=CaseStatus.EXTRACTING)
    def start_extraction(self): ...

    @transition(field=status, source=CaseStatus.EXTRACTING, target=[CaseStatus.LLM_STRUCT, CaseStatus.FAILED])
    def extraction_complete(self, success): ...

    @transition(field=status, source=CaseStatus.LLM_STRUCT, target=[CaseStatus.LLM_SUGGEST, CaseStatus.FAILED])
    def llm1_complete(self, success): ...

    @transition(field=status, source=CaseStatus.LLM_SUGGEST, target=[CaseStatus.R2_POST_WIDGET, CaseStatus.FAILED])
    def llm2_complete(self, success): ...

    # --- Doctor Decision ---
    @transition(field=status, source=CaseStatus.R2_POST_WIDGET, target=CaseStatus.WAIT_DOCTOR)
    def ready_for_doctor(self): ...

    @transition(field=status, source=CaseStatus.WAIT_DOCTOR, target=[CaseStatus.DOCTOR_ACCEPTED, CaseStatus.DOCTOR_DENIED])
    def doctor_decide(self, decision): ...

    # --- Scheduling ---
    @transition(field=status, source=CaseStatus.DOCTOR_ACCEPTED, target=CaseStatus.R3_POST_REQUEST)
    def ready_for_scheduler(self): ...

    @transition(field=status, source=CaseStatus.R3_POST_REQUEST, target=CaseStatus.WAIT_APPT)
    def scheduler_request_posted(self): ...

    @transition(field=status, source=CaseStatus.WAIT_APPT, target=[CaseStatus.APPT_CONFIRMED, CaseStatus.APPT_DENIED])
    def scheduler_decide(self, appointment_status): ...

    # --- Closure ---
    @transition(field=status, source=[
        CaseStatus.DOCTOR_DENIED,
        CaseStatus.APPT_CONFIRMED,
        CaseStatus.APPT_DENIED,
        CaseStatus.FAILED,
        CaseStatus.R1_FINAL_REPLY_POSTED,
    ], target=CaseStatus.WAIT_R1_CLEANUP_THUMBS)
    def final_reply_posted(self): ...

    @transition(field=status, source=CaseStatus.WAIT_R1_CLEANUP_THUMBS, target=CaseStatus.CLEANUP_RUNNING)
    def cleanup_triggered(self): ...

    @transition(field=status, source=CaseStatus.CLEANUP_RUNNING, target=CaseStatus.CLEANED)
    def cleanup_completed(self): ...
```

---

## Notas Finais

1. **O domínio clínico é rico e deve ser preservado fielmente** — o decision
   engine é o coração do sistema.

2. **A interface Matrix desaparece completamente** — Forms HTML + Templates
   Django substituem chat + parsing de templates.

3. **A complexidade se desloca**: do parsing de templates textuais para
   validação de forms Django; do tracking de eventos Matrix para uma
   timeline de auditoria limpa.

4. **O sistema de prompts versionados** é essencial e deve ser mantido.

5. **O prior case lookup** é uma regra de negócio que precisa ser preservada.

6. **A semântica de cleanup** precisa ser redefinida para o contexto web
   (LGPD, retenção de dados).
