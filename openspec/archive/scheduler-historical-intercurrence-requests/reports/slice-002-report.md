# Relatório Slice 002 — CHD mencionado: detalhe read-only e resposta sem workflow

## Resumo da implementação

Implementação do Slice 002: quando um scheduler/CHD é mencionado (`@scheduler` / `@chd` / `@username`) em um caso fora de `WAIT_APPT`, ao abrir a notificação ele é redirecionado para um detalhe contextual read-only. O detalhe mostra dados do caso, timeline e thread de comunicação, permitindo responder apenas quando o caso não está `CLEANED`. Nenhuma ação de workflow (lock, confirmar/negar agendamento, intercorrência) é exibida.

## Arquivos alterados

| Arquivo | Tipo de mudança |
|---------|----------------|
| `apps/accounts/services.py` | **Edit**: `resolve_notification_redirect_url` — scheduler não-WAIT_APPT vai para `scheduler:context_detail` |
| `apps/scheduler/urls.py` | **Edit**: nova rota `context/<uuid:case_id>/` → `scheduler_context_detail` |
| `apps/scheduler/views.py` | **Add**: view `scheduler_context_detail` + helper `_scheduler_has_context_notification` |
| `templates/scheduler/context_detail.html` | **Add**: template read-only contextual |
| `apps/scheduler/tests/test_views.py` | **Add**: classe `TestSchedulerContextDetail` com 10 testes |
| `apps/accounts/tests/test_notifications.py` | **Edit**: novos testes de redirect + atualização de teste existente |
| `apps/scheduler/tests/test_communication.py` | **Edit**: hardening test — exclui `apps/scheduler/views.py` da verificação (intencional) |
| `openspec/changes/.../tasks.md` | **Edit**: Slice 002 marcado como concluído |

## Evidência do RED

Comando executado:

```bash
uv run pytest apps/scheduler/tests/test_views.py::TestSchedulerContextDetail -x --no-header -q
```

Testes falhando (rota não existe):

1. `test_scheduler_context_detail_requires_login` — 404 (rota não existe)
2. `test_scheduler_context_detail_requires_scheduler_role` — 404
3. `test_scheduler_context_detail_requires_notification_for_user` — 404
4. `test_scheduler_context_detail_allows_recipient_notification` — 404
5. `test_scheduler_context_detail_does_not_allow_other_scheduler_notification` — 404
6. `test_scheduler_context_detail_renders_readonly_case_context` — 404
7. `test_scheduler_context_detail_hides_workflow_actions` — 404
8. `test_scheduler_context_detail_allows_communication_reply_when_not_cleaned` — 404
9. `test_scheduler_context_detail_post_reply_creates_message` — 404
10. `test_scheduler_context_detail_cleaned_is_readonly_for_communication` — 404

E nos testes de redirect:

```bash
uv run pytest apps/accounts/tests/test_notifications.py -k "test_scheduler_notification" --no-header -q
```

2 falharam com `NoReverseMatch` para `context_detail`:
- `test_scheduler_notification_for_non_wait_appt_redirects_to_context_detail`
- `test_scheduler_notification_for_doctor_accepted_redirects_to_context_detail`

## Evidência do GREEN

```bash
uv run pytest apps/scheduler/tests/ apps/accounts/tests/test_notifications.py -x --no-header -q
```

Resultado: **202 passed**

## Snippets antes/depois

### `apps/accounts/services.py` — resolve_notification_redirect_url

**Antes:**
```python
if active_role == "scheduler":
    if status == CaseStatus.WAIT_APPT:
        return reverse("scheduler:confirm", kwargs={"case_id": case.pk})
    return reverse("scheduler:queue")
```

**Depois:**
```python
if active_role == "scheduler":
    if status == CaseStatus.WAIT_APPT:
        return reverse("scheduler:confirm", kwargs={"case_id": case.pk})
    return reverse("scheduler:context_detail", kwargs={"case_id": case.pk})
```

### `apps/scheduler/urls.py`

**Antes:** sem rota `context/`

**Depois:**
```python
path("context/<uuid:case_id>/", views.scheduler_context_detail, name="context_detail"),
```

### `apps/scheduler/views.py` — view nova

```python
@login_required
@role_required("scheduler")
def scheduler_context_detail(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """GET: Detalhe contextual read-only para scheduler mencionado.
    
    Exige que o usuário logado possua UserNotification vinculada ao caso.
    Não adquire lock, não altera FSM, não mostra ações de workflow.
    ...
    """
```

### `templates/scheduler/context_detail.html` — template novo

Template que estende `base.html` e mostra:
- Dados do paciente, registro, origem
- Stepper de progresso
- Decisão médica (se houver)
- Dados de agendamento (se houver)
- Intercorrência pós-agendamento (read-only, se houver)
- Thread de comunicação (com `_communication_thread.html`)
- Timeline
- Apenas botão "← Voltar" — sem ações de workflow

## Resultados do quality gate

```text
uv run ruff check .       → All checks passed!
uv run ruff format --check . → 166 files already formatted
uv run mypy .             → Success: no issues found in 185 source files
uv run pytest             → 1536 passed
```

## Respostas aos gates de autoavaliação

1. **Qual rota nova abre o detalhe contextual scheduler?**
   `scheduler:context_detail` → URL: `/scheduler/context/<uuid:case_id>/`

2. **Como a rota valida que o scheduler foi mencionado/notificado?**
   View `scheduler_context_detail` usa o helper `_scheduler_has_context_notification(user, case)` que verifica se existe `UserNotification` para o par `(recipient=user, case=case)`.

3. **Qual teste prova que outro scheduler não acessa por UUID?**
   `test_scheduler_context_detail_does_not_allow_other_scheduler_notification` — cria notificação para `other_scheduler`, mas tenta acessar como `sched_other_notif` → recebe 404.

4. **Qual teste prova que o redirect de `WAIT_APPT` não quebrou?**
   `test_scheduler_notification_for_wait_appt_still_redirects_to_confirm` — scheduler com caso `WAIT_APPT` continua sendo redirecionado para `scheduler:confirm`.

5. **Quais ações de workflow foram explicitamente escondidas?**
   O teste `test_scheduler_context_detail_hides_workflow_actions` verifica que a resposta não contém: `"Confirmar Agendamento"`, `"Negar Agendamento"`, `"lock_token"`, `"lock-renew"`, `"scheduler:submit"`, `"work-lock-config"`, `"SchedulerDecisionForm"`.

6. **O detalhe adquire lock?**
   **Não.** A view não chama `claim_case_lock` nem qualquer função de lock.

7. **A resposta de comunicação reutiliza o endpoint/serviço existentes?**
   **Sim.** O template usa `communication_post_url` apontando para `intake:post_case_communication` e o serviço `post_case_communication_message` existente.

8. **Algum suporte a caso `CLEANED` foi implementado aqui?**
   **Não.** O template usa `can_post_communication = case.status != CaseStatus.CLEANED`, que bloqueia o form de post em casos `CLEANED`. O teste `test_scheduler_context_detail_cleaned_is_readonly_for_communication` valida que a mensagem "Não é possível enviar mensagens" aparece.

## Nenhum arquivo extra tocado

Todos os arquivos alterados estavam na lista esperada do slice. Nenhum arquivo extra foi necessário.
