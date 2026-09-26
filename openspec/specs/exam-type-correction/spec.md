# exam-type-correction Specification

## Purpose
TBD - created by archiving change introduce-colonoscopy-exam-workflow. Update Purpose after archive.

## Requirements

### Requirement: Divergência pode ser corrigida antes da fila médica

O NIR MUST corrigir a seleção declarada do mesmo caso para qualquer singleton canônico ou EDA + Colonoscopia quando o caso estiver em revisão por mismatch, combinado incompleto, conjunto incompatível ou unknown, antes de qualquer decisão médica e respeitando somente as flags preexistentes aplicáveis.

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

### Requirement: Reprocessamento preserva fontes e invalida derivados

Correção MUST preservar documentos e texto, limpar detecção/recomendações derivadas e enfileirar uma única nova análise sem reextrair PDF.

#### Scenario: Correção válida

- **GIVEN** caso manual com artefatos v2 e procedimentos detectados
- **WHEN** declaração é corrigida
- **THEN** PDF, anexos, texto, ocorrência e eventos são preservados
- **AND** estados de detecção, `structured_data`, resumo, recomendações e sinais derivados são invalidados
- **AND** uma única execução LLM é agendada.

### Requirement: Correção é append-only e concorrência é segura

O sistema MUST serializar correção e registrar conjunto anterior/novo sem texto clínico integral.

#### Scenario: Worker ou lease incompatível

- **GIVEN** worker/reserva incompatível
- **WHEN** NIR tenta corrigir
- **THEN** operação falha sem atualização parcial
- **AND** nenhuma segunda análise é enfileirada.

### Requirement: Reenvio corrigido pode escolher tipo diferente

Novo caso corrigido MUST aceitar qualquer singleton canônico ou EDA + Colonoscopia sem herdar procedimentos do original e respeitando somente as flags preexistentes de novos intakes.

#### Scenario: EDA original reenviada como CPRE

- **GIVEN** NIR inicia reenvio corrigido de EDA e a flag de CPRE está ativa
- **WHEN** escolhe CPRE e envia novo PDF
- **THEN** o novo caso possui somente CPRE declarada
- **AND** o original permanece inalterado.

#### Scenario: EDA original reenviada como Retossigmoidoscopia + Argônio

- **GIVEN** NIR inicia reenvio corrigido de EDA
- **WHEN** escolhe Retossigmoidoscopia + Argônio e envia novo PDF
- **THEN** o novo caso possui somente `rectosigmoidoscopy_argon` declarada
- **AND** o original permanece inalterado.

#### Scenario: EDA original reenviada como combinado

- **GIVEN** NIR inicia reenvio corrigido de EDA e Colonoscopia está habilitada
- **WHEN** escolhe EDA + Colonoscopia e envia novo PDF
- **THEN** o novo caso possui duas rows declaradas
- **AND** o original permanece inalterado.

#### Scenario: Alias enviado como valor

- **GIVEN** o POST de reenvio contém `GTT` em vez de `eda_gastrostomy`
- **WHEN** backend valida
- **THEN** nenhum novo caso é criado
- **AND** a interface informa seleção inválida.

### Requirement: Upgrade automático não requer correção NIR

Single→combined confirmado MUST seguir ao médico e apenas informar o NIR.

#### Scenario: Upgrade visível

- **GIVEN** NIR declarou EDA e análise detectou ambos
- **WHEN** NIR consulta acompanhamento
- **THEN** vê declaração EDA e análise EDA + Colonoscopia
- **AND** não há CTA obrigatório de correção/ACK para o caso prosseguir.

### Requirement: Resposta final compara as três dimensões

O resultado ao NIR MUST listar declarado, detectado, autorizado e razões por procedimento para as dez identidades suportadas, preservando uma única linha semântica por pacote e duas decisões somente para EDA + Colonoscopia.

#### Scenario: Procedimento especializado incluído pelo médico

- **GIVEN** EDA foi detectada e o médico a substituiu por CPRE
- **WHEN** NIR recebe o resultado
- **THEN** a resposta mostra EDA como detectada/negada e CPRE como incluída/autorizada
- **AND** a justificativa médica é explícita.

#### Scenario: Negativa de Ecoendoscopia

- **GIVEN** Ecoendoscopia foi declarada/detectada e negada pelo médico
- **WHEN** a resposta final é exibida
- **THEN** declaração, detecção, negativa e motivo próprio permanecem visíveis.

#### Scenario: Pacote incluído pelo médico

- **GIVEN** EDA foi detectada e o médico a substituiu por EDA + Cápsula
- **WHEN** NIR recebe o resultado
- **THEN** a resposta mostra EDA como detectada/negada e EDA + Cápsula como incluída/autorizada
- **AND** a justificativa médica é explícita.

#### Scenario: Negativa de Retossigmoidoscopia

- **GIVEN** Retossigmoidoscopia foi declarada/detectada e negada pelo médico
- **WHEN** a resposta final é exibida
- **THEN** declaração, detecção, negativa e motivo próprio permanecem visíveis.

#### Scenario: Aprovação parcial

- **GIVEN** EDA + Colonoscopia detectada foi autorizada somente para EDA
- **WHEN** a resposta final é exibida
- **THEN** EDA aparece autorizada
- **AND** Colonoscopia aparece negada com motivo.

#### Scenario: Procedimento incluído pelo médico

- **GIVEN** somente EDA foi detectada e o médico incluiu Colonoscopia
- **WHEN** NIR recebe o resultado
- **THEN** a inclusão de Colonoscopia e sua justificativa são explícitas.

### Requirement: Correção especializada SHALL reprocessar com contrato atual sem reextrair anexos

A correção para qualquer identidade canônica SHALL preservar PDF principal, anexos e texto extraído, invalidar derivados e executar uma única análise com o contrato gravável 4.0. Anexos SHALL permanecer fora da sugestão automática.

#### Scenario: Caso 2.0 aberto corrigido para CPRE

- **GIVEN** caso histórico aberto possui artefato 2.0 e está elegível à correção
- **WHEN** NIR corrige a declaração para CPRE
- **THEN** o mesmo caso é reprocessado em 4.0 usando o texto do relatório principal
- **AND** nenhum anexo é enviado à análise automática
- **AND** o JSON anterior não é reescrito.

#### Scenario: Caso 3.0 aberto corrigido para EDA + Dilatação

- **GIVEN** caso histórico aberto possui artefato 3.0 e está elegível à correção
- **WHEN** NIR corrige a declaração para EDA + Dilatação
- **THEN** o mesmo caso é reprocessado em 4.0 usando o texto do relatório principal
- **AND** nenhum anexo é enviado à análise automática
- **AND** o JSON anterior não é reescrito.

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
