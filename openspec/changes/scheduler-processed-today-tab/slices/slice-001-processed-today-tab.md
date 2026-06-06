# Slice 001: Aba Processados Hoje + detalhe read-only agendador

## Contexto zero para implementador

A tela do agendador (`/scheduler/`) foi criada no change arquivado `openspec/archive/scheduler-queue/`. Ela trouxe pills `Pendentes`, `Confirmados Hoje` e `Histórico` herdados do mock. Hoje:

- `Histórico` não foi implementado; é placeholder visual.
- `Confirmados Hoje` não é uma aba funcional; é um `<span>` no header e uma tabela opcional abaixo da fila.
- O nome está incorreto: o agendador pode confirmar ou recusar, então a lista deve ser de `Processados Hoje`.
- A query atual não filtra explicitamente pelo agendador logado e depende de status/evento.

O dashboard de supervisor/admin já tem detalhe read-only em `apps/dashboard/views.py::dashboard_case_detail`, renderizando `templates/intake/case_detail.html` com navegação parametrizada.

## Objetivo do slice

Implementar uma entrega vertical:

```text
Agendador abre /scheduler/ → clica Processados Hoje → vê cards de casos que confirmou/recusou hoje → clica Ver detalhes → vê detalhe read-only completo → volta para Processados Hoje
```

Também remover a aba `Histórico` e remover/renomear `Confirmados Hoje`.

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/scheduler/views.py`
2. `apps/scheduler/urls.py`
3. `templates/scheduler/queue.html`
4. `templates/scheduler/_queue_content.html`
5. `apps/scheduler/tests/test_views.py`

Se for necessário extrair helper compartilhado de detalhe read-only, justificar no relatório do slice.

## Requisitos funcionais

### R1. Navegação

Em `templates/scheduler/queue.html`:

- substituir pills estáticos por links;
- manter `Pendentes` ativo por padrão;
- adicionar `Processados Hoje` como link para `/scheduler/?tab=processed`;
- remover `Histórico`;
- remover o rótulo `Confirmados Hoje`.

Exemplo conceitual:

```django
<a class="nav-link {% if active_tab == 'pending' %}active{% endif %}" href="{% url 'scheduler:queue' %}?tab=pending">Pendentes</a>
<a class="nav-link {% if active_tab == 'processed' %}active{% endif %}" href="{% url 'scheduler:queue' %}?tab=processed">Processados Hoje</a>
```

O `hx-get` deve preservar a aba ativa:

```django
hx-get="{% url 'scheduler:queue_partial' %}?tab={{ active_tab }}"
```

### R2. Query correta de processados hoje

Em `apps/scheduler/views.py`, implementar bounds do dia local:

```python
def _local_day_bounds(day: date | None = None) -> tuple[datetime, datetime]:
    local_day = day or timezone.localdate()
    current_tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(local_day, time.min), current_tz)
    end = start + timedelta(days=1)
    return start, end
```

A query de processados hoje deve usar:

```python
Case.objects.filter(
    scheduler=scheduler_user,
    appointment_status__in=["confirmed", "denied"],
    appointment_decided_at__gte=start,
    appointment_decided_at__lt=end,
)
```

Não filtrar por `status__in=[APPT_CONFIRMED, APPT_DENIED]` como critério principal.

### R3. Partial por aba ativa

Em `templates/scheduler/_queue_content.html`:

- se `active_tab == "pending"`: renderizar alerta, vindas imediatas para ciência operacional e cards pendentes;
- se `active_tab == "processed"`: renderizar cards dos processados hoje;
- remover a tabela antiga `Confirmados Hoje` abaixo dos pendentes.

### R4. Cards de processados hoje

Cada item deve mostrar pelo menos:

- nome do paciente;
- registro;
- idade/sexo quando disponíveis;
- horário do processamento (`appointment_decided_at`);
- status do processamento:
  - `Confirmado` se `appointment_status == "confirmed"`;
  - `Recusado` se `appointment_status == "denied"`;
- data/hora agendada se confirmado;
- motivo se recusado;
- suporte/fluxo;
- médico responsável;
- botão `Ver detalhes`.

### R5. Detalhe read-only para agendador

Adicionar URLs:

```python
path("processed/<uuid:case_id>/", views.scheduler_processed_detail, name="processed_detail")
path("processed/<uuid:case_id>/pdf/", views.scheduler_processed_pdf, name="processed_pdf")
```

A detail view deve:

- exigir login e papel ativo `scheduler`;
- buscar apenas caso com `case_id`, `scheduler=request.user`, `appointment_status__in=["confirmed", "denied"]`;
- retornar 404 para caso inexistente ou processado por outro agendador;
- renderizar `templates/intake/case_detail.html` em modo read-only, similar ao dashboard;
- usar:

```python
"show_intake_nav": False,
"back_url": reverse("scheduler:queue") + "?tab=processed",
"back_label": "← Voltar aos processados hoje",
"pdf_url": reverse("scheduler:processed_pdf", args=[case.case_id]),
"can_confirm_receipt": False,
```

A PDF view deve:

- exigir login e papel ativo `scheduler`;
- buscar apenas caso processado pelo agendador logado;
- retornar PDF inline se existir;
- retornar 404 se não houver PDF ou se o caso for de outro agendador.

## TDD obrigatório

Antes de implementar, adicionar testes falhando em `apps/scheduler/tests/test_views.py`.

### Testes mínimos

1. `test_queue_nav_has_functional_processed_tab_and_no_history`
   - GET `/scheduler/` como scheduler;
   - contém link para `?tab=processed`;
   - contém `Processados Hoje`;
   - não contém `Histórico` nem `Confirmados Hoje`.

2. `test_processed_today_tab_uses_appointment_decided_at_not_status`
   - criar caso processado hoje pelo scheduler com `appointment_status="confirmed"`, `appointment_decided_at=now`, e status posterior como `WAIT_R1_CLEANUP_THUMBS` ou `CLEANED`;
   - GET `/scheduler/?tab=processed`;
   - paciente aparece.

3. `test_processed_today_tab_includes_denied_cases`
   - criar caso com `appointment_status="denied"` processado hoje;
   - aparece em `/scheduler/?tab=processed`.

4. `test_processed_today_tab_excludes_other_scheduler_cases`
   - caso processado hoje por outro scheduler não aparece.

5. `test_pending_tab_does_not_render_processed_list`
   - GET `/scheduler/?tab=pending` não mostra bloco/lista de processados.

6. `test_processed_tab_has_detail_link`
   - item processado hoje contém URL `scheduler:processed_detail`.

7. `test_scheduler_processed_detail_renders_read_only_case_detail`
   - caso processado pelo scheduler logado;
   - GET `/scheduler/processed/<case_id>/` retorna 200;
   - mostra dados do caso/timeline;
   - contém back label `Voltar aos processados hoje`;
   - não mostra botão operacional de alterar/agendar/confirmar recebimento.

8. `test_scheduler_processed_detail_404_for_other_scheduler_case`
   - scheduler A tenta abrir caso processado pelo scheduler B;
   - retorna 404.

9. `test_scheduler_processed_pdf_404_for_other_scheduler_case`
   - scheduler A tenta abrir PDF de caso processado pelo scheduler B;
   - retorna 404.

10. `test_queue_partial_preserves_processed_tab`
   - GET `/scheduler/partials/queue/?tab=processed` retorna conteúdo de processados e não pendentes.

## Critérios de sucesso

- [ ] TDD seguido: testes novos falham antes da implementação e passam após.
- [ ] `Histórico` removido.
- [ ] `Confirmados Hoje` substituído por `Processados Hoje`.
- [ ] `Processados Hoje` é aba funcional.
- [ ] Query captura confirmados e recusados hoje pelo scheduler logado usando `appointment_decided_at`.
- [ ] Lista usa cards com botão `Ver detalhes`.
- [ ] Agendador consegue abrir detalhe read-only de caso próprio processado.
- [ ] Agendador não consegue abrir detalhe/PDF de caso de outro agendador.
- [ ] HTMX polling mantém aba ativa.
- [ ] Quality gate do AGENTS.md passa.

## Gates de autoavaliação

Antes de finalizar, responder no relatório:

1. A query de `Processados Hoje` depende de `status`? Se sim, está errado.
2. O template ainda mostra `Histórico` ou `Confirmados Hoje`? Se sim, está errado.
3. Casos recusados aparecem em `Processados Hoje`? Qual teste prova?
4. O detalhe agendador reutiliza o padrão visual de supervisor/admin? Onde?
5. A autorização impede acesso a caso/PDF de outro agendador? Quais testes provam?
6. O polling HTMX preserva `tab=processed`? Qual teste prova?

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/scheduler-processed-today-tab/proposal.md, design.md, tasks.md and this slice.
Implement ONLY Slice 001.
Use TDD: first add failing tests in apps/scheduler/tests/test_views.py, then implement minimal code.
Do not implement multi-day history. Remove the Histórico pill.
Rename/remove Confirmados Hoje and implement Processados Hoje as functional tab using /scheduler/?tab=processed.
Fix processed-today query to use appointment_decided_at local-day bounds, scheduler=request.user, and appointment_status in confirmed/denied; do not depend on status.
Add read-only scheduler detail and PDF routes for cases processed by the logged-in scheduler, using the same case_detail template pattern as dashboard supervisor/admin.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/scheduler-processed-today-tab/tasks.md when complete.
Create a temp markdown report with before/after snippets, commit and push.
Return REPORT_PATH=<path> and stop.
```
