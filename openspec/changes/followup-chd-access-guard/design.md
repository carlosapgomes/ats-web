# Design: Acesso à aba Follow-up restrito a supervisores do CHD

## D1 — Política como função pura única (`apps/accounts/services.py`)

A regra do proposal vira UMA função, **fonte única** consumida por decorator e
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

## D2 — Decorator específico consumindo a política única

`role_required` verifica apenas o papel ativo. O novo decorator é
**específico do follow-up** e **chama `can_access_followup`** — nenhuma
segunda implementação da composição existe no código:

```python
def followup_access_required(view_func):
    """Exige a política CHD (D1). Empilhar após @login_required +
    @role_required("manager", "admin"). Sem acesso: flash + redirect("/")."""
```

- Empilhado DEPOIS de `@login_required` + `@role_required("manager","admin")`
  (só roda para manager/admin ativos; o resto já foi redirecionado antes).
- Sem acesso: mesma UX do `role_required` — `messages.error` ("Você não tem
  permissão para acessar esta página.") + `redirect("/")`.
- Nav (context processor) e views consultam a MESMA função D1 → coesão por
  construção, sem parâmetros repetidos em dois lugares.

Alternativa descartada (review P1): decorator genérico parametrizado
(membership + isenções passados nas views) — permitia divergência entre nav e
URLs por repetir a composição da política em dois lugares. Se um
segundo consumidor de guarda composta surgir no futuro, generaliza-se a partir
deste, com teste.

## D3 — UX de bloqueio (decisão do dono)

- **Nav**: pill "Follow-up" (`templates/dashboard/_nav.html`) renderiza somente
  com `{% if can_access_followup %}`. Context processor `role_context`
  (`apps/accounts/context_processors.py`) passa a expor `can_access_followup`
  (chama D1; `False` para anônimo). Uma query `exists()` barata por request
  autenticado (mesmo custo do `queue_counts` existente).
- **URL**: 4 views (`followup_list`, `followup_form`, `followup_history`,
  `followup_history_export` em `apps/dashboard/views.py`) recebem
  `@followup_access_required`. Redireciona para `/` com flash — idêntico ao
  comportamento de papel errado hoje (`role_required`), sem página nova.

## D4 — Admin isento (decisão do dono)

`admin` ativo acessa sem possuir `scheduler`: papel de emergência/suporte.
A isenção vive DENTRO de D1 (função única) — política declarada em um lugar.
O superusuário de plantão (que possui todos os papéis) continua acessando.

## D5 — Specs: MODIFIED/RENAMED nas duas capabilities

- `supervisor-appointment-follow-up`:
  - RENAMED do requisito de acesso ("apenas a manager e admin" → "apenas a
    supervisores do CHD e admin") + MODIFIED com cenários CHD (manager sem
    vínculo bloqueado; manager com vínculo preservado; admin isento; papel sem
    permissão; 404/inelegível e sem-procedimentos preservados com GIVEN
    qualificado para supervisor do CHD).
  - MODIFIED do requisito de gravação (linha ~8): "papéis `manager` e `admin`
    registram" → "supervisores do CHD … e `admin` registram"; cenário
    "Registro inicial de desfecho" com WHEN qualificado (review P1: menções
    amplos ficariam semanticamente errôneas após o guard).
  - Nota: o bloco `## Purpose` (linha ~4) menciona `manager`/`admin` como
    público; deltas OpenSpec operam sobre Requirements, não sobre Purpose. O
    requisito de acesso modificado carrega a regra precisa; Purpose permanece
    como resumo de capability (desvio documentado e aceito).
- `supervisor-followup-history`: requisito das sub-abas (linha ~8) recebe a
  cláusula de acesso CHD + "aba oculta"; cenário "Sub-abas visíveis e ativas"
  com GIVEN manager+scheduler; novo cenário "Manager sem vínculo CHD não vê a
  aba". Os demais requisitos (janela, versão corrente, cards, filtros,
  exportação) tratam apenas de comportamento dado o acesso e não afirmam que
  qualquer `manager` acessa — os cenários "sem papel" (linhas ~21/~112)
  permanecem verdadeiros como subconjunto dos bloqueados.
- Textos de manual ficam para `followup-pos-procedimento-ui` (reescreve §6
  inteiro depois deste change; dependência declarada lá).

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

Unit: D1 (7 linhas da matriz) + decorator `followup_access_required`
(bloqueio/flash/redirect e passagem, consumindo D1) + context processor
(expõe o bool certo; anônimo `False`). Views: aplicação nas 4 rotas (coluna
"4 rotas") + pill em `dashboard:index`.

**Estratégia de helpers (review P1)**: dezenas de testes de comportamento
chamam `_login_as(client, "manager")` e esperam 200 — após o guard, manager de
papel único receberia 302. Decisão: nos 3 arquivos de teste de follow-up,
`_login_as("manager")` passa a criar o usuário com os papéis
`manager`+`scheduler` (manager de teste = supervisor do CHD, refletindo a
população real da feature), e um helper novo `_login_as_plain_manager` cria
`manager` sem `scheduler` exclusivamente para os testes de bloqueio. Os testes
de comportamento existentes seguem passando sem edição individual; os casos
`test_manager_allowed` ganham asserção de que o usuário possui ambos os papéis
(documentação viva do requisito). A linha "admin + scheduler ativo manager" da
matriz ganha teste explícito de view (usuário com os dois papéis, sessão
`manager`).

## D7 — Ordem e riscos

- Slice 001 (accounts: política+decorator+processor) não muda comportamento
  observável do usuário (nenhum consumidor ainda) — aceitável como fundação
  testável de forma independente; slice 002 torna tudo observável end-to-end.
- Risco baixo: nenhuma migration, nenhum dado, guard aditivo. Rollback = remover
  decorator + condicional (revert limpo).
- Em produção, 5 usuários `manager`+`scheduler` (incl. `admin`) mantêm acesso;
  demais `manager` perdem a aba (efeito desejado).
- Ordem entre changes: este change DEVE ser executado/arquivado antes de
  `followup-pos-procedimento-ui` (dependência do manual e dos deltas
  encadeados no requisito das sub-abas).
