<!-- markdownlint-disable MD013 -->

# Slice 001: Janela de visibilidade de leitura na lista de notificações

## Handoff para implementador LLM com contexto zero

Você está no monolito Django SSR em `/projects/dev/ats-web`. Este é o **único slice** do change `notifications-read-visibility`. Não existe slice futuro a antecipar.

Leia integralmente, nesta ordem, antes de planejar ou editar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/notifications-read-visibility/proposal.md`
4. `openspec/changes/notifications-read-visibility/design.md`
5. `openspec/changes/notifications-read-visibility/specs/user-notifications/spec.md`
6. `openspec/changes/notifications-read-visibility/tasks.md`
7. este arquivo
8. `apps/accounts/models.py` — `UserNotification` (campos `recipient`, `read_at` nullable, `created_at`, `Meta.ordering`, constraints); não alterar campos
9. `apps/accounts/views.py` — `notifications_list`, `get_unread_notification_count`, views de open/mark-read (linhas ~114-230)
10. `apps/accounts/tests/test_notifications.py` — estilo de fixtures e testes de listagem existentes
11. `config/settings/base.py` — seção de constantes operacionais (ex.: `CASE_LOCK_LEASE_SECONDS`)

### Estado atual esperado

- `notifications_list` renderiza **todas** as `UserNotification` do usuário: `UserNotification.objects.filter(recipient=request.user).select_related("case", "communication_message", "triggered_by")`.
- `read_at` é `null` até a notificação ser aberta/marcada como lida.
- O template `accounts/notifications.html` e o badge de não lidas funcionam e não devem ser alterados.
- Não existe spec promovida para notificações; este change cria a capacidade `user-notifications`.

Se qualquer premissa divergir, registre no relatório antes de editar. Se houver worktree sujo, baseline vermelho ou necessidade de migration/template/JS, reporte **INCOMPLETE/BLOQUEADO** e pare em vez de improvisar.

## Fluxo vertical a entregar

```text
Usuário abre /accounts/notifications/
→ QuerySet visible_for_list() filtra read_at < now - 48h (NULL-safe)
→ view renderiza somente não lidas + leituras dos últimos 48h
→ badge de não lidas e fluxos de leitura permanecem idênticos
→ nada é apagado do banco
```

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 QuerySet NULL-safe oculta lidas antigas | `apps/accounts/models.py`, `apps/accounts/tests/test_notifications.py` | novos testes do QuerySet `visible_for_list` (4 casos de D2 do design) |
| R2 View usa a janela de visibilidade | `apps/accounts/views.py`, `apps/accounts/tests/test_notifications.py` | teste de integração da lista: lida há 49h ausente do HTML; lida há 1h e não lida antiga presentes |
| R3 Constante de settings com fallback | `config/settings/base.py`, `apps/accounts/models.py` | teste com `override_settings(NOTIFICATION_READ_RETENTION_HOURS=0)` esconde toda notificação lida |
| R4 Sem mutação de dados | — | `git diff` limitado aos arquivos previstos; nenhum `.delete()`/`.update()` adicionado |

## Requisitos verificáveis

### R1. `UserNotificationQuerySet.visible_for_list(now=None)`

- Criar `UserNotificationQuerySet(models.QuerySet)` com `visible_for_list(self, *, now=None)`:
  - `cutoff = (now or timezone.now()) - timedelta(hours=getattr(settings, "NOTIFICATION_READ_RETENTION_HOURS", 48))`;
  - retornar `self.exclude(read_at__lt=cutoff)` (não lidas têm `read_at` `NULL` e **não** são excluídas — cobrir com teste).
- Expor via manager (`from_queryset`) em `UserNotification.objects` preservando a API atual (`filter`, `create`, ordering de `Meta`).
- Testes unitários do QuerySet com `now` injetado, sem freezegun:
  1. lida há 49h → oculta;
  2. lida há 1h → visível;
  3. não lida criada há 30 dias → visível;
  4. criada há 100h e lida há 1h → visível; criada há 1h e lida há 100h → oculta.

### R2. `notifications_list` consome a janela

- Substituir o `filter(recipient=...)` pela chamada equivalente com `visible_for_list()` (mantendo `recipient`, `select_related` e o contexto existente, incluindo `unread_count`).
- Teste de integração com `client`: notificação lida há 49h não aparece na resposta; lida há 1h aparece; não lida antiga aparece.

### R3. Settings

- Adicionar `NOTIFICATION_READ_RETENTION_HOURS = 48` em `config/settings/base.py`, próximo das constantes operacionais existentes.
- Um teste com `django.test.override_settings` provando que a constante é efetivamente consumida (ex.: janela `0` oculta qualquer notificação lida).

### R4. Sem mutação e sem expansão

- Nenhum método de escrita novo; nenhum template/JS/URL/migration tocado.
- Verificação por `git status --short` + `git diff --stat`: somente `apps/accounts/models.py`, `apps/accounts/views.py`, `config/settings/base.py`, `apps/accounts/tests/test_notifications.py` (e artefatos deste change em `openspec/`).

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/accounts/models.py
  - apps/accounts/views.py
  - config/settings/base.py
  - apps/accounts/tests/test_notifications.py

allowed_incidental_files: []

out_of_scope:
  - deletar/atualizar notificações (qualquer .delete()/.update() em produção)
  - alterar badge, polling JS, templates, URLs, permissões
  - alterar CaseCommunicationMessage ou CaseEvent
  - paginação, filtros novos, env vars
  - migrations (nenhuma é necessária; se parecer necessária, é bloqueio)
```

Escale em vez de ampliar silenciosamente se precisar tocar qualquer arquivo fora da lista.

## Plano de testes do slice

### Baseline (antes de editar)

1. `git status --short` limpo (ignorando apenas as deleções pré-existentes não relacionadas em `.pi/skills/`); registre branch `change/notifications-read-visibility` criada a partir de `main` atualizado e `BASE_REF=$(git rev-parse HEAD)`.
2. `uv run pytest` — registre exit code e totais (`passed`, `failed`, `errors`). Se houver falha/erro pré-existente, pare e reporte bloqueio.

### RED

- Comando: `uv run pytest apps/accounts/tests/test_notifications.py -k "read_visibility" -x`
- Escreva primeiro os testes novos (classe `TestNotificationsListReadVisibility` e testes do QuerySet) **antes** de qualquer edição de produção.
- Falha esperada: os testes de ocultação falham porque `visible_for_list` não existe (`AttributeError`) ou porque a view ainda lista a notificação lida há 49h. Falha por import quebrado do módulo inteiro não conta como RED válido — se acontecer, ajuste o teste para importar somente o necessário.

### GREEN / verificação local

- `uv run pytest apps/accounts/tests/test_notifications.py -k "read_visibility"` — exit code 0.
- `uv run pytest apps/accounts/tests/` — exit code 0 (regressão do app).
- `uv run ruff check apps/accounts config` e `uv run ruff format --check apps/accounts config` — exit code 0.
- `uv run mypy apps/accounts` — exit code 0.
- Inspeção: `rg -n "delete\(\)|\.update\(" apps/accounts/models.py apps/accounts/views.py` não deve retornar linhas novas adicionadas por este slice (interprete no relatório).

### Gate final do change (após GREEN)

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

Pytest final: exit code 0, zero failures/errors, `passed_final >= passed_baseline`.

## Critérios de aceitação

- [ ] R1: `visible_for_list` NULL-safe com 4 casos de teste unitário passando.
- [ ] R2: lista da view não renderiza lidas há 49h; mantém lidas há 1h e não lidas.
- [ ] R3: `NOTIFICATION_READ_RETENTION_HOURS` definido e consumido (teste com override).
- [ ] R4: diff limitado aos 4 arquivos previstos; zero mutação de dados.
- [ ] RED/GREEN comprovados no relatório; gate final completo verde.

## Conclusão controlada

Somente após todos os gates: marque o Slice 001 e os itens comprovados em `tasks.md`, gere o relatório em `/tmp/notifications-read-visibility-slice-001-report.md` (baseline, RED/GREEN, snippets antes/depois, inspeções, gates, rerun, `Handoff para verificador`), faça commit rastreável (`feat(accounts): hide read notifications older than 48h from list`), push da branch, atualize o relatório com hash/push, responda com `REPORT_PATH` e **pare**.
