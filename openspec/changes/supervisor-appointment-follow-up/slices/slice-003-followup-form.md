# Slice 003 — Formulário de follow-up (desfecho por procedimento + internação)

## Objetivo

Comportamento observável: ao abrir um caso na aba, o supervisor vê o formulário com um bloco por procedimento (realizado/não realizado + causa estruturada) e internação por caso, com a versão atual e histórico compacto; submeter grava **nova versão** via `record_case_follow_up`, registra o `CaseEvent` correspondente e volta à lista com `messages.success`. Submissão inválida re-renderiza com erros — nada persiste.

## Contexto necessário (ler antes de editar)

- `apps/cases/followup.py` — `record_case_follow_up`, `ProcedureOutcomeInput`, `get_current_follow_up` e **`is_followup_eligible`** (Slice 002) e validações (não duplicar no form: o form traduz erros de `ValueError` quando aplicável, mas as regras condicionais vivem nos DOIS lados: form valida UX, service valida contrato).
- `templates/dashboard/followup_list.html` (Slice 002) — o card NÃO tem link ainda; este slice adiciona o link para `dashboard:followup_form`.
- `apps/dashboard/views.py` + `urls.py` — onde a view `followup_form` entra; padrão de permissão D5.
- `apps/scheduler/forms.py::SchedulerDecisionForm` — padrão casa de `forms.Form` (não ModelForm).
- `templates/scheduler/confirm.html` — referência visual de formulário Bootstrap com radios.
- `openspec/changes/supervisor-appointment-follow-up/design.md` — D2 (condições de campos), D3 (eventos), D6 (formulário e histórico na página).

## Requisitos verificáveis

- **R1** — `GET dashboard:followup_form` (case_id): requer `manager`/`admin`; **revalida `is_followup_eligible`** — caso inelegível ou inexistente → 404 com mensagem; exibe ocorrência/nome do paciente, data/hora agendada ou fluxo de admissão, um bloco por `CaseProcedure` do caso (condicionais escondidos via JS), internação (radio sim/não, sempre visível), versão atual (autor+timestamp) e histórico de versões; caso elegível **sem rows `CaseProcedure`** (defensivo) → 200 com aviso orientando correção do caso, sem campos de gravação.
- **R2** — `POST` válido revalida elegibilidade e chama `record_case_follow_up` (nova versão mesmo se já existia), redireciona para `dashboard:followup_list` com `messages.success`; `CaseEvent` `FOLLOWUP_RECORDED`/`FOLLOWUP_UPDATED` presente.
- **R3** — `POST` inválido (motivo ausente p/ não realizado; `resource_shortage` sem submotivo; `other` sem texto; id de procedimento estranho) re-renderiza com erro por campo e **não** cria rows/eventos.
- **R4** — Re-gravação cria versão 2 preservando v1 (integração com service testada já no Slice 001; aqui o teste é de fluxo HTTP).
- **R5** — `static/js/followup_form.js` incluído pelo template esconde/mostra `resource_shortage_detail`/`other_reason` conforme radio de motivo (sem lógica de negócio; validação continua server-side).
- **R6** — Card da listagem (`templates/dashboard/followup_list.html`) passa a renderizar link para `dashboard:followup_form` (rota agora existente); navegação listagem → formulário → volta à lista funciona ponta a ponta.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `apps/dashboard/forms.py`, `views.py`, `urls.py`, `templates/dashboard/followup_form.html` | `pytest apps/dashboard/tests/test_followup_form_view.py -k "get or ineligible"` |
| R2 | idem | `pytest ... -k post_valid` + assert `CaseEvent` |
| R3 | `forms.py` + view | `pytest ... -k post_invalid` (assert `not CaseFollowUp.objects.exists()`) |
| R4 | view + tests | `pytest ... -k second_version` |
| R5 | `static/js/followup_form.js`, template | `pytest ... -k js_include` + check estático |
| R6 | `templates/dashboard/followup_list.html` + testes | `pytest ... -k list_link` (client acessa lista e segue o link) |

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/dashboard/forms.py                 # novo (FollowUpForm)
  - apps/dashboard/views.py                 # +followup_form
  - apps/dashboard/urls.py                  # +rota
  - templates/dashboard/followup_form.html  # novo
  - static/js/followup_form.js              # novo
  - templates/dashboard/followup_list.html  # edit: +link no card (R6)
  - apps/dashboard/tests/test_followup_form_view.py  # novo

allowed_incidental_files: []

out_of_scope:
  - apps/cases (service/models já fechados nos Slices 001/002)
  - edição/deleção de versões anteriores, aprovações, notificações
  - métricas/agregações
```

**Escalar** se: precisar alterar `record_case_follow_up` (contrato do Slice 001), adicionar migration, ou tocar templates de outros apps.

## Plano de testes do slice

### RED

Escreva primeiro `apps/dashboard/tests/test_followup_form_view.py` (importando a rota/view novas). Depois:

```bash
uv run pytest apps/dashboard/tests/test_followup_form_view.py -q
```

Falha esperada: erro de coleção/import — view/rota não existem. POST usa payload prefixado por procedimento (`proc_<id>-performed` etc., definido pelo form com `prefix`).

### GREEN

```bash
uv run pytest apps/dashboard/tests/test_followup_form_view.py -q
```

### Verificação do slice (gate final do change — suíte global UMA vez aqui)

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -q
```

## Critérios de aceitação

- [ ] R1–R6 verdes; POST inválido não persiste nada (rows nem eventos).
- [ ] GET/POST rejeitam caso inelegível com 404 (`pytest ... -k ineligible`).
- [ ] Card da listagem linka para o formulário (`rg "followup_form" templates/dashboard/followup_list.html` → ≥1 ocorrência).
- [ ] Atualização cria nova versão com `recorded_by` do usuário logado; v1 preservada.
- [ ] Quality gate global do change verde (ruff/mypy/pytest).
- [ ] Nenhum arquivo fora do blast radius.
