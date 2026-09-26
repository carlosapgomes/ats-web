# searchable-procedure-selection Specification

## Purpose
Define uma seleção de procedimentos escalável, acessível e progressivamente aprimorada para as jornadas SSR de intake, correção e decisão médica.

## Requirements

### Requirement: Seletores de procedimento SHALL oferecer busca sem acentos

Upload, correção/reenvio NIR e inclusão/substituição médica SHALL apresentar um combobox pesquisável com todas as opções permitidas para a jornada. A busca SHALL ignorar caixa e diacríticos e SHALL pesquisar labels e aliases aprovados sem alterar o código técnico submetido.

#### Scenario: Busca por capsula sem acento

- **GIVEN** o combobox contém `EDA + Cápsula`
- **WHEN** usuário pesquisa `capsula`
- **THEN** a opção permanece disponível
- **AND** a seleção submete exatamente `eda_capsule`.

#### Scenario: Busca por GTT

- **GIVEN** o combobox de intake está aberto
- **WHEN** usuário pesquisa `GTT`
- **THEN** encontra `EDA + GTT`
- **AND** nenhuma abreviação não aprovada aparece como opção.

#### Scenario: Termo sem resultado

- **WHEN** a busca não corresponde a label ou alias permitido
- **THEN** a interface informa que não há resultados
- **AND** não cria valor livre submetível.

### Requirement: Combobox SHALL atender interação por teclado e semântica acessível

O controle aprimorado SHALL expor nome acessível, estado expandido, opção ativa e lista associada, e SHALL permitir abrir, navegar, selecionar e fechar por teclado. Foco visível e mensagens de erro MUST NOT depender somente de cor.

#### Scenario: Seleção somente por teclado

- **GIVEN** o foco está no combobox fechado
- **WHEN** usuário abre, percorre opções com setas e confirma com Enter
- **THEN** a opção ativa é anunciada e selecionada
- **AND** o código correspondente fica no controle submetido.

#### Scenario: Escape fecha a lista

- **GIVEN** a lista está aberta
- **WHEN** usuário pressiona Escape
- **THEN** a lista fecha sem alterar a seleção confirmada
- **AND** o foco permanece no controle.

#### Scenario: Erro de obrigatoriedade

- **GIVEN** nenhuma opção foi selecionada
- **WHEN** o formulário é submetido
- **THEN** o erro é associado ao controle
- **AND** a mensagem textual fica perceptível por tecnologia assistiva.

### Requirement: Progressive enhancement SHALL preservar fallback SSR

Sem JavaScript, o formulário SHALL continuar oferecendo um controle HTML submetível com todas as opções permitidas e validação backend idêntica. Com JavaScript, o aprimoramento MUST manter um único valor autoritativo e MUST NOT alterar nomes de campos ou contrato POST.

#### Scenario: JavaScript indisponível

- **GIVEN** scripts não carregaram
- **WHEN** usuário seleciona um procedimento no fallback e envia
- **THEN** o backend recebe o mesmo código técnico esperado
- **AND** a jornada continua funcional.

#### Scenario: Re-renderização inválida

- **GIVEN** o backend rejeitou outro campo do formulário
- **WHEN** a página SSR é re-renderizada
- **THEN** a seleção válida anterior permanece selecionada
- **AND** o aprimoramento JavaScript restaura o mesmo label.

### Requirement: Backend SHALL validar código exato e contexto permitido

O backend SHALL aceitar somente chaves de seleção canônicas permitidas naquela jornada, independentemente do estado do JavaScript. Label, alias, texto livre, identidade desconhecida ou combinação proibida MUST ser rejeitados sem persistência parcial.

#### Scenario: Alias enviado como valor

- **GIVEN** request manipulado envia `GTT` em vez do código canônico
- **WHEN** o backend valida
- **THEN** o formulário é inválido
- **AND** nenhum procedimento é persistido.

#### Scenario: Código canônico proibido no conjunto final

- **GIVEN** a decisão médica tenta manter Colonoscopia e adicionar `eda_dilation`
- **WHEN** o backend valida o submit
- **THEN** rejeita o conjunto final incompatível
- **AND** nenhuma decisão parcial é persistida.

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
