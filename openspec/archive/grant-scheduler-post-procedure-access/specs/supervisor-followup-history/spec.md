# Delta — Histórico & Exportação para Agendador

## MODIFIED Requirements

### Requirement: A aba Pós-Procedimento SHALL organizar-se em sub-abas Registrar e Histórico

A superfície Pós-Procedimento SHALL apresentar sub-abas "Registrar" (`/dashboard/follow-ups/`) e "Histórico & Exportação" (`/dashboard/follow-ups/history/`), com estado ativo conforme a página corrente. O acesso SHALL ser permitido a Agendador (`scheduler` ativo), supervisor do CHD (`manager` ativo com papel `scheduler`) e `admin`, autenticados e ativos, conforme a política de rede existente. A aba SHALL ficar oculta para usuários sem acesso.

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

#### Scenario: Agendador alterna as sub-abas sem acessar o dashboard

- **GIVEN** um usuário autenticado e ativo apenas com papel `scheduler` ativo e dentro da intranet
- **WHEN** abre Pós-Procedimento pela navegação do Agendador e alterna Registrar e Histórico & Exportação
- **THEN** acessa ambas as sub-abas, com indicação ativa correta
- **AND** mantém a navegação do Agendador sem links administrativos

### Requirement: O sistema SHALL exportar o Histórico em CSV fiel aos filtros

`GET /dashboard/follow-ups/history/export/` SHALL permitir Agendador, supervisor do CHD e admin autorizados ao Pós-Procedimento, aceitar os mesmos parâmetros da página e responder CSV UTF-8 com BOM, separador `;`, header em português, uma linha por desfecho de procedimento da versão corrente e nome de arquivo derivado da janela, sem criar eventos de auditoria.

#### Scenario: CSV com filtros da página

- **GIVEN** o Histórico aberto numa janela com filtro de causa E população filtrada com mais de 25 linhas
- **WHEN** o supervisor exporta
- **THEN** o CSV chega com `Content-Type` `text/csv; charset=utf-8`, BOM presente, header esperado
- **AND** as linhas correspondem exatamente às da tabela filtrada, com valores em português, incluindo TODAS as linhas da população filtrada (a exportação ignora a paginação da tabela)
- **AND** nenhum `CaseEvent` é criado pela exportação

#### Scenario: Campos com separador são escapados

- **GIVEN** um desfecho com texto de outra causa contendo `;` e quebra de linha
- **WHEN** exportado
- **THEN** a célula é delimitada/escapada corretamente e o CSV permanece parseável com uma coluna por campo do header

#### Scenario: Exportação sem papel é bloqueada

- **GIVEN** usuário com papel ativo `doctor` ou `nir`, manager sem vínculo CHD, ou anônimo
- **WHEN** solicita a exportação diretamente pela URL
- **THEN** o acesso é negado e nenhum conteúdo de follow-up é baixado

#### Scenario: Agendador exporta sem vínculo Supervisor

- **GIVEN** um usuário autenticado e ativo apenas com papel `scheduler` ativo, dentro da intranet
- **AND** desfechos elegíveis registrados por usuários distintos na janela escolhida
- **WHEN** exporta com os filtros da página
- **THEN** recebe o CSV completo da população filtrada, sem restrição ao responsável pelo agendamento ou autor do registro
- **AND** os registros, versões e eventos persistidos permanecem inalterados

## ADDED Requirements

### Requirement: Agendador e supervisor SHALL consultar o mesmo histórico de pós-procedimento

O Histórico & Exportação do Agendador SHALL usar os mesmos desfechos correntes, população global elegível, resumos e filtros do supervisor do CHD. Defaults, limites de período, paginação, projeção de causas legadas e formato CSV SHALL permanecer iguais, sem filtro por agendador ou autoria. Consultar/exportar SHALL NOT modificar rows ou eventos.

#### Scenario: Paridade de consulta e CSV entre papéis

- **GIVEN** casos elegíveis agendados por diferentes usuários e de vinda imediata, com versões registradas por supervisor e agendador
- **WHEN** Agendador e supervisor do CHD consultam o mesmo período e busca e aplicam os mesmos filtros de desfecho, causa e internação
- **THEN** recebem os mesmos resumos, linhas correntes e CSV
- **AND** os filtros de linha não alteram os cards-resumo, conforme o comportamento atual
- **AND** nenhum registro ou evento é criado, alterado ou removido por consulta/exportação

#### Scenario: Versão criada pelo Agendador aparece para o supervisor

- **GIVEN** um caso elegível com versão 1 registrada pelo supervisor e versão 2 pelo Agendador
- **WHEN** ambos abrem o Histórico na janela do caso
- **THEN** ambos veem somente a versão 2 na tabela analítica, com o mesmo autor e timestamp
- **AND** a versão 1 permanece preservada no histórico de versões do formulário
