## MODIFIED Requirements

### Requirement: A aba Follow-up SHALL organizar-se em sub-abas Registrar e Histórico

A superfície Follow-up SHALL apresentar sub-abas "Registrar" (fluxo de registro
existente em `/dashboard/follow-ups/`, comportamento inalterado) e "Histórico &
Exportação" (`/dashboard/follow-ups/history/`), com estado ativo visível
conforme a página corrente e acesso restrito aos papéis `manager` e `admin`,
com a exigência adicional de que um `manager` ativo possua o papel `scheduler`
(CHD); `admin` ativo é isento. A aba SHALL ficar oculta na navegação para
usuários que não satisfizerem essas condições.

#### Scenario: Sub-abas visíveis e ativas

- **GIVEN** um usuário com papéis `manager` e `scheduler`, papel ativo `manager`
- **WHEN** acessa `/dashboard/follow-ups/` e depois `/dashboard/follow-ups/history/`
- **THEN** ambas as páginas exibem as duas sub-abas
- **AND** a sub-aba correspondente à página corrente aparece como ativa

#### Scenario: Papéis sem acesso são bloqueados

- **GIVEN** usuário sem papel `manager`/`admin` (ou anônimo)
- **WHEN** acessa a página de histórico
- **THEN** o acesso é negado (sem expor dados de follow-up)

#### Scenario: Manager sem vínculo CHD não vê a aba

- **GIVEN** um usuário autenticado que possui apenas o papel `manager`
- **WHEN** navega pelo dashboard e acessa diretamente as rotas de follow-up
- **THEN** o pill Follow-up não aparece na navegação
- **AND** as rotas o redirecionam com mensagem de erro, sem renderizar conteúdo
