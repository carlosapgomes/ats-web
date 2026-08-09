# per-procedure-medical-decision Spec Delta

## MODIFIED Requirements

### Requirement: Re-renderização com erro de validação SHALL exibir banner de erro no topo

A página de decisão médica SHALL exibir um banner de erro no topo do conteúdo sempre que uma submissão falhar por validação, com mensagem clara e botão de âncora para o formulário, de modo que os erros fiquem visíveis sem depender de rolagem automática.

#### Scenario: Submit com erro de validação

- **GIVEN** o médico preencheu o formulário de decisão em um caso `WAIT_DOCTOR`
- **WHEN** o submit é rejeitado por validação e a página é re-renderizada
- **THEN** o topo do conteúdo exibe um banner de erro com a contagem de campos com erro
- **AND** o banner contém um botão de âncora apontando para o formulário de decisão
- **AND** a página não depende de rolagem automática para revelar os erros

#### Scenario: Página sem erros

- **GIVEN** o médico abre a tela de decisão sem submissão inválida
- **WHEN** a página é renderizada
- **THEN** nenhum banner de erro é exibido
