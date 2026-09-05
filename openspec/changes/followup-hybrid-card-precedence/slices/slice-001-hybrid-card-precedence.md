# Slice 001 — Card híbrido mostra data do agendamento + docstring defasada

## Objetivo

Comportamento observável: na aba Follow-up (`/dashboard/follow-ups/`), o card de um caso **híbrido** (agendamento confirmado com `appointment_at` **e** fluxo operacional) passa a exibir 📅 a data/hora do **agendamento** — igual ao agrupamento/ordenação e ao formulário — em vez de ⚡ label do fluxo. Casos puros permanecem como hoje. Docstring defasada da view corrigida.

## Contexto necessário (ler antes de editar)

- `apps/dashboard/views.py` — `_enrich_followup_item` (~L1423), `_followup_group_date`/`_followup_event_time` (precedência canônica já implementada: ramo agendado válido vence), `is_followup_eligible` (importado de `apps/cases/followup.py`), docstring de `followup_list` (afirma que cards não linkam — defasada).
- `templates/dashboard/followup_list.html` L55-59 — card: `{% if item.is_immediate %}⚡ label do fluxo{% else %}📅 {{ item.case.appointment_at }}{% endif %}`.
- `apps/dashboard/tests/test_followup_list_view.py` — `TestFollowUpListHybridCase` e helper `_create_hybrid_case` já existem (Slice 002); `apps/dashboard/tests/test_followup_form_view.py::TestFollowUpFormHybridCase` — referência do comportamento esperado (form já corrigido).
- `openspec/changes/supervisor-appointment-follow-up/design.md` § D4 — decisão de precedência aprovada (não redecidir).

## Requisitos verificáveis

- **R1** — `_enrich_followup_item` deriva `is_immediate` com a mesma precedência de `is_followup_eligible`: ramo agendado válido (`appointment_status="confirmed"` E `appointment_at` não nulo) → apresentação agendada (`is_immediate=False`, `admission_flow_label=""`); ⚡ fluxo apenas quando o caso cai no ramo operacional. Teste: híbrido confirmado renderiza a data do agendamento no card e NÃO renderiza o label do fluxo.
- **R2** — Casos puros inalterados: agendado puro continua mostrando 📅 data; imediato puro (sem agendamento válido, com `doctor_decided_at`) continua mostrando ⚡ label do fluxo. Testes existentes devem continuar verdes.
- **R3** — Docstring de `followup_list` atualizada: remover a afirmação de que os cards não linkam para o formulário (desatualizada desde o Slice 003 do change pai).

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `apps/dashboard/views.py` | `pytest apps/dashboard/tests/test_followup_list_view.py -k hybrid` (novo teste: card mostra `appointment_at` formatado e não o label do fluxo) |
| R2 | idem | `pytest apps/dashboard/tests/test_followup_list_view.py -k "immediate or scheduled"` (existente) |
| R3 | `apps/dashboard/views.py` | `rg "não linkam" apps/dashboard/views.py` → vazio |

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/dashboard/views.py                     # _enrich_followup_item + docstring
  - apps/dashboard/tests/test_followup_list_view.py  # +1 teste híbrido (R1)

allowed_incidental_files: []

out_of_scope:
  - apps/cases (fechado), templates, JS, forms
  - centralizar classificador de ramo (P2 separado)
  - truncatechars, pill ativo, EVENT_DOT_CSS (P2s diferidos)
  - tasks.md (parent atualiza), commit/push (parent decide)
```

**Escalar** se: precisar tocar algo além de `apps/dashboard/views.py` + testes da listagem.

## Plano de testes do slice

### RED

```bash
uv run pytest apps/dashboard/tests/test_followup_list_view.py -k hybrid -q
```

Falha esperada: o NOVO teste R1 falha — card híbrido renderiza o label do fluxo (⚡) em vez da data do agendamento (bug atual). Escreva o teste ANTES do fix.

### GREEN / verificação local

```bash
uv run pytest apps/dashboard/tests/test_followup_list_view.py -q        # exit 0
uv run pytest apps/dashboard/tests apps/cases/tests -q                  # exit 0 (regressão local)
uv run ruff check apps/dashboard && uv run ruff format --check apps/dashboard
uv run mypy apps/dashboard
rg "não linkam" apps/dashboard/views.py   # vazio (R3)
```

## Critérios de aceitação

- [ ] R1: card híbrido mostra data do agendamento; label do fluxo ausente.
- [ ] R2: casos puros inalterados (suite da listagem verde).
- [ ] R3: docstring sem afirmação defasada.
- [ ] Verificações locais verdes; nenhum arquivo fora do blast radius.
