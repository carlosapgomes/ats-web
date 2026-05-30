# Design: Correção IntranetGuardMiddleware + Bypass Multi-Role

## Problema

1. `IntranetGuardMiddleware` define `EXEMPT_PATHS` mas **não checa** — o path `/switch-role/` é bloqueado quando `active_role` é `nir`/`scheduler`, impedindo o usuário de trocar de papel.
2. Usuários com múltiplos papéis (ex: admin + nir) ficam presos: mesmo tendo papel admin, são bloqueados se o papel ativo for `nir`.

## Solução

### A) Respeitar EXEMPT_PATHS no IntranetGuardMiddleware

Adicionar `request.path not in EXEMPT_PATHS` antes de bloquear. Isso garante que `/switch-role/` (e `/login/`, `/logout/`) sempre funcionem, permitindo que o usuário troque de papel mesmo com `active_role` restrito.

### B) Bypass para usuários com múltiplos papéis não-restritos

Se o usuário possui **qualquer** papel fora de `{"nir", "scheduler"}`, o guard não bloqueia — mesmo que o `active_role` atual seja `nir` ou `scheduler`.

Lógica:
```python
user_roles = set(request.user.roles.values_list("name", flat=True))
has_unrestricted = bool(user_roles - INTRANET_RESTRICTED_ROLES)
if has_unrestricted:
    return self.get_response(request)  # bypass
```

### Fluxo completo do `__call__`

```
1. Não autenticado? → passa
2. active_role não é nir/scheduler? → passa
3. path é EXEMPT? → passa
4. usuário tem papel não-restrito? → passa (bypass multi-role)
5. IP é intranet? → passa
6. Senão → 403
```

### Impacto na segurança

- **Pessoas com múltiplos papéis**: só admin e manager recebem papéis extras (`nir`, `scheduler`). Ambos são papéis de confiança. O bypass não enfraquece a segurança porque esses usuários já têm acesso privilegiado de qualquer forma.
- **Usuários só-NIR / só-Scheduler**: continuam bloqueados de fora da intranet. Nenhuma mudança.
- **EXEMPT_PATHS**: `/switch-role/`, `/login/`, `/logout/` já eram isentos no `ActiveRoleMiddleware`. Só está sendo corrigida a inconsistência.

## Arquivos alterados

| Arquivo | Mudança |
|---|---|
| `apps/accounts/middleware.py` | Adicionar checagem de EXEMPT_PATHS + bypass multi-role no `IntranetGuardMiddleware.__call__` |
| `apps/accounts/tests/test_intranet_guard.py` | 5 novos testes: EXEMPT_PATHS exemption, multi-role bypass (nir+admin, scheduler+manager, nir-only still blocked, nir sem outros papéis) |

## Critérios de sucesso

- [ ] `/switch-role/` acessível com `active_role=nir` de IP externo
- [ ] Usuário com `nir` + `admin` não é bloqueado de IP externo
- [ ] Usuário com `scheduler` + `manager` não é bloqueado de IP externo
- [ ] Usuário **só** com `nir` continua bloqueado de IP externo
- [ ] Usuário **só** com `scheduler` continua bloqueado de IP externo
- [ ] Testes passando (RED → GREEN)
- [ ] Lint + type check passando
