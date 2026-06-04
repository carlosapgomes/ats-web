# Slice 001: Consolidar fixtures comuns de casos e usuários

## Handoff para implementador LLM com contexto zero

Leia:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/consolidate-duplicated-test-fixtures/proposal.md`
4. `openspec/changes/consolidate-duplicated-test-fixtures/tasks.md`
5. Este arquivo
6. `apps/*/tests/conftest.py`
7. `conftest.py` na raiz do projeto

Implemente somente este slice.

## Objetivo

Remover duplicações óbvias entre fixtures de teste, especialmente helpers de
usuário, papéis, `case_factory` e avanço de FSM, preservando a suíte verde.

## Escopo

- Comparar `apps/cases/tests/conftest.py`, `apps/intake/tests/conftest.py`,
  `apps/scheduler/tests/conftest.py` e demais `conftest.py` relevantes.
- Extrair helpers comuns para local compartilhado apropriado.
- Atualizar imports/uso nos testes afetados.
- Manter fixtures locais quando tiverem comportamento específico do app.

## Fora de escopo

- Alterar lógica de produção.
- Reescrever testes em massa.
- Criar abstração complexa ou dependência nova.

## Critérios de aceite

- [ ] Duplicação comum foi reduzida de forma mensurável.
- [ ] Testes afetados continuam legíveis.
- [ ] `uv run pytest apps/cases/tests apps/intake/tests apps/scheduler/tests -q`
  passa.
- [ ] Quality gate completo passa, se possível.

## Relatório obrigatório

Criar:

```text
/tmp/ats-web-consolidate-test-fixtures-slice-001-report.md
```

Responder com:

```text
REPORT_PATH=/tmp/ats-web-consolidate-test-fixtures-slice-001-report.md
```

## Prompt pronto

```text
Read AGENTS.md, PROJECT_CONTEXT.md and consolidate-duplicated-test-fixtures OpenSpec through Slice 001. Implement ONLY Slice 001. Inventory duplicated conftest fixtures across apps, extract common case/user/role helpers to an appropriate shared test location, keep app-specific fixtures local, preserve test readability, run validations, update tasks.md, create /tmp/ats-web-consolidate-test-fixtures-slice-001-report.md, commit and push, reply REPORT_PATH and stop.
```
