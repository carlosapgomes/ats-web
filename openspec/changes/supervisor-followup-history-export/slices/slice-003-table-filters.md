# Slice 003 — Filtros de linha (desfecho/causa/internação) na tabela e no CSV

## Objetivo

Comportamento observável: a página Histórico ganha filtros de linha — `?performed=yes|no`, `?reason=absenteeism|resource_shortage|other`, `?admitted=yes|no` — que filtram a **tabela** e o **CSV exportado**, sem alterar os cards-resumo (que continuam resumindo janela+busca; design D4). `performed`/`reason` filtram linhas de desfecho de procedimento; `admitted` filtra casos inteiros. Valores inválidos são ignorados (equivale a "todos"). Os controles ficam no form de filtros (GET) e persistem o estado selecionado.

## Contexto necessário (ler antes de editar)

- Slices 001/002 aplicados: página Histórico com janela/busca/cards/tabela + export; helper(s) que compõem as linhas exibidas e exportadas (fonte comum).
- Labels das choices de causa: `FollowUpNonPerformanceReason` (`apps/cases/models.py`).
- Design: seção **D4** (cards × filtros de linha; assimetria documentada) de `../design.md`.
- Spec: requirements "filtros de linha" (scenarios "Filtro por causa mantém cards intactos" e "Filtro por internação remove casos inteiros").

## Requisitos verificáveis

- **R1** — `?performed=yes`/`no` filtra linhas da tabela e do CSV por desfecho; valor inválido/ausente = sem filtro. Labels humanos no controle (`Realizado`/`Não realizado`/`Todos`).
- **R2** — `?reason=<choice>` filtra linhas por causa (`absenteeism`/`resource_shortage`/`other`); inválido/ausente = sem filtro; labels humanos.
- **R3** — `?admitted=yes`/`no` remove/adiciona **casos inteiros** (todas as linhas do caso), na tabela e no CSV; inválido/ausente = sem filtro.
- **R4** — Cards-resumo NÃO mudam com filtros de linha (permanecem função de janela+busca) — comprovado por teste.
- **R5** — Controles no form (3 selects `btn-sm`, `method="get"`, mesmos `name`s) com estado persistido e opção explícita "Todos"; submeter mantém os demais params (`start/end/q`).
- **R6** — Combinação: filtros compõem entre si e com janela/busca na mesma querystring (tabela e CSV concordam — teste com `performed+reason` combinados e exportação conferida).

## Matriz requisito → arquivo(s) → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1–R3 | `apps/dashboard/views.py` (parsing/filtragem das linhas/casos) | `pytest apps/dashboard/tests/test_followup_history.py -k "filter_performed or filter_reason or filter_admitted"` (novos) |
| R1–R3 (inválidos) | `apps/dashboard/views.py` | `... -k filter_invalid_values` (novo, parametrizado: `?performed=banana`, `?reason=xyz`, `?admitted=talvez` → tabela E CSV idênticos à ausência dos filtros; cards idênticos) |
| R4 | `apps/dashboard/views.py` | `... -k filter_keeps_cards` (novo) |
| R5 | `templates/dashboard/followup_history.html` | `... -k "filter_controls or filter_persist"` (novo; HTML) |
| R6 | `apps/dashboard/views.py` | `... -k "filter_combo or export_filters"` (novo) |

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/dashboard/views.py                        # parsing + filtragem
  - templates/dashboard/followup_history.html      # controles no form
  - apps/dashboard/tests/test_followup_history.py  # + testes R1–R6

allowed_incidental_files: []

out_of_scope:
  - submotivo (`resource_shortage_detail`) como filtro
  - qualquer mudança nos cards (R4 os congela como função de janela+busca)
  - aba Registrar, models/migrations, JS, tasks.md/commit/push (parent)
```

Escale se: a implementação exigir mudar contrato dos helpers dos slices anteriores de forma estrutural.

## Plano de testes do slice

### RED

Ordem: escreva os testes novos primeiro (arquivo já existe desde os slices anteriores). Com os testes escritos:

- `uv run pytest apps/dashboard/tests/test_followup_history.py -k filter -q` → falham porque os filtros ainda não existem (linhas sem filtrar; valores inválidos ainda não são ignorados por design).

### GREEN / verificação local

```bash
uv run pytest apps/dashboard/tests/test_followup_history.py -q   # exit 0
uv run pytest apps/dashboard/tests -q                            # exit 0
uv run ruff check apps/dashboard && uv run ruff format --check apps/dashboard  # exit 0
```

## Critérios de aceitação

- [ ] R1–R6 verdes; tabela e CSV concordam sob os mesmos params (teste direto).
- [ ] Cards inalterados pelos filtros de linha (teste direto).
- [ ] Diff dentro do blast radius.
