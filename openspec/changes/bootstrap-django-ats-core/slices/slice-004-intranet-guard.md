# Slice 4: Middleware Intranet Guard

> **Status**: DONE
> **Depende de**: Slice 2 (accounts app com User/Role)
> **Change**: `openspec/changes/bootstrap-django-ats-core/`

---

## Leitura Obrigatória Antes de Implementar

Antes de escrever qualquer código, leia estes arquivos na ordem:

1. `AGENTS.md` — regras do projeto, stack, comandos de validação, política de testes
2. `docs/adr/ADR-0001-arquitetura-django-web-ssr-ats-triagem-eda.md` — decisão arquitetural aceita
3. `docs/DOMAIN_ANALYSIS.md` — análise completa de domínio (entidades, estados, transições, eventos, permissões, telas)

Estes documentos dão o contexto de **por que** cada modelo, estado e regra existe.
Sem lê-los, você não terá contexto do domínio clínico (triagem EDA, políticas de pré-operatório, fluxo NIR-médico-agendador).

---

## Handoff para Implementador (LLM com contexto zero)

### Contexto

Você está em `/home/carlos/projects/ats-web/`, um projeto Django greenfield.
Os **Slices 1-3** já foram executados:
- Estrutura base + app accounts (User multi-role) + app cases (Case FSM + CaseEvent)

Leia `AGENTS.md` para regras do projeto.

### Sua Tarefa

Criar middleware que restringe acesso de papéis `nir` e `scheduler` ao range
de IPs da intranet, configurado via env var `INTRANET_IP_RANGE` (formato CIDR).
Papéis `doctor`, `manager` e `admin` podem acessar de qualquer lugar.

O sistema é acessado externamente via túnel Cloudflare com SSL. O header
`CF-Connecting-IP` carrega o IP real do cliente.

### Arquivos a Criar/Modificar (idealmente <= 5)

```
apps/accounts/middleware.py   # MODIFICAR: adicionar IntranetGuardMiddleware
config/settings/base.py       # MODIFICAR: adicionar config + middleware
apps/accounts/tests/test_intranet_guard.py  # testes do middleware
```

### Detalhes Técnicos

#### apps/accounts/middleware.py — adicionar IntranetGuardMiddleware

```python
import ipaddress
import logging

from django.conf import settings
from django.http import HttpResponseForbidden


logger = logging.getLogger(__name__)

INTRANET_RESTRICTED_ROLES = {"nir", "scheduler"}


def _get_client_ip(request) -> str:
    """Extrai IP real do cliente do header configurado ou REMOTE_ADDR."""
    header = getattr(settings, "TRUSTED_PROXY_HEADER", None)
    if header:
        value = request.META.get(header, "")
        if value:
            # X-Forwarded-For pode ter múltiplos IPs; pegar o primeiro
            return value.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _is_intranet_ip(client_ip: str) -> bool:
    """Verifica se o IP está dentro do range da intranet."""
    ip_range = getattr(settings, "INTRANET_IP_RANGE", None)
    if not ip_range:
        # Se não configurado, bloquear papéis restritos por segurança
        return False
    try:
        network = ipaddress.ip_network(ip_range, strict=False)
        addr = ipaddress.ip_address(client_ip)
        return addr in network
    except (ValueError, TypeError):
        return False


class IntranetGuardMiddleware:
    """Bloqueia acesso de papéis restritos (nir, scheduler) fora da intranet."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            active_role = request.session.get("active_role")
            if active_role in INTRANET_RESTRICTED_ROLES:
                client_ip = _get_client_ip(request)
                if not _is_intranet_ip(client_ip):
                    logger.warning(
                        "intranet_guard_blocked user=%s role=%s ip=%s path=%s",
                        request.user.pk,
                        active_role,
                        client_ip,
                        request.path,
                    )
                    return HttpResponseForbidden(
                        "Acesso restrito à rede interna do hospital."
                    )
        return self.get_response(request)
```

#### config/settings/base.py — adicionar

```python
# Intranet Guard
# Range CIDR da intranet (ex: "10.0.0.0/8" ou "192.168.0.0/16")
# Se vazio, papéis nir/scheduler são bloqueados de qualquer IP.
INTRANET_IP_RANGE = env("INTRANET_IP_RANGE", default="")

# Header do proxy/tunnel com IP real do cliente
# Cloudflare Tunnel padrão usa CF-Connecting-IP
TRUSTED_PROXY_HEADER = env("TRUSTED_PROXY_HEADER", default="HTTP_CF_CONNECTING_IP")
```

Adicionar `"apps.accounts.middleware.IntranetGuardMiddleware"` em `MIDDLEWARE`
após `"apps.accounts.middleware.ActiveRoleMiddleware"`.

### TDD — Testes a Escrever PRIMEIRO

Criar `apps/accounts/tests/test_intranet_guard.py`:

1. `test_doctor_role_allowed_from_any_ip`: doctor + IP externo → 200
2. `test_manager_role_allowed_from_any_ip`: manager + IP externo → 200
3. `test_admin_role_allowed_from_any_ip`: admin + IP externo → 200
4. `test_nir_role_blocked_from_external_ip`: nir + IP externo (1.2.3.4) → 403
5. `test_scheduler_role_blocked_from_external_ip`: scheduler + IP externo → 403
6. `test_nir_role_allowed_from_intranet_ip`: nir + IP interno (10.0.0.1) → 200
7. `test_scheduler_role_allowed_from_intranet_ip`: scheduler + IP interno → 200
8. `test_no_intranet_range_configured_blocks_restricted_roles`: sem INTRANET_IP_RANGE → nir bloqueado
9. `test_unauthenticated_user_not_blocked`: sem login → passa pelo middleware
10. `test_no_active_role_not_blocked`: autenticado sem active_role → passa

**Helper para testes**: criar factory/function que gera request mock com
`user`, `session["active_role"]`, e `META["REMOTE_ADDR"]` configuráveis.

### Critérios de Sucesso (Self-Eval Gates)

```bash
# Gate 1: Django check
uv run python manage.py check --settings=config.settings.dev

# Gate 2: testes do middleware
uv run pytest apps/accounts/tests/test_intranet_guard.py -v
# Esperado: todos passando

# Gate 3: testes existentes continuam passando
uv run pytest -v
# Esperado: zero regressões
```

### Relatório

Gere `/tmp/slice-004-report.md`.
Informe `REPORT_PATH=/tmp/slice-004-report.md`.
