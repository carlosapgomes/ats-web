# exam-type-correction Delta

## Purpose

Simplificar o card de correção conforme decisão do dono no smoke do rc.2
(2026-09-26): sem listagem de pistas; o motivo da revisão informa a origem da
detecção; as pistas permanecem apenas no payload de auditoria.

## REMOVED Requirements

### Requirement: Card de correção exibe pistas detectadas no corpo do relatório

**Reason:** a listagem crua de ocorrências (termos duplicados sob múltiplas
identidades, excerpt reduzido ao termo casado, menções de outras famílias)
confundia mais do que informava. Substituída pelo requisito de motivo com
origem abaixo; o payload `detected_body_clues` permanece para auditoria.

## ADDED Requirements

### Requirement: Motivo da revisão informa a origem da detecção

Quando a reconciliação devolve revisão NIR e o conjunto detectado tem ocorrências de solicitação atual com seção de origem identificada, o `reason_text` exibido no card de correção MUST informar a origem (ex.: "Origem da detecção: Justificativa da Transferência"), usando rótulos traduzidos e estáveis. O card de correção MUST exibir apenas tipo declarado, tipo detectado e motivo da revisão — a listagem de pistas MUST NOT ser renderizada. O payload de revisão (`detected_body_clues`) MUST permanecer disponível para auditoria em `suggested_action`/eventos, sem renderização na UI.

#### Scenario: Mismatch com origem na Justificativa

- **GIVEN** caso em revisão com reason `exam_type_mismatch`
- **AND** ocorrências atuais do conjunto detectado na seção `justificativa_da_transferencia`
- **WHEN** o NIR abre o card de correção
- **THEN** o motivo exibe o texto do reason com o acréscimo da origem "Justificativa da Transferência"
- **AND** nenhuma listagem de pistas é renderizada.

#### Scenario: Sem origem identificada permanece o texto atual

- **GIVEN** caso em revisão sem ocorrências atuais com seção identificada
- **WHEN** o card renderiza
- **THEN** o motivo exibe exatamente o `reason_text` atual, sem sufixo de origem.

#### Scenario: Pistas seguem no payload para auditoria

- **GIVEN** payload de revisão 2.1 com `detected_body_clues`
- **WHEN** o card renderiza
- **THEN** as pistas não aparecem na UI
- **AND** `suggested_action` continua contendo `detected_body_clues` para auditoria/eventos.
