# administrative-closure — delta: rotina diária de casos não avaliados + razão na timeline

## ADDED Requirements

### Requirement: Motivo dedicado para rotina de não avaliados

O catálogo de encerramento administrativo SHALL conter o motivo
`not_evaluated_by_doctor` ("Não avaliado pelo médico — rotina 06:00"),
utilizável tanto pelo caminho manual quanto pela rotina automática.

#### Scenario: Motivo disponível no catálogo

- **WHEN** o catálogo `ADMINISTRATIVE_CLOSURE_REASONS` é consultado
- **THEN** ele contém `not_evaluated_by_doctor` com label em pt-BR.

### Requirement: Razão do encerramento visível na Linha do Tempo

A Linha do Tempo do caso SHALL exibir, no evento `CASE_ADMINISTRATIVELY_CLOSED`,
linhas de detalhe com o motivo (label do catálogo e/ou texto) e o status
anterior, projetadas exclusivamente do `payload` do evento.

#### Scenario: Encerrado pela rotina mostra motivo e origem

- **WHEN** a timeline renderiza um `CASE_ADMINISTRATIVELY_CLOSED` com
  `payload = {reason_code: not_evaluated_by_doctor, reason_text, previous_status: WAIT_DOCTOR}`
- **THEN** as linhas de detalhe contêm o motivo e `WAIT_DOCTOR` (ou seu label).

#### Scenario: Evento histórico sem payload não quebra

- **WHEN** a timeline renderiza um `CASE_ADMINISTRATIVELY_CLOSED` com payload
  vazio ou sem `reason_code`
- **THEN** nenhum erro é levantado (linhas degradadas ou vazias).

### Requirement: Fechamento automático diário de WAIT_DOCTOR sem lock válido

Todo dia às 06:00 America/Bahia, o sistema SHALL encerrar administrativamente
todo caso em `WAIT_DOCTOR` sem reserva (lock) válida, com ator sistema e motivo
`not_evaluated_by_doctor`. Casos com lock válido SHALL ser pulados e reportados.

#### Scenario: Caso parado sem lock é encerrado

- **WHEN** a rotina executa e o caso está em `WAIT_DOCTOR` sem lock válido
- **THEN** o caso vai para `CLEANED` com evento `CASE_ADMINISTRATIVELY_CLOSED`
  (`actor_type="system"`, `previous_status="WAIT_DOCTOR"`) e some das filas
  operacionais, permanecendo na auditoria.

#### Scenario: Lock válido é respeitado

- **WHEN** o caso está em `WAIT_DOCTOR` com lock válido de outro usuário
- **THEN** o caso NÃO é encerrado, o lock permanece intacto e o caso consta
  em `skipped_locked` no relatório.

#### Scenario: Mudança de status durante a varredura não gera erro

- **WHEN** o caso sai de `WAIT_DOCTOR` entre a listagem e o processamento
- **THEN** ele é contado em `skipped_changed`, sem evento e sem exceção.

#### Scenario: Re-execução é idempotente

- **WHEN** a rotina executa duas vezes no mesmo dia
- **THEN** a segunda execução encerra zero casos já encerrados e não duplica
  eventos.
