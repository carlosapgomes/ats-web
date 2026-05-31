# Design: Corrigir contadores do dashboard

## Estado atual

### Código em `apps/dashboard/views.py`

```python
def _compute_summary() -> dict[str, int]:
    today = timezone.now().date()
    today_cases = Case.objects.filter(created_at__date=today)

    total_today = today_cases.count()

    accepted = (
        today_cases.filter(
            doctor_decision="accept",
        )
        .exclude(
            status__in=[CaseStatus.DOCTOR_DENIED, CaseStatus.FAILED],
        )
        .count()
    )

    denied = today_cases.filter(
        status__in=[CaseStatus.DOCTOR_DENIED, CaseStatus.APPT_DENIED],
    ).count()

    in_progress = total_today - accepted - denied

    return {
        "total_today": total_today,
        "accepted": accepted,
        "denied": denied,
        "in_progress": in_progress,
    }
```

### Problemas identificados

1. **`accepted`**: usa `doctor_decision="accept"` (decisão médica), mas não verifica `appointment_status`. Casos aceitos pelo médico e negados pelo scheduler são contados como aceitos.

2. **`denied`**: usa `status__in=[DOCTOR_DENIED, APPT_DENIED]` (estado FSM), ignorando `doctor_decision` e `appointment_status`. Casos negados que transicionaram para CLEANED não são capturados.

3. **`in_progress`**: subtração propaga os erros. Casos negados não capturados por `denied` e não qualificados como `accepted` caem aqui.

4. **Risco de sobreposição**: um caso com `doctor_decision="accept"` e `status=APPT_DENIED` seria contado em ambos `accepted` e `denied`, fazendo `in_progress` subcontar.

## Decisões

### D1: Usar campos de decisão imutáveis em vez de estado FSM

Os campos `doctor_decision` (`accept`/`deny`) e `appointment_status` (`confirmed`/`denied`) são definidos no momento da decisão e **nunca mais se alteram**. Já o `status` FSM transiciona naturalmente (ex: `DOCTOR_DENIED` → `WAIT_R1_CLEANUP_THUMBS` → `CLEANED`).

**Justificativa:** para métricas de desfecho, a decisão é a fonte de verdade, não o estado atual do pipeline.

### D2: Nova definição de "Aceitos"

```python
accepted = today_cases.filter(
    doctor_decision="accept"
).exclude(
    appointment_status="denied"
).count()
```

- Médico aceitou **E** scheduler não negou.
- Casos com `appointment_status=""` (ainda não decidido) contam como aceitos — o médico já aprovou.
- Casos com `appointment_status="denied"` são excluídos — o desfecho final foi negativo.

### D3: Nova definição de "Negados"

```python
denied = today_cases.filter(
    Q(doctor_decision="deny") | Q(appointment_status="denied")
).count()
```

- Médico negou **OU** scheduler negou.
- Independe do `status` FSM. Funciona para casos em `DOCTOR_DENIED`, `APPT_DENIED`, `WAIT_R1_CLEANUP_THUMBS`, ou `CLEANED`.
- Precisa importar `from django.db.models import Q`.

### D4: "Em Andamento" mantém fórmula de subtração

```python
in_progress = total_today - accepted - denied
```

Com D2 e D3, `accepted` e `denied` são **mutuamente exclusivos**:
- Se `doctor_decision="accept"` e `appointment_status="denied"` → conta em `denied`, não em `accepted` (excluído pelo `.exclude`).
- Se `doctor_decision="deny"` → conta em `denied`, não em `accepted` (`doctor_decision ≠ "accept"`).
- Sem sobreposição possível. A subtração é confiável.

### D5: Ajuste no import

Adicionar `Q` ao import do `django.db.models` no topo de `views.py`:

```python
from django.db.models import Avg, DurationField, ExpressionWrapper, F, Q
```

`Q` é o único novo import necessário. Nenhuma dependência externa adicionada.

### D6: Submétricas não alteradas

- `_compute_stage_waiting()` — já usa `status` (estado atual), correto para "aguardando".
- `_compute_admission_flow()` — já usa `doctor_decision="accept"`, consistente com D2.
- `_compute_average_times()` — usa timestamps, não afetado.

Nenhuma alteração nessas funções.

### D7: Template inalterado

O template `templates/dashboard/index.html` apenas renderiza `{{ summary.total_today }}`, `{{ summary.accepted }}`, `{{ summary.denied }}`, `{{ summary.in_progress }}`. Nenhuma mudança necessária.

## Arquivos previstos

Apenas **2 arquivos** (mais o slice e tasks.md):

1. `apps/dashboard/views.py` — reescrever `_compute_summary()` + adicionar `Q` ao import.
2. `apps/dashboard/tests/test_dashboard.py` — ajustar testes existentes + adicionar testes de regressão.

Arquivos de documentação do change:

3. `openspec/changes/fix-dashboard-counters/proposal.md`
4. `openspec/changes/fix-dashboard-counters/design.md` (este arquivo)
5. `openspec/changes/fix-dashboard-counters/tasks.md`
6. `openspec/changes/fix-dashboard-counters/slices/slice-001-fix-counters.md`

## Testes a ajustar

### Testes existentes que precisam de ajuste

`test_summary_cards_show_correct_counts`: Cria 4 casos (APPT_CONFIRMED, WAIT_DOCTOR, DOCTOR_DENIED, APPT_DENIED) e espera Aceitos=1, Negados=2. Com as novas queries:
- APPT_CONFIRMED + `doctor_decision="accept"` → Aceitos ✅
- WAIT_DOCTOR sem decisão → Em Andamento ✅
- DOCTOR_DENIED → `doctor_decision` não setado explicitamente no teste, mas status=DOCTOR_DENIED sem `doctor_decision="deny"` → Em Andamento. Ajustar o teste para setar `doctor_decision="deny"` explicitamente.
- APPT_DENIED → sem `doctor_decision` nem `appointment_status` setados → Em Andamento. Ajustar o teste para setar `doctor_decision="accept"` e `appointment_status="denied"`.

### Novos testes de regressão

1. **`test_denied_captures_cleaned_cases`**: caso com `doctor_decision="deny"` e `status=CLEANED` → conta como Negados.
2. **`test_denied_captures_appt_denied_cleaned_cases`**: caso com `doctor_decision="accept"`, `appointment_status="denied"`, `status=CLEANED` → conta como Negados, não Aceitos.
3. **`test_accepted_excludes_appt_denied`**: caso com `doctor_decision="accept"`, `appointment_status="denied"` → não conta como Aceitos.
4. **`test_in_progress_excludes_denied_cleaned`**: caso negado e CLEANED → não aparece em Em Andamento.
5. **`test_no_double_count`**: caso com `doctor_decision="accept"`, `appointment_status="denied"` não é contado duplamente.

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Quebrar testes existentes | Ajustar os testes para refletir a nova semântica, documentando a razão no slice |
| Casos legados sem `doctor_decision` ou `appointment_status` setados | A query lida naturalmente: campos vazios não batem com `"accept"`, `"deny"`, `"denied"` → caem em "Em Andamento" |
| Mudança de comportamento percebida por gestores | "Aceitos" pode diminuir e "Negados" aumentar — isso é uma **correção**, não uma regressão. Comunicar no relatório |
| Performance das queries | Adicionar `Q` e `.exclude` não introduz JOINs extras; performance equivalente |

## Rollback

Reverter `apps/dashboard/views.py::_compute_summary()` para a versão anterior. Nenhuma migration, modelo ou template afetado.
