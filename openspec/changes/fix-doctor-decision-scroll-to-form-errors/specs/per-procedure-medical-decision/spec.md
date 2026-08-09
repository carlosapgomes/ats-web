# per-procedure-medical-decision Spec Delta

## ADDED Requirements

### Requirement: Re-renderização com erro de validação SHALL reposicionar o médico no formulário

A página de decisão médica SHALL marcar o formulário para rolagem até o primeiro campo inválido sempre que uma submissão falhar por validação, de modo que os erros fiquem visíveis sem navegação manual.

#### Scenario: Submit com erro de validação

- **GIVEN** o médico preencheu o formulário de decisão em um caso `WAIT_DOCTOR`
- **WHEN** o submit é rejeitado por validação e a página é re-renderizada
- **THEN** o formulário contém o marcador `data-scroll-to-errors`
- **AND** o script da página rola até o primeiro campo `.is-invalid`

#### Scenario: Página sem erros

- **GIVEN** o médico abre a tela de decisão sem submissão inválida
- **WHEN** a página é renderizada
- **THEN** o formulário não contém o marcador `data-scroll-to-errors`
