# Design: Prior Case Lookup

## Decisões

### D1: Service function em `apps/pipeline/prior_case.py`

Função pura que opera sobre QuerySet do Django ORM. Sem novo modelo.

```python
@dataclass(frozen=True)
class PriorCaseSummary:
    prior_case_id: UUID
    decided_at: datetime
    decision: Literal["deny_triage", "deny_appointment"]
    reason: str

@dataclass(frozen=True)
class PriorCaseContext:
    prior_case: PriorCaseSummary | None
    prior_denial_count_7d: int | None

def lookup_prior_case_context(
    case_id: UUID,
    agency_record_number: str,
    now: datetime | None = None,
) -> PriorCaseContext:
    """Busca contexto de casos anteriores com negações nos últimos 7 dias."""
    ...
```

Lógica portada fielmente de `build_prior_case_context()` do legado:
1. Busca casos com mesmo `agency_record_number`, exclui caso atual
2. Filtra por denial events (doctor_decision=deny com decided_at, ou appointment_status=denied com decided_at)
3. Filtra por janela de 7 dias
4. Retorna caso mais recente + contagem

### D2: Integração no orchestrator

`apps/pipeline/orchestrator.py` — antes de chamar `run_llm2_service()`:

```python
from apps.pipeline.prior_case import lookup_prior_case_context

prior_context = lookup_prior_case_context(
    case_id=case.case_id,
    agency_record_number=case.agency_record_number,
)
prior_case_json = None
if prior_context.prior_case is not None:
    prior_case_json = asdict(prior_context)  # dict para JSON
```

Passar `prior_case_json` para `run_llm2_service()` — o parâmetro já existe e é testado.

### D3: CaseEvent auditável

Após lookup com resultados, registrar CaseEvent:

```python
CaseEvent.objects.create(
    case=case,
    actor_type="system",
    event_type="PRIOR_CASE_LOOKUP",
    payload={
        "prior_case_id": str(prior_context.prior_case.prior_case_id),
        "decision": prior_context.prior_case.decision,
        "reason": prior_context.prior_case.reason,
        "denial_count_7d": prior_context.prior_denial_count_7d,
    },
)
```

### D4: Card na decisão médica

`templates/doctor/decision.html` — adicionar card condicional:

```html
{% if prior_context and prior_context.prior_case %}
<div class="card border-warning mb-3">
  <div class="card-header bg-warning text-dark">
    ⚠️ Caso Anterior — Negação Recente
  </div>
  <div class="card-body">
    <p><strong>Decisão:</strong> {{ prior_context.prior_case.decision_display }}</p>
    <p><strong>Motivo:</strong> {{ prior_context.prior_case.reason }}</p>
    <p><strong>Data:</strong> {{ prior_context.prior_case.decided_at|date:"d/m/Y H:i" }}</p>
    {% if prior_context.prior_denial_count_7d > 1 %}
    <p class="text-danger"><strong>{{ prior_context.prior_denial_count_7d }} negações nos últimos 7 dias</strong></p>
    {% endif %}
  </div>
</div>
{% endif %}
```

### D5: Contexto na view do doctor

`apps/doctor/views.py` — `doctor_decision()`: se case tem `agency_record_number`,
chamar `lookup_prior_case_context()` e adicionar ao contexto do template.

### D6: Card no case detail

`templates/intake/case_detail.html` — se houver CaseEvent `PRIOR_CASE_LOOKUP`,
mostrar card com informações do caso anterior.

### D7: Sem busca manual

O lookup é automático — sempre que há `agency_record_number`, o sistema busca.
Não há interface de busca manual por paciente.

## Arquivos previstos

| Arquivo | Tipo |
|---------|------|
| `apps/pipeline/prior_case.py` | novo (lookup logic) |
| `apps/pipeline/orchestrator.py` | modificado (integrar prior context) |
| `apps/doctor/views.py` | modificado (adicionar prior_context) |
| `templates/doctor/decision.html` | modificado (card caso anterior) |
| `templates/intake/case_detail.html` | modificado (card caso anterior) |
| `apps/pipeline/tests/test_prior_case.py` | novo (~15 testes) |
| `apps/doctor/tests/test_views.py` | modificado (testes do card) |
| `apps/intake/tests/test_case_detail.py` | modificado (testes do card) |

## Orçamento de testes

- `prior_case.py` unitários: ~12 (lookup vazio, 1 denial, múltiplos, fora da janela, etc.)
- Orchestrator integração: ~3
- Doctor decision view: ~3
- Case detail view: ~2
- Total estimado: ~20 novos testes
