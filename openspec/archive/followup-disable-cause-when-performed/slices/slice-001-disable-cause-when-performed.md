# Slice 001 — Fieldset de causa desabilitável + JS por radio performed

## Objetivo

Comportamento observável: no formulário de follow-up (`/dashboard/follow-ups/cases/<uuid>/`), marcar **Realizado** em um procedimento desabilita (gray-out nativo via `<fieldset disabled>`) e desmarca a **Causa da não realização** e esconde os grupos condicionais (submotivo/texto); voltar a **Não realizado** reabilita e aplica o show/hide atual. Estado correto também no load/re-render pós-erro.

## Contexto necessário (ler antes de editar)

- `templates/dashboard/followup_form.html` — bloco por procedimento (`data-followup-proc-id="{{ procedure.id }}"`, ~L113); radios `{{ form.performed }}` (valores do ChoiceField: `"yes"`/`"no"`, ~L117-127); seção de causa hoje é `<div class="mb-2">` (~L129) contendo radios `{{ form.non_performance_reason }}` e os grupos `data-followup-detail` (submotivo ~L141, texto ~L154) — o `</div>` fecha depois dos grupos.
- `static/js/followup_form.js` — hoje: listener apenas nos radios de causa; `refresh(block)` mostra grupo conforme causa ativa; binding com `let/const` por iteração (mantenha o padrão — fix de closure anterior).
- `apps/dashboard/tests/test_followup_form_view.py` — `TestFollowUpFormGet`/`TestFollowUpFormJs` (padrão de asserções no HTML renderizado).
- Regra de ouro (design D6): JS é só apresentação; validação/normalização server-side (apps/cases/followup.py) permanecem a autoridade e NÃO mudam neste slice.

## Requisitos verificáveis

- **R1** — Template: a seção de causa vira `<fieldset class="mb-2" data-followup-reason-section>…</fieldset>` envolvendo radios de causa E grupos condicionais (fecho correto: `</fieldset>` onde hoje é o `</div>` da seção; atenção para não quebrar o aninhamento dos blocos de procedimento).
- **R2** — JS: listener `change` nos radios `performed` do bloco (valores REAIS do `ChoiceField`: `"yes"` = Realizado, `"no"` = Não realizado — ver `apps/dashboard/forms.py::FollowUpForm.performed.choices`); quando `"yes"`: `section.disabled = true`, desmarcar todos os radios de causa (`checked = false`) e esconder os grupos `data-followup-detail`; quando `"no"`: `section.disabled = false` + `refresh(block)` existente. Estado inicial idem no load (cobre re-render pós-erro com realizado marcado).
- **R3** — Sem regressão: alternância causa→submotivo/texto existente continua funcionando com "Não realizado" ativo; múltiplos blocos independentes entre si.
- **R4** — Teste de template: GET do formulário renderiza `data-followup-reason-section` (1 por bloco de procedimento); suíte existente do form verde.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `templates/dashboard/followup_form.html` | `pytest apps/dashboard/tests/test_followup_form_view.py -k reason_section` (novo) |
| R2 | `static/js/followup_form.js` | `node --check` + revisão (limitação conhecida: JS não é pytest-exercitável — P2 registrada) |
| R3 | idem | `pytest apps/dashboard/tests/test_followup_form_view.py -q` (existente) |
| R4 | `apps/dashboard/tests/test_followup_form_view.py` | idem R1 + suíte |

## Escopo e expected blast radius

```yaml
expected_files:
  - templates/dashboard/followup_form.html   # div.mb-2 → fieldset
  - static/js/followup_form.js               # listener performed + disable section
  - apps/dashboard/tests/test_followup_form_view.py  # +1 teste

allowed_incidental_files: []

out_of_scope:
  - apps/dashboard/forms.py, apps/cases (server-side intocado), listagem
  - tasks.md (parent atualiza), commit/push (parent decide)
```

## Plano de testes do slice

### RED

`pytest apps/dashboard/tests/test_followup_form_view.py -k reason_section -q` → falha (fieldset inexistente no HTML hoje).

### GREEN / verificação local

```bash
uv run pytest apps/dashboard/tests/test_followup_form_view.py -q      # exit 0
uv run pytest apps/dashboard/tests -q                                  # exit 0
node --check static/js/followup_form.js                                # ok
uv run ruff check apps/dashboard && uv run ruff format --check apps/dashboard static 2>/dev/null || true
```

## Critérios de aceitação

- [ ] R1–R4 verdes; HTML estruturalmente válido (aninhamento fieldset/div correto).
- [ ] Nenhum arquivo fora do blast radius; server-side intocado.
