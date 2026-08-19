<!-- markdownlint-disable MD013 -->

# Proposal: Recebidos hoje e todos os estados por padrão no dashboard

**Change ID**: `dashboard-today-all-states-default`  
**Risco**: PROFISSIONAL (altera a população inicial de uma superfície gerencial, sem mutação de dados/FSM)  
**Dependências**: `apps/dashboard`, filtros existentes `case_scope`, `date_from`/`date_to`, paginação SSR e busca parcial Vanilla JS

## Problema

Desde a `v0.4.0`, a lista do dashboard resolve a ausência de `case_scope` como `active`: mostra todos os casos não `CLEANED`, inclusive backlog antigo, e omite os encerrados. Essa decisão protegeu a visibilidade das pendências antigas, mas não corresponde ao principal uso diário relatado para supervisor/admin: abrir o dashboard para acompanhar os casos recebidos hoje e conferir tanto os que ainda estão em andamento quanto os já avaliados ou encerrados.

O dashboard atual combina universos diferentes na carga inicial:

- cards e analytics usam período de métricas `today` por padrão;
- a lista usa todos os casos ativos, sem data;
- um caso recebido hoje e já `CLEANED` entra nas métricas, mas desaparece da lista;
- um caso ativo antigo aparece na lista, embora não pertença ao total de recebidos hoje.

A listagem inicial, portanto, não permite explicar diretamente os números diários exibidos acima dela.

## Objetivo

Tornar a jornada inicial coerente com a supervisão diária:

1. `/dashboard/` deve listar **casos recebidos hoje em todos os estados**, incluindo `CLEANED`;
2. backlog antigo ativo deve continuar acessível por uma ação visível **Casos ativos**;
3. **Atenção necessária** deve continuar abrindo o backlog problemático transversalmente, sem receber o filtro diário implícito;
4. filtros avançados, histórico completo, paginação SSR e busca parcial devem continuar funcionais.

“Recebidos hoje” significa `Case.created_at` dentro do dia local corrente. Não significa “qualquer caso que recebeu uma ação hoje”.

## Escopo incluído

- Novo default efetivo da lista: `case_scope=all` + `date_from=date_to=timezone.localdate()`.
- Uso dos parâmetros já existentes `date_from` e `date_to`; nenhum alias `date=today` será criado.
- Compatibilidade do acesso histórico explícito: `?case_scope=all` sem datas continua significando todos os casos de todas as datas.
- Atalho visível para `?case_scope=active`, sem datas implícitas, mostrando backlog ativo de qualquer data.
- Modo `attention=1` sem datas implícitas, mantendo a exclusão operacional de `CLEANED` já existente.
- Preservação explícita de `case_scope` e datas em links SSR, paginação e busca parcial para que nenhum modo seja perdido.
- Testes end-to-end do default, backlog ativo, atenção transversal, histórico e propagação SSR/JS.
- Atualização da spec canônica `dashboard-case-list` por delta OpenSpec.

## Fora de escopo

- Alterar o significado de `Case.created_at` ou criar uma dimensão “atividade ocorrida hoje”.
- Filtrar por `doctor_decided_at`, `appointment_decided_at`, `cleanup_completed_at` ou `CaseEvent` na lista inicial.
- Vincular automaticamente a lista ao seletor `metrics_period`; métricas e lista continuam controles independentes.
- Alterar `_compute_stage_waiting()`, contagens de atenção, analytics ou tempos médios.
- Alterar estados FSM, significado de `CLEANED`, modelos, migrations, índices, URLs, permissões ou auditoria.
- Criar nova página de backlog/histórico, endpoint, API JSON, DRF, HTMX, SPA ou framework frontend.
- Refatorar genericamente a montagem de query strings dos templates.
- Alterar paginação de 20 itens ou a faixa elidida introduzida na `v0.4.0`.

## Dimensionamento em slices

O change terá **um único slice vertical**.

A mudança é pequena, mas o fluxo só fica correto quando a mesma semântica atravessa backend, controles SSR, links de paginação, busca parcial e regressões. Separar backend/template/JS em slices seria horizontal, deixaria estados intermediários quebrados e repetiria os mesmos testes. O slice prevê exatamente cinco arquivos funcionais, no limite ideal do projeto:

1. `apps/dashboard/views.py`
2. `templates/dashboard/index.html`
3. `templates/dashboard/_case_list.html`
4. `static/js/dashboard_search.js`
5. `apps/dashboard/tests/test_dashboard.py`

Nenhum CSS, model, migration, URL ou outro app é necessário.

## Critérios de sucesso globais

- `/dashboard/` sem parâmetros mostra casos de hoje ativos e `CLEANED`, e não mostra casos antigos.
- O contexto inicial resolve `case_scope=all` e preenche `date_from`/`date_to` com a data local corrente.
- `?case_scope=active` mostra ativos antigos, exclui `CLEANED` e não aplica data implícita.
- Existe ação visível e testada para abrir `?case_scope=active` diretamente.
- `?case_scope=all` sem datas mantém o acesso ao histórico completo.
- Limpar datas explicitamente continua permitindo consulta sem restrição temporal.
- `?attention=1` alcança casos problemáticos antigos e não recebe o default diário.
- O link “Atenção necessária” entra no modo ativo transversal e não carrega `date_from`/`date_to` do default.
- Escopo e datas sobrevivem a paginação, períodos de métricas, dimensão e busca parcial.
- Paginação server-side de 20, faixa elidida, permissões e fallback sem JavaScript permanecem intactos.
- Quality gate completo do `AGENTS.md` passa.

## Rollout e rollback

Não há migration nem transformação de dados. O rollout ocorre com deploy da aplicação. O rollback é o revert dos cinco arquivos funcionais e da spec promovida; nenhum caso é criado, removido ou alterado por este change.

Risco operacional principal: um supervisor deixar de notar backlog antigo na carga inicial. Mitigações: ação visível “Casos ativos”, contador/link “Atenção necessária” transversal e testes que provam que ambos ignoram o default diário.