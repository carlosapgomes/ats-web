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
