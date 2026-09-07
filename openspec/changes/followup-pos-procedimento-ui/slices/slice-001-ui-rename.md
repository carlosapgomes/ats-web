# Slice 001 — Rename completo na UI: "follow-up" → "Pós-Procedimento"

## Objetivo

Todo rótulo visível ao usuário que hoje diz "Follow-up"/"follow-up" passa a
dizer "Pós-Procedimento"/"pós-procedimento" (regra tipográfica D1), nos 5
templates do dashboard, na flash message de sucesso e nos labels da timeline
do caso, com asserts convertidos e teste de varredura anti-regresso sobre
texto visível.

## Contexto necessário

- Design: D1 (regra tipográfica), D2 (inventário), D5 (metodologia de testes e
  critério grep) de `openspec/changes/followup-pos-procedimento-ui/design.md`.
- Templates: `templates/dashboard/{_nav,_followup_tabs,followup_list,followup_form,followup_history}.html`.
- Flash: `apps/dashboard/views.py` ~:2008 ("Follow-up registrado (versão {n})…").
- Timeline: `apps/intake/views.py:343-344` — `EVENT_LABELS` de
  `FOLLOWUP_RECORDED`/`FOLLOWUP_UPDATED` ("Follow-up registrado/atualizado"),
  render-time na timeline de `case_detail` (template compartilhado com o
  dashboard). Sem migration: `CaseEvent` armazena `event_type`; eventos
  antigos passam a exibir o rótulo novo.
- Testes: 4 asserts com "Follow-up" (`test_followup_list_view.py:302,304,346`,
  `test_followup_form_view.py:381`) + docstrings/comentários (higiene) + a
  fixture `"Com Follow-up"` (`test_followup_history.py:266`, renomear — ver D5).
- **Não renomear**: URLs (`/dashboard/follow-ups/`), names de rotas, ids/classes
  CSS, `data-*` attributes, nomes de arquivos de template, filename do CSV
  (`followups_*.csv`), comentários de código.

## Requisitos verificáveis

- R1 Inventário D2 integralmente convertido com a capitalização correta por
  contexto (Title Case em título/pill; minúsculo no meio de frase), incluindo
  os 2 labels da timeline em `apps/intake/views.py`.
- R2 Flash message usa "Pós-procedimento registrado (versão {n})…".
- R3 Os 4 asserts existentes convertidos; docstrings/comentários dos testes
  acompanham o rename; fixture `"Com Follow-up"` renomeada para nome neutro.
- R4 Varredura anti-regresso (metodologia D5): para as páginas-chave (list com
  e sem follow-up, form, history), `strip_tags` no HTML → texto normalizado →
  "follow-up" (case-insensitive) ausente; e assert direto de que nenhum valor
  de `EVENT_LABELS` (`apps/intake/views.py`) contém "follow-up".

## Matriz requisito -> arquivo -> teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | 5 templates + `apps/intake/views.py` (D2) | R4 + inspeção do grep classificado (D5) |
| R2 | `apps/dashboard/views.py` | assert existente da flash convertida (`test_followup_form_view.py:381`) |
| R3 | 3 arquivos de teste | suíte focada verde |
| R4 | `apps/dashboard/tests/test_followup_list_view.py` (ou arquivo mais adequado) | `test_no_followup_anglicism_visible_*` + `test_event_labels_sem_anglicismo` |

```yaml
expected_files:
  - templates/dashboard/_nav.html
  - templates/dashboard/_followup_tabs.html
  - templates/dashboard/followup_list.html
  - templates/dashboard/followup_form.html
  - templates/dashboard/followup_history.html
  - apps/dashboard/views.py            # apenas a string da flash
  - apps/intake/views.py               # apenas os 2 valores de EVENT_LABELS
  - apps/dashboard/tests/test_followup_list_view.py
  - apps/dashboard/tests/test_followup_form_view.py
  - apps/dashboard/tests/test_followup_history.py

allowed_incidental_files:
  - apps/intake/tests/**               # apenas se algum teste do intake assertar os labels antigos da timeline

out_of_scope:
  - docs/manual/** (slice 002)
  - specs, código, URLs, filename CSV
  - ocorrências novas além do inventário → re-executar
    `rg -in "follow.?up" templates/ apps/{dashboard,intake,scheduler,doctor,cases}/views.py`
    e converter TODAS as visíveis (o inventário é o contrato mínimo, não o
    teto); se surgir string visível em outro app/arquivo fora do previsto
    acima, escalar em vez de expandir silenciosamente
```

## Plano de testes do slice

### RED

- comando: `uv run pytest apps/dashboard/tests -k "anglicism or event_labels" -q`
- falha esperada: os testes novos (R4) falham — "Follow-up" ainda aparece no
  texto visível das páginas e nos valores de `EVENT_LABELS`.

### GREEN / verificação local

- `uv run pytest apps/dashboard/tests -q` — exit 0 (asserts convertidos + varredura + matriz vigente)
- `uv run pytest apps/intake/tests -q` — exit 0 (timeline sem regressão)
- `uv run ruff check apps/dashboard apps/intake && uv run ruff format --check apps/dashboard apps/intake` — exit 0
- Grep classificado conforme D5: `rg -in "follow.?up" templates/ apps/ -g '!*/tests/*' -g '!*__pycache__*'`
  — resultado esperado: TODO hit classificável como identificador/URL/comentário
  de código; nenhum hit em string visível ao usuário.

## Critérios de aceitação

- [ ] Inventário D2 100% convertido (incluindo timeline) com capitalização correta
- [ ] Varredura R4 verde nas 4 páginas-chave + labels da timeline
- [ ] Grep classificado sem nenhum hit em texto visível
- [ ] Nenhuma mudança além de strings de UI/flash/labels/asserts/fixture/docstrings
- [ ] Gates locais verdes
