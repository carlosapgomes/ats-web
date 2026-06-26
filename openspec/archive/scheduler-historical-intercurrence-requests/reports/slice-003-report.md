# Relatório Slice 003 — Busca histórica scheduler + mensagem ao NIR

## Resumo da implementação

Implementação vertical do Slice 003 conforme spec: busca histórica scheduler, detalhe histórico read-only, e mensagem operacional CHD → NIR em caso `CLEANED`.

### Funcionalidades entregues

1. **R1. Busca histórica scheduler**: rota `/scheduler/historical/` com query por `agency_record_number` ou nome do paciente. Escopo: `doctor_decision=accept`, `doctor_admission_flow=scheduled`, `appointment_status` em `confirmed/denied/cancelled`.
2. **R2. Link de navegação**: botão "🔍 Buscar histórico" na queue template.
3. **R3. Detalhe histórico scheduler**: extensão da `scheduler_context_detail` para permitir acesso a casos no escopo histórico mesmo sem notificação prévia.
4. **R4. Mensagem CHD → NIR**: endpoint POST `/scheduler/historical/<uuid>/message-nir/` que valida escopo histórico, garante `@nir`, preserva menções adicionais, chama `post_case_communication_message` com `allow_cleaned=True`.
5. **R5. `allow_cleaned` opt-in**: parâmetro `allow_cleaned: bool = False` adicionado a `post_case_communication_message`. Default `False` preserva comportamento existente. O endpoint histórico chama com `True`.
6. **R6. Notificação NIR**: `UserNotification` criada via parser de menções existente. NIR ativo recebe notificação.
7. **R7. Status inalterado**: mensagem não altera `Case.status`.

### Arquivos alterados

| Arquivo | Tipo de mudança |
|---------|----------------|
| `apps/scheduler/views.py` | 3 novas funções + extensão de autorização |
| `apps/scheduler/urls.py` | 2 novas rotas |
| `templates/scheduler/historical_search.html` | **Novo** template |
| `templates/scheduler/queue.html` | Link de navegação |
| `templates/scheduler/context_detail.html` | Formulário de mensagem ao NIR |
| `apps/cases/services.py` | Parâmetro `allow_cleaned` |
| `apps/scheduler/tests/test_views.py` | 20 novos testes |
| `openspec/changes/scheduler-historical-intercurrence-requests/tasks.md` | Atualização DoD |

### Evidência RED

Comando executado:
```bash
uv run python -m pytest apps/scheduler/tests/test_views.py \
  -k "TestSchedulerHistoricalSearch or TestSchedulerHistoricalContextDetail or TestSchedulerHistoricalMessageNir or TestPostCaseCommunicationAllowCleaned" \
  -x --tb=short
```

Resultado: 1 falha — `test_scheduler_historical_search_requires_scheduler_role`:
```
assert 404 == 302
```
Rota `/scheduler/historical/` não existia.

### Evidência GREEN

Após implementação, comando:
```bash
uv run python -m pytest apps/scheduler/tests/test_views.py \
  -k "TestSchedulerHistoricalSearch or TestSchedulerHistoricalContextDetail or TestSchedulerHistoricalMessageNir or TestPostCaseCommunicationAllowCleaned" \
  -x --tb=short
```

Resultado: **20 passed, 103 deselected** — todos os 20 testes verdes.

### Quality gate

```bash
uv run ruff check .           # All checks passed
uv run ruff format --check .  # 1 file reformatted, now clean
uv run mypy .                 # Success: no issues found
uv run pytest                 # 1559 passed
```

### Snippets antes/depois

#### `apps/cases/services.py` — `post_case_communication_message`

Antes:
```python
    # Validação 5: caso CLEANED bloqueia post no MVP
    if case.status == CaseStatus.CLEANED:
        raise CaseCommunicationError("Não é possível enviar mensagens em um caso encerrado (CLEANED).")
```

Depois:
```python
def post_case_communication_message(
    *,
    case: Case,
    author: Any,
    author_role: str,
    body: str,
    allow_cleaned: bool = False,
) -> CaseCommunicationMessage:
    ...
    if case.status == CaseStatus.CLEANED and not allow_cleaned:
        raise CaseCommunicationError("Não é possível enviar mensagens em um caso encerrado (CLEANED).")
```

#### `apps/scheduler/views.py` — nova autorização

Antes:
```python
    if not _scheduler_has_context_notification(request.user, case):
        raise Http404("Nenhuma notificação encontrada para este caso.")
```

Depois:
```python
    if not _scheduler_has_context_notification(request.user, case) and not _is_scheduler_historical_case(case):
        raise Http404("Nenhuma notificação encontrada para este caso.")
```

#### Novos helpers

```python
def _is_scheduler_historical_case(case: Case) -> bool:
    if case.doctor_decision != "accept":
        return False
    if case.doctor_admission_flow != "scheduled":
        return False
    if case.appointment_status not in ("confirmed", "denied", "cancelled"):
        return False
    return True
```

#### Nova view `scheduler_historical_message_nir`

```python
@login_required
@role_required("scheduler")
def scheduler_historical_message_nir(request, case_id):
    if request.method != "POST":
        ...
    case = get_object_or_404(Case, case_id=case_id)
    if not _is_scheduler_historical_case(case):
        raise Http404(...)
    body_raw = request.POST.get("body", "").strip()
    if not body_raw:
        ...
    parsed = parse_mentions(body_raw)
    if "nir" not in parsed.role_tokens:
        body_raw = f"@nir {body_raw}"
    post_case_communication_message(
        case=case, author=request.user, author_role=active_role,
        body=body_raw, allow_cleaned=True,
    )
```

### Gates de autoavaliação

1. **Critério exato de "caso histórico scheduler"?** Centralizado em `_is_scheduler_historical_case(case)` e `_scheduler_historical_queryset()` em `apps/scheduler/views.py`.
2. **Busca limitada ao scheduler logado?** Não. A view usa `_scheduler_historical_queryset()` sem filtrar por `scheduler=request.user`. A intenção do produto é busca institucional.
3. **Teste que prova que busca não se limita a processados hoje?** `test_scheduler_historical_search_not_limited_to_today_or_current_scheduler`.
4. **Teste que prova que caso fora do escopo não abre por UUID?** `test_scheduler_context_detail_blocks_non_historical_case_without_notification`.
5. **Como o endpoint garante que NIR será notificado?** Usa `parse_mentions` e adiciona `@nir` se ausente. `post_case_communication_message` chama `create_case_communication_notifications`.
6. **Como preserva menções adicionais?** O `parse_mentions` extrai todas as menções e o `@nir` é apenas prefixado quando ausente — não há sanitização/remoção. Teste: `test_scheduler_historical_message_preserves_additional_mentions`.
7. **`post_case_communication_message` continua bloqueando `CLEANED` por padrão?** Sim, `allow_cleaned=False` por default. Teste: `test_post_case_communication_cleaned_still_blocked_by_default`.
8. **Teste que prova que mensagem não altera `Case.status`?** `test_scheduler_historical_message_does_not_change_case_status`.
9. **Novo modelo/tabela criado?** Não.
10. **Ação para CHD reabrir caso diretamente?** Não.

### Arquivos extras tocados

Nenhum além dos previstos. O template `scheduler/context_detail.html` já era esperado (item 4 na lista do slice).
