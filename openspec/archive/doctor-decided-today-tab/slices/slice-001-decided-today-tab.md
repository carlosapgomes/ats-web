# Slice 001: Aba Decididos Hoje + detalhe read-only médico

## Contexto zero para implementador

A tela médica (`/doctor/`) foi criada no change arquivado `openspec/archive/doctor-queue/`. Ela trouxe pills `Pendentes`, `Decididos Hoje` e `Histórico` herdados do mock. Hoje:

- `Histórico` não foi planejado nem implementado; é placeholder visual.
- `Decididos Hoje` não é uma aba funcional; é apenas um `<span>` no header e uma seção opcional abaixo da fila.
- A query de `Decididos Hoje` filtra `status__in=[DOCTOR_ACCEPTED, DOCTOR_DENIED]`, mas o fluxo real avança o caso para outros estados logo após a decisão médica.

O dashboard de supervisor/admin já tem detalhe read-only em `apps/dashboard/views.py::dashboard_case_detail`, renderizando `templates/intake/case_detail.html` com navegação parametrizada.

## Objetivo do slice

Implementar uma entrega vertical:

```text
Médico abre /doctor/ → clica Decididos Hoje → vê casos que decidiu hoje → clica Ver detalhes → vê detalhe read-only completo → volta para Decididos Hoje
```

Também remover a aba `Histórico`.

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/doctor/views.py`
2. `apps/doctor/urls.py`
3. `templates/doctor/queue.html`
4. `templates/doctor/_queue_content.html`
5. `apps/doctor/tests/test_views.py`

Se for necessário extrair helper compartilhado com dashboard, justificar no relatório do slice.

## Requisitos funcionais

### R1. Navegação

Em `templates/doctor/queue.html`:

- substituir pills estáticos por links;
- manter `Pendentes` ativo por padrão;
- adicionar `Decididos Hoje` como link para `/doctor/?tab=decided`;
- remover `Histórico`.

Exemplo conceitual:

```django
<a class="nav-link {% if active_tab == 'pending' %}active{% endif %}" href="{% url 'doctor:queue' %}?tab=pending">Pendentes</a>
<a class="nav-link {% if active_tab == 'decided' %}active{% endif %}" href="{% url 'doctor:queue' %}?tab=decided">Decididos Hoje</a>
```

O `hx-get` deve preservar a aba ativa:

```django
hx-get="{% url 'doctor:queue_partial' %}?tab={{ active_tab }}"
```

### R2. Query correta de decididos hoje

Em `apps/doctor/views.py`, implementar bounds do dia local:

```python
def _local_day_bounds(day: date | None = None) -> tuple[datetime, datetime]:
    local_day = day or timezone.localdate()
    current_tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(local_day, time.min), current_tz)
    end = start + timedelta(days=1)
    return start, end
```

A query de decididos hoje deve usar:

```python
Case.objects.filter(
    doctor=doctor_user,
    doctor_decision__in=["accept", "deny"],
    doctor_decided_at__gte=start,
    doctor_decided_at__lt=end,
)
```

Não filtrar por `status__in=[DOCTOR_ACCEPTED, DOCTOR_DENIED]`.

### R3. Partial por aba ativa

Em `templates/doctor/_queue_content.html`:

- se `active_tab == "pending"`: renderizar alerta e cards pendentes;
- se `active_tab == "decided"`: renderizar lista/cards dos decididos hoje;
- remover seção antiga `Recently Decided` abaixo dos pendentes.

### R4. Card/lista de decididos hoje

Cada item deve mostrar pelo menos:

- nome do paciente;
- registro;
- idade/sexo quando disponíveis;
- horário da decisão (`doctor_decided_at`);
- decisão (`ACEITAR`/`NEGAR`);
- suporte/fluxo quando aceito, ou motivo quando negado;
- botão `Ver detalhes`.

### R5. Detalhe read-only para médico

Adicionar URL:

```python
path("decided/<uuid:case_id>/", views.doctor_decided_detail, name="decided_detail")
```

A view deve:

- exigir login e papel ativo `doctor`;
- buscar apenas caso com `case_id`, `doctor=request.user`, `doctor_decision__in=["accept", "deny"]`;
- retornar 404 para caso inexistente ou decidido por outro médico;
- renderizar `templates/intake/case_detail.html` em modo read-only, similar ao dashboard;
- usar:

```python
"show_intake_nav": False,
"back_url": reverse("doctor:queue") + "?tab=decided",
"back_label": "← Voltar aos decididos hoje",
"pdf_url": reverse("doctor:serve_pdf", args=[case.case_id]),
"can_confirm_receipt": False,
```

## TDD obrigatório

Antes de implementar, adicionar testes falhando em `apps/doctor/tests/test_views.py`.

### Testes mínimos

1. `test_queue_nav_has_functional_decided_tab_and_no_history`
   - GET `/doctor/` como doctor;
   - contém link para `?tab=decided`;
   - não contém `Histórico`.

2. `test_decided_today_tab_uses_doctor_decided_at_not_status`
   - criar caso decidido hoje pelo médico com `status=WAIT_APPT` ou `WAIT_R1_CLEANUP_THUMBS`;
   - GET `/doctor/?tab=decided`;
   - paciente aparece.

3. `test_decided_today_tab_excludes_other_doctor_cases`
   - caso decidido hoje por outro médico não aparece.

4. `test_pending_tab_does_not_render_decided_list`
   - GET `/doctor/?tab=pending` não mostra bloco/lista de decididos.

5. `test_decided_tab_has_detail_link`
   - item decidido hoje contém URL `doctor:decided_detail`.

6. `test_doctor_decided_detail_renders_read_only_case_detail`
   - caso decidido pelo médico logado;
   - GET `/doctor/decided/<case_id>/` retorna 200;
   - mostra dados do caso/timeline;
   - contém back label `Voltar aos decididos hoje`;
   - não mostra botão operacional de confirmar recebimento.

7. `test_doctor_decided_detail_404_for_other_doctor_case`
   - médico A tenta abrir caso decidido pelo médico B;
   - retorna 404.

8. `test_queue_partial_preserves_decided_tab`
   - GET `/doctor/partials/queue/?tab=decided` retorna conteúdo de decididos e não pendentes.

## Critérios de sucesso

- [ ] TDD seguido: testes novos falham antes da implementação e passam após.
- [ ] `Histórico` removido.
- [ ] `Decididos Hoje` é aba funcional.
- [ ] Query captura casos decididos hoje em estados posteriores ao submit médico.
- [ ] Médico consegue abrir detalhe read-only de caso próprio decidido.
- [ ] Médico não consegue abrir detalhe de caso de outro médico.
- [ ] HTMX polling mantém aba ativa.
- [ ] Quality gate do AGENTS.md passa.

## Gates de autoavaliação

Antes de finalizar, responder no relatório:

1. A query de `Decididos Hoje` depende de `status`? Se sim, está errado.
2. O template ainda mostra `Histórico`? Se sim, está errado.
3. O detalhe médico reutiliza o padrão visual de supervisor/admin? Onde?
4. A autorização impede acesso a caso de outro médico? Qual teste prova?
5. O polling HTMX preserva `tab=decided`? Qual teste prova?

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/doctor-decided-today-tab/proposal.md, design.md, tasks.md and this slice.
Implement ONLY Slice 001.
Use TDD: first add failing tests in apps/doctor/tests/test_views.py, then implement minimal code.
Do not implement multi-day history. Remove the Histórico pill.
Make Decididos Hoje a functional tab using /doctor/?tab=decided.
Fix decided-today query to use doctor_decided_at local-day bounds and doctor=request.user, not status.
Add read-only doctor detail route for cases decided by the logged-in doctor, using the same case_detail template pattern as dashboard supervisor/admin.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/doctor-decided-today-tab/tasks.md when complete.
Create a temp markdown report with before/after snippets, commit and push.
Return REPORT_PATH=<path> and stop.
```
