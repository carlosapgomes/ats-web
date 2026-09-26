# exam-type-correction Delta

## Purpose

Registrar o polimento proposto pós-rc para a exibição de pistas no card de
correção (entregue em `detect-report-body-procedure-clues`): rótulo de seção
traduzido e copy de motivo de conflito estável. Item condicional — executar
somente sob o gatilho registrado no `tasks.md` deste change.

## ADDED Requirements

### Requirement: Seção das pistas exibe rótulo traduzido

Quando as pistas do corpo exibem a seção de origem, o card de correção MUST apresentar rótulo traduzido legível (ex.: "Justificativa da Transferência") em vez do identificador canônico (`justificativa_da_transferencia`), sem alterar o valor persistido no payload nem o contrato de exibição das demais informações da pista.

#### Scenario: Pista com seção traduzida

- **GIVEN** payload de revisão com `detected_body_clues` contendo pista com `section` igual a `justificativa_da_transferencia`
- **WHEN** o card de correção renderiza
- **THEN** a pista exibe "Justificativa da Transferência" como rótulo da seção
- **AND** o valor do campo `section` no payload permanece o identificador canônico.

### Requirement: Copy de motivo de conflito é estável

O `reason_text` exibido para `conflicting_procedure_evidence` MUST ser coberto por teste automatizado que pine o texto apresentado, garantindo que edições acidentais de copy sejam detectadas, da mesma forma que o `reason_code` já é.

#### Scenario: Edição de copy quebra o teste

- **GIVEN** o texto de motivo registrado para `conflicting_procedure_evidence`
- **WHEN** o teste de contrato executa
- **THEN** o `reason_text` renderizado corresponde ao texto pinado
- **AND** qualquer alteração intencional de copy exige atualizar o teste junto.
