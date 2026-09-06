# Slice 001 — Rename completo na UI: "follow-up" → "Pós-Procedimento"

## Objetivo

Todo rótulo visível ao usuário que hoje diz "Follow-up"/"follow-up" passa a
dizer "Pós-Procedimento"/"pós-procedimento" (regra tipográfica D1), nos 5
templates do dashboard e na flash message de sucesso, com asserções de teste
convertidas e uma varredura anti-regresso que trava o anglicismo.

## Contexto necessário

- Design: D1 (regra tipográfica), D2 (inventário) e D5 (testes) de
  `openspec/changes/followup-pos-procedimento-ui/design.md`.
- Templates: `templates/dashboard/{_nav,_followup_tabs,followup_list,followup_form,followup_history}.html`.
- Flash: `apps/dashboard/views.py` ~:2008 ("Follow-up registrado (versão {n})…").
- Testes com asserções de texto: `apps/dashboard/tests/test_followup_{list_view,form_view,history}.py`
  (9 ocorrências de "Follow-up").
- **Não renomear**: URLs (`/dashboard/follow-ups/`), names de rotas, ids/classes
  CSS, `data-*` attributes, nomes de arquivos de template, filename do CSV
  (`followups_*.csv`), comentários de código.

## Requisitos verificáveis

- R1 Inventário D2 integralmente convertido com a capitalização correta por
  contexto (Title Case em título/pill; minúsculo no meio de frase).
- R2 Flash message usa "Pós-procedimento registrado (versão {n})…".
- R3 As 9 asserções de teste existentes convertidas; nenhum teste deletado.
- R4 Varredura anti-regresso: teste que renderiza as páginas-chave (list com e
  sem follow-up, form, history) e afirma que "follow-up" (case-insensitive)
  não aparece no HTML de conteúdo visível.

## Matriz requisito -> arquivo -> teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | 5 templates (D2) | R4 + revisão |
| R2 | `apps/dashboard/views.py` | asserção existente da flash convertida |
| R3 | 3 arquivos de teste | suíte focada verde |
| R4 | `apps/dashboard/tests/test_followup_list_view.py` (ou arquivo mais adequado) | `test_no_followup_anglicism_visible_*` |

```yaml
expected_files:
  - templates/dashboard/_nav.html
  - templates/dashboard/_followup_tabs.html
  - templates/dashboard/followup_list.html
  - templates/dashboard/followup_form.html
  - templates/dashboard/followup_history.html
  - apps/dashboard/views.py            # apenas a string da flash
  - apps/dashboard/tests/test_followup_list_view.py
  - apps/dashboard/tests/test_followup_form_view.py
  - apps/dashboard/tests/test_followup_history.py

allowed_incidental_files: []

out_of_scope:
  - docs/manual/** (slice 002)
  - specs, código, URLs, filename CSV
  - ocorrências novas além do inventário → re-executar
    `rg -in "follow.?up" templates/ apps/dashboard/views.py` e converter TODAS
    as visíveis (o inventário é o contrato mínimo, não o teto); se surgir
    ocorrência em outro app/template, escalar em vez de expandir
```

## Plano de testes do slice

### RED

- comando: `uv run pytest apps/dashboard/tests -k "anglicism" -q`
- falha esperada: o teste novo de varredura (R4) falha — "Follow-up" ainda
  aparece no HTML das páginas atuais.

### GREEN / verificação local

- `uv run pytest apps/dashboard/tests -q` — exit 0 (matriz de acesso vigente +
  strings convertidas + varredura)
- `uv run ruff check apps/dashboard && uv run ruff format --check apps/dashboard` — exit 0
- `rg -in "follow.?up" templates/ apps/dashboard/views.py` — resultado esperado:
  zero ocorrências de texto visível (restam apenas URLs/identificadores, se houver)

## Critérios de aceitação

- [ ] Inventário D2 100% convertido com capitalização correta
- [ ] Varredura R4 verde e cobrindo as 4 páginas-chave
- [ ] Nenhuma mudança além de strings de UI/flash/asserts de teste
- [ ] Gates locais verdes
