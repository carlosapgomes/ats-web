# Revisão Inicial da Migração Legado Matrix para Django Web

Data: 2026-05-18

## Contexto

Este documento registra a primeira exploração comparativa entre:

- Projeto legado: `/home/carlos/projects/augmented-triage-system/`
- Projeto atual Django: `/home/carlos/projects/ats-web/`

Objetivo: manter memória rastreável no Git sobre pontos que precisam ser investigados antes de corrigir equívocos da implementação inicial da migração.

## Entendimento Consolidado

### Projeto legado: `augmented-triage-system`

Arquitetura original:

- Entrada e interação humana via Matrix rooms:
  - Room 1: NIR envia PDF e recebe resultado final.
  - Room 2: médico recebe resumo/sugestão e responde decisão.
  - Room 3: agendador confirma/nega agendamento ou recebe aviso de vinda imediata.
  - Room 4/dashboard: supervisão.
- Backend com:
  - `bot-matrix`
  - `bot-api`
  - `worker`
  - PostgreSQL
  - SQLAlchemy/Alembic
  - filas/jobs próprios.
- Forte separação arquitetural:
  - adapters → application services → domain → infrastructure ports.
- Máquina de estado central em `CaseStatus`.
- Auditoria append-only em `case_events`.
- `case_messages` existia para mapear eventos Matrix e permitir cleanup/redaction.
- Cleanup original era disparado por reação 👍 na resposta final da Room 1.
- O projeto legado já tinha movimento posterior para Django como superfície humana/admin, mas Matrix ainda era runtime de backend.

### Projeto atual: `ats-web`

Reimplementação Django SSR/PWA:

- Interface Matrix foi removida.
- Rooms viraram filas/páginas web por papel:
  - `intake` / NIR
  - `doctor`
  - `scheduler`
  - `dashboard`
  - `admin_ui`
- Stack:
  - Django 5.2
  - PostgreSQL
  - django-fsm
  - django-q2
  - Bootstrap + vanilla JS.
- Apps principais:
  - `accounts`
  - `cases`
  - `llm`
  - `pipeline`
  - `intake`
  - `doctor`
  - `scheduler`
  - `dashboard`
  - `admin_ui`
- Fluxo pretendido:
  - upload PDF → pipeline LLM → decisão médica → agendamento/vinda imediata → resultado NIR → confirmação → cleanup.
- `CaseEvent` substitui o tracking Matrix como trilha de auditoria principal.
- `case_messages` não existe no Django atual.

## Arquivos e Artefatos Consultados

### Projeto atual

- `PROJECT_CONTEXT.md`
- `ROADMAP.md`
- `docs/DOMAIN_ANALYSIS.md`
- `openspec/archive/*/design.md` dos principais changes
- `apps/cases/models.py`
- `apps/pipeline/orchestrator.py`
- `apps/intake/views.py`
- `apps/doctor/views.py`
- `apps/scheduler/views.py`
- `apps/accounts/views.py`
- `apps/accounts/middleware.py`

### Projeto legado

- `PROJECT_CONTEXT.md`
- `docs/architecture.md`
- `docs/decision-engine-and-rulebook.md`
- `src/triage_automation/domain/case_status.py`
- `src/triage_automation/application/services/handle_doctor_decision_service.py`
- `src/triage_automation/application/services/post_immediate_admission_flow_service.py`
- `src/triage_automation/application/services/nir_final_acknowledgment_service.py`

## Pontos para Investigação

### 1. Documentação atual possivelmente defasada

`PROJECT_CONTEXT.md` diz que a fase atual é “Fase 2b concluída / próxima Fase 3”.

`ROADMAP.md` mostra fases até PWA/polish concluídas, com 541 testes.

Necessário reconciliar os documentos antes de planejar novas mudanças.

### 2. Contagem dos estados

A documentação fala em “17 estados preservados”, mas a enumeração atual/listada contém 18 estados se contar `NEW` e `CLEANED`.

Necessário confirmar se a expressão “17 estados” veio do legado excluindo algum estado terminal/inicial ou se é erro documental.

### 3. Fluxo `immediate` possivelmente tratado como agendamento normal

Contrato documentado:

- `accept + scheduled`: médico aceita → agendador agenda → resultado NIR.
- `accept + immediate`: médico aceita → agendador é notificado apenas informativamente → resultado NIR, sem ação do agendador.

Indício no código atual:

- `apps/doctor/views.py::doctor_submit()` manda todo `accept` para `R3_POST_REQUEST → WAIT_APPT`, independentemente de `doctor_admission_flow`.

Investigar se há outro ponto compensando isso. Caso não haja, corrigir fluxo.

### 4. Scope gate non-EDA/unknown possivelmente indo para médico

Contrato documentado:

- Casos `non_eda` ou `unknown_exam_type` devem ir para revisão manual/resultado NIR, sem passar por decisão médica.

Indício no código atual:

- `apps/cases/models.py::scope_gate_bypass()` transiciona `LLM_STRUCT → WAIT_DOCTOR`.
- `apps/pipeline/orchestrator.py` chama esse bypass após `EDA_SCOPE_GATED_MANUAL_REVIEW`.

Investigar o comportamento esperado na UI atual e nos testes.

### 5. Controle de papel inconsistente em doctor/scheduler

Observação:

- `intake` usa `@role_required("nir")`.
- `dashboard/admin_ui` têm decorators próprios.
- `doctor/views.py` e `scheduler/views.py` aparecem apenas com `@login_required`.

Risco:

- usuário autenticado com papel ativo inadequado pode acessar filas/telas de médico ou agendador.

Investigar cobertura de testes e corrigir autorização por papel ativo se confirmado.

### 6. Resultado final no detalhe NIR pode estar classificando errado

Indício em `apps/intake/views.py::case_detail()`:

- qualquer caso em `WAIT_R1_CLEANUP_THUMBS` ou `CLEANED` cai primeiro como `accepted_scheduled`.

Risco:

- resultados reais de `doctor_denied`, `appt_denied` ou `failed` podem ser exibidos incorretamente após a transição para `WAIT_R1_CLEANUP_THUMBS`/`CLEANED`.

Investigar testes e comportamento real da tela.

### 7. Auditoria/eventos podem ter perdas por `_pending_event` único

O modelo `Case` usa `_pending_event` para criar `CaseEvent` via signal após `save()`.

Riscos a investigar:

- chamadas a `_record_event()` sem `save()` posterior imediato;
- transições ou eventos subsequentes sobrescrevendo `_pending_event` antes de persistir;
- eventos duplicados ou ausentes em fluxos pipeline/doctor/scheduler.

### 8. Cleanup atual é síncrono na view

Contrato legado/web posterior:

- confirmação final deveria ser checkpoint humano canônico;
- cleanup com semântica idempotente/CAS + job.

Indício no código atual:

- `apps/intake/views.py::confirm_receipt()` executa `cleanup_triggered()` e `cleanup_completed()` diretamente na request.

Pode ser simplificação aceitável do MVP, mas difere do contrato robusto do legado. Investigar impacto e prioridade.

## Leitura Geral

O projeto atual já implementa uma vertical completa em Django, mas algumas decisões da migração parecem ter simplificado ou distorcido partes importantes do workflow original, principalmente:

- roteamento por estado;
- `immediate` vs `scheduled`;
- scope gate;
- autorização por papel ativo;
- semântica do resultado final;
- fidelidade da auditoria.

## Próximo Passo Sugerido

Antes de implementar correções, transformar cada ponto confirmado em um slice pequeno com:

- teste de caracterização ou teste RED;
- mudança mínima;
- atualização de documentação/spec quando necessário;
- validação focada;
- relatório de implementação.
