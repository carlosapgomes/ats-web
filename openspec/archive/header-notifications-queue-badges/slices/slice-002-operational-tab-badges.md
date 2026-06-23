# Slice 002: Badges semânticos nas abas médico/agendador

## Handoff para implementador com contexto zero

Leia primeiro:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/header-notifications-queue-badges/proposal.md`
4. `openspec/changes/header-notifications-queue-badges/design.md`
5. `openspec/changes/header-notifications-queue-badges/tasks.md`
6. Este arquivo

Pré-requisito recomendado: Slice 001 deste change concluído, pois ele separa visualmente notificações pessoais do header. Este slice trata apenas de contadores nas abas operacionais.

Contexto atual:

- `templates/doctor/queue.html` usa `.notif-badge` para `Pendentes` e `Decididos Hoje`.
- `templates/scheduler/queue.html` usa `.notif-badge` para `Pendentes`.
- `.notif-badge::after` em `static/css/app.css` é vermelho.
- Vermelho é adequado para pendências/ação, mas não para itens já concluídos (`Decididos Hoje`, `Processados Hoje`).
- `apps/scheduler/views.py` já calcula e passa `processed_today_count`, mas `templates/scheduler/queue.html` ainda não mostra contador em `Processados Hoje`.

## Objetivo do slice

Entregar verticalmente:

```text
Médico abre fila → vê Pendentes com contador de ação e Decididos Hoje com contador neutro
Agendador abre fila → vê Pendentes com contador de ação e Processados Hoje com contador neutro
```

Sem alterar lógica de contagem, modelos ou queries.

## Arquivos esperados

Idealmente tocar apenas:

1. `static/css/app.css`
2. `templates/doctor/queue.html`
3. `templates/scheduler/queue.html`
4. `apps/doctor/tests/test_views.py`
5. `apps/scheduler/tests/test_views.py`

Se precisar tocar outros arquivos, justifique no relatório do slice.

## Requisitos funcionais

### R1. Criar classes semânticas para contadores de abas

Em `static/css/app.css`, criar classes específicas para contador de aba operacional, por exemplo:

```css
.nav-count-badge {
  position: relative;
}

.nav-count-badge::after {
  content: attr(data-count);
  position: absolute;
  top: -6px;
  right: -10px;
  font-size: 0.7rem;
  font-weight: 700;
  min-width: 18px;
  height: 18px;
  line-height: 18px;
  text-align: center;
  border-radius: 999px;
  padding: 0 4px;
}

.nav-count-badge--danger::after {
  background: #e74c3c;
  color: #fff;
}

.nav-count-badge--neutral::after {
  background: #6c757d;
  color: #fff;
}

.nav-count-badge:not([data-count])::after,
.nav-count-badge[data-count="0"]::after {
  display: none;
}
```

Nomes exatos podem variar, mas devem expressar semântica clara e passar nos testes. Evite reutilizar `.notif-badge` nas abas operacionais.

### R2. Médico: `Pendentes` ação, `Decididos Hoje` neutro

Em `templates/doctor/queue.html`:

- substituir `.notif-badge` por classe operacional no link `Pendentes`;
- usar variante de ação/vermelha em `Pendentes`;
- substituir `.notif-badge` por classe operacional no link `Decididos Hoje`;
- usar variante neutra em `Decididos Hoje`;
- manter `data-count="{{ pending_count }}"` e `data-count="{{ decided_count }}"`.

### R3. Agendador: `Pendentes` ação, `Processados Hoje` neutro

Em `templates/scheduler/queue.html`:

- substituir `.notif-badge` por classe operacional no link `Pendentes`;
- usar variante de ação/vermelha em `Pendentes`;
- manter `data-count="{{ total_notice_count }}"` em `Pendentes`;
- adicionar classe operacional e `data-count="{{ processed_today_count }}"` no link `Processados Hoje`;
- usar variante neutra em `Processados Hoje`.

`processed_today_count` já é calculado por `_scheduler_queue_context`; não altere query nem view salvo se um teste demonstrar ausência real do contexto.

### R4. Não alterar NIR

Não adicionar contadores em templates NIR:

- `templates/intake/intake_home.html`
- `templates/intake/my_cases.html`
- `templates/intake/case_detail.html`
- `templates/intake/closed_cases_search.html`
- `templates/intake/post_schedule_issue_form.html`

Se algum arquivo NIR for tocado, justificar no relatório. A expectativa é não tocar.

### R5. Não mexer em notificações pessoais

Não alterar `templates/base.html`, `templates/accounts/notifications.html` nem `static/js/notifications.js` neste slice, salvo correção mínima justificada por conflito com Slice 001.

## TDD obrigatório

Antes de implementar, adicionar/ajustar testes que falhem.

### Testes mínimos sugeridos

Em `apps/doctor/tests/test_views.py`:

1. `test_queue_nav_uses_action_and_neutral_count_badges`
   - login como doctor;
   - GET `/doctor/`;
   - assert link `Pendentes` contém `data-count` e classe operacional de ação;
   - assert link `Decididos Hoje` contém `data-count` e classe operacional neutra;
   - assert link `Decididos Hoje` não usa `.notif-badge`.

2. Se já existir teste de navegação de `Decididos Hoje`, pode ser ajustado para incluir os asserts acima, evitando duplicação excessiva.

Em `apps/scheduler/tests/test_views.py`:

3. `test_queue_nav_uses_action_and_neutral_count_badges`
   - login como scheduler;
   - GET `/scheduler/`;
   - assert link `Pendentes` contém `data-count` e classe operacional de ação;
   - assert link `Processados Hoje` contém `data-count` e classe operacional neutra;
   - assert link `Processados Hoje` não usa `.notif-badge`.

4. `test_processed_today_nav_badge_uses_processed_today_count`
   - criar caso processado hoje pelo scheduler logado;
   - GET `/scheduler/`;
   - assert o link `Processados Hoje` possui `data-count="1"`.

Teste estático opcional em um dos arquivos de teste, se o projeto já usa esse padrão:

5. Verificar `static/css/app.css` contém classes operacional danger e neutral.

## Critérios de aceitação

- [ ] TDD seguido: testes novos/ajustados falham antes da implementação e passam após.
- [ ] `templates/doctor/queue.html` não usa `.notif-badge` nas abas.
- [ ] `Pendentes` médico tem contador com semântica de ação.
- [ ] `Decididos Hoje` médico tem contador com semântica neutra.
- [ ] `templates/scheduler/queue.html` não usa `.notif-badge` nas abas.
- [ ] `Pendentes` agendador tem contador com semântica de ação.
- [ ] `Processados Hoje` agendador tem `data-count="{{ processed_today_count }}"` e semântica neutra.
- [ ] Nenhuma query ou regra de negócio de fila foi alterada.
- [ ] Templates NIR não foram alterados.
- [ ] Quality gate do AGENTS.md executado.

## Gates de autoavaliação para relatório

Responder no relatório markdown temporário:

1. Quais classes CSS representam contador de ação e contador neutro?
2. Qual teste prova que `Decididos Hoje` usa contador neutro?
3. Qual teste prova que `Processados Hoje` usa `processed_today_count`?
4. As abas ainda usam `.notif-badge`? Se sim, por quê?
5. Algum template NIR foi alterado? Se sim, por quê?
6. Alguma query/view de contagem foi alterada? Se sim, justifique.
7. Quantos arquivos foram tocados e por que esse número é necessário?

## Relatório obrigatório

Criar um relatório temporário em markdown, por exemplo:

```text
/tmp/ats-web-header-notifications-queue-badges-slice-002-report.md
```

O relatório deve conter:

- resumo do slice;
- evidência RED: testes falhando antes da implementação;
- evidência GREEN: testes passando após implementação;
- snippets antes/depois dos trechos principais;
- respostas aos gates de autoavaliação;
- comandos de validação executados e resultado;
- arquivos tocados e justificativa;
- riscos residuais, se houver.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/header-notifications-queue-badges/proposal.md, design.md, tasks.md and slices/slice-002-operational-tab-badges.md.

Implement ONLY Slice 002. Use TDD: first add/adjust failing tests, then implement minimal code. Keep it clean, DRY and YAGNI. Do not change models, migrations, queue queries, notification polling, header notification icon or NIR templates. Create semantic CSS classes for operational tab counters: one for action/pending and one neutral for already completed items. Update doctor queue tabs so Pendentes uses action counter and Decididos Hoje uses neutral counter. Update scheduler queue tabs so Pendentes uses action counter and Processados Hoje shows processed_today_count with neutral counter. Avoid using .notif-badge for operational tabs.

Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/header-notifications-queue-badges/tasks.md when complete for Slice 002 only.
Create /tmp/ats-web-header-notifications-queue-badges-slice-002-report.md with RED/GREEN evidence, before/after snippets, quality gate results and self-evaluation answers.
Commit and push. Reply with REPORT_PATH=/tmp/ats-web-header-notifications-queue-badges-slice-002-report.md and stop.
```
