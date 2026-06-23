# Slice 002: Labels downstream alinhados

## Contexto zero para implementador

Leia primeiro:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/clarify-doctor-writing-ux/proposal.md`
4. `openspec/changes/clarify-doctor-writing-ux/design.md`
5. `openspec/changes/clarify-doctor-writing-ux/tasks.md`
6. `openspec/changes/clarify-doctor-writing-ux/slices/slice-001-decisao-medica-sem-ambiguidade.md`
7. Este arquivo

O Slice 001 deve ter mudado a semântica da UI médica: `doctor_observation` deixou de ser uma observação genérica e passou a representar **orientações médicas vinculadas ao aceite**, para agendamento/execução.

Este slice não muda storage nem regras de decisão. Ele alinha a nomenclatura nas telas downstream para NIR, agendador, supervisor e admin.

## Objetivo do slice

Entregar uma mudança vertical de consistência downstream:

```text
NIR/agendador/supervisor/admin visualizam casos aceitos com doctor_observation → a UI chama o conteúdo de Orientação médica/Orientações médicas → ninguém vê mais Observação Médica genérica fora da tela médica
```

## Arquivos esperados

Tocar idealmente apenas templates e testes existentes:

1. `templates/intake/_my_cases_content.html`
2. `templates/intake/case_detail.html`
3. `templates/scheduler/_queue_content.html`
4. `templates/scheduler/confirm.html`
5. `templates/scheduler/confirm_post_schedule_issue.html`
6. testes existentes em:
   - `apps/intake/tests/test_my_cases.py`
   - `apps/intake/tests/test_case_detail.py`
   - `apps/scheduler/tests/test_views.py`
   - `apps/dashboard/tests/test_dashboard.py`

Se `rg "Observação Médica|Obs\. médica|Observação médica" templates apps -g '*.html' -g '*.py'` encontrar outras ocorrências visíveis ao usuário relacionadas a `doctor_observation`, avaliar inclusão neste slice e justificar no relatório.

Não tocar modelo, migrations, FSM, services de comunicação, views ou queries salvo se um teste provar necessidade real.

## Requisitos funcionais

### R1. NIR — listagem

Em `templates/intake/_my_cases_content.html`, trocar badge:

De:

```text
📝 Obs. médica
```

Para:

```text
📝 Orientação médica
```

Manter a condição atual baseada em `item.has_doctor_observation`.

### R2. NIR + supervisor/admin — detalhe compartilhado

Em `templates/intake/case_detail.html`, trocar título do card:

De:

```text
📝 Observação Médica
```

Para:

```text
📝 Orientações médicas
```

Manter:

- renderização apenas quando `case.has_doctor_observation`;
- preservação de quebras de linha;
- uso do mesmo template para NIR e dashboard manager/admin.

### R3. Agendador — fila

Em `templates/scheduler/_queue_content.html`, trocar labels/badges visíveis:

- `📝 Obs. médica` → `📝 Orientação médica`
- `📝 Observação médica:` → `📝 Orientação médica:` ou `📝 Orientações médicas:`

Manter a lógica para pendentes e vinda imediata.

### R4. Agendador — confirmação/ciência operacional

Em:

- `templates/scheduler/confirm.html`
- `templates/scheduler/confirm_post_schedule_issue.html`

trocar label:

De:

```text
Observação Médica
```

Para:

```text
Orientações médicas
```

Manter a condição `case.has_doctor_observation`.

### R5. Não alterar lógica

Este slice é de nomenclatura/UX downstream. Não alterar:

- `Case.doctor_observation`;
- `Case.has_doctor_observation`;
- queries/listas;
- fluxo de agendamento;
- comunicação operacional;
- eventos.

## TDD obrigatório

Antes de implementar, ajustar/adicionar testes para falhar com a nomenclatura antiga e passar com a nova.

### Testes mínimos

1. `apps/intake/tests/test_my_cases.py`
   - Atualizar teste de badge para esperar `Orientação médica`.
   - Provar que badge ainda aparece somente quando há conteúdo.

2. `apps/intake/tests/test_case_detail.py`
   - Atualizar teste do detalhe para esperar `Orientações médicas`.
   - Provar que o texto completo ainda aparece.
   - Provar que card vazio não aparece.

3. `apps/dashboard/tests/test_dashboard.py`
   - Atualizar teste manager/admin para esperar `Orientações médicas` no detalhe compartilhado.
   - Provar que continua oculto quando vazio.

4. `apps/scheduler/tests/test_views.py`
   - Atualizar testes da fila para esperar `Orientação médica`.
   - Atualizar teste da tela de confirmação para esperar `Orientações médicas`.
   - Provar que o texto completo ainda aparece e que casos vazios não renderizam card.

5. Busca de regressão textual
   - Pode ser teste automatizado simples ou evidência no relatório usando:

```bash
rg "Observação Médica|Obs\. médica|Observação médica" templates apps -g '*.html' -g '*.py'
```

O resultado não deve conter labels visíveis ao usuário para `doctor_observation`. Se restarem ocorrências em testes antigos, comentários ou contexto não relacionado, justificar.

## Critérios de sucesso

- [ ] TDD seguido: testes atualizados falham antes da troca de labels e passam depois.
- [ ] NIR vê `Orientação médica` na listagem quando há `doctor_observation`.
- [ ] NIR vê card `Orientações médicas` no detalhe.
- [ ] Manager/admin veem `Orientações médicas` via detalhe compartilhado.
- [ ] Agendador vê `Orientação médica` na fila.
- [ ] Agendador vê `Orientações médicas` na tela de confirmação e ciência operacional.
- [ ] Casos sem `doctor_observation` continuam sem badge/card vazio.
- [ ] Nenhuma lógica de negócio, modelo, migration, FSM ou comunicação operacional foi alterada.
- [ ] Quality gate do AGENTS.md passa ou eventual falha externa é documentada.

## Gates de autoavaliação

Responder no relatório temporário:

1. `rg "Observação Médica|Obs\. médica|Observação médica"` ainda encontra labels visíveis ao usuário? Se sim, onde e por quê?
2. Quais templates downstream foram alterados?
3. Alguma view/service/model/migration foi alterada? Se sim, justificar; o esperado é não alterar.
4. Como os testes provam que casos sem orientação não exibem badge/card vazio?
5. Como os testes provam que NIR, scheduler e dashboard continuam vendo o texto completo quando preenchido?
6. A nomenclatura escolhida é consistente entre badge e card?

## Relatório obrigatório

Ao concluir, criar um arquivo markdown temporário, por exemplo:

```text
/tmp/clarify-doctor-writing-ux-slice-002-report.md
```

O relatório deve conter:

- resumo do que mudou;
- lista de arquivos tocados;
- snippets antes/depois dos labels principais;
- evidência TDD: quais testes falharam antes e passaram depois;
- resultado da busca textual por nomenclatura antiga;
- respostas aos gates de autoavaliação;
- comandos de quality gate executados e resultados.

Responder ao usuário/planner com:

```text
REPORT_PATH=/tmp/clarify-doctor-writing-ux-slice-002-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/clarify-doctor-writing-ux/proposal.md, design.md, tasks.md, slices/slice-001-decisao-medica-sem-ambiguidade.md and slices/slice-002-labels-downstream-alinhados.md.
Implement ONLY Slice 002.
Use a vertical, lean slice. Prefer touching only downstream templates and existing tests. Do not alter models, migrations, FSM, communication services, notifications, queues or business logic unless a failing test proves it is necessary.
Follow TDD: first update tests to expect the new downstream nomenclature, see them fail, then change templates minimally, then refactor safely.
Apply clean code, DRY, YAGNI. This is a UX/text consistency slice, not a data model slice.
Replace user-visible doctor_observation labels downstream: Obs. médica/Observação Médica/Observação médica → Orientação médica/Orientações médicas as appropriate.
Keep all existing conditions: only show badge/card when has_doctor_observation is true and preserve full text rendering.
Run: rg "Observação Médica|Obs\\. médica|Observação médica" templates apps -g '*.html' -g '*.py' and document remaining occurrences, if any.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/clarify-doctor-writing-ux/tasks.md for Slice 002 and DoD when complete.
Create /tmp/clarify-doctor-writing-ux-slice-002-report.md with before/after snippets, TDD evidence, rg result, quality gate results and self-evaluation gate answers.
Commit and push.
Return REPORT_PATH=/tmp/clarify-doctor-writing-ux-slice-002-report.md and STOP.
```
