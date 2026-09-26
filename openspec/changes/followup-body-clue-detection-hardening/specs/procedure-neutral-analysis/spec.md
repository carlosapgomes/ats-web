# procedure-neutral-analysis Delta

## Purpose

Registrar o hardening proposto pós-rc para a detecção por seção entregue em
`detect-report-body-procedure-clues`: terminadores de seção ancorados
explicitamente, eliminando o falso negativo de span truncado por palavra
narrativa. Item condicional — executar somente sob o gatilho registrado no
`tasks.md` deste change.

## ADDED Requirements

### Requirement: Terminadores de seção exigem ancoragem explícita

Os terminadores que delimitam a seção `Justificativa da Transferência` (e o campo `Motivo da Solicitação`) MUST casar apenas como rótulo ancorado — com `:` ou em início de linha — e MUST NOT casar como substring no meio de narrativa clínica, de modo que palavras como "encaminhamento" ou "complemento" dentro da Justificativa não truncam o span. A direção de falha do endurecimento MUST permanecer fail-closed (falso positivo gera revisão NIR, nunca prosseguimento silencioso).

#### Scenario: Palavra narrativa não trunca a seção

- **GIVEN** Justificativa contendo no meio da narrativa uma palavra que é rótulo terminador quando ancorada (ex.: "encaminhamento" sem dois-pontos, no meio de uma frase)
- **AND** procedimento da família nomeado após essa palavra
- **WHEN** o detector executa
- **THEN** o span da Justificativa não é truncado pela palavra narrativa
- **AND** a ocorrência do procedimento é promovida a `current_request`.

#### Scenario: Rótulo ancorado continua terminando a seção

- **GIVEN** rótulo terminador legítimo com dois-pontos (ex.: `Complemento da Solicitação:`) ou em início de linha após a Justificativa
- **WHEN** o detector executa
- **THEN** o span da Justificativa termina nesse rótulo
- **AND** ocorrências posteriores não são promovidas pela seção.
