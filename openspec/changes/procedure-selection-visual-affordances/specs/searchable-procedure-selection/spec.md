# searchable-procedure-selection Delta

## Purpose

Estender a capability com affordances visuais que comunicam a funcionalidade
do combobox (placeholder, hint persistente, chevron, bordas e estado
selecionado) sem alterar o contrato de seleção canônica.

## ADDED Requirements

### Requirement: Combobox aprimorado SHALL comunicar funcionalidade por affordances visuais

O controle aprimorado SHALL exibir placeholder específico da jornada quando nenhum valor está selecionado, SHALL indicar visualmente que abre uma lista com estado ligado à expansão, SHALL manter bordas de repouso e hover distinguíveis com alvo de toque mínimo de 44 px, e SHALL marcar a opção correspondente ao valor confirmado de forma distinguível do destaque de navegação por teclado quando a lista reabre.

#### Scenario: Placeholder orienta a busca

- **GIVEN** nenhum valor selecionado na superfície
- **WHEN** a página carrega com o aprimoramento JavaScript
- **THEN** o input exibe o placeholder da jornada
- **AND** o placeholder desaparece quando o usuário digita
- **AND** sem JavaScript o select continua exibindo a primeira option instrucional como placeholder natural.

#### Scenario: Chevron sinaliza lista expansível

- **GIVEN** o controle aprimorado está fechado
- **THEN** um chevron indica que o controle abre uma lista
- **WHEN** a lista abre (`aria-expanded="true"`)
- **THEN** o estado visual do chevron muda por rotação
- **AND** o indicador não depende somente de cor.

#### Scenario: Opção selecionada distinguível na listbox

- **GIVEN** um valor foi confirmado no combobox
- **WHEN** a lista é reaberta
- **THEN** a linha correspondente ao valor selecionado exibe marcador além de cor
- **AND** esse marcador é distinto do destaque de opção ativa por teclado
- **AND** a linha selecionada expõe `aria-selected="true"`.

#### Scenario: Alvo de toque e hover

- **GIVEN** o controle aprimorado renderizado
- **THEN** sua altura mínima é de 44 px
- **AND** o hover muda a borda do controle
- **AND** a borda de repouso é distinguível do fundo da superfície.

### Requirement: Superfícies de seleção SHALL exibir hint persistente de busca

As quatro superfícies de seleção (upload, correção, reenvio NIR e destino médico) SHALL exibir hint textual persistente sobre a busca sem acentos, sinônimos aprovados e navegação por teclado, associado por `aria-describedby` ao select canônico e herdado pelo input aprimorado. O hint MUST sobreviver à re-renderização com erro e MUST NOT ser substituído pelo placeholder.

#### Scenario: Hint presente e associado em cada superfície

- **GIVEN** qualquer uma das quatro superfícies renderizada
- **THEN** o hint de busca está visível abaixo do controle com id estável
- **AND** o `aria-describedby` do select referencia o hint
- **AND** o input aprimorado herda a mesma associação.

#### Scenario: Hint sobrevive a re-renderização com erro

- **GIVEN** o backend rejeitou o submit da superfície
- **WHEN** a página é re-renderizada com o erro
- **THEN** o hint permanece visível
- **AND** a associação do controle inclui simultaneamente hint e erro.

#### Scenario: Placeholder não é portador único

- **GIVEN** a superfície define placeholder da jornada
- **THEN** o hint persistente permanece visível após seleção e durante digitação
- **AND** a orientação funcional não depende do placeholder.
