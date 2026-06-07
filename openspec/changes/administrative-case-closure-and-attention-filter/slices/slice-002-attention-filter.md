# Slice 002: Filtro “Atenção necessária” no dashboard

## Contexto zero para implementador

Este slice depende do Slice 001 estar completo. O sistema já terá ação de encerramento administrativo para supervisor/admin. Agora precisamos facilitar a identificação dos casos que merecem revisão humana, sem criar página separada.

A listagem inicial do supervisor/admin é o dashboard em `templates/dashboard/index.html`, alimentado por `apps/dashboard/views.py::dashboard_index`. Ela já possui filtros por status e data e cards de caso com botão “Ver detalhes”.

O objetivo do filtro não é afirmar que o caso está definitivamente travado. Por isso, o nome deve ser **Atenção necessária**, não “Travados”. O supervisor usa o filtro, abre o detalhe e decide se encerra administrativamente ou acompanha.

Leia antes de implementar:

- `AGENTS.md`
- `PROJECT_CONTEXT.md`
- `openspec/changes/administrative-case-closure-and-attention-filter/proposal.md`
- `openspec/changes/administrative-case-closure-and-attention-filter/design.md`
- `openspec/changes/administrative-case-closure-and-attention-filter/tasks.md`
- `openspec/changes/administrative-case-closure-and-attention-filter/slices/slice-001-administrative-closure.md`
- este slice

## Objetivo do slice

Entregar fluxo vertical completo:

```text
Supervisor/admin abre dashboard
→ clica/seleciona Atenção necessária
→ vê apenas casos operacionais suspeitos
→ cada card mostra motivo compacto
→ abre detalhe e pode usar o encerramento administrativo já entregue no Slice 001
```

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/dashboard/views.py`
2. `templates/dashboard/index.html`
3. `apps/dashboard/tests/test_dashboard.py` ou arquivo equivalente

Se precisar criar helper compartilhado fora do dashboard, justificar no relatório.

## Requisitos funcionais

### R1. Query string do preset

Usar query string simples:

```text
/dashboard/?attention=1
```

No contexto do template:

```python
"attention_filter": attention_filter,
"attention_count": attention_count,
```

`attention_filter` deve ser verdadeiro apenas quando `request.GET.get("attention") == "1"`.

### R2. Critérios de atenção

O filtro deve sempre excluir `CLEANED`.

Critérios iniciais:

1. `FAILED` sempre entra.
2. Lock expirado entra:
   - `locked_by IS NOT NULL`
   - `locked_until IS NOT NULL`
   - `locked_until <= now`
3. Estados de processamento/handoff antigos entram se `updated_at <= now - 30min`.
4. Estados de espera humanos antigos entram se `updated_at <= now - 48h`.

Use constantes nomeadas em `apps/dashboard/views.py`, por exemplo:

```python
ATTENTION_PROCESSING_STUCK_AFTER = timedelta(minutes=30)
ATTENTION_WAITING_STUCK_AFTER = timedelta(hours=48)

ATTENTION_PROCESSING_STATUSES = (...)
ATTENTION_WAITING_STATUSES = (...)
```

Listas sugeridas:

```python
ATTENTION_PROCESSING_STATUSES = (
    CaseStatus.NEW,
    CaseStatus.R1_ACK_PROCESSING,
    CaseStatus.EXTRACTING,
    CaseStatus.LLM_STRUCT,
    CaseStatus.LLM_SUGGEST,
    CaseStatus.R2_POST_WIDGET,
    CaseStatus.DOCTOR_ACCEPTED,
    CaseStatus.DOCTOR_DENIED,
    CaseStatus.R3_POST_REQUEST,
    CaseStatus.APPT_CONFIRMED,
    CaseStatus.APPT_DENIED,
    CaseStatus.R1_FINAL_REPLY_POSTED,
    CaseStatus.CLEANUP_RUNNING,
)

ATTENTION_WAITING_STATUSES = (
    CaseStatus.WAIT_DOCTOR,
    CaseStatus.WAIT_APPT,
    CaseStatus.WAIT_R1_CLEANUP_THUMBS,
)
```

Query conceitual:

```python
now = timezone.now()
processing_cutoff = now - ATTENTION_PROCESSING_STUCK_AFTER
waiting_cutoff = now - ATTENTION_WAITING_STUCK_AFTER

attention_q = (
    Q(status=CaseStatus.FAILED)
    | Q(locked_by__isnull=False, locked_until__isnull=False, locked_until__lte=now)
    | Q(status__in=ATTENTION_PROCESSING_STATUSES, updated_at__lte=processing_cutoff)
    | Q(status__in=ATTENTION_WAITING_STATUSES, updated_at__lte=waiting_cutoff)
)

cases_qs = cases_qs.exclude(status=CaseStatus.CLEANED).filter(attention_q)
```

### R3. Composição com filtros existentes

O dashboard já aceita:

- `status`
- `date_from`
- `date_to`
- `page`

O filtro `attention=1` deve compor com `status`, `date_from` e `date_to`. Exemplo:

```text
/dashboard/?attention=1&status=FAILED
```

mostra apenas casos `FAILED` dentro do conjunto de atenção.

Paginação deve preservar `attention=1` nos links.

### R4. Contador/preset visual

Em `templates/dashboard/index.html`, adicionar controle visível na área de filtros:

- botão/link `Atenção necessária`;
- quando ativo, deve ter estilo ativo/alerta;
- mostrar contador se simples de calcular (`attention_count`).

Exemplo conceitual:

```django
<a href="{% url 'dashboard:index' %}?attention=1" class="btn btn-sm {% if attention_filter %}btn-warning{% else %}btn-outline-warning{% endif %}">
  ⚠ Atenção necessária{% if attention_count is not None %} ({{ attention_count }}){% endif %}
</a>
```

Se os filtros de data/status estiverem preenchidos, não precisa gerar combinador sofisticado para o botão inicial, mas os links de paginação devem preservar os parâmetros da requisição atual.

### R5. Motivo compacto no card

Criar helper em `apps/dashboard/views.py`, por exemplo:

```python
def _get_attention_reason(case: Case, *, now: datetime | None = None) -> str:
    ...
```

Retornos sugeridos:

- `Falha no processamento`
- `Lock expirado`
- `Processamento parado há mais de 30 min`
- `Aguardando ação humana há mais de 48 h`
- `""` quando não suspeito

Adicionar no `_enrich_case()`:

```python
"attention_reason": _get_attention_reason(case),
```

No card, renderizar badge quando houver motivo:

```django
{% if item.attention_reason %}
<span class="badge bg-warning text-dark">⚠ Atenção necessária</span>
<small class="text-muted d-block">{{ item.attention_reason }}</small>
{% endif %}
```

### R6. Não alterar fechamento de casos

Este slice não deve criar novas ações de POST e não deve modificar o encerramento administrativo do Slice 001. Ele apenas lista/sinaliza.

## TDD obrigatório

Antes de implementar, adicionar testes falhando.

### Testes mínimos

1. `test_dashboard_has_attention_filter_control`
   - GET dashboard como manager/admin;
   - contém texto/link “Atenção necessária” e `attention=1`.

2. `test_attention_filter_includes_failed_operational_cases`
   - caso `FAILED` aparece em `?attention=1`;
   - caso `CLEANED` não aparece.

3. `test_attention_filter_includes_old_processing_case`
   - criar caso em `LLM_SUGGEST` ou `EXTRACTING` com `updated_at` artificialmente antigo;
   - aparece em `?attention=1`.

4. `test_attention_filter_excludes_fresh_processing_case`
   - mesmo status, `updated_at` recente;
   - não aparece.

5. `test_attention_filter_includes_old_waiting_case`
   - `WAIT_DOCTOR`, `WAIT_APPT` ou `WAIT_R1_CLEANUP_THUMBS` com `updated_at` > 48h;
   - aparece.

6. `test_attention_filter_excludes_fresh_waiting_case`
   - wait recente;
   - não aparece.

7. `test_attention_filter_includes_expired_lock`
   - caso não `CLEANED` com `locked_by` e `locked_until` no passado;
   - aparece e mostra motivo “Lock expirado”.

8. `test_attention_filter_badge_shows_reason`
   - GET `?attention=1`;
   - HTML contém badge “Atenção necessária” e motivo esperado.

9. `test_attention_filter_composes_with_status_filter`
   - `?attention=1&status=FAILED` mostra `FAILED` e exclui outro suspeito não-FAILED.

10. `test_attention_pagination_preserves_attention_param`
    - criar casos suficientes para paginar;
    - links de próxima/anterior contêm `attention=1`.

## Dicas de teste

Para setar `updated_at` antigo, crie o caso normalmente e depois faça update direto:

```python
old_time = timezone.now() - timedelta(hours=1)
Case.objects.filter(pk=case.pk).update(updated_at=old_time)
case.refresh_from_db()
```

Para caso `CLEANED`, use fixture/advance existente ou crie diretamente se os testes atuais do projeto já fazem isso para o FSM protected field. Siga o padrão dos testes existentes.

## Critérios de sucesso

- [ ] TDD seguido: testes novos falham antes da implementação e passam após.
- [ ] `?attention=1` filtra apenas casos suspeitos não `CLEANED`.
- [ ] `FAILED` entra sempre.
- [ ] Estados intermediários antigos entram pelo threshold de 30 min.
- [ ] Estados de espera antigos entram pelo threshold de 48 h.
- [ ] Lock expirado entra.
- [ ] Casos recentes não aparecem por falso positivo.
- [ ] Card mostra motivo compacto.
- [ ] Paginação preserva `attention=1`.
- [ ] Nenhuma ação de encerramento é executada automaticamente.
- [ ] Quality gate do AGENTS.md passa.

## Gates de autoavaliação

Responder no relatório do slice:

1. O filtro fecha ou altera casos automaticamente? Se sim, está errado.
2. O filtro exclui `CLEANED` sempre? Qual teste prova?
3. Quais thresholds foram implementados e onde estão definidos?
4. `FAILED` entra mesmo com `updated_at` recente? Qual teste prova?
5. Casos de espera recentes ficam fora? Qual teste prova?
6. A paginação preserva `attention=1`? Qual teste prova?
7. O card mostra o motivo, não apenas um badge genérico? Onde?
8. O relatório contém snippets antes/depois dos pontos principais?

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/administrative-case-closure-and-attention-filter/proposal.md, design.md, tasks.md, slices/slice-001-administrative-closure.md and slices/slice-002-attention-filter.md.
Assume Slice 001 is already complete. Implement ONLY Slice 002.
Use TDD: first add failing dashboard tests for the attention filter, then implement minimal code.
Add /dashboard/?attention=1 as a preset/filter on the existing dashboard list. Do not create a separate page.
Criteria: exclude CLEANED always; include FAILED, expired locks, processing/handoff statuses older than 30 minutes, and wait statuses older than 48 hours.
Show a compact “Atenção necessária” badge and reason on cards.
Preserve attention=1 in pagination links.
Do not close or mutate cases in this slice.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/administrative-case-closure-and-attention-filter/tasks.md when this slice is complete.
Create a detailed temporary markdown report with before/after snippets, commit and push.
Return REPORT_PATH=<path> and stop. Do not start any next slice without explicit confirmation.
```
