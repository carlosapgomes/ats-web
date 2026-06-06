# Slice 001: Exibir labels em português para motivos de intercorrência

## Handoff para implementador LLM com contexto zero

Leia, nesta ordem:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/archive/post-schedule-intercurrence/tasks.md`
4. `openspec/archive/post-schedule-intercurrence/slices/slice-003-scheduler-resolve-issue.md`
5. `openspec/archive/post-schedule-intercurrence/slices/slice-005-timeline-badges-hardening.md`
6. `openspec/changes/localize-post-schedule-issue-reasons/proposal.md`
7. `openspec/changes/localize-post-schedule-issue-reasons/design.md`
8. `openspec/changes/localize-post-schedule-issue-reasons/tasks.md`
9. Este arquivo

Implemente somente este slice.

## Contexto do bug

Teste manual abriu intercorrência com motivo de falecimento. Para o agendador,
o sistema mostrou:

```text
Motivo: death
```

O valor `death` deve continuar sendo o código interno persistido, mas a UI deve
mostrar:

```text
Motivo: Paciente faleceu
```

## Diagnóstico inicial

Pontos onde o código cru aparece ou é passado para UI:

- `apps/scheduler/views.py::_build_case_card`
- `apps/scheduler/views.py::_build_confirm_context`
- `templates/scheduler/_queue_content.html`
- `templates/scheduler/confirm_post_schedule_issue.html`

Existe mapeamento local duplicado em `apps/intake/views.py` para o detalhe NIR.
Consolidar se couber sem ampliar muito o escopo.

## Objetivo

Garantir que motivos oficiais de intercorrência pós-agendamento sejam exibidos
em português em todas as superfícies operacionais do scheduler e permaneçam
corretos no NIR.

## Escopo

- Criar/consolidar uma fonte única de labels para motivos de intercorrência.
- Atualizar scheduler queue para renderizar label em português.
- Atualizar scheduler confirm para renderizar label em português.
- Atualizar/remover mapeamento duplicado no detalhe NIR, se simples.
- Ajustar testes que hoje aceitam código cru como alternativa.

## Fora de escopo

- Não alterar valores salvos em `Case.post_schedule_issue_reason`.
- Não criar migration.
- Não alterar motivos oficiais.
- Não alterar regras de validação, FSM, locks ou fluxos.
- Não revisar vocabulário fora de intercorrência pós-agendamento.

## Plano TDD obrigatório

### RED

Adicionar/ajustar testes antes da implementação:

1. Scheduler queue com issue `death` mostra `Paciente faleceu`.
2. Scheduler queue não mostra `Motivo (death)`.
3. Scheduler confirm com issue `death` mostra `Paciente faleceu`.
4. Scheduler confirm não mostra `Motivo: death`.
5. Scheduler queue ou confirm com `reschedule_request` mostra
   `Solicitação de reagendamento pela unidade de origem` e a mensagem do NIR.
6. Detalhe NIR de issue respondida continua mostrando label em português.

Observação: se o código aparecer em outro lugar técnico do HTML, faça asserts
mais específicos ao bloco visível de motivo ou ao contexto de template, evitando
falso positivo/frágil.

### GREEN

Implementar o mínimo:

- Adicionar helper/constante de label no domínio.
- Passar `post_schedule_issue_reason_label` nos cards do scheduler.
- Passar `ps_issue_reason_label` no contexto da tela de resolução.
- Renderizar labels nos templates.

### REFACTOR

- Remover mapeamento duplicado em `apps/intake/views.py` se ficar simples.
- Manter códigos internos como estão.
- Não criar abstração genérica de i18n agora.

## Critérios de aceite

- [ ] Agendador nunca vê `death` como motivo visível.
- [ ] Agendador vê `Paciente faleceu`.
- [ ] Todos os motivos oficiais têm label em português centralizada.
- [ ] NIR mantém labels em português no detalhe/timeline relacionado.
- [ ] Testes relevantes passam.

## Gates de validação

Rodar no mínimo:

```bash
uv run pytest apps/scheduler/tests/test_post_schedule_issue.py apps/scheduler/tests/test_views.py apps/intake/tests/test_post_schedule_issue_ack.py apps/intake/tests/test_post_schedule_issue_hardening.py -q
uv run ruff check apps/cases apps/scheduler apps/intake
uv run ruff format --check apps/cases apps/scheduler apps/intake
uv run mypy apps/cases apps/scheduler apps/intake
```

Se viável, rodar quality gate completo:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório obrigatório

Criar relatório em:

```text
/tmp/ats-web-localize-post-schedule-issue-reasons-slice-001-report.md
```

O relatório deve conter:

- resumo do bug;
- arquivos alterados;
- snippets antes/depois;
- testes adicionados/ajustados;
- validações executadas;
- commit hash;
- confirmação de push.

Resposta final obrigatória:

```text
REPORT_PATH=/tmp/ats-web-localize-post-schedule-issue-reasons-slice-001-report.md
```

Depois, parar e aguardar confirmação explícita.

## Prompt pronto para implementador

```text
Read AGENTS.md, PROJECT_CONTEXT.md, archived post-schedule-intercurrence slices 003 and 005, and openspec/changes/localize-post-schedule-issue-reasons through Slice 001. Implement ONLY Slice 001. Fix the scheduler UI leak where post-schedule issue reasons display raw codes like death: centralize Portuguese labels for official reasons, render labels in scheduler queue and scheduler confirm, keep persisted codes unchanged, consolidate NIR detail mapping if simple, add tests first, run validations, update tasks.md only after completion, create /tmp/ats-web-localize-post-schedule-issue-reasons-slice-001-report.md, commit and push, reply with REPORT_PATH and stop.
```
