## RENAMED Requirements

- FROM: `### Requirement: A aba e o formulário SHALL ser acessíveis apenas a manager e admin`
- TO: `### Requirement: A aba e o formulário de follow-up SHALL ser acessíveis apenas a supervisores do CHD e admin`

## MODIFIED Requirements

### Requirement: O sistema SHALL registrar o desfecho por procedimento de casos agendados e de vinda imediata

O sistema SHALL permitir que supervisores do CHD (`manager` com papel `scheduler`, papel ativo `manager`) e `admin` registrem, por caso, o desfecho de cada `CaseProcedure` (realizado / não realizado) e a ocorrência de internação no nível do caso, sem alterar o estado FSM do caso nem disparar fluxos operacionais.

#### Scenario: Registro inicial de desfecho

- **GIVEN** um caso elegível com procedimentos EDA e Colonoscopia declarados
- **WHEN** um supervisor do CHD (`manager` com papel `scheduler`) submete o formulário de follow-up com desfechos para ambos e internação
- **THEN** uma `CaseFollowUp` versão 1 é criada com uma `ProcedureFollowUp` por procedimento
- **AND** um `CaseEvent` `FOLLOWUP_RECORDED` é criado com snapshot do desfecho
- **AND** o `status` do caso permanece inalterado

#### Scenario: Validação de causa estruturada

- **GIVEN** um procedimento marcado como não realizado
- **WHEN** o motivo é `resource_shortage` sem submotivo, `other` sem texto, ou nenhum motivo
- **THEN** a gravação é rejeitada com erro de validação específico
- **AND** nenhuma row de follow-up é criada

#### Scenario: Causa com valor ou combinação inválida

- **GIVEN** um procedimento marcado como não realizado
- **WHEN** o submotivo informado está fora das opções previstas, ou um motivo diferente de `resource_shortage` vem acompanhado de submotivo, ou um motivo diferente de `other` vem acompanhado de texto
- **THEN** a gravação é rejeitada com erro de validação amigável (`ValueError`)
- **AND** nenhuma row é gravada e nenhum `IntegrityError` é exposto

### Requirement: A aba e o formulário de follow-up SHALL ser acessíveis apenas a supervisores do CHD e admin

As rotas de follow-up SHALL exigir autenticação e papel ativo `manager` ou
`admin`. Um usuário com papel ativo `manager` adicionalmente SHALL possuir o
papel `scheduler` (CHD); usuários com papel ativo `admin` são isentos dessa
exigência. Quem não satisfizer SHALL ser redirecionado com mensagem de erro,
sem alterar o guard de intranet existente, e a aba SHALL ficar oculta na
navegação para esses usuários.

#### Scenario: Manager sem vínculo CHD é bloqueado

- **GIVEN** um usuário autenticado que possui apenas o papel `manager`, com papel ativo `manager`
- **WHEN** navega pelo dashboard e acessa diretamente qualquer rota de follow-up
- **THEN** o pill Follow-up não aparece na navegação
- **AND** a rota o redireciona para `/` com mensagem de erro, sem renderizar conteúdo

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
