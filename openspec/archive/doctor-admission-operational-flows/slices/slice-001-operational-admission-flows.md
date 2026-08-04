# Slice 001: Novos fluxos de admissão com ciência operacional CHD

## Objetivo

Implementar, em um único slice vertical, o novo comportamento de aceite médico:

- suporte final do CHD apenas `Nenhum` ou `Anestesista`;
- cinco fluxos de admissão;
- somente `Agendamento` abre fila de agendamento;
- demais fluxos geram ciência operacional CHD, resultado final NIR e métricas separadas.

## Contexto zero para implementador

O sistema é um monolito Django SSR. A página médica fica em `templates/doctor/decision.html`, com validação em `apps/doctor/forms.py` e submit em `apps/doctor/views.py::doctor_submit`.

Hoje:

- `doctor_support_flag` aceita `none`, `anesthesist`, `anesthesist_icu`;
- `doctor_admission_flow` aceita `scheduled`, `immediate`;
- `accept + scheduled` vai para `WAIT_APPT`;
- `accept + immediate` não agenda, registra notice para CHD e manda resultado ao NIR.

Novo comportamento:

```text
Suporte Necessário:
- none → Nenhum
- anesthesist → Anestesista

Fluxo de Admissão:
- scheduled        → Agendamento
- immediate        → Vinda Imediata
- pre_icu          → Vinda prévia para UTI
- ward_icu_backup  → Vinda para enfermaria (para retaguarda em UTI)
- pediatric_em     → Compartilhar com EM pediátrica
```

Apenas `scheduled` abre agendamento. Todos os outros fluxos são ciência operacional para CHD e ação do NIR.

## Arquivos prováveis

Ideal manter o slice enxuto. Arquivos esperados:

- `apps/doctor/forms.py`
- `templates/doctor/decision.html`
- `static/js/decision.js`
- `apps/doctor/views.py`
- `apps/scheduler/views.py`
- `templates/scheduler/_queue_content.html`
- `apps/accounts/context_processors.py`
- `apps/intake/views.py`
- `templates/intake/case_detail.html`
- `templates/intake/closed_case_detail.html`
- `apps/dashboard/views.py`
- `templates/dashboard/index.html`
- testes em `apps/doctor/tests/`, `apps/scheduler/tests/`, `apps/intake/tests/`, `apps/dashboard/tests/`, `apps/accounts/tests/`

Se a implementação precisar tocar muito mais arquivos, registre justificativa no relatório do slice.

## Requisitos funcionais

### R1. Form médico

- Remover `Anestesista + UTI` do select de suporte.
- Remover `anesthesist_icu` das choices válidas de `DoctorDecisionForm.support_flag`.
- Adicionar os três novos fluxos no select e nas choices de `admission_flow`.
- Manter `support_flag` e `admission_flow` obrigatórios apenas quando `decision=accept`.

### R2. Submit médico

- `accept + scheduled` preserva comportamento atual: `WAIT_APPT`.
- `accept + immediate/pre_icu/ward_icu_backup/pediatric_em`:
  - persiste decisão;
  - registra notice operacional;
  - posta resultado final;
  - não cria solicitação de agendamento;
  - não entra em `WAIT_APPT`.

### R3. Eventos

- Criar eventos novos para daqui em diante:
  - `ADMISSION_FLOW_OPERATIONAL_NOTICE`;
  - `SCHEDULER_OPERATIONAL_NOTICE_ACK`.
- Consultas devem reconhecer eventos legados:
  - `IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE`;
  - `SCHEDULER_IMMEDIATE_ACK`.
- Adicionar labels/dots em maps de timeline.

### R4. CHD fila ativa

- Mostrar cards de ciência para todos os fluxos não agendamento.
- Cada card deve ter mensagem específica por fluxo.
- Botão único: `Confirmar ciência`.
- Ack remove o card ativo.

### R5. CHD histórico de ciência

- Adicionar histórico do dia local atual para papel `scheduler`.
- Escopo: equipe CHD, não apenas usuário logado.
- Mostrar quem confirmou ciência e quando.
- Multi-dia, busca e paginação ficam fora do slice.

### R6. NIR

- Todos os fluxos não agendamento devem ser tratados como terminais sem etapa de agendamento.
- Mostrar badge/body específico:
  - immediate mantém texto atual;
  - pre_icu orienta reserva de UTI;
  - ward_icu_backup orienta leito/enfermaria e retaguarda UTI;
  - pediatric_em orienta acionar coordenador da EM Pediátrica.

### R7. Dashboard

- Métrica `Fluxo de Admissão` deve mostrar os cinco fluxos separados.
- Novos fluxos sem agendamento não podem aparecer como “Aguardando Agendamento”.

### R8. Modal JS

- Para `scheduled`: informar encaminhamento para CHD/agendamento.
- Para fluxos sem agendamento: informar ciência operacional CHD e seguimento pelo NIR.

## TDD recomendado

### RED

Adicionar/ajustar testes antes de alterar implementação:

1. `DoctorDecisionForm` rejeita `support_flag=anesthesist_icu`.
2. Página médica não contém opção `Anestesista + UTI` no select de suporte.
3. Página/form aceita novos fluxos.
4. POST `accept + pre_icu` vai para `WAIT_R1_CLEANUP_THUMBS`, cria notice operacional e não cria `SCHEDULER_REQUEST_POSTED`.
5. CHD vê card de ciência para `pre_icu`, confirma e card some.
6. Histórico CHD mostra ator da ciência.
7. NIR vê texto específico de `pre_icu`.
8. Dashboard conta `pre_icu` separadamente.

Depois replicar cobertura suficiente para `ward_icu_backup` e `pediatric_em` sem duplicação excessiva.

### GREEN

Implementar o mínimo para passar, evitando refactor amplo.

### REFACTOR

- Se houver muita duplicação de maps, extrair helpers pequenos e estáveis.
- Não criar abstrações genéricas grandes.
- Não alterar pipeline LLM.
- Não migrar dados históricos.

## Critérios de sucesso do slice

- [ ] Médico consegue finalizar aceite para todos os fluxos novos.
- [ ] CHD só agenda casos `scheduled`.
- [ ] CHD recebe e confirma ciência para todos os fluxos não agendamento.
- [ ] Histórico CHD mostra ator/data da ciência.
- [ ] NIR vê mensagem específica e caso fica aguardando confirmação.
- [ ] Dashboard exibe cinco fluxos separados.
- [ ] Casos históricos com `anesthesist_icu` continuam exibindo label.
- [ ] Eventos legados de vinda imediata continuam compatíveis.

## Gates de autoavaliação

Antes de finalizar:

1. Algum fluxo não agendamento entra em `WAIT_APPT` por engano?
2. O formulário backend rejeita `anesthesist_icu` mesmo se alguém postar manualmente?
3. As queries de CHD excluem corretamente notices já confirmados?
4. O histórico mostra o ator do ack, não apenas que houve ack?
5. NIR e dashboard usam a mesma definição de “fluxo sem agendamento”?
6. O modal de confirmação médica não promete agendamento para fluxo sem agendamento?
7. Dados/eventos legados de `immediate` continuam funcionando?

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/doctor-admission-operational-flows/design.md first.
Implement ONLY Slice 001 from openspec/changes/doctor-admission-operational-flows/slices/slice-001-operational-admission-flows.md.
Use TDD: add failing tests before implementation. Keep the slice vertical and lean.
Do not change the LLM pipeline or migrate historical data. Do not create DB migrations unless a hard blocker is discovered.
Support final choices must be only none/anesthesist, but historical anesthesist_icu display must remain compatible.
Admission flows are scheduled, immediate, pre_icu, ward_icu_backup and pediatric_em. Only scheduled opens WAIT_APPT. All other flows generate CHD operational awareness and NIR final result.
Add CHD same-day operational-awareness history showing who acknowledged.
Update NIR result messages and dashboard admission-flow metrics with separate counts.
Run ruff check, ruff format --check, mypy and pytest. Generate a temporary markdown report with before/after snippets, commit and push. Reply with REPORT_PATH and stop for planner review.
```
