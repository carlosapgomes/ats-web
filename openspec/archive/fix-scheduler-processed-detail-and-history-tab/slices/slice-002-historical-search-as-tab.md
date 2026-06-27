# Slice 002: `Buscar caso antigo` como terceira aba do agendador

## Handoff para implementador LLM com contexto zero

Você está no projeto ATS Web, um monolito Django SSR. Antes de codar, leia integralmente:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/fix-scheduler-processed-detail-and-history-tab/proposal.md`
4. `openspec/changes/fix-scheduler-processed-detail-and-history-tab/design.md`
5. `openspec/changes/fix-scheduler-processed-detail-and-history-tab/tasks.md`
6. `openspec/changes/fix-scheduler-processed-detail-and-history-tab/slices/slice-001-unified-scheduler-detail-message-nir.md`
7. Este arquivo
8. Código atual em:
   - `templates/scheduler/queue.html`
   - `templates/scheduler/historical_search.html`
   - `apps/scheduler/views.py`
   - `apps/scheduler/tests/test_views.py`

Assuma que o Slice 001 já foi implementado. Implemente **somente este slice**.

Use TDD obrigatório: **RED → GREEN → REFACTOR**. Primeiro escreva testes falhando para a navegação esperada, depois implemente o mínimo necessário.

Aplique clean code, DRY e YAGNI:

- não alterar regras de busca histórica;
- não alterar permissões;
- não refatorar a fila inteira;
- não criar JS novo;
- não criar migrations;
- se extrair partial de navegação, mantenha-o pequeno e focado.

## Contexto do problema

Hoje, na tela do agendador, a busca histórica existe, mas aparece como botão discreto separado:

```text
🔍 Buscar histórico
```

A navegação principal mostra apenas:

```text
Pendentes | Processados Hoje
```

Produto quer que `Buscar caso antigo` seja uma aba/entrada principal, no mesmo nível operacional das outras duas áreas.

## Objetivo do slice

Entrega vertical:

```text
Agendador abre /scheduler/
→ vê três abas: Pendentes, Processados Hoje, Buscar caso antigo
→ clica Buscar caso antigo
→ abre /scheduler/historical/
→ vê a mesma navegação com Buscar caso antigo ativo
→ busca histórica existente continua funcionando
```

## Escopo funcional

### R1. Navegação principal com três abas

Em `templates/scheduler/queue.html`, a navegação deve exibir:

```text
Pendentes | Processados Hoje | Buscar caso antigo
```

A aba `Buscar caso antigo` deve apontar para:

```django
{% url 'scheduler:historical_search' %}
```

O botão pequeno separado `🔍 Buscar histórico` deve ser removido.

### R2. Página histórica com a mesma navegação

Em `templates/scheduler/historical_search.html`, adicionar a navegação do agendador no bloco adequado, com `Buscar caso antigo` ativo.

A página deve continuar renderizando o formulário de busca e resultados já existentes.

### R3. DRY local opcional

Opção preferida se ficar simples: extrair partial pequeno:

```text
templates/scheduler/_nav.html
```

Contexto possível:

```django
scheduler_active_tab = "pending" | "processed" | "historical"
total_notice_count
processed_today_count
```

Uso esperado:

- `queue.html`: passa/usa `active_tab` existente ou mapeia para `scheduler_active_tab`.
- `historical_search.html`: marca `historical` ativo.

Mas se a extração exigir alterações desnecessárias em views/contextos, é aceitável duplicar poucas linhas de nav em `historical_search.html`, desde que o relatório justifique.

### R4. Badges

Manter badges existentes:

- `Pendentes` com `total_notice_count`;
- `Processados Hoje` com `processed_today_count`.

`Buscar caso antigo` não precisa de badge.

Se `historical_search.html` não tiver contadores disponíveis, duas opções aceitáveis:

1. montar contexto de contadores reutilizando `_scheduler_queue_context(user=request.user, tab="historical")` sem renderizar listas; ou
2. renderizar a nav histórica sem badges numéricos nessa página.

Preferência: consistência visual simples sem aumentar muito o custo de query. Se os testes exigirem badges apenas em `/scheduler/`, a página histórica pode mostrar as abas sem contadores.

### R5. Rótulo

Usar o texto:

```text
Buscar caso antigo
```

Não usar apenas ícone/lupa. Ícone pode permanecer complementar, mas o texto deve estar sempre visível.

## Fora de escopo

Não implementar neste slice:

- mudanças no detalhe do caso;
- mudanças em comunicação ao NIR;
- alterações em queryset da busca histórica;
- filtros avançados/período/paginação/export;
- novas permissões;
- alterações em `Case`/FSM;
- JS/HTMX novo.

## Arquivos esperados

Idealmente tocar apenas:

1. `templates/scheduler/queue.html`
2. `templates/scheduler/historical_search.html`
3. opcional: `templates/scheduler/_nav.html`
4. `apps/scheduler/tests/test_views.py`
5. `openspec/changes/fix-scheduler-processed-detail-and-history-tab/tasks.md`

Se precisar tocar `apps/scheduler/views.py` para passar contexto mínimo, justificar no relatório.

## TDD obrigatório

Adicione testes falhando antes da implementação.

### Testes mínimos sugeridos

1. `test_scheduler_queue_nav_has_historical_search_tab`
   - GET `/scheduler/` como scheduler;
   - assert contém `Pendentes`;
   - assert contém `Processados Hoje`;
   - assert contém `Buscar caso antigo`;
   - assert contém link para `/scheduler/historical/`;
   - assert não depende de hover/ícone isolado.

2. `test_scheduler_queue_no_small_standalone_historical_button`
   - GET `/scheduler/`;
   - assert não contém o bloco/botão antigo `🔍 Buscar histórico` ou classe de botão isolada, conforme HTML atual;
   - cuidado para não falhar apenas porque existe texto legítimo da aba. O alvo é o botão antigo, não a nova aba.

3. `test_scheduler_historical_search_nav_marks_historical_active`
   - GET `/scheduler/historical/`;
   - assert contém `Buscar caso antigo`;
   - assert o link/aba histórica tem classe `active` ou indicador equivalente.

4. `test_scheduler_historical_search_form_still_works`
   - preservar/ajustar teste existente de busca por ocorrência/nome;
   - garante que a inclusão da nav não quebrou resultados.

5. `test_scheduler_queue_pending_and_processed_tabs_still_work`
   - preservar testes existentes de `?tab=pending` e `?tab=processed`.

## Critérios de aceitação do slice

- [ ] TDD RED → GREEN → REFACTOR documentado no relatório.
- [ ] `/scheduler/` mostra três abas com texto visível.
- [ ] `Buscar caso antigo` aponta para `scheduler:historical_search`.
- [ ] Botão pequeno separado de busca histórica foi removido.
- [ ] `/scheduler/historical/` mostra a mesma navegação com aba histórica ativa.
- [ ] Busca histórica existente continua funcionando.
- [ ] Badges de pendentes/processados continuam funcionando onde já existiam.
- [ ] Nenhuma migration criada.
- [ ] Nenhuma regra de permissão/FSM alterada.
- [ ] `tasks.md` atualizado marcando este slice ao concluir.
- [ ] Quality gate executado.
- [ ] Relatório temporário criado e informado via `REPORT_PATH`.

## Gates de autoavaliação

Responder no relatório:

1. A navegação foi extraída para partial ou duplicada? Por quê?
2. Que teste prova que `Buscar caso antigo` é aba/link principal?
3. Que teste prova que a página histórica marca essa aba como ativa?
4. O botão antigo com lupa foi removido? Que teste ou snippet prova?
5. A busca histórica/query/permissão foi alterada? Esperado: não, salvo justificativa.
6. Alguma migration/FSM/model foi criado/alterado? Esperado: não.
7. Quais comandos de validação foram executados?

## Relatório obrigatório

Criar relatório markdown temporário em:

```text
/tmp/fix-scheduler-processed-detail-and-history-tab-slice-002-report.md
```

O relatório deve conter:

- resumo da mudança;
- arquivos tocados;
- evidência TDD RED/GREEN/REFACTOR;
- snippets antes/depois dos pontos principais;
- resposta aos gates de autoavaliação;
- comandos de validação e resultados;
- riscos/observações.

Responder ao planner com:

```text
REPORT_PATH=/tmp/fix-scheduler-processed-detail-and-history-tab-slice-002-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/fix-scheduler-processed-detail-and-history-tab/{proposal.md,design.md,tasks.md,slices/slice-002-historical-search-as-tab.md}.
Implement ONLY Slice 002. Assume Slice 001 is done.
Use TDD: write failing tests first for /scheduler/ showing three visible tabs, the old standalone search button removed, /scheduler/historical/ showing Buscar caso antigo active, and historical search still working.
Keep it lean: prefer templates/scheduler/queue.html, templates/scheduler/historical_search.html, optional small templates/scheduler/_nav.html, apps/scheduler/tests/test_views.py, and tasks.md only.
Do not change case detail, communication, permissions, models, migrations or FSM. Do not add JS or advanced search.
Apply clean code, DRY if a small nav partial helps, and YAGNI.
Run quality gate from AGENTS.md, update tasks.md, create /tmp/fix-scheduler-processed-detail-and-history-tab-slice-002-report.md with before/after snippets and gate answers, commit and push, then reply only with REPORT_PATH and stop.
```
