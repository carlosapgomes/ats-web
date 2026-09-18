# supervisor-followup-history Specification

## Purpose
Disponibilizar a supervisores do CHD e administradores uma visão histórica e exportável dos desfechos pós-procedimento, sempre baseada na versão corrente de cada caso, com filtros, agregados e CSV consistentes. A leitura consolida causas legadas sob a taxonomia oficial quando há equivalência confirmada, preserva rows e eventos append-only e sinaliza combinações desconhecidas sem inventar equivalência.

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

A página SHALL exibir cards-resumo do período (nº de casos com pós-procedimento, taxa de realizado por procedimento, causas oficiais de não realização, eventual categoria técnica não mapeada e internações) calculados sobre a janela + busca, e uma tabela paginada com uma linha por desfecho de procedimento (ocorrência, paciente, data, procedimento, desfecho, causa/texto, internação, versão, autor e momento do registro). Causas legadas com mapeamento definido SHALL ser agregadas sob a causa oficial equivalente, sem alterar a row persistida. O parâmetro `q` SHALL filtrar por número da ocorrência ou nome do paciente dentro da janela.

#### Scenario: Agregados refletem a janela

- **GIVEN** dois casos na janela, um com procedimento realizado e outro não realizado por `patient_no_show` e com internação
- **WHEN** o Histórico é aberto nessa janela
- **THEN** os cards indicam dois casos, taxa de realizado 50%, **Não comparecimento do paciente** com uma ocorrência e uma internação

#### Scenario: Causas equivalentes de eras diferentes são consolidadas

- **GIVEN** na janela uma row atual com `patient_no_show` e uma row legada com `absenteeism`
- **WHEN** o Histórico é aberto
- **THEN** tabela e cards apresentam ambas como **Não comparecimento do paciente**
- **AND** o card dessa causa contabiliza duas ocorrências, sem categoria separada de Absenteísmo

#### Scenario: Busca dentro da janela

- **GIVEN** dois casos na janela, de ocorrências/pacientes distintos
- **WHEN** o Histórico é aberto com `?q=` igual à ocorrência (ou nome) de um deles
- **THEN** apenas os desfechos daquele caso aparecem na tabela e nos cards

### Requirement: O Histórico SHALL filtrar linhas por desfecho, causa e internação

Filtros de linha (`performed`, `reason`, `admitted`) SHALL aplicar-se à tabela e ao CSV exportado, sem alterar os cards-resumo do período: `performed` e `reason` filtram linhas de desfecho de procedimento; `admitted` filtra casos inteiros. O filtro `reason` SHALL oferecer e aceitar somente códigos da taxonomia oficial atual. Ao filtrar uma causa oficial, rows legadas projetadas para a mesma causa SHALL ser incluídas. Valores inválidos, inclusive códigos legados, SHALL ser ignorados (equivale a "todos").

#### Scenario: Filtro por causa mantém cards intactos

- **GIVEN** a janela contém uma row `patient_no_show`, uma row legada `absenteeism` e outras causas
- **WHEN** o Histórico é aberto com `?reason=patient_no_show`
- **THEN** tabela e CSV incluem as duas rows equivalentes
- **AND** excluem as demais causas
- **AND** os cards-resumo continuam refletindo a janela completa

#### Scenario: Filtros com valores inválidos são ignorados

- **GIVEN** casos na janela com desfechos variados
- **WHEN** o Histórico recebe `performed`, `reason` ou `admitted` inválidos, incluindo `reason=absenteeism` ou `reason=resource_shortage`
- **THEN** a tabela e o CSV equivalem à ausência desses filtros
- **AND** os cards-resumo permanecem idênticos aos do período sem filtros

#### Scenario: Filtro por internação remove casos inteiros

- **GIVEN** na janela um caso internado com dois procedimentos e um caso não internado
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

### Requirement: O Histórico SHALL projetar causas legadas sem reescrever auditoria

Para leitura analítica, o sistema SHALL projetar `absenteeism` como **Não comparecimento do paciente** e os detalhes de `resource_shortage` como **Prioridade para urgência**, **Tempo excedido** ou **Falta de equipamentos**, conforme o mapeamento aprovado. A mesma projeção SHALL alimentar tabela, cards, filtro e CSV. Dado legado fora desses mapeamentos SHALL usar a categoria técnica não filtrável **Causa legada não mapeada**, sem ser convertido em causa oficial. Consultar ou exportar o Histórico MUST NOT alterar `ProcedureFollowUp`, `CaseFollowUp` ou `CaseEvent` existentes.

#### Scenario: Quatro mapeamentos históricos oficiais

- **GIVEN** rows legadas com `absenteeism` e com cada um dos detalhes válidos de `resource_shortage`
- **WHEN** a página, o resumo e o CSV são produzidos
- **THEN** os labels resultantes são, respectivamente, **Não comparecimento do paciente**, **Prioridade para urgência**, **Tempo excedido** e **Falta de equipamentos**
- **AND** nenhum label legado é exibido como categoria paralela

#### Scenario: Dado legado desconhecido não recebe equivalência inventada

- **GIVEN** uma row histórica com causa ou detalhe fora dos quatro mapeamentos aprovados
- **WHEN** o Histórico ou CSV é produzido defensivamente
- **THEN** a row aparece como **Causa legada não mapeada**, com códigos técnicos preservados para diagnóstico
- **AND** a categoria não aparece nas opções do filtro oficial
- **AND** nenhum código da taxonomia oficial é atribuído à row

#### Scenario: Preflight bloqueia rollout com dado não mapeável

- **GIVEN** existe ao menos uma row histórica fora do catálogo atual e dos quatro mapeamentos aprovados
- **WHEN** o preflight de rollout é executado
- **THEN** ele termina com falha e informa contagem/identificadores técnicos sem dados clínicos
- **AND** migration/deploy não são liberados até decisão humana

#### Scenario: Consulta e exportação preservam dados append-only

- **GIVEN** rows e eventos legados existentes antes da consulta
- **WHEN** o usuário abre o Histórico, aplica filtro oficial e exporta CSV
- **THEN** os códigos e detalhes persistidos permanecem inalterados
- **AND** nenhum evento de auditoria é criado, editado ou removido

#### Scenario: CSV mantém estrutura e usa causa oficial

- **GIVEN** uma row legada projetável e uma row atual de **Outras causas** com texto contendo `;` e quebra de linha
- **WHEN** o Histórico é exportado
- **THEN** o CSV mantém BOM, separador, header e ordem de colunas existentes
- **AND** a row legada usa o label oficial projetado e submotivo vazio
- **AND** o texto de **Outras causas** permanece corretamente escapado e parseável
