# Slice 006 — Role Guard Médico

## Handoff para Implementador LLM

Leia os artefatos do change e confirme que os slices anteriores estão aplicados.

Implemente somente este slice.

## Problema

As views médicas atuais usam apenas `@login_required`, permitindo que qualquer usuário autenticado acesse URLs médicas se souber o caminho.

## Objetivo

Exigir papel ativo `doctor` em todas as views médicas.

## Escopo Preferencial

Arquivos prováveis:

- `apps/doctor/views.py`
- `apps/doctor/tests/test_views.py`

Não alterar middleware ou decorators globais, salvo se houver bug explícito.

## Requisitos Funcionais

1. Aplicar `@role_required("doctor")` às views:
   - `doctor_queue`
   - `doctor_decision`
   - `doctor_submit`
2. Usuário sem login continua redirecionando para login.
3. Usuário logado com papel ativo diferente de `doctor` deve ser bloqueado/redirecionado conforme comportamento atual de `role_required`.
4. Usuário com papel `doctor` ativo continua acessando normalmente.

## TDD — Testes RED Esperados

1. NIR autenticado não acessa `/doctor/`.
2. Scheduler autenticado não acessa `/doctor/`.
3. Manager/admin autenticado não acessa `/doctor/`, salvo se explicitamente tiver `active_role=doctor`.
4. NIR não consegue GET `/doctor/<case_id>/`.
5. NIR não consegue POST `/doctor/<case_id>/submit/`.
6. Doctor continua conseguindo acessar e submeter.

## Critérios de Sucesso

- Área médica protegida por papel ativo.
- Nenhum fluxo médico legítimo quebrado.
- Testes de autorização claros.

## Comandos de Validação Focados

```bash
uv run pytest apps/doctor/tests/test_views.py -q
uv run ruff check apps/doctor
uv run mypy apps/doctor
```

## Relatório Obrigatório

Crie:

```text
/tmp/ats-web-slice-006-doctor-role-guard-report.md
```

Responda com:

```text
REPORT_PATH=/tmp/ats-web-slice-006-doctor-role-guard-report.md
```

## Stop Rule

Não implemente mudanças em scheduler/admin neste slice.
