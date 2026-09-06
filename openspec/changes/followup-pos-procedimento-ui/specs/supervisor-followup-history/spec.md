## RENAMED Requirements

- FROM: `### Requirement: A aba Follow-up SHALL organizar-se em sub-abas Registrar e Histórico`
- TO: `### Requirement: A aba Pós-Procedimento SHALL organizar-se em sub-abas Registrar e Histórico`

## MODIFIED Requirements

### Requirement: A aba Pós-Procedimento SHALL organizar-se em sub-abas Registrar e Histórico

A superfície Pós-Procedimento SHALL apresentar sub-abas "Registrar" (fluxo de
registro existente em `/dashboard/follow-ups/`, comportamento inalterado) e
"Histórico & Exportação" (`/dashboard/follow-ups/history/`), com estado ativo
visível conforme a página corrente e acesso restrito a supervisores do CHD
(`manager` ativo com papel `scheduler`) e `admin`. A aba SHALL ficar oculta na
navegação para usuários sem acesso.

#### Scenario: Sub-abas visíveis e ativas

- **GIVEN** um usuário com papéis `manager` e `scheduler`, papel ativo `manager`
- **WHEN** acessa `/dashboard/follow-ups/` e depois `/dashboard/follow-ups/history/`
- **THEN** ambas as páginas exibem as duas sub-abas
- **AND** a sub-aba correspondente à página corrente aparece como ativa

#### Scenario: Papéis sem acesso são bloqueados

- **GIVEN** usuário sem permissão de acesso (ou anônimo)
- **WHEN** acessa a página de histórico
- **THEN** o acesso é negado (sem expor dados de follow-up)

#### Scenario: Manager sem vínculo CHD não vê a aba

- **GIVEN** um usuário autenticado que possui apenas o papel `manager`
- **WHEN** navega pelo dashboard e acessa diretamente as rotas de follow-up
- **THEN** o pill Pós-Procedimento não aparece na navegação
- **AND** as rotas o redirecionam com mensagem de erro, sem renderizar conteúdo
