<!-- markdownlint-disable MD013 -->

# Capability Spec: Intercorrência pós-aceitação

## Purpose

Definir o comportamento auditável para mudanças posteriores ao aceite médico, distinguindo ação sobre agenda de simples ciência operacional do CHD e garantindo persistência de notices até ACK.

## Requirements

### Requirement R1 — Notice operacional inicial durável

O sistema DEVE manter na fila e no badge do CHD todo notice operacional inicial sem ACK, independentemente do dia em que foi criado.

#### Scenario: Notice atravessa a virada do dia

- **GIVEN** caso aceito em fluxo sem agendamento com notice criado no dia anterior
- **AND** nenhum ACK compatível foi registrado
- **WHEN** o CHD abre a fila no dia atual
- **THEN** o card permanece visível
- **AND** o badge inclui esse card.

#### Scenario: ACK remove notice durável

- **GIVEN** notice antigo ainda pendente
- **WHEN** CHD confirma ciência
- **THEN** o ACK auditável é criado uma única vez
- **AND** o card deixa a fila ativa
- **AND** aparece no histórico de confirmações do dia do ACK.

### Requirement R2 — Compatibilidade histórica

O sistema DEVE preservar leitura, labels e projeções dos eventos legados `POST_SCHEDULE_ISSUE_*`, `IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE` e `SCHEDULER_IMMEDIATE_ACK`.

`POST_SCHEDULE_ISSUE_OPENED` e `POST_SCHEDULE_ISSUE_RESPONDED` mantêm labels, timeline e projeção sistêmica. `POST_SCHEDULE_ISSUE_ACKNOWLEDGED` preserva label/dot na timeline mas é **omitido da thread** (payload legado vazio). `POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED` é projetado na thread (possui `cycle_id`, `context`, `admission_flow`). Nenhum evento legado é apagado, renomeado ou reescrito. Ciclos novos geram somente `POST_ACCEPTANCE_ISSUE_*`.

#### Scenario: Caso histórico continua legível

- **GIVEN** caso com eventos legados
- **WHEN** NIR, CHD ou auditor abre detalhe/timeline/thread
- **THEN** os eventos continuam com labels compreensíveis
- **AND** nenhum evento append-only é reescrito ou apagado.

### Requirement R3 — Contexto e ciclo explícitos

Cada nova intercorrência pós-aceitação DEVE possuir um `cycle_id` e contexto `scheduled` ou `operational_notice` no ciclo ativo e nos eventos correspondentes.

#### Scenario: Novo ciclo depois de ACK anterior

- **GIVEN** caso com ciclo anterior já confirmado
- **WHEN** NIR abre nova intercorrência elegível
- **THEN** um novo `cycle_id` é criado
- **AND** ACKs de ciclos anteriores não ocultam a pendência nova.

### Requirement R4 — Fluxo agendado preservado

Caso aceito, `CLEANED`, com fluxo `scheduled` e agendamento confirmado DEVE continuar permitindo cancelar, reagendar, manter ou negar solicitação com lock CHD e retorno ao NIR.

#### Scenario: Reagendamento pós-aceitação

- **GIVEN** caso agendado elegível
- **WHEN** NIR abre intercorrência e CHD reagenda
- **THEN** o caso percorre `CLEANED → WAIT_APPT → WAIT_R1_CLEANUP_THUMBS`
- **AND** os novos dados da agenda são persistidos
- **AND** evento registra snapshots anterior e novo
- **AND** NIR confirma ciência e o caso volta a `CLEANED`.

### Requirement R5 — Elegibilidade sem agenda

Caso `CLEANED`, aceito e com fluxo `immediate`, `pre_icu`, `ward_icu_backup` ou `pediatric_em` DEVE permitir intercorrência pós-aceitação sem exigir `appointment_status="confirmed"`.

#### Scenario: Paciente evadiu-se

- **GIVEN** caso aceito em `pre_icu` e concluído
- **WHEN** NIR registra motivo “paciente evadiu-se”
- **THEN** uma pendência de ciência é criada para o CHD
- **AND** o caso permanece `CLEANED`.

#### Scenario: Paciente aceito por unidade mais próxima

- **GIVEN** caso aceito em qualquer fluxo sem agenda e concluído
- **WHEN** NIR registra aceite/transferência para unidade mais próxima
- **THEN** o motivo estruturado e a mensagem ficam auditados
- **AND** CHD recebe a pendência.

### Requirement R6 — Ciência sem ação de agenda

Em contexto `operational_notice`, CHD DEVE apenas confirmar ciência e o sistema NÃO DEVE alterar estado FSM nem campos de agendamento.

#### Scenario: CHD confirma ciência

- **GIVEN** intercorrência operacional aberta
- **WHEN** CHD confirma ciência
- **THEN** ACK com ator, horário, contexto, fluxo e `cycle_id` é registrado atomicamente
- **AND** o ciclo ativo é limpo para permitir ciclo futuro
- **AND** `Case.status` permanece `CLEANED`
- **AND** todos os campos `appointment_*` permanecem idênticos.

### Requirement R7 — Sem duplicidade visual

Uma intercorrência operacional ativa DEVE substituir o notice inicial pendente do mesmo caso na fila do CHD.

#### Scenario: Notice inicial ainda sem ACK

- **GIVEN** caso possui notice inicial não confirmado
- **AND** NIR abre intercorrência operacional
- **WHEN** CHD abre a fila
- **THEN** vê exatamente um card acionável para o caso
- **AND** o card mostra a intercorrência mais recente.

### Requirement R8 — Uma intercorrência ativa por caso

O sistema DEVE impedir atomicamente uma segunda abertura enquanto existir ciclo `opened` ou `responded`.

#### Scenario: Duas aberturas concorrentes

- **GIVEN** caso elegível sem intercorrência ativa
- **WHEN** duas requisições tentam abrir ciclos concorrentes
- **THEN** apenas uma persiste
- **AND** a outra recebe erro de domínio compreensível.

### Requirement R9 — Permissões preservadas

Somente papel ativo `nir` DEVE abrir intercorrência e somente papel ativo `scheduler` DEVE responder/confirmar ciência.

#### Scenario: Papel indevido tenta operar

- **GIVEN** usuário autenticado com outro papel ativo
- **WHEN** acessa ou envia endpoint de intercorrência
- **THEN** a operação é bloqueada
- **AND** nenhum campo/evento é alterado.

### Requirement R10 — Encerramento administrativo não substitui intercorrência

O sistema NÃO DEVE reutilizar `CASE_ADMINISTRATIVELY_CLOSED` como comunicação de mudança pós-aceitação.

#### Scenario: Caso retirado por evasão

- **GIVEN** caso aceito elegível
- **WHEN** NIR informa evasão pelo fluxo novo
- **THEN** evento de intercorrência pós-aceitação é criado
- **AND** nenhuma métrica/classificação de encerramento administrativo é produzida.
