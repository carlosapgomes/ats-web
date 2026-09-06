# Design: Acesso à aba Follow-up restrito a supervisores do CHD

## D1 — Política como função pura única (`apps/accounts/services.py`)

A regra do proposal vira UMA função, fonte única consumida por decorator e
context processor:

```python
def can_access_followup(user, active_role: str) -> bool:
    """Aba Follow-up é operação do supervisor do CHD.

    Papel ativo manager exige posse do papel scheduler (CHD);
    papel ativo admin é isento (emergência/suporte).
    """
```

Implementação: `active_role in {"manager","admin"}` e, se `manager`,
`user.roles.filter(name="scheduler").exists()`. Precedentes de checagem de
posse de papel (independente do papel ativo) já existem em
`apps/accounts/middleware.py` (bypass multi-role do guard de intranet) e
`apps/admin_ui/views.py`.

## D2 — Decorator composto em `apps/accounts/decorators.py`

`role_required` verifica apenas o papel ativo. O novo decorator é genérico e
reutilizável, sem embutir política de follow-up:

```python
@role_membership_required("scheduler", exempt_active_roles=("admin",))
```

- Deve ser empilhado DEPOIS de `@login_required` + `@role_required("manager","admin")`
  (só roda para manager/admin ativos; o resto já foi redirecionado antes).
- Sem posse: mesma UX do `role_required` — `messages.error` ("Você não tem
  permissão para acessar esta página.") + `redirect("/")`.
- O decorator consulta `can_access_followup`? **Não**: o decorator recebe
  `(membership_role, exempt_active_roles)` genéricos; a função D1 compõe a
  mesma lógica para o processador de contexto. Para evitar divergência entre
  decorator e função, o decorator de follow-up nas views é construído a partir
  dos MESMOS parâmetros da política: em `views.py`,
  `@role_membership_required("scheduler", exempt_active_roles=("admin",))`
  espelha D1. A coesão é garantida por testes da matriz (D6) cobrindo os dois
  caminhos com os mesmos cenários.

Alternativa descartada: decorator específico `chd_followup_required` em
`apps/dashboard` — criaria segunda implementação da política e acoplaria
dashboard à leitura direta de `Role`.

## D3 — UX de bloqueio (decisão do dono)

- **Nav**: pill "Follow-up" (`templates/dashboard/_nav.html`) renderiza somente
  com `{% if can_access_followup %}`. Context processor `role_context`
  (`apps/accounts/context_processors.py`) passa a expor `can_access_followup`
  (chama D1; `False` para anônimo). Uma query `exists()` barata por request
  autenticado (mesmo custo do `queue_counts` existente).
- **URL**: 4 views (`followup_list`, `followup_form`, `followup_history`,
  `followup_history_export` em `apps/dashboard/views.py`) recebem o decorator.
  Redireciona para `/` com flash — idêntico ao comportamento de papel errado
  hoje (`role_required`), sem página nova de erro.

## D4 — Admin isento (decisão do dono)

`admin` ativo acessa sem possuir `scheduler`: é o papel de emergência/suporte.
Isenção expressa via `exempt_active_roles=("admin",)` — política declarada, não
`hardcode` escondido. O superusuário de plantão (que possui todos os papéis)
continua acessando por qualquer caminho.

## D5 — Specs: MODIFIED nas duas capabilities

- `supervisor-appointment-follow-up`: requisito de acesso (linha ~83) passa a
  exigir posse de `scheduler` para `manager` ativo; cenários novos ("manager sem
  vínculo CHD é bloqueado", "admin acessa sem vínculo CHD"); cenário "Papel sem
  permissão" (scheduler ativo) mantido.
- `supervisor-followup-history`: requisito das sub-abas (linha ~8) recebe a
  mesma cláusula de acesso + "aba oculta na navegação para quem não satisfizer".
- Textos de manual ficam para o change de renomeação (reescreve §6 inteiro
  depois deste).

## D6 — Matriz de testes (mesma para unit e views)

| Usuário (papéis possuídos) | Papel ativo | Nav pill | 4 rotas |
|---|---|---|---|
| manager + scheduler | manager | visível | 200 (fluxo atual) |
| manager | manager | oculta | 302 `/` + flash |
| admin | admin | visível | 200 |
| admin + scheduler | manager | visível | 200 |
| scheduler (+manager) | scheduler | oculta | 302 (como hoje) |
| doctor / nir | doctor/nir | oculta | 302 (como hoje) |
| — | anônimo | oculta | 302 login (como hoje) |

Unit: D1 (7 linhas da matriz) + decorator (bloqueio/flash/redirect e passagem)
+ context processor (expõe o bool certo; anônimo `False`). Views: aplicação do
decorator nas 4 rotas (coluna "4 rotas") + pill em `dashboard:index`.

Helpers `_login_as(role)` dos testes de dashboard criam usuários de papel
único: casos permitidos passam a usar helper novo (ex.: `_login_as_chd_manager`)
que atribui `manager`+`scheduler`; `test_manager_allowed` existentes convertem
para o helper novo, e testes novos cobrem manager-sem-CHD bloqueado.

## D7 — Ordem e riscos

- Slice 001 (accounts: política+decorator+processor) não muda comportamento
  observável do usuário (nenhum consumidor ainda) — aceitável como fundação
  testável de forma independente; slice 002 torna tudo observável end-to-end.
- Risco baixo: nenhuma migration, nenhum dado, guard aditivo. Rollback = remover
  decorator + condicional (revert limpo).
- Em produção, 5 usuários `manager`+`scheduler` (incl. `admin`) mantêm acesso;
  demais `manager` perdem a aba (efeito desejado).
