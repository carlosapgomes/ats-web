<!-- markdownlint-disable MD013 -->

# Slice 001: Polimento UX do dashboard

## Contexto zero para implementador

O dashboard gerencial fica em `/dashboard/` e é implementado principalmente em:

- `apps/dashboard/views.py`
- `templates/dashboard/index.html`
- `apps/dashboard/tests/test_dashboard.py`

Hoje existem dois problemas simples:

1. `_fmt_duration()` retorna tudo em minutos, o que torna valores como
   `1100 min` pouco intuitivos.
2. Os inputs `date_from` e `date_to` do card "Todos os Casos" usam apenas
   placeholder. Em Android/mobile, inputs `type="date"` frequentemente não
   exibem placeholder.

Leia antes de implementar:

- `AGENTS.md`
- `PROJECT_CONTEXT.md`
- `openspec/changes/dashboard-metrics-search-ux/proposal.md`
- `openspec/changes/dashboard-metrics-search-ux/design.md`
- `openspec/changes/dashboard-metrics-search-ux/tasks.md`
- este slice

## Objetivo do slice

Entregar fluxo vertical completo:

```text
Manager/admin abre dashboard
→ vê labels explícitas para datas em "Todos os Casos"
→ vê tempos médios em minutos quando curtos
→ vê tempos médios em horas/minutos quando longos
```

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/dashboard/views.py`
2. `templates/dashboard/index.html`
3. `apps/dashboard/tests/test_dashboard.py`

Se precisar tocar outro arquivo, justificar no relatório.

## Requisitos funcionais

### R1. Duração humana no card "Tempo médio"

Atualizar `_fmt_duration()` para retornar:

| Caso | Saída |
| --- | --- |
| valor ausente | `—` |
| menos de 60 minutos | `N min` |
| exatamente 60 minutos | `1 h` |
| 65 minutos | `1 h 05 min` |
| 1100 minutos | `18 h 20 min` |

Critérios adicionais:

- preservar arredondamento por piso para minutos inteiros, se já era assim;
- não criar template tag nova;
- manter helper pequeno, puro e testável;
- tratar `timedelta(0)` como `0 min`, não como ausente.

### R2. Labels visíveis nos filtros de data

No formulário de "Todos os Casos", adicionar labels visíveis para:

- `date_from`: `Data inicial`
- `date_to`: `Data final`

Os labels devem usar `for`/`id` corretamente. Placeholders podem permanecer como
apoio, mas não devem ser a única identificação do campo.

### R3. Não alterar filtros ou métricas ainda

Este slice não deve:

- adicionar seletor `metrics_date`;
- criar busca por nome/registro;
- alterar paginação;
- alterar permissões ou FSM.

## TDD obrigatório

Antes de implementar, adicionar testes falhando.

Testes mínimos:

1. `_fmt_duration(None)` retorna `—`.
2. `_fmt_duration(timedelta(minutes=59))` retorna `59 min`.
3. `_fmt_duration(timedelta(minutes=60))` retorna `1 h`.
4. `_fmt_duration(timedelta(minutes=65))` retorna `1 h 05 min`.
5. `_fmt_duration(timedelta(minutes=1100))` retorna `18 h 20 min`.
6. GET `/dashboard/` como manager contém labels `Data inicial` e `Data final`.
7. HTML associa labels aos inputs por `for="..."` e `id="..."`.

## Critérios de sucesso

- [ ] Testes foram escritos antes da implementação e falharam inicialmente.
- [ ] Durações menores que 60 minutos continuam em minutos.
- [ ] Durações de 60 minutos ou mais aparecem em horas/minutos.
- [ ] `timedelta(0)` aparece como `0 min`.
- [ ] Inputs de data têm labels visíveis e acessíveis.
- [ ] Layout Bootstrap continua responsivo.
- [ ] Nenhuma funcionalidade fora do slice foi alterada.
- [ ] Quality gate do `AGENTS.md` passa.

## Gates de autoavaliação

Responder no relatório do slice:

1. Qual teste prova que `1100 min` virou formato em horas?
2. Qual teste prova que `timedelta(0)` não virou `—`?
3. Os labels são visíveis ou apenas `visually-hidden`? Por quê?
4. Quais arquivos foram tocados e por quê?
5. Houve alteração de query, FSM ou permissão? Se sim, está errado.
6. O relatório contém snippets antes/depois dos pontos principais?

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/dashboard-metrics-search-ux/proposal.md, design.md, tasks.md and slices/slice-001-dashboard-ux-polish.md.
Implement ONLY Slice 001.
Use TDD: first add failing tests for _fmt_duration and date input labels, then implement the minimal code.
Follow clean code, DRY and YAGNI. Do not introduce a template tag or generic formatter framework.
Expected files: apps/dashboard/views.py, templates/dashboard/index.html and apps/dashboard/tests/test_dashboard.py.
Do not add metrics_date, search, JavaScript, migrations or new pages in this slice.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Create a detailed temporary markdown report with before/after snippets and self-evaluation answers.
Run markdownlint-cli2 only on markdown files you create, such as the temporary report. Do not lint or rewrite existing markdown broadly.
Commit and push only implementation files created/changed for this slice. Do not commit OpenSpec files before final archival of the change.
Return REPORT_PATH=<path> and stop. Do not start the next slice without explicit confirmation.
```
