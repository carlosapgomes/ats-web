# exam-type-correction Delta

## Purpose

Estender a correção de tipo para exibir ao NIR, no momento da seleção do novo
conjunto, as pistas de procedimento detectadas no corpo do relatório, e
habilitar a correção para o novo reason code de conflito de item estruturado.

## ADDED Requirements

### Requirement: Card de correção exibe pistas detectadas no corpo do relatório

Quando o payload de revisão NIR (schema 2.1) contém `detected_body_clues`, o card de correção de tipo MUST exibi-las junto ao seletor do novo conjunto, com rótulo do procedimento, qualificação traduzida, rótulo da seção de origem (quando presente) e excerpt limitado do texto. As pistas MUST restringir-se ao corpo do relatório: ocorrências do campo `Motivo da Solicitação` MUST NOT aparecer como pistas (declarado/detectado já resumem o Motivo). A exibição MUST usar apenas classes de estilo já existentes no projeto e MUST NOT alterar o contrato POST, a elegibilidade existente ou o combobox canônico. Payloads sem `detected_body_clues` (casos legados) MUST renderizar o card exatamente como antes.

#### Scenario: Pistas visíveis no momento da seleção

- **GIVEN** caso em `WAIT_R1_CLEANUP_THUMBS` com `suggested_action` de manual review contendo `detected_body_clues` com uma pista `rectosigmoidoscopy_dilation`, qualificação `current_request`, seção `justificativa_da_transferencia` e excerpt do texto
- **WHEN** o NIR detém o lock e abre o detalhe do caso
- **THEN** o card de correção lista a pista com rótulo do procedimento, qualificação traduzida, seção e excerpt
- **AND** o seletor do novo conjunto permanece o combobox canônico com as mesmas chaves POST.

#### Scenario: Caso legado sem pistas

- **GIVEN** caso em revisão com payload sem `detected_body_clues`
- **WHEN** o detalhe do caso renderiza
- **THEN** o card de correção exibe declarado/detectado/motivo como antes
- **AND** nenhuma seção de pistas aparece.

#### Scenario: Correção elegível por conflito de item estruturado

- **GIVEN** caso em manual review com reason `conflicting_procedure_evidence`
- **WHEN** o NIR abre o detalhe do caso
- **THEN** o card de correção está disponível (reason elegível)
- **AND** o fluxo de correção/reprocessamento é o mesmo dos demais reasons elegíveis.
