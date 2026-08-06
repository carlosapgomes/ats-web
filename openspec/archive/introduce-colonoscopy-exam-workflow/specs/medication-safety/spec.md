# Capability: Segurança medicamentosa pré-procedimento

## ADDED Requirements

### Requirement: Medicamentos descritos são extraídos de forma estruturada

O sistema MUST extrair somente medicamentos explicitamente descritos no relatório e MUST preservar evidência textual para cada item.

#### Scenario: Anticoagulante em uso atual

- **GIVEN** relatório informa uso atual de rivaroxabana
- **WHEN** LLM1 processa o caso
- **THEN** a coleção estruturada contém o medicamento
- **AND** sua classe é `anticoagulant`
- **AND** o status de uso é atual ou indefinido conforme a evidência
- **AND** existe `source_text_hint` não vazio.

#### Scenario: Antiagregante explicitamente suspenso

- **GIVEN** relatório informa clopidogrel suspenso
- **WHEN** LLM1 processa o caso
- **THEN** o item é classificado como `antiplatelet`
- **AND** o status preserva que foi suspenso
- **AND** o sistema não o descreve como uso atual confirmado.

#### Scenario: Nenhum medicamento descrito

- **GIVEN** relatório sem medicamento explícito
- **WHEN** LLM1 processa o caso
- **THEN** a coleção é vazia
- **AND** nenhum medicamento é inferido por doença, idade, exame ou diagnóstico.

### Requirement: Alerta medicamentoso é informativo

O relatório médico MUST destacar anticoagulantes e antiagregantes, mas MUST NOT alterar automaticamente a sugestão ou criar orientação farmacológica.

#### Scenario: Anticoagulante identificado

- **GIVEN** caso com anticoagulante estruturado
- **WHEN** médico abre a avaliação
- **THEN** vê alerta de medicamento relevante
- **AND** vê nome, status e evidência disponível
- **AND** recebe orientação neutra para confirmar manejo peri-procedimento.

#### Scenario: Decisão permanece independente

- **GIVEN** caso com anticoagulante ou antiagregante
- **WHEN** policy e reconciliação são executadas
- **THEN** a presença do medicamento não força `accept` nem `deny`
- **AND** não produz instrução de suspensão, dose ou janela farmacológica.

### Requirement: EDA e colonoscopia compartilham o contrato medicamentoso

A extração e a apresentação MUST ser aplicáveis a todos os tipos suportados.

#### Scenario: Mesmo alerta nos dois procedimentos

- **GIVEN** uma EDA e uma colonoscopia com o mesmo anticoagulante descrito
- **WHEN** cada caso chega ao relatório médico
- **THEN** ambos exibem alerta com a mesma semântica
- **AND** nenhum perfil cria hard rule medicamentosa.
