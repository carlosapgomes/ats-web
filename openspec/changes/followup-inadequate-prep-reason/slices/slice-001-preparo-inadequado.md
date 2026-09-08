# Slice 001 — Causa "Preparo inadequado" end-to-end (enum → gravação → Histórico/CSV → manual)

## Objetivo

O pós-procedimento passa a oferecer a causa **"Preparo inadequado"**
(`inadequate_prep`) para procedimentos não realizados — solicitação da equipe
do CHD para exames interrompidos/não iniciados por preparo inadequado do
paciente. A causa é gravável pelo formulário e pelo service (com espelho em
`CaseEvent`), rejeita submotivo/texto livre (como absenteísmo), aparece nos
cards "Causas de não realização", no filtro de causa e no CSV do Histórico,
e é documentada no manual do usuário §6.

Importante para o implementador: a causa é **nova opção do conjunto fechado
de causas de não realização** — NÃO é um terceiro desfecho (o campo
`performed` continua booleano). Ver design.md D1 antes de qualquer edição.

## Contexto necessário

Leitura antes de editar (contexto zero):

- `openspec/changes/followup-inadequate-prep-reason/design.md` — D1..D7
  (decisões: causa vs terceiro estado, rótulo/valor, posição no enum, sem
  submotivo/texto, superfícies derivadas, migração, spec).
- `apps/cases/models.py` — `FollowUpNonPerformanceReason` (~:820) e
  `ProcedureFollowUp` (~:868, campo `non_performance_reason` e as 6
  CheckConstraints — nenhuma muda).
- `apps/cases/followup.py` — `_validate_outcomes`: validação genérica por
  `FollowUpNonPerformanceReason.values` (nenhuma edição esperada neste
  arquivo).
- `apps/dashboard/forms.py` — `FollowUpForm` (choices derivadas do enum;
  `clean()` genérico; nenhuma edição esperada).
- `apps/dashboard/views.py` — `_followup_history_rows` (~:1597): branch
  `else:  # absenteeism` que zera submotivo/texto — apenas o comentário
  fica defasado (R6).
- `docs/manual/manual-usuarios.md` — §6, lista de causas (~:1127) e regras
  do formulário (~:1141).
- Testes existentes (padrões e helpers):
  - `apps/cases/tests/test_followup_services.py` — helpers
    `_case_with_procedures`, `_outcome`, `_assert_rejeitado`; classe de
    rejeições e `test_absenteismo_e_outras_causas_sao_gravados`.
  - `apps/dashboard/tests/test_followup_form_view.py` — helpers `_login_as`,
    `_create_case`, `_add_procedure`, `_valid_payload`, `_form_url`,
    `_assert_success_redirect`; `test_post_valid_not_performed_with_reason`
    (modelo a espelhar).
  - `apps/dashboard/tests/test_followup_history.py` — helper `_record`;
    `CSV_COL` para asserts de exportação; testes de cards/filtro (ex.:
    asserts de `<option value="absenteeism">`) e de CSV (ex.:
    `test_outra_causa_texto_e_nao_realizado_nao_internado`).
  - `tests/test_user_manual_artifacts.py` — asserções sobre o conteúdo do
    manual.
- Convenção: todos os testes novos deste slice contêm `preparo_inadequado`
  no nome (ancora o filtro `-k` do RED/GREEN).

## Requisitos verificáveis

- R1 Enum: `FollowUpNonPerformanceReason` ganha
  `INADEQUATE_PREP = "inadequate_prep", "Preparo inadequado"` imediatamente
  após `ABSENTEEISM` (ordem relevante — D3).
- R2 Migração choices-only em `apps/cases` (`0018_*`, gerada por
  `makemigrations`): `AlterField` em `ProcedureFollowUp.non_performance_reason`;
  nenhuma constraint criada/removida.
- R3 Service: `record_case_follow_up` aceita não realizado +
  `reason="inadequate_prep"` (sem submotivo/texto), persiste a causa com
  `resource_shortage_detail=""` e `other_reason=""`, e espelha
  `non_performance_reason="inadequate_prep"` no payload do `CaseEvent`.
- R4 Service (rejeições): causa nova + submotivo é rejeitada com a mensagem
  específica de submotivo ("Submotivo só deve ser informado quando a causa
  é falta de recursos."); causa nova + texto, com a mensagem específica de
  texto ("Texto de outras causas só deve ser informado quando a causa é
  'Outras causas'."); nada é gravado. Assert de mensagem exata (não usar
  `_assert_rejeitado` genérico — ele não distingue motivo da rejeição).
- R5 Form/POST: o formulário renderiza a opção "Preparo inadequado" e o
  POST válido persiste `non_performance_reason="inadequate_prep"` com
  submotivo/texto vazios (redireciona com sucesso).
- R6 Histórico/CSV (sem editar código dessas superfícies — D5): caso
  gravado com a causa nova aparece (a) nos cards "Causas de não realização"
  com label "Preparo inadequado"; (b) no filtro como
  `<option value="inadequate_prep">Preparo inadequado</option>`; (c) no CSV
  com coluna Causa = "Preparo inadequado" e colunas Submotivo e
  "Outra causa (texto)" vazias. Única edição permitida em
  `apps/dashboard/views.py`: comentário do branch `else` em
  `_followup_history_rows` (`# absenteeism` → `# absenteeism/inadequate_prep`).
- R7 Manual: §6 lista "**Preparo inadequado**" na lista de causas (com
  descrição no padrão das demais, mencionando que o exame não foi realizado
  ou foi interrompido por preparo inadequado) e o teste de artefatos de
  manual passa a asserir a presença do termo em §6.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) | Teste/check |
| --- | --- | --- |
| R1 | `apps/cases/models.py` | R3/R5/R6 (uso do enum) |
| R2 | `apps/cases/migrations/0018_*.py` | `uv run python manage.py makemigrations cases --check --dry-run --settings=config.settings.test` → "No changes detected" |
| R3 | (sem edição — derivação) | `test_preparo_inadequado_gravado_e_espelhado` (services) |
| R4 | (sem edição — derivação) | `test_preparo_inadequado_com_submotivo_ou_texto_rejeitado` (services, `pytest.raises(ValueError, match=...)`) |
| R5 | (sem edição — derivação) | `test_post_valid_preparo_inadequado` + assert da opção no GET (form view) |
| R6 | `apps/dashboard/views.py` (só comentário) | `test_preparo_inadequado_em_cards_e_filtro` + `test_preparo_inadequado_no_csv` (history) |
| R7 | `docs/manual/manual-usuarios.md` | `test_manual_documenta_preparo_inadequado` (tests/test_user_manual_artifacts.py) |

```yaml
expected_files:
  - apps/cases/models.py
  - apps/cases/migrations/0018_*.py  # gerada por makemigrations
  - apps/dashboard/views.py          # APENAS comentário (R6)
  - docs/manual/manual-usuarios.md
  - apps/cases/tests/test_followup_services.py
  - apps/dashboard/tests/test_followup_form_view.py
  - apps/dashboard/tests/test_followup_history.py
  - tests/test_user_manual_artifacts.py

allowed_incidental_files: []

out_of_scope:
  - terceiro estado de desfecho / tocar `performed` ou CheckConstraints (D1)
  - submotivo ou texto livre para a nova causa (D4)
  - apps/cases/followup.py e apps/dashboard/forms.py (validação genérica cobre)
  - templates e static/js/followup_form.js (derivação D5)
  - specs e archive: o delta já está no change; a atualização do Purpose
    da spec no archive é operação do PARENT no fechamento do change (tasks.md,
    gate final) — NÃO é tarefa do implementador do slice
  - migração/retrofit de dados históricos
```

Escalar (não ampliar silenciosamente) se: precisar editar service/form/JS/
template, criar constraint, tocar FSM/`CaseEvent`/URLs, ou descobrir que
alguma superfície derivada NÃO herda a causa nova.

## Plano de testes do slice

### RED

Comando (todos os testes novos usam `preparo_inadequado` no nome):

```bash
uv run pytest apps/cases/tests/test_followup_services.py \
  apps/dashboard/tests/test_followup_form_view.py \
  apps/dashboard/tests/test_followup_history.py \
  tests/test_user_manual_artifacts.py -k preparo_inadequado -q
```

Falha esperada pelo motivo esperado:

- services: `record_case_follow_up` com `reason="inadequate_prep"` levanta
  `ValueError("Informe a causa do procedimento não realizado.")` (valor fora
  do enum) → o teste de gravação falha por erro; o de rejeição falha porque
  a mensagem não bate com `match` específico.
- form view: GET não renderiza a opção "Preparo inadequado"; POST é
  rejeitado pela `ChoiceField` (200 com erro, sem redirect).
- history: `_record(..., reason="inadequate_prep")` levanta `ValueError`
  (enum inexistente) → teste falha por erro na montagem do dado.
- manual: termo "Preparo inadequado" ausente do manual → assert falha.

### GREEN

Implementação mínima: R1 (enum) → R2 (makemigrations) → R6 (comentário) →
R7 (manual). R3/R4/R5 não exigem edição de código (derivação). Mesmo comando
do RED → exit 0.

### Verificação do slice (regressão local — não rodar suíte completa)

```bash
# módulos diretamente afetados
uv run pytest apps/cases/tests/test_followup_services.py \
  apps/dashboard/tests/test_followup_form_view.py \
  apps/dashboard/tests/test_followup_history.py \
  tests/test_user_manual_artifacts.py -q

# migração íntegra (nenhuma pendente)
uv run python manage.py makemigrations cases --check --dry-run --settings=config.settings.test

# lint/format/typecheck escopados
uv run ruff check apps/cases apps/dashboard tests
uv run ruff format --check apps/cases apps/dashboard tests
uv run mypy apps/cases apps/dashboard
```

Check por inspeção (contrato sem teste automatizado): nenhum outro arquivo
de código alterado além do previsto (`git status`); diff de
`apps/dashboard/views.py` contém apenas o comentário.

## Critérios de aceitação

- [ ] R1–R7 verdes na matriz acima; comando do RED → exit 0 pós-implementação
- [ ] Verificação local completa verde (módulos + makemigrations --check + ruff/format/mypy escopados)
- [ ] `performed`, CheckConstraints, service, form, JS e templates sem nenhuma edição
- [ ] Diff total de código: 1 linha no enum (+docstring), 1 comentário, migração gerada, manual §6
- [ ] Blast radius = 8 arquivos previstos, zero incidentais

## Contrato de handoff (prompt pronto para o implementador)

O slice é autocontido: um worker com contexto fresco implementa sem conhecer
a discussão que o originou. Prompt de disparo (copy-paste):

```text
Read AGENTS.md and PROJECT_CONTEXT.md first.
Implement ONLY the slice described in
openspec/changes/followup-inadequate-prep-reason/slices/slice-001-preparo-inadequado.md
(its "Contexto necessário" lists every file you need; design.md D1–D7 holds the decisions).
Follow TDD strictly: write the new tests FIRST (all names contain "preparo_inadequado"),
run the slice's RED command and confirm it fails for the stated reasons, then apply the
minimal GREEN edits — enum value + generated migration + one comment in views.py + manual §6.
Do NOT edit apps/cases/followup.py, apps/dashboard/forms.py, templates or JS (derivation by design D5);
if any of those seems to require a change, STOP and escalate instead of expanding scope.
Run the slice's local verification commands (focused modules, makemigrations --check,
ruff/format/mypy scoped). Do NOT update tasks.md, do NOT commit/push, do NOT start other slices.
Reply with a concise report: RED evidence (failing output), GREEN evidence (passing output),
files touched vs expected_files, and any deviations.
```

Papéis (workflow pi-subagents do projeto): o **worker** implementa e reporta;
o **reviewer** valida read-only; o **parent** atualiza `tasks.md` e commita
somente após review aceito. Atualização do Purpose da spec é operação do
parent no fechamento (archive), não do implementador.
