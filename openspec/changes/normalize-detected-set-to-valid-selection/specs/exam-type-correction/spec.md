# exam-type-correction Delta

## Purpose

Tornar a correção NIR capaz de resolver revisões por conflito de item
estruturado: quando há evidência textual atual e a correção é exatamente a
seleção válida mais completa que cobre a detecção (ADR-0011), o caso
prossegue em vez de reentrar na mesma revisão; coincidências sem evidência
atual reentram.

## MODIFIED Requirements

### Requirement: Divergência pode ser corrigida antes da fila médica

O NIR MUST corrigir a seleção declarada do mesmo caso para qualquer singleton canônico ou EDA + Colonoscopia quando o caso estiver em revisão por mismatch, combinado incompleto, conjunto incompatível, conflito de item estruturado ou unknown, antes de qualquer decisão médica e respeitando somente as flags preexistentes aplicáveis. Quando a revisão tiver reason `conflicting_procedure_evidence` (ou conjunto incompatível coberto por seleção válida), houver ao menos uma ocorrência textual atual e a correção for exatamente a seleção válida mais completa que cobre o conjunto detectado exibido no card, o reprocessamento MUST prosseguir com a declaração corrigida até a fila médica correspondente, sem reentrar na mesma revisão pelo mesmo conflito, preservando a união bruta no evento de auditoria.

#### Scenario: EDA declarada mas Ecoendoscopia detectada

- **GIVEN** o caso está em revisão, sem decisão médica, e a flag de Ecoendoscopia está ativa
- **WHEN** NIR corrige a declaração para Ecoendoscopia
- **THEN** o mesmo UUID é reprocessado sob o contrato gravável 4.0
- **AND** declaração e detecção anteriores permanecem auditáveis.

#### Scenario: EDA declarada mas EDA + GTT detectada

- **GIVEN** o caso está em revisão e sem decisão médica
- **WHEN** NIR corrige a declaração para EDA + GTT
- **THEN** o mesmo UUID é reprocessado sob o contrato gravável 4.0
- **AND** declaração e detecção anteriores permanecem auditáveis.

#### Scenario: Correção de conflito para a seleção mais completa com evidência atual prossegue

- **GIVEN** o caso está em revisão por `conflicting_procedure_evidence`
- **AND** existe ocorrência textual atual (ex.: Motivo com EDA) e o corpo traz a variação apenas não-atual
- **AND** o card exibe como detectado a seleção válida mais completa que cobre a evidência (ex.: `EDA + Dilatação`)
- **WHEN** NIR corrige a declaração para exatamente essa seleção
- **THEN** o reprocessamento prossegue com a declaração até a fila médica
- **AND** não é emitida nova revisão pelo mesmo conflito
- **AND** a união bruta da detecção permanece auditável no evento.

#### Scenario: Correção para outra seleção reentra na revisão

- **GIVEN** o caso está em revisão por `conflicting_procedure_evidence`
- **AND** a seleção mais completa exibida é `EDA + Dilatação`
- **WHEN** NIR corrige a declaração para uma seleção válida diferente
- **THEN** o reprocessamento retorna à revisão NIR com o mesmo reason
- **AND** o card continua exibindo a seleção mais completa como detectado.

#### Scenario: Coincidência negada ou histórica sem evidência atual não é resolvida por igualdade

- **GIVEN** o texto nega ou apenas historiza o termo do item estruturado (nenhuma ocorrência atual)
- **AND** a declaração vigente coincide com esse tipo
- **WHEN** o NIR reenvia qualquer seleção
- **THEN** a revisão por `conflicting_procedure_evidence` persiste enquanto a coincidência for a única base
- **AND** o caso não prossegue ao médico somente pela coincidência.

#### Scenario: Caso já na fila médica

- **GIVEN** caso em `WAIT_DOCTOR` ou posterior
- **WHEN** NIR tenta mudar declaração
- **THEN** backend rejeita
- **AND** procedimentos e artefatos permanecem íntegros.

#### Scenario: Combinado declarado mas somente EDA detectada

- **GIVEN** o caso está em revisão e não possui decisão médica
- **WHEN** NIR corrige declaração para EDA
- **THEN** o mesmo UUID é reprocessado
- **AND** Colonoscopia deixa de estar declarada sem apagar eventos anteriores.

#### Scenario: Correção para conjunto proibido

- **GIVEN** o request manipulado tenta declarar uma variação junto de Colonoscopia
- **WHEN** backend valida
- **THEN** a operação é rejeitada antes de alterar rows
- **AND** nenhuma nova análise é enfileirada.
