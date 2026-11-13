# Design — Acesso compartilhado ao Pós-Procedimento

## Context

Motivação e decisões de produto em `proposal.md`. A investigação do baseline encontrou:

- `can_access_followup` em `apps/accounts/services.py` centraliza a política consumida por `followup_access_required` e pelo context processor `role_context`.
- `followup_list`, `followup_form`, `followup_history` e `followup_history_export` têm três guards: login, `role_required("manager", "admin")` e `followup_access_required`. Ambos os guards de papel precisam ser coerentes com a nova matriz.
- As demais views do dashboard têm autorização própria por papel; não existe autorização global pelo prefixo `/dashboard/` em `config/urls.py`.
- Os três templates de páginas de pós-procedimento estendem `base.html`, mas incluem `dashboard/_nav.html`. Esse partial mostra Dashboard, Prompts e Usuários. Os links internos e o redirect após POST usam o namespace `dashboard`.
- `apps/cases/followup.py` contém elegibilidade, leitura corrente, validação e gravação append-only; não exige um papel de autor, não altera o caso nem dispara fluxo operacional. As views protegem a entrada HTTP e revalidam elegibilidade no GET/POST.
- `IntranetGuardMiddleware` aplica-se pelo papel ativo, não pelo prefixo de URL. Usuários com papéis não restritos têm bypass multi-role já existente.

## Goals / Non-Goals

**Goals:** ampliar somente a capacidade de pós-procedimento; compartilhar população, versões e validações; manter o Agendador em navegação operacional; provar a negativa de acesso gerencial.

**Non-Goals:** ver `proposal.md`. Não extrair o recurso para outro app ou refatorar consultas/formulários como pré-requisito. Não mudar o mecanismo de sessão/papel ativo ou middleware.

## Decisions

### D1 — Matriz central por papel ativo, sem atribuição de papéis adicionais

Esta é a matriz final, após S2. A liberação incremental das rotas e o estado seguro após S1 estão definidos em D6.

| Identidade / papel ativo | Pós-Procedimento | Dashboard e demais permissões |
| --- | --- | --- |
| Autenticado e ativo, `scheduler` | Sim, todos os elegíveis, incluindo histórico e CSV | Mantém bloqueio gerencial |
| Autenticado e ativo, `manager`, com vínculo `scheduler` | Sim, comportamento atual | Mantém permissões atuais |
| Autenticado e ativo, `manager`, sem vínculo `scheduler` | Não | Mantém permissões atuais |
| Autenticado e ativo, `admin` | Sim, sem exigir vínculo CHD | Mantém permissões atuais |
| `doctor` ou `nir` ativos, mesmo em conta multi-role | Não | Mantém permissões atuais |
| Anônimo, inativo ou papel ativo ausente/desconhecido | Não | Mantém guards existentes |

Ampliar `can_access_followup` para reconhecer `scheduler`, mantendo autenticação/atividade e a exigência de vínculo CHD do `manager`. O contexto continua delegando à mesma política, sem predicado paralelo nos templates. A sessão continua sendo a fonte do papel ativo, conforme as convenções atuais.

Adicionar `scheduler` ao `role_required` **somente nas quatro views** citadas no Context, mantendo o guard específico. Atualizar a documentação do decorator que hoje prescreve empilhamento limitado a manager/admin. Login permanece obrigatório em todas elas.

Alternativas rejeitadas: conceder `manager` ao Agendador; liberar todas as views do dashboard; usar posse de qualquer papel privilegiado para ignorar o papel ativo. Todas ampliariam o acesso além do autorizado.

### D2 — Mesmas URLs e implementação; segunda entrada de navegação

Manter os nomes e caminhos existentes:

| Rota | Finalidade |
| --- | --- |
| `dashboard:followup_list` — `/dashboard/follow-ups/` | Pesquisa e lista de elegíveis |
| `dashboard:followup_form` — `/dashboard/follow-ups/cases/<uuid>/` | GET/POST de registro e atualização |
| `dashboard:followup_history` — `/dashboard/follow-ups/history/` | Histórico, filtros e resumos |
| `dashboard:followup_history_export` — `/dashboard/follow-ups/history/export/` | CSV |

O prefixo não concede acesso ao dashboard: cada endpoint continua protegido. Assim, links de sub-abas, filtros, Cancelar e redirect de sucesso permanecem válidos e chegam à mesma interface contextual.

Alternativa rejeitada: rotas e handlers espelhados em `/scheduler/`, com regras e redirecionamentos próprios. Não há exigência de URL separada e a duplicação aumenta risco de divergência. Extração para app compartilhado é desnecessária nesta entrega.

### D3 — Navegação escolhida pelo papel ativo nas três páginas

Nos templates `followup_list.html`, `followup_form.html` e `followup_history.html`, selecionar o partial do Agendador quando `active_role == "scheduler"`; para supervisor/admin preservar `dashboard/_nav.html`.

Adicionar a entrada **Pós-Procedimento** a `scheduler/_nav.html`, condicionada à política de acesso exposta no contexto. Marcar essa entrada como ativa em lista, formulário e histórico sem ativar Pendentes/Processados/Busca. Não duplicar o conteúdo do partial administrativo ou os formulários. Reutilizar classes Bootstrap/CSS já existentes; nenhum novo vocabulário CSS é necessário.

A seleção de partial é apresentação, não autorização. Testar também URLs diretas. O Agendador não recebe links de Dashboard, Prompts, Usuários, PDF ou detalhe gerencial por meio do novo recurso. O header de sessão (perfil, manual, troca de papel e notificações) permanece intacto.

### D4 — População global, mesmas versões e mesmos filtros

Não adicionar filtros por `case.scheduler`, criador ou autor do follow-up. Casos confirmados e fluxos operacionais elegíveis seguem exatamente `is_followup_eligible`, inclusive após encerramento quando ainda atendam ao predicado atual. Não confundir essa população com os critérios da busca histórica de agendamento em `apps/scheduler/views.py`.

O Agendador pode registrar a primeira versão ou atualizar versão de outro autor, inclusive supervisor. O supervisor vê a nova versão e pode atualizar de volta; o autor da versão e do `CaseEvent` é sempre o usuário que submeteu. Nunca editar rows anteriores. Preservar validação de procedimentos autorizados, causas oficiais e rejeição de caso/procedimento inválido, sem ampliar permissões sobre o próprio caso.

Histórico, resumos, paginação, projeção de causas legadas e CSV continuam no mesmo caminho de leitura. Provar paridade entre papéis com dados representativos, não reimplementar todos os testes analíticos existentes.

### D5 — Testar a fronteira HTTP e a rede, não apenas visibilidade

Usar fixtures reais com somente `scheduler`, dentro da intranet, para evitar falso positivo de bypass multi-role. Adicionar cenário com conta multi-role usando papel ativo `scheduler` e garantir que o dashboard continue bloqueado; posse de `manager` não libera a view com papel ativo errado.

Cobrir GET das quatro rotas, POST inicial/atualização e POST inválido. Negativas: doctor/nir, manager sem CHD, anônimo, caso inexistente/inelegível e procedimento negado/estranho. Uma negativa de POST não cria `CaseFollowUp`, `ProcedureFollowUp` ou eventos. Não enfraquecer testes existentes removendo a linha scheduler sem adicionar seus cenários positivos.

Para isolamento gerencial, parametrizar rotas reais de `apps/dashboard/urls.py`: index, summaries, case_detail, administrative_close (POST), case_pdf/pdf_viewer e endpoints de anexos/viewers. Utilizar casos/anexos existentes e payload válido para que o bloqueio seja do guard, não um 404/erro de formulário. Não seguir redirects ao testar a negativa; exigir redirect para `/` e nenhuma mutação/download. Incluir Prompts/Usuários como regressão das superfícies administrativas linkadas pelo antigo partial.

Rede: scheduler-only fora da intranet recebe 403 nas rotas de pós-procedimento, inclusive POST/CSV; dentro recebe o recurso. Preservar e caracterizar o bypass atual de conta multi-role, sem alterá-lo ou afirmar que todo scheduler é intranet-only sem exceção.

### D6 — Dois slices verticais, com estado intermediário seguro

**Lacuna do plano anterior:** o contrato único agrupava dois fluxos completos (registro e consulta/exportação), com oito requisitos e testes de quatro endpoints na mesma entrega. Faltava definir a fronteira de uma entrega menor sem anunciar rotas ainda bloqueadas. O redimensionamento abaixo resolve somente essa lacuna de execução; não modifica D1–D5 como alvo final, as specs ou as decisões de produto.

| Etapa | Valor entregue ao Agendador | Guards externos liberados para scheduler | Navegação do Agendador |
| --- | --- | --- | --- |
| S1 | Pesquisar elegíveis e registrar/atualizar versões auditáveis | Apenas `followup_list` e `followup_form` | Pós-Procedimento → Registrar; Histórico & Exportação oculto |
| S2, depende de S1 aceito | Consultar histórico, resumos e filtros e exportar CSV | Acrescentar `followup_history` e `followup_history_export` | Duas sub-abas acessíveis e navegação contextual nas três páginas |

**S1** amplia a política central conforme D1 e entrega lista/formulário com menu operacional. Os dois `role_required("manager", "admin")` de histórico/CSV ficam intactos: mesmo com a política central reconhecendo scheduler, esses endpoints continuam negando acesso. Não alterar os testes que exigem esse bloqueio antes de S2. A leitura do histórico de versões no próprio formulário faz parte de S1; a consulta analítica/exportação é S2.

O partial `templates/dashboard/_followup_tabs.html` hoje anuncia as duas sub-abas incondicionalmente. Em S1, ocultar o link de histórico somente para `scheduler` com uma condição transitória de apresentação; supervisor/admin conservam as duas sub-abas. Isso não é mecanismo de autorização, nova política ou feature flag. Os guards dos endpoints continuam obrigatórios. Referenciar S2 no comentário dessa condição para não deixar dívida sem plano.

**S2** libera os dois endpoints de leitura/exportação, adapta `followup_history.html` ao menu operacional e remove a condição transitória do partial e seu teste de ausência. Substituir as negativas de histórico/CSV do scheduler por testes positivos, mantendo negativas de doctor/nir, manager sem CHD e autenticação. Reexecutar as negativas gerenciais e de rede entregues por S1; não reimplementar sua política ou o fluxo de gravação.

Cada slice inclui seus testes e a documentação do comportamento efetivamente disponível. Em S1 o manual/contexto deve declarar que histórico/CSV ainda não estão disponíveis ao Agendador; S2 atualiza para o contrato completo, sem deixar texto ou testes transitórios. Não promover specs canônicas nem tratar o change como concluído em S1. A divisão não autoriza release/deploy intermediário automático.

**Blast radius provável por slice (mais de cinco arquivos justificados antes de codar):**

- **S1:** `apps/accounts/services.py`, `decorators.py`; somente os guards de lista/formulário em `apps/dashboard/views.py`; `templates/dashboard/followup_list.html`, `followup_form.html`, `_followup_tabs.html`; `templates/scheduler/_nav.html`; unitários em `apps/accounts/tests/test_access_policy.py`, expectativas de lista/formulário nos testes existentes e integração de fronteira preferencialmente em `apps/dashboard/tests/test_scheduler_followup_access.py`; manual/contexto e testes do manual. São sete arquivos funcionais mais evidências/documentação: todos necessários para abrir a jornada de registro sem liberar outra superfície.
- **S2:** somente os guards de histórico/CSV em `apps/dashboard/views.py`; `templates/dashboard/followup_history.html` e `_followup_tabs.html`; testes `test_followup_history.py` e o arquivo integrado de S1; manual/contexto e testes do manual. São três arquivos funcionais mais evidências/documentação. Não há alteração esperada na política central ou nas páginas de registro.

Não dividir em backend/UI/testes como slices separados: cada etapa deve sair utilizável e verificável. Não criar um terceiro slice de testes/documentação, pois essas evidências pertencem à respectiva entrega. Mais divisões exigiriam recortar navegação ou autorização sem valor adicional de ponta a ponta.

Consultar para regressão, sem mudança esperada: middleware de contas, context processor, URLs, `apps/cases/followup.py`, forms, models, signals e CSS. Arquivos adicionais devem ser justificados no relatório; nova política, migration/FSM ou extração estrutural exige escalada.

## Risks / Trade-offs

- **Ampliação de acesso a dados identificáveis e CSV** → aprovada explicitamente para todos os elegíveis; sem filtros de ownership, mas sem acesso aos demais endpoints gerenciais. Revisão da matriz e regressões negativas são obrigatórias.
- **Link administrativo aparecendo em página compartilhada** → selecionar navegação em todas as três páginas, inclusive re-render de POST inválido, e verificar os hrefs renderizados.
- **Política aceita scheduler, mas decorator externo ainda bloqueia** → teste HTTP das quatro rotas, além do unitário da política.
- **Middleware bloqueia fixture e mascara a autorização testada** → IP/configuração explícitos; separar cenários de rede e de papel ativo.
- **Prefixo `/dashboard/` confunde a organização visual** → jornada usa menu do Agendador; explicar no manual e preservar guards. URL própria poderá ser outro change se virar requisito.
- **Corrida preexistente em atualizações simultâneas** → o serviço calcula `MAX(version)+1` antes do bloco atômico, com constraint única por caso/versão. Este change não promete resolução de conflitos e não altera persistência; registrar o risco na revisão e tratar hardening em trabalho separado. Versões sequenciais entre papéis são escopo obrigatório.
- **Artefatos canônicos ainda descrevem exclusividade do supervisor** → aplicar deltas somente no arquivamento após implementação; atualizar os textos de Purpose das duas specs nessa etapa, sem renomear capabilities. Manual/contexto operacional mudam junto da implementação.

## Migration Plan

Não há migration ou seed de papéis. Deploy da imagem/código e smoke como scheduler-only na intranet: menu → busca de caso de outro agendador/vinda imediata → registrar/atualizar → histórico/CSV → tentativa direta de dashboard negada. Supervisor do CHD/admin mantêm comportamento; scheduler-only externo permanece 403.

Rollback: reverter a imagem/código restaura o bloqueio ao scheduler; versões já gravadas são compatíveis com o schema e permanecem disponíveis a supervisor/admin. Não apagar ou reescrever dados/eventos. Sem deploy no escopo do planejamento.
