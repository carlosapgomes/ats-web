# Slice 001 — Política de acesso CHD em accounts

## Objetivo

Criar a política de acesso composto (papel ativo + posse de papel) como
unidades testáveis em `apps/accounts`: função `can_access_followup`,
decorator `followup_access_required` e variável de contexto
`can_access_followup`. Nenhuma view/template consome ainda (slice 002);
o comportamento entregue é a política correta comprovada por testes.

## Contexto necessário

- `apps/accounts/decorators.py` — `role_required` (padrão de flash + `redirect("/")`).
- `apps/accounts/context_processors.py` — `role_context` (expõe `active_role`).
- `apps/accounts/services.py` — services do app; precedentes de leitura de posse
  de papéis em `apps/accounts/middleware.py` (bypass multi-role do intranet guard).
- `apps/accounts/tests/test_context_processors.py` — padrões de teste com `rf`.
- Design: seções D1, D2, D3 e D6 de `openspec/changes/followup-chd-access-guard/design.md`.

## Requisitos verificáveis

- R1 `can_access_followup(user, active_role)` implementa exatamente a matriz D6
  (7 linhas: manager+scheduler/manager/admin/admin+scheduler ativo manager/
  scheduler ativo/doctor/nir/anônimo).
- R2 `followup_access_required` (decorator específico que CONSOME R1; ver
  design D2 — não há segunda implementação da composição): sem acesso →
  `messages.error` + `redirect("/")` (mesma UX/texto do `role_required`);
  com acesso → executa a view.
- R3 `role_context` expõe `can_access_followup` chamando R1 (anônimo → `False`).
- R4 Tipagem mypy estrita (decorator preserva assinatura via `wraps`).

## Matriz requisito -> arquivo -> teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `apps/accounts/services.py` | `test_can_access_followup_*` (matriz 7 casos) |
| R2 | `apps/accounts/decorators.py` | `test_followup_access_required_*` (bloqueia/pass) em view dummy |
| R3 | `apps/accounts/context_processors.py` | `test_can_access_followup_context_*` |
| R4 | idem | `uv run mypy apps/accounts` |

```yaml
expected_files:
  - apps/accounts/services.py
  - apps/accounts/decorators.py
  - apps/accounts/context_processors.py
  - apps/accounts/tests/test_access_policy.py   # novo (R1–R3)

allowed_incidental_files: []

out_of_scope:
  - qualquer arquivo de apps/dashboard ou templates
  - migrações, seeds, mudanças em Role
```

## Plano de testes do slice

### RED

- comando: `uv run pytest apps/accounts/tests/test_access_policy.py -q`
- falha esperada: `ImportError`/`AttributeError` — `can_access_followup`,
  `followup_access_required` e a variável de contexto não existem.

### GREEN / verificação local

- `uv run pytest apps/accounts/tests/test_access_policy.py -q` — exit 0
- `uv run pytest apps/accounts/tests -q` — exit 0 (sem regressão no app)
- `uv run ruff check apps/accounts && uv run ruff format --check apps/accounts` — exit 0
- `uv run mypy apps/accounts` — exit 0

## Critérios de aceitação

- [ ] Matriz D6 integral coberta por testes de R1
- [ ] Decorator bloqueia/pass conforme R2 consumindo a política única (D1/D2)
- [ ] Context processor expõe o bool correto (incl. anônimo)
- [ ] Blast radius = 4 arquivos previstos; gates locais verdes
