# Design: Corrigir semântica de encerramento administrativo no dashboard

## Estado atual

### 1. Resultado final no detalhe

`apps/dashboard/views.py::dashboard_case_detail()` monta `result_info` com esta regra simplificada:

```python
terminal_with_result = case.status in (
    CaseStatus.WAIT_R1_CLEANUP_THUMBS,
    CaseStatus.CLEANED,
)

...
elif case.status == CaseStatus.APPT_CONFIRMED or terminal_with_result:
    result_info = {"type": "accepted_scheduled", ...}
```

Como encerramento administrativo também move o caso para `CLEANED`, um caso sem outro desfecho específico cai em `accepted_scheduled` e o template `templates/intake/case_detail.html` mostra “Agendamento Confirmado”.

### 2. Badge de resultado na listagem

`apps/dashboard/views.py::_compute_result()` decide o label por campos como `doctor_decision`, `appointment_status` e `status`. Não há uma regra prioritária para `CASE_ADMINISTRATIVELY_CLOSED`, então um caso administrativamente encerrado pode parecer em andamento, aceito ou confirmado, dependendo dos campos residuais.

### 3. Cards de totalização

`_compute_summary()` já usa data local e campos imutáveis para `accepted`/`denied`, mas não separa encerramento administrativo. Casos sem decisão (`doctor_decision=""`, `appointment_status=""`) encerrados administrativamente sobram no residual:

```python
in_progress = total_today - accepted - denied
```

## Decisões

### D1. Fonte de verdade para encerramento administrativo

Usar o evento append-only `CaseEvent.event_type == "CASE_ADMINISTRATIVELY_CLOSED"` como fonte de verdade.

Motivos:

- O estado `CLEANED` também representa encerramentos normais.
- Não há campo booleano no `Case` que diferencie fechamento normal de administrativo.
- O evento já é auditável e contém payload com `previous_status`, `reason_code`, `reason_text` e `active_role`.

### D2. Helper local para detecção

Criar helper pequeno em `apps/dashboard/views.py`:

```python
def _administrative_closure_event(case: Case) -> CaseEvent | None:
    ...
```

Requisitos do helper:

- deve funcionar quando `case.events` já estiver pré-carregado;
- deve fazer query defensiva quando não estiver;
- deve retornar o evento mais recente/primeiro suficiente de `CASE_ADMINISTRATIVELY_CLOSED`.

Alternativa aceitável para slice enxuto: usar `case.events.filter(...).order_by("-timestamp").first()` diretamente nos pontos de uso. Porém o helper reduz duplicação entre `_compute_result()` e `dashboard_case_detail()`.

### D3. Prioridade máxima no resultado do detalhe

Em `dashboard_case_detail()`, antes de scope-gate, negativa médica, vinda imediata, agendamento negado ou confirmado, verificar evento administrativo:

```python
admin_close_event = _administrative_closure_event(case)

if admin_close_event:
    payload = admin_close_event.payload or {}
    result_info = {
        "type": "administratively_closed",
        "reason_code": payload.get("reason_code", ""),
        "reason_text": payload.get("reason_text", ""),
        "previous_status": payload.get("previous_status", ""),
        "closed_at": admin_close_event.timestamp,
        "actor_display": admin_close_event.actor_display,
    }
elif is_scope_gated:
    ...
```

Justificativa: encerramento administrativo é o desfecho operacional final do caso e não deve ser sobrescrito por campos clínicos/agendamento residuais.

### D4. Novo branch no template compartilhado

Adicionar em `templates/intake/case_detail.html`, dentro de “Resultado Final”, antes dos branches de resultados normais:

```django
{% if result_info.type == "administratively_closed" %}
  <span class="badge bg-secondary fs-6 px-3 py-2">Encerrado administrativamente</span>
  <p class="mt-3 mb-0 text-muted">
    Caso removido das filas operacionais por intervenção administrativa.
    Este encerramento não representa confirmação de agendamento.
  </p>
  ...
{% elif result_info.type == "manual_review_required" %}
```

Campos opcionais:

- `Motivo`: `reason_text`;
- `Status anterior`: `previous_status`, usando label se houver mapeamento simples;
- `Responsável`: `actor_display` se disponível;
- `Data`: `closed_at`.

### D5. Prioridade máxima no badge da listagem

Em `_compute_result(case)`, antes de qualquer outra regra:

```python
if _administrative_closure_event(case):
    return ("🔒 Encerrado administrativamente", "bg-secondary")
```

Assim a lista do dashboard não mostra “Agendamento Confirmado” nem “Aguardando ...” para caso administrativamente encerrado.

### D6. Totalização diária com categoria exclusiva

Manter a base `today_cases = Case.objects.filter(created_at__gte=start, created_at__lt=end)` para preservar a semântica “casos criados hoje”.

Criar subconjunto de encerrados administrativos:

```python
administratively_closed = today_cases.filter(
    events__event_type="CASE_ADMINISTRATIVELY_CLOSED",
).distinct()
```

Ajustar contadores para categorias mutuamente exclusivas:

```python
admin_closed_count = administratively_closed.count()
admin_closed_ids = administratively_closed.values("pk")

accepted = (
    today_cases.exclude(pk__in=admin_closed_ids)
    .filter(doctor_decision="accept")
    .exclude(appointment_status="denied")
    .count()
)

denied = (
    today_cases.exclude(pk__in=admin_closed_ids)
    .filter(Q(doctor_decision="deny") | Q(appointment_status="denied"))
    .count()
)

in_progress = total_today - accepted - denied - admin_closed_count
```

Retorno:

```python
return {
    "total_today": total_today,
    "accepted": accepted,
    "denied": denied,
    "administratively_closed": admin_closed_count,
    "in_progress": in_progress,
}
```

### D7. Card novo no template do dashboard

Adicionar card “Encerrados admin.” em `templates/dashboard/index.html`.

Opção preferida: trocar layout de 4 para 5 cards responsivos:

```html
<div class="col-6 col-md">
```

para cada card. Isso mantém os cinco cards na mesma linha em telas médias/grandes e em duas colunas no mobile.

Label recomendado:

> Encerrados admin.

Cor recomendada:

- `var(--bs-secondary)` ou classe visual equivalente;
- evitar verde/vermelho para não confundir com sucesso/negativa.

### D8. Performance e duplicação

O uso de `events__event_type` em `_compute_summary()` é aceitável para volume atual. Para listagem, `_compute_result()` pode gerar query por caso; se necessário, otimizar em slice futuro com `prefetch_related("events")` ou anotação `Exists`.

Para este bugfix, priorizar correção e testes. Se o implementador tocar a query principal do dashboard, manter escopo mínimo.

## Arquivos previstos

1. `apps/dashboard/views.py`
   - helper de evento administrativo;
   - `_compute_result()` com prioridade administrativa;
   - `dashboard_case_detail()` com `result_info.type = "administratively_closed"`;
   - `_compute_summary()` com `administratively_closed` e ajuste de `in_progress`.

2. `templates/intake/case_detail.html`
   - novo branch visual para `administratively_closed`.

3. `templates/dashboard/index.html`
   - novo card “Encerrados admin.”.

4. `apps/dashboard/tests/test_dashboard.py`
   - testes de regressão para detalhe, badge e contadores.

## Testes mínimos

1. **Detalhe não mostra agendamento confirmado**
   - criar caso com `doctor_decision="accept"`, `appointment_status="confirmed"`;
   - encerrar administrativamente;
   - GET `dashboard:case_detail`;
   - assert contém “Encerrado administrativamente”;
   - assert não contém badge “Agendamento Confirmado” no resultado final.

2. **Resumo separa encerrados administrativos**
   - criar 11 casos hoje:
     - 1 aceito normal;
     - 4 encerrados administrativamente sem decisão;
     - 6 em andamento;
   - `_compute_summary()` retorna:
     - `total_today == 11`;
     - `accepted == 1`;
     - `denied == 0`;
     - `administratively_closed == 4`;
     - `in_progress == 6`.

3. **Categorias exclusivas**
   - caso aceito/confirmado encerrado administrativamente conta somente em `administratively_closed`, não em `accepted`.

4. **Listagem mostra badge administrativo**
   - caso encerrado administrativamente aparece com “Encerrado administrativamente” em vez de “Agendamento Confirmado”/“Aguardando”.

## Riscos

| Risco | Mitigação |
|------|-----------|
| Confundir encerramento normal `CLEANED` com administrativo | Usar evento específico, não status |
| Dupla contagem entre aceitos/negados/admin | Excluir admin_closed antes de accepted/denied |
| Regressão no detalhe NIR | O branch no template só renderiza quando `result_info.type` for novo tipo; views NIR não geram esse tipo inicialmente |
| Layout apertado com cinco cards | Usar grid responsivo `col-6 col-md` |
