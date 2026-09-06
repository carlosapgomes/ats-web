## RENAMED Requirements

- FROM: `### Requirement: A aba e o formulário SHALL ser acessíveis apenas a manager e admin`
- TO: `### Requirement: A aba e o formulário de follow-up SHALL ser acessíveis apenas a supervisores do CHD e admin`

## MODIFIED Requirements

### Requirement: A aba e o formulário de follow-up SHALL ser acessíveis apenas a supervisores do CHD e admin

As rotas de follow-up SHALL exigir autenticação e papel ativo `manager` ou
`admin`. Um usuário com papel ativo `manager` adicionalmente SHALL possuir o
papel `scheduler` (CHD); usuários com papel ativo `admin` são isentos dessa
exigência. Quem não satisfizer SHALL ser redirecionado com mensagem de erro,
sem alterar o guard de intranet existente, e a aba SHALL ficar oculta na
navegação para esses usuários.

#### Scenario: Manager sem vínculo CHD é bloqueado
#### Scenario: Manager com vínculo CHD acessa

- **GIVEN** um usuário autenticado que possui os papéis `manager` e `scheduler`, com papel ativo `manager`
- **WHEN** acessa as rotas de follow-up
- **THEN** o comportamento existente é preservado (listagem, formulário, histórico e exportação)

#### Scenario: Admin acessa sem vínculo CHD

- **GIVEN** um usuário autenticado que possui apenas o papel `admin`, com papel ativo `admin`
- **WHEN** acessa as rotas de follow-up
- **THEN** o acesso é permitido (isenção de papel de emergência/suporte)

#### Scenario: Papel sem permissão

- **GIVEN** um usuário autenticado com papel ativo `scheduler`
- **WHEN** ele acessa `/dashboard/follow-ups/`
- **THEN** é redirecionado com mensagem de erro e nenhum dado de follow-up é exposto

#### Scenario: Acesso direto por URL a caso inelegível

- **GIVEN** um caso sem agendamento confirmado e sem fluxo de vinda imediata
- **WHEN** um supervisor do CHD (`manager` com papel `scheduler`) ou `admin` abre o formulário de follow-up desse caso diretamente pela URL
- **THEN** recebe resposta 404 com mensagem explicativa
- **AND** nenhum formulário é renderizado e nenhuma gravação é aceita

#### Scenario: Caso elegível sem procedimentos declarados

- **GIVEN** um caso elegível sem rows `CaseProcedure` (situação defensiva; não deve ocorrer no fluxo atual)
- **WHEN** um supervisor do CHD (`manager` com papel `scheduler`) abre o formulário de follow-up desse caso
- **THEN** a página exibe aviso orientando a correção do caso, sem campos de gravação
- **AND** qualquer tentativa de POST é rejeitada sem criar rows nem eventos
