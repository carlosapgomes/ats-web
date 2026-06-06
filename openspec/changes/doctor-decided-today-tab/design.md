# Design: Aba Decididos Hoje na fila médica

## Estado atual

### Template

`templates/doctor/queue.html` renderiza pills estáticos:

```html
<span class="nav-link active ...">Pendentes</span>
<span class="nav-link">Decididos Hoje</span>
<span class="nav-link">Histórico</span>
```

`templates/doctor/_queue_content.html` renderiza pendentes e, abaixo, uma seção `Decididos Hoje` condicional. Isso torna `Decididos Hoje` uma seção, não uma aba.

### Query atual

`apps/doctor/views.py::_doctor_queue_context()` usa:

```python
Case.objects.filter(
    status__in=[CaseStatus.DOCTOR_ACCEPTED, CaseStatus.DOCTOR_DENIED],
    doctor=doctor_user,
    events__event_type__startswith="DOCTOR_",
    events__timestamp__date=today,
).distinct()
```

Essa consulta perde casos que passaram para estados posteriores após o submit médico.

## Decisões

### D1. Abas por query string simples

Usar `?tab=pending` e `?tab=decided` em `/doctor/`.

Rotas:

```text
/doctor/                       → Pendentes (default)
/doctor/?tab=pending           → Pendentes
/doctor/?tab=decided           → Decididos Hoje
/doctor/partials/queue/        → partial respeitando ?tab=
```

Motivos:

- evita introduzir novas páginas para uma troca simples de lista;
- mantém SSR e HTMX atual;
- baixo risco e poucos arquivos.

### D2. Remover `Histórico`

Remover o pill `Histórico` de `templates/doctor/queue.html`.

Motivo: não há requisito formal nem implementação. Histórico multi-dia fica fora de escopo.

### D3. Query de decididos hoje baseada em decisão imutável

Criar helper local para início/fim do dia no fuso configurado, equivalente ao padrão usado no dashboard:

```python
start, end = _local_day_bounds()
```

Consultar casos decididos pelo médico logado hoje:

```python
Case.objects.filter(
    doctor=doctor_user,
    doctor_decision__in=["accept", "deny"],
    doctor_decided_at__gte=start,
    doctor_decided_at__lt=end,
).select_related("doctor", "scheduler", "created_by").order_by("-doctor_decided_at")
```

Isso independe do `status` FSM atual e captura casos que avançaram no fluxo.

#### Compatibilidade com dados antigos

Se houver preocupação com casos legados sem `doctor_decided_at`, pode-se incluir fallback por evento `DOCTOR_*`, mas o comportamento-alvo primário deve ser `doctor_decided_at`, pois `doctor_submit` já preenche esse campo.

### D4. Contexto separado por aba ativa

`_doctor_queue_context(request)` passa a incluir:

```python
{
    "active_tab": "pending" | "decided",
    "pending_cases": [...],
    "decided_today": [...],
    "pending_count": ...,
    "decided_today_count": ...,
    "avg_wait_minutes": ...,
}
```

Para manter contadores nos pills, ambos os counts podem ser calculados independentemente da aba ativa. Para evitar renderizar listas desnecessárias, somente a lista da aba ativa precisa ser materializada.

### D5. Partial renderiza somente a aba ativa

`templates/doctor/_queue_content.html` deve separar:

- se `active_tab == "pending"`: alert + cards pendentes;
- se `active_tab == "decided"`: lista/tabela/cards de decididos hoje.

A seção antiga `Recently Decided` abaixo dos pendentes deve ser removida.

### D6. Detalhe read-only para médico

Adicionar rota no namespace médico:

```text
/doctor/decided/<uuid:case_id>/ → doctor:decided_detail
```

Regras de autorização:

- `@login_required`
- `@role_required("doctor")`
- caso deve ter `doctor=request.user` e `doctor_decision` preenchido;
- se não for caso decidido pelo médico logado, retornar 404.

Não restringir o detalhe apenas ao dia atual. A lista é de hoje, mas se o médico abrir um link recém-renderizado e cruzar meia-noite, o detalhe ainda deve funcionar para o caso dele. O escopo continua sem criar tela de histórico multi-dia.

### D7. Reuso do detalhe supervisor/admin

O dashboard já renderiza detalhes via `templates/intake/case_detail.html`, parametrizado com:

```python
show_intake_nav=False
back_url=reverse("dashboard:index")
back_label="← Voltar ao dashboard"
pdf_url=reverse("dashboard:case_pdf", args=[case.case_id])
can_confirm_receipt=False
```

A implementação deve evitar duplicar regra visual complexa. Duas opções aceitáveis:

1. **Preferida:** extrair um helper compartilhado para montar contexto de detalhe read-only, por exemplo em `apps/cases/presenters.py` ou helper privado reaproveitável, usado por dashboard e doctor.
2. **Aceitável para slice enxuto:** criar helper em `apps/doctor/views.py` que replica minimamente o contexto do dashboard e usa o mesmo template `intake/case_detail.html`.

Para o médico, parametrizar:

```python
show_intake_nav=False
back_url=reverse("doctor:queue") + "?tab=decided"
back_label="← Voltar aos decididos hoje"
pdf_url=reverse("doctor:serve_pdf", args=[case.case_id])
can_confirm_receipt=False
```

A rota `doctor:serve_pdf` já existe e é protegida por papel `doctor`.

### D8. Link `Ver detalhes`

Cada item em `Decididos Hoje` deve renderizar link:

```django
<a href="{% url 'doctor:decided_detail' c.case_id %}" class="btn btn-outline-primary btn-sm">Ver detalhes</a>
```

O card deve mostrar pelo menos:

- paciente;
- registro;
- horário da decisão;
- decisão (`ACEITAR`/`NEGAR`);
- suporte/fluxo ou motivo, conforme aplicável;
- status/result atual compacto.

## Arquivos previstos

| Arquivo | Tipo | Mudança |
|---------|------|---------|
| `apps/doctor/views.py` | modificado | query correta, aba ativa, detalhe read-only |
| `apps/doctor/urls.py` | modificado | rota `decided_detail` |
| `templates/doctor/queue.html` | modificado | pills como links, remover Histórico, hx-get com aba ativa |
| `templates/doctor/_queue_content.html` | modificado | render condicional por aba, link de detalhe |
| `apps/doctor/tests/test_views.py` | modificado | testes de query, abas, detalhe e autorização |

## Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| Duplicar lógica do detalhe do dashboard | Preferir helper compartilhado ou limitar duplicação ao contexto necessário |
| Médico acessar caso alheio via URL | Query com `doctor=request.user` e teste de 404 |
| Dia UTC vs dia local | Usar bounds timezone-aware do dia local |
| Polling voltar para pendentes ao atualizar partial | Incluir `?tab={{ active_tab }}` no `hx-get` |
| A lista de decididos hoje ficar vazia após transições | Query por `doctor_decided_at`, não por `status` |
