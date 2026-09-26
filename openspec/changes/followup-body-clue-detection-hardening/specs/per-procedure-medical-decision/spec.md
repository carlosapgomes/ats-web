# per-procedure-medical-decision Delta

## Purpose

Registrar a proposta pós-rc de visibilidade completa das reduções de
precedência ao médico (metadado `procedure_precedence_rules` introduzido em
`detect-report-body-procedure-clues`). Item condicional — executar somente
sob o gatilho registrado no `tasks.md` deste change.

## ADDED Requirements

### Requirement: Médico é informado de cada redução de precedência aplicada

Quando mais de uma redução de precedência se aplica ao conjunto detectado (ex.: variação sobre a base E família absorvendo o guarda-chuva do Motivo), a superfície de decisão médica MUST informar cada redução aplicada a partir de `procedure_precedence_rules`, com copy própria por regra, em vez de exibir somente a regra mais significativa. Os avisos MUST permanecer informativos e não bloqueantes.

#### Scenario: Cenário combinado mostra ambas as reduções

- **GIVEN** caso cujo conjunto detectado passou por supressão de variação sobre a base e por absorção do guarda-chuva do Motivo pela regra de família
- **WHEN** o médico abre a superfície de decisão
- **THEN** ambos os avisos são exibidos, um por redução aplicada, com copy própria de cada regra
- **AND** nenhum aviso altera policy, formulário, validação ou FSM.

#### Scenario: Regra única permanece como hoje

- **GIVEN** caso com exatamente uma redução de precedência aplicada
- **WHEN** o médico abre a superfície de decisão
- **THEN** o aviso exibido é idêntico ao comportamento atual (compatibilidade).
