# Relatório: Slice 3 — Quality Gate

## Data: 2026-05-07

## Resultados da Validação

| Gate | Status | Detalhes |
|------|--------|----------|
| `ruff check .` | ✅ | All checks passed |
| `ruff format --check .` | ✅ | 107 files already formatted |
| `mypy .` | ✅ | Success: no issues in 113 source files |
| `pytest` | ✅ | 479 passed in 13.93s |
| Teste manual no browser | ✅ | Usuários criados, login com novos usuários OK |

## Observações

- Os warnings exibidos são de terceiros (`django-q2` — retry/timeout misconfigured; `django-fsm` — deprecation notice) e não afetam o código do projeto.
- Warnings de `staticfiles/` ausente são esperados em dev; o diretório é criado pelo `collectstatic` em produção.
- Todos os 479 testes da suite passaram sem falhas.

## Problema encontrado e corrigido: Roles não semeadas

**Problema**: O banco não tinha os 5 papéis padrão (`nir`, `doctor`, `scheduler`, `manager`, `admin`).
O usuário `admin` (superuser) só tinha `nir`, `doctor`, `manager` — sem o papel `admin` porque o registro não existia.

**Correção**:
- Data migration `apps/accounts/migrations/0002_seed_roles.py` — cria os 5 papéis via `get_or_create`
- A migration também atribui o papel `admin` a todos os superusuários existentes
- 9 arquivos de teste corrigidos para usar `get_or_create` (idempotente) em vez de `create`

## Melhoria solicitada: Reset de senha

O formulário de edição de usuário (`UserUpdateForm`) não inclui campo de senha.
Sugestão: usar Django admin (`/admin/auth/user/`) para redefinir senhas,
ou implementar feature de reset de senha na admin_ui (fora do escopo atual).
