# Slice 001: Scheduler role guard

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`, um monolito Django 5.2 SSR com templates Bootstrap, sem API REST e sem SPA.

Antes de codar, leia obrigatoriamente:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/shared-work-queue-leases/proposal.md`
4. `openspec/changes/shared-work-queue-leases/design.md`
5. Este arquivo

Implemente **somente este slice**. Use TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Corrigir autorização do app scheduler para exigir papel ativo `scheduler` em todas as views operacionais.

Este slice é propositalmente pequeno e deve ser feito antes dos locks para reduzir risco de ampliar uma superfície de acesso já incorreta.

## Fluxo vertical entregue

```text
Usuário autenticado sem papel ativo scheduler tenta acessar fila/agendamento
→ acesso bloqueado pelo role guard

Usuário com papel ativo scheduler
→ acessa fila e ações do agendador normalmente
```

## Escopo funcional

Adicionar `@role_required("scheduler")` às views públicas do `apps/scheduler/views.py`:

- `scheduler_queue`
- `scheduler_queue_partial`
- `immediate_ack`
- `scheduler_confirm`
- `scheduler_submit`

Preservar `@login_required`.

## Fora de escopo

- Implementar locks.
- Alterar templates.
- Alterar FSM.
- Alterar intranet guard.
- Alterar regras de NIR ou médico.

## Arquivos prováveis

Idealmente tocar poucos arquivos:

1. `apps/scheduler/views.py`
2. testes em `apps/scheduler/tests/`
3. `openspec/changes/shared-work-queue-leases/tasks.md` ao final

Se tocar outros arquivos, justifique no relatório.

## Plano TDD obrigatório

### RED

Adicionar/ajustar testes antes da implementação:

1. Usuário logado com papel ativo diferente de `scheduler` não acessa:
   - fila scheduler;
   - partial da fila;
   - tela de confirmação;
   - submit;
   - immediate ack.
2. Usuário com papel ativo `scheduler` continua acessando fluxo existente.

Siga o padrão de testes já existente para `role_required` em apps como doctor/intake.

### GREEN

Adicionar import:

```python
from apps.accounts.decorators import role_required
```

E aplicar decorators mantendo ordem compatível com o projeto:

```python
@login_required
@role_required("scheduler")
def scheduler_queue(...):
    ...
```

### REFACTOR

- Remover duplicação nos testes se houver helper já existente.
- Não criar abstração nova se apenas poucos testes precisarem de setup.

## Critérios de aceitação

- [ ] Todas as views públicas do scheduler exigem papel ativo `scheduler`.
- [ ] Usuário autenticado com outro papel não acessa endpoints do scheduler.
- [ ] Usuário scheduler continua usando fluxo existente.
- [ ] Testes relevantes passam.
- [ ] Nenhuma regra de negócio de agendamento foi alterada.
- [ ] `tasks.md` marcado somente para este slice ao final.

## Gates de autoavaliação

Responder no relatório:

1. Todas as views públicas do scheduler foram cobertas?
2. A ordem dos decorators segue padrão do projeto?
3. Algum comportamento funcional além de autorização mudou? Se sim, por quê?
4. Quantos arquivos foram tocados?

## Comandos de validação mínimos

```bash
uv run pytest apps/scheduler/tests -q
uv run ruff check apps/scheduler
uv run ruff format --check apps/scheduler
uv run mypy apps/scheduler
```

Se possível, rode o quality gate completo:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório final obrigatório

Criar relatório temporário em:

```text
/tmp/ats-web-slice-001-scheduler-role-guard-report.md
```

O relatório deve conter:

- resumo do que foi implementado;
- arquivos alterados;
- snippets antes/depois;
- testes adicionados/alterados;
- comandos executados e resultados;
- riscos/observações;
- confirmação de atualização de `tasks.md`;
- commit hash e push, quando realizados.

Resposta final obrigatória:

```text
REPORT_PATH=/tmp/ats-web-slice-001-scheduler-role-guard-report.md
```

Depois pare e peça confirmação explícita antes do próximo slice.

## Prompt pronto para implementador

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/shared-work-queue-leases/proposal.md, design.md and slices/slice-001-scheduler-role-guard.md.
Implement ONLY Slice 001 using TDD.
Add role_required("scheduler") to all public scheduler views and tests proving non-scheduler active roles are blocked while scheduler role still works.
Do not implement locks or alter business flow.
Run validations, update tasks.md, create /tmp/ats-web-slice-001-scheduler-role-guard-report.md with before/after snippets, commit and push, then reply with REPORT_PATH and stop.
```
