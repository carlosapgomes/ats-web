# Slice 001: Filtro dinâmico client-side na aba médica Pendentes

## Handoff para implementador com contexto zero

O sistema é um monolito Django SSR, sem API REST e sem SPA. O frontend deve continuar usando Bootstrap 5.3, templates Django, HTMX já existente e Vanilla JS. Não introduza React/Vue, bundler, DRF, endpoint novo ou dependência JS.

A tela médica principal fica em `/doctor/` e é implementada por:

- `apps/doctor/views.py::doctor_queue`
- `apps/doctor/views.py::doctor_queue_partial`
- `templates/doctor/queue.html`
- `templates/doctor/_queue_content.html`

A fila atual não tem paginação. Na aba `Pendentes`, todos os casos `WAIT_DOCTOR` são renderizados como cards. O card já mostra o nome do paciente e o número de ocorrência como `Reg. {{ c.agency_record_number }}`. O campo canônico do número de ocorrência é `Case.agency_record_number`.

O problema operacional: quando o NIR lança 50–60 relatórios, o médico precisa localizar rapidamente um paciente específico por nome ou ocorrência, sem procurar visualmente em toda a lista.

## Objetivo do slice

Implementar uma entrega vertical enxuta:

```text
Médico abre /doctor/ na aba Pendentes
→ digita nome ou ocorrência no campo de busca
→ cards pendentes são filtrados dinamicamente no navegador
→ UI mostra que o filtro está ativo e quantos pacientes aparecem
→ médico limpa com botão Limpar, Esc ou apagando o texto
→ todos os cards voltam
```

A solução deve ser client-side porque a fila atual não possui paginação. Não implementar busca server-side neste slice.

## Arquivos esperados

Idealmente tocar apenas:

1. `templates/doctor/queue.html`
2. `templates/doctor/_queue_content.html`
3. `static/js/doctor_queue_filter.js` (novo)
4. `apps/doctor/tests/test_views.py`

Evite tocar `apps/doctor/views.py`, `apps/doctor/urls.py`, modelos, migrations ou serviços. Se precisar tocar algo além desses arquivos, justifique claramente no relatório.

## Metodologia obrigatória

Siga TDD:

1. **RED** — primeiro adicione/ajuste testes que falham para o contrato HTML novo.
2. **GREEN** — implemente o mínimo para passar.
3. **REFACTOR** — limpe nomes/duplicações sem ampliar escopo.

Princípios:

- **Clean code**: nomes claros, funções JS pequenas e defensivas.
- **DRY**: não duplicar lógica de normalização/filtro.
- **YAGNI**: não criar server-side search, paginação, endpoint, localStorage, analytics ou framework de teste JS.
- **Escopo mínimo**: preservar queries, locks, FSM e fluxo de decisão médica.

## Requisitos funcionais

### R1. Controles de busca na aba Pendentes

Em `templates/doctor/queue.html`, adicionar bloco de busca somente quando `active_tab == 'pending'`.

Requisitos do bloco:

- label visível: `Buscar por nome ou ocorrência`;
- input `type="search"`;
- placeholder sugerido: `Digite nome do paciente ou nº da ocorrência`;
- atributo para JS, por exemplo `data-doctor-queue-search`;
- botão `Limpar` com `type="button"` e atributo `data-doctor-queue-clear`;
- área de status com `data-doctor-queue-filter-status` e `aria-live="polite"`;
- área de sem resultado com `data-doctor-queue-no-results`, inicialmente oculta.

O bloco deve ficar **fora** de `#doctor-queue-content`, pois esse container é substituído pelo polling HTMX a cada 20s. Isso preserva o texto digitado durante auto-refresh.

### R2. Contrato HTML dos cards pesquisáveis

Em `templates/doctor/_queue_content.html`, na raiz de cada card/coluna pendente, adicionar atributos `data-*` explícitos:

```django
<div class="col-12"
     data-doctor-queue-card
     data-patient-name="{{ c.patient_name }}"
     data-agency-record-number="{{ c.agency_record_number }}">
```

Não depender de parsing do texto visual do card.

Atributos devem ser adicionados apenas aos cards pendentes. Não é necessário filtrar `Decididos Hoje`.

### R3. Script Vanilla JS

Criar `static/js/doctor_queue_filter.js`.

Características:

- IIFE com `"use strict"`;
- sem dependências externas;
- se os elementos não existirem na página, retornar sem erro;
- normalizar texto com `String.prototype.normalize("NFD")` e remoção de diacríticos;
- comparar termo com `data-patient-name` e `data-agency-record-number` usando `includes`;
- alternar exibição dos cards com `hidden` ou `style.display = "none"`;
- atualizar status com contagem visível/total;
- exibir/esconder botão `Limpar` conforme houver texto;
- exibir mensagem de sem resultados quando filtro válido não encontrar cards;
- tecla `Esc` limpa o filtro quando o input está focado;
- evento `input` filtra dinamicamente;
- evento `htmx:afterSwap` reaplica filtro quando `event.target.id === "doctor-queue-content"`;
- não usar URL/query string, storage, cookie ou sessão.

### R4. Limiar de filtragem

Para nomes:

- se o termo contém letras e tem menos de 3 caracteres normalizados, não filtrar;
- mostrar todos os cards;
- status pode orientar: `Digite pelo menos 3 letras para filtrar por nome.`.

Para ocorrência:

- se o termo não contém letras, permitir filtro a partir de 1 caractere;
- isso permite buscar diretamente por `agency_record_number`.

### R5. Limpeza operacional

O médico não deve precisar apagar letra por letra.

O filtro deve ser removido por:

1. clicar no botão `Limpar`;
2. pressionar `Esc` no campo;
3. apagar todo o texto manualmente.

Após limpar:

- todos os cards voltam;
- status volta para estado neutro, por exemplo `Mostrando todos os 58 pacientes pendentes.`;
- mensagem de sem resultado desaparece;
- botão `Limpar` pode ficar oculto ou desabilitado.

### R6. Não persistir filtro ao sair/voltar

Não guardar o termo em localStorage/sessionStorage/cookie/sessão. Se o médico clicar em `Avaliar`, sair da tela e depois voltar para a fila, ela deve abrir sem filtro. Isso evita a falsa impressão de que a fila tem menos pacientes.

## TDD obrigatório

Antes de implementar o HTML/JS, adicionar testes falhando em `apps/doctor/tests/test_views.py`.

### Testes mínimos server-side

1. `test_pending_queue_renders_search_controls`
   - GET `/doctor/?tab=pending` como doctor;
   - assert contém `Buscar por nome ou ocorrência`;
   - assert contém `data-doctor-queue-search`;
   - assert contém `data-doctor-queue-clear`;
   - assert contém `doctor_queue_filter.js`.

2. `test_decided_tab_does_not_render_pending_search_controls`
   - GET `/doctor/?tab=decided` como doctor;
   - assert não contém `data-doctor-queue-search`;
   - assert não contém `Buscar por nome ou ocorrência`.

3. `test_pending_cards_expose_search_data_attributes`
   - criar caso `WAIT_DOCTOR` com `structured_data.patient.name = "João da Silva"` e `agency_record_number = "123456"`;
   - GET `/doctor/?tab=pending`;
   - assert contém `data-doctor-queue-card`;
   - assert contém `data-patient-name="João da Silva"`;
   - assert contém `data-agency-record-number="123456"`.

4. `test_queue_hx_get_preserves_active_tab_with_search_controls`
   - GET `/doctor/?tab=pending`;
   - assert contém `hx-get="/doctor/partials/queue/?tab=pending"` ou equivalente gerado por `{% url 'doctor:queue_partial' %}?tab={{ active_tab }}`.

### Verificação manual obrigatória do JS

Como não há browser test runner no projeto, registrar no relatório uma verificação manual/estática do comportamento JS:

- filtro por nome com acento: `joao` encontra `João`;
- filtro por ocorrência encontra `agency_record_number`;
- `Limpar` restaura todos os cards;
- `Esc` restaura todos os cards;
- `htmx:afterSwap` chama reaplicação sem erro.

Não introduza framework de teste JS neste slice.

## Critérios de aceitação

- [ ] Campo de busca aparece somente em `Pendentes`.
- [ ] Campo usa label claro e placeholder operacional.
- [ ] Cards pendentes têm atributos `data-patient-name` e `data-agency-record-number`.
- [ ] Filtro client-side compara nome e ocorrência.
- [ ] Busca por nome é case-insensitive e accent-insensitive.
- [ ] Menos de 3 letras não reduz a lista; status orienta o usuário.
- [ ] Ocorrência pode filtrar a partir de 1 caractere.
- [ ] Botão `Limpar` limpa o filtro.
- [ ] Tecla `Esc` limpa o filtro.
- [ ] Apagar todo o texto limpa o filtro.
- [ ] Status mostra filtro ativo e contagem visível/total.
- [ ] Sem resultados mostra mensagem clara.
- [ ] Auto-refresh HTMX reaplica o filtro enquanto o usuário fica na página.
- [ ] Não há persistência do filtro fora da página atual.
- [ ] Nenhum endpoint, rota, model, migration, lock ou FSM foi alterado.

## Gates de autoavaliação

Responder no relatório antes de finalizar:

1. A busca é client-side apenas? Quais arquivos provam que nenhum endpoint/rota novo foi criado?
2. O filtro fica fora de `#doctor-queue-content` para sobreviver ao auto-refresh? Onde?
3. Como o médico limpa o filtro sem apagar letra por letra?
4. O filtro é persistido em URL/storage/sessão? A resposta correta é não.
5. Qual teste prova que a aba `Decididos Hoje` não recebeu o filtro?
6. Qual teste prova que os cards expõem `agency_record_number` para busca?
7. O script JS falha silenciosamente/retorna se os elementos não existem?
8. O que acontece após `htmx:afterSwap`?
9. Se houver paginação no futuro, esta solução ainda buscará fora da página carregada? A resposta correta é não; documentar limitação aceita e necessidade de change server-side futuro.

## Comandos de validação

Executar ao final:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

Também rodar pelo menos os testes médicos relevantes durante o ciclo:

```bash
uv run pytest apps/doctor/tests/test_views.py -q
```

## Relatório obrigatório

Criar relatório markdown temporário para revisão por terceiro LLM, por exemplo:

```text
/tmp/doctor-pending-queue-quick-filter-slice-001-report.md
```

O relatório deve conter:

- resumo do que foi implementado;
- lista de arquivos alterados;
- evidência RED/GREEN/REFACTOR;
- snippets antes/depois dos templates e do JS novo;
- resultados dos comandos de validação;
- respostas aos gates de autoavaliação;
- limitações aceitas, incluindo ausência de busca server-side/paginação;
- confirmação de commit e push.

Ao responder, retornar:

```text
REPORT_PATH=/tmp/doctor-pending-queue-quick-filter-slice-001-report.md
```

E parar, aguardando confirmação explícita para qualquer próximo slice.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/doctor-pending-queue-quick-filter/proposal.md, design.md, tasks.md and slices/slice-001-client-side-pending-filter.md.

Implement ONLY Slice 001. Use a vertical, lean slice. Prefer touching only templates/doctor/queue.html, templates/doctor/_queue_content.html, static/js/doctor_queue_filter.js and apps/doctor/tests/test_views.py.

Follow TDD: first add failing tests for the HTML contract in apps/doctor/tests/test_views.py, then implement the minimal template/JS changes, then refactor safely. Keep clean code, DRY helpers and YAGNI. Do not implement server-side search, pagination, endpoint, route, model, migration, localStorage/sessionStorage/cookies, or any FSM/lock/decision change.

Add a pending-tab search UI outside #doctor-queue-content so HTMX polling does not erase the typed term. Add explicit data attributes to pending cards for patient name and agency_record_number. Create static/js/doctor_queue_filter.js using Vanilla JS to filter dynamically by normalized patient name or occurrence, show visible/total status, show no-results, support Limpar, support Esc, and reapply after htmx:afterSwap for #doctor-queue-content. Do not show the filter on Decididos Hoje.

Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/doctor-pending-queue-quick-filter/tasks.md when complete.
Create /tmp/doctor-pending-queue-quick-filter-slice-001-report.md with before/after snippets, TDD evidence, validation results, accepted limitations and answers to all self-evaluation gates.
Commit and push the current branch.
Return REPORT_PATH=/tmp/doctor-pending-queue-quick-filter-slice-001-report.md and STOP.
```
