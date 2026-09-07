# supervisor-followup-history Specification

## Purpose
TBD - created by archiving change supervisor-followup-history-export. Update Purpose after archive.

## Requirements

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

### Requirement: O Histórico SHALL listar desfechos da versão corrente por data de grupo em janela de datas

A página de Histórico SHALL considerar apenas casos com follow-up registrado, cada caso exatamente uma vez pela sua versão corrente (maior `version`), ordenados do mais recente para o mais antigo, com o eixo temporal definido pela data de grupo do caso (agendamento confirmado ou decisão de vinda imediata — mesma semântica da aba Registrar). A janela SHALL aceitar `start`/`end` em datas locais com default de 7 dias incluindo hoje, limite de 31 dias, e parâmetros inválidos, invertidos ou acima do limite SHALL cair no default.

#### Scenario: Default de 7 dias

- **GIVEN** follow-ups registrados com datas de grupo hoje, há 6 dias, há 10 dias e há 1 mês
- **WHEN** o supervisor abre o Histórico sem parâmetros
- **THEN** apenas os desfechos com data de grupo nos últimos 7 dias (incluindo hoje) aparecem

#### Scenario: Versões antigas não distorcem a listagem

- **GIVEN** um caso com follow-up versão 1 (internação = não) e versão 2 (internação = sim)
- **WHEN** o Histórico é aberto no período
- **THEN** o caso aparece uma única vez, com os dados da versão 2

#### Scenario: Janela explícita e fallback

- **WHEN** o Histórico é aberto com `?start=&end=` válidos (span ≤ 31 dias)
- **THEN** a listagem segue a janela informada
- **WHEN** recebe datas inválidas, `start > end` ou span > 31 dias
- **THEN** o comportamento equivale ao default de 7 dias

#### Scenario: Data de grupo prevalece sobre o momento do registro

- **GIVEN** um caso cuja data de grupo (agendamento confirmado) é hoje mas cujo follow-up foi registrado há 10 dias E um caso cuja data de grupo é há 10 dias mas cujo follow-up foi registrado hoje
- **WHEN** o Histórico é aberto no default de 7 dias
- **THEN** o primeiro caso aparece e o segundo não (o eixo é a data de grupo, não `recorded_at`)

### Requirement: O Histórico SHALL exibir agregados do período e tabela com busca

A página SHALL exibir cards-resumo do período (nº de casos com follow-up, taxa de realizado por procedimento, causas de não realização com breakdown de submotivos e internações) calculados sobre a janela + busca, e uma tabela paginada com uma linha por desfecho de procedimento (ocorrência, paciente, data, procedimento, desfecho, causa/submotivo/texto, internação, versão, autor e momento do registro). O parâmetro `q` SHALL filtrar por número de ocorrência ou nome do paciente dentro da janela.

#### Scenario: Agregados refletem a janela

- **GIVEN** 2 casos na janela, um com 1 procedimento realizado e outro com 1 procedimento não realizado por absenteísmo e internação
- **WHEN** o Histórico é aberto nessa janela
- **THEN** os cards indicam 2 casos, taxa de realizado 50%, absenteísmo com 1 ocorrência e 1 internação

#### Scenario: Busca dentro da janela

- **GIVEN** dois casos na janela, de ocorrências/pacientes distintos
- **WHEN** o Histórico é aberto com `?q=` igual à ocorrência (ou nome) de um deles
- **THEN** apenas os desfechos daquele caso aparecem na tabela e nos cards

### Requirement: O Histórico SHALL filtrar linhas por desfecho, causa e internação

Filtros de linha (`performed`, `reason`, `admitted`) SHALL aplicar-se à tabela e ao CSV exportado, sem alterar os cards-resumo do período: `performed` e `reason` filtram linhas de desfecho de procedimento; `admitted` filtra casos inteiros. Valores inválidos SHALL ser ignorados (equivale a "todos").

#### Scenario: Filtro por causa mantém cards intactos

- **GIVEN** casos na janela com causas distintas
- **WHEN** o Histórico é aberto com `?reason=resource_shortage`
- **THEN** a tabela exibe apenas linhas de procedimentos não realizados por falta de recursos
- **AND** os cards-resumo continuam refletindo a janela completa

#### Scenario: Filtros com valores inválidos são ignorados

- **GIVEN** casos na janela com desfechos variados
- **WHEN** o Histórico é aberto com `?performed=banana&reason=xyz&admitted=talvez`
- **THEN** a tabela e o CSV equivalem à ausência desses filtros (todos os valores válidos aceitos como "todos")
- **AND** os cards-resumo permanecem idênticos aos do período sem filtros

#### Scenario: Filtro por internação remove casos inteiros

- **GIVEN** na janela um caso internado com 2 procedimentos e um caso não internado
- **WHEN** o Histórico é aberto com `?admitted=yes`
- **THEN** apenas as linhas do caso internado aparecem

### Requirement: O sistema SHALL exportar o Histórico em CSV fiel aos filtros

`GET /dashboard/follow-ups/history/export/` SHALL aceitar os mesmos parâmetros da página e responder CSV UTF-8 com BOM, separador `;`, header em português, uma linha por desfecho de procedimento da versão corrente e nome de arquivo derivado da janela, sem criar eventos de auditoria.

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

- **GIVEN** usuário sem papel `manager`/`admin` (ou anônimo)
- **WHEN** solicita a exportação
- **THEN** o acesso é negado e nenhum conteúdo de follow-up é baixado
