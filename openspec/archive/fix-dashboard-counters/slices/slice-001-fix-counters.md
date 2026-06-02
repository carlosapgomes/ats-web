# Slice 001: Reescrever `_compute_summary()` com queries baseadas em decisão

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`, um monolito Django 5.2 SSR com templates Bootstrap, sem API REST e sem SPA.

Antes de codar, leia obrigatoriamente:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/fix-dashboard-counters/proposal.md`
4. `openspec/changes/fix-dashboard-counters/design.md`
5. Este arquivo de slice

Implemente **somente este slice**. Use TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Reescrever `_compute_summary()` em `apps/dashboard/views.py` para que os contadores "Aceitos" e "Negados" usem os campos de **decisão imutáveis** (`doctor_decision`, `appointment_status`) em vez do **estado FSM transitório** (`status`).

Este slice entrega o fluxo vertical completo:

```text
Query corrigida → contadores corretos → template renderiza valores precisos → testes validam
```

## Escopo funcional

- **Aceitos**: `doctor_decision="accept"` **E** `appointment_status ≠ "denied"`
- **Negados**: `doctor_decision="deny"` **OU** `appointment_status="denied"`
- **Em Andamento**: `total_today - accepted - denied`
- **Total Hoje**: sem alteração

## Fora de escopo neste slice

- Alterar submétricas (`_compute_stage_waiting`, `_compute_admission_flow`, `_compute_average_times`).
- Alterar o template `templates/dashboard/index.html`.
- Alterar o modelo `Case`, FSM ou migrations.
- Alterar a tabela de casos ou filtros.

## Arquivos previstos

Mantenha o slice enxuto. Apenas **2 arquivos** de código:

1. `apps/dashboard/views.py` — reescrever `_compute_summary()`, adicionar `Q` ao import
2. `apps/dashboard/tests/test_dashboard.py` — ajustar testes existentes + adicionar testes de regressão

Documentação:

3. `openspec/changes/fix-dashboard-counters/tasks.md` — marcar slice como concluído

Se tocar outros arquivos, justifique no relatório final.

## Implementação

### 1. `apps/dashboard/views.py`

#### 1a. Adicionar `Q` ao import

No topo do arquivo, alterar a linha:

```python
from django.db.models import Avg, DurationField, ExpressionWrapper, F
```

Para:

```python
from django.db.models import Avg, DurationField, ExpressionWrapper, F, Q
```

#### 1b. Reescrever `_compute_summary()`

Substituir a função atual por:

```python
def _compute_summary() -> dict[str, int]:
    """Computa métricas resumidas do dashboard.

    Usa campos de decisão imutáveis (doctor_decision, appointment_status)
    em vez do status FSM transitório, garantindo que:
    - Casos negados e já limpos (CLEANED) ainda são contados como negados.
    - Casos aceitos pelo médico mas negados pelo scheduler são contados
      como negados, não como aceitos.
    - Aceitos e Negados são mutuamente exclusivos.
    """
    today = timezone.now().date()
    today_cases = Case.objects.filter(created_at__date=today)

    total_today = today_cases.count()

    accepted = (
        today_cases.filter(doctor_decision="accept")
        .exclude(appointment_status="denied")
        .count()
    )

    denied = today_cases.filter(
        Q(doctor_decision="deny") | Q(appointment_status="denied")
    ).count()

    in_progress = total_today - accepted - denied

    return {
        "total_today": total_today,
        "accepted": accepted,
        "denied": denied,
        "in_progress": in_progress,
    }
```

### 2. `apps/dashboard/tests/test_dashboard.py`

#### 2a. Ajustar `test_summary_cards_show_correct_counts`

O teste existente cria:

```python
_create_case(created_by=user, status=CaseStatus.APPT_CONFIRMED, doctor_decision="accept")
_create_case(created_by=user, status=CaseStatus.WAIT_DOCTOR)
_create_case(created_by=user, status=CaseStatus.DOCTOR_DENIED)
_create_case(created_by=user, status=CaseStatus.APPT_DENIED)
```

Com as novas queries:

| Caso | doctor_decision | appointment_status | Nova classificação |
|------|:--------------:|:------------------:|--------------------|
| APPT_CONFIRMED | `accept` | *(vazio)* | Aceitos ✅ |
| WAIT_DOCTOR | *(vazio)* | *(vazio)* | Em Andamento ✅ |
| DOCTOR_DENIED | *(vazio)* | *(vazio)* | Em Andamento ❌ (antes era Negados) |
| APPT_DENIED | *(vazio)* | *(vazio)* | Em Andamento ❌ (antes era Negados) |

O terceiro e quarto casos não têm `doctor_decision="deny"` nem `appointment_status="denied"`. O ajuste necessário é:

**Para DOCTOR_DENIED:** adicionar `doctor_decision="deny"` explicitamente.
**Para APPT_DENIED:** adicionar `doctor_decision="accept"` e `appointment_status="denied"`.

Resultado após ajuste: Aceitos=1, Negados=2 (APPT_DENIED com `appointment_status="denied"` + DOCTOR_DENIED com `doctor_decision="deny"`), Em Andamento=1 (WAIT_DOCTOR). Total=4.

As assertions existentes verificam `"4"` no conteúdo e a presença de labels — devem continuar passando.

#### 2b. Adicionar testes de regressão

Adicionar uma nova classe de teste `TestDashboardSummaryFixed` (ou estender `TestDashboardSummaryCards`) com:

##### `test_denied_captures_doctor_deny_cleaned`

```python
def test_denied_captures_doctor_deny_cleaned(self, client) -> None:
    """Caso negado pelo médico e já CLEANED conta como Negados."""
    user = _login_as(client, "manager")
    _create_case(
        created_by=user,
        status=CaseStatus.CLEANED,
        doctor_decision="deny",
        agency_record_number="REG-DENY-CLEANED",
    )
    response = client.get("/dashboard/")
    assert response.status_code == 200
    # O número exato depende de outros casos criados em setup/outros testes.
    # Verificar que o card de Negados existe e não é 0.
    content = response.content.decode()
    assert "Negados" in content
```

> **Nota sobre isolamento:** como os testes usam `@pytest.mark.django_db` sem transação por classe, o banco pode acumular casos entre testes. Use `Case.objects.all().delete()` no início do teste ou faça assertions relativas. Ou melhor: crie os casos necessários e verifique valores absolutos após limpar.

##### `test_accepted_excludes_appt_denied`

```python
def test_accepted_excludes_appt_denied(self, client) -> None:
    """Caso com doctor_decision=accept e appointment_status=denied NÃO conta como Aceitos."""
    user = _login_as(client, "manager")
    Case.objects.all().delete()
    _create_case(
        created_by=user,
        status=CaseStatus.CLEANED,
        doctor_decision="accept",
        appointment_status="denied",
        agency_record_number="REG-ACCEPT-DENIED",
    )
    _create_case(
        created_by=user,
        status=CaseStatus.WAIT_DOCTOR,
        agency_record_number="REG-WAIT",
    )
    response = client.get("/dashboard/")
    assert response.status_code == 200
    content = response.content.decode()
    # Aceitos deve mostrar 0 (o caso accept+denied é Negados, não Aceitos)
    # Negados deve mostrar 1
    # Em Andamento deve mostrar 1 (WAIT_DOCTOR)
```

> Use `Case.objects.all().delete()` para isolar o teste de dados residuais.

##### `test_negados_captures_appt_denied_cleaned`

```python
def test_negados_captures_appt_denied_cleaned(self, client) -> None:
    """Caso com appointment_status=denied e já CLEANED conta como Negados."""
    user = _login_as(client, "manager")
    Case.objects.all().delete()
    _create_case(
        created_by=user,
        status=CaseStatus.CLEANED,
        doctor_decision="accept",
        appointment_status="denied",
        agency_record_number="REG-APPT-DENIED",
    )
    response = client.get("/dashboard/")
    assert response.status_code == 200
    content = response.content.decode()
    # O card de Negados deve mostrar 1
```

##### `test_no_double_count_appt_denied`

```python
def test_no_double_count_appt_denied(self, client) -> None:
    """Caso accept+denied aparece só em Negados, não duplamente."""
    user = _login_as(client, "manager")
    Case.objects.all().delete()
    _create_case(
        created_by=user,
        status=CaseStatus.APPT_DENIED,
        doctor_decision="accept",
        appointment_status="denied",
        agency_record_number="REG-DOUBLE",
    )
    response = client.get("/dashboard/")
    assert response.status_code == 200
    # Aceitos = 0, Negados = 1, Em Andamento = 0
    # Total = 1 → soma aceitos+negados+em_andamento = 1 (sem dupla contagem)
```

## Critérios de aceitação do slice

- [ ] `_compute_summary()` reescrita usando `doctor_decision` e `appointment_status`.
- [ ] `Q` adicionado ao import de `django.db.models`.
- [ ] "Aceitos" exclui casos com `appointment_status="denied"`.
- [ ] "Negados" captura `doctor_decision="deny"` e `appointment_status="denied"`.
- [ ] "Aceitos" e "Negados" são mutuamente exclusivos.
- [ ] "Em Andamento" = `total_today - accepted - denied` (confiável).
- [ ] Casos scope-gated (sem decisão médica) permanecem em "Em Andamento".
- [ ] Teste existente `test_summary_cards_show_correct_counts` ajustado e passando.
- [ ] Novos testes de regressão passando.
- [ ] Submétricas inalteradas continuam funcionando.
- [ ] Nenhum template alterado.
- [ ] `tasks.md` atualizado com slice concluído.

## Gates de autoavaliação

Antes de finalizar, responda no relatório:

1. `accepted` e `denied` são mutuamente exclusivos? Demonstre com um caso concreto.
2. Casos negados e já CLEANED são capturados? Qual query garante isso?
3. Casos scope-gated (sem `doctor_decision`) são classificados corretamente? Onde?
4. A dupla contagem foi eliminada? Como verificar?
5. Quantos arquivos foram tocados e por quê?
6. Os testes novos cobrem os 4 bugs do relatório de investigação?

## Comandos de validação

Rode no mínimo:

```bash
uv run pytest apps/dashboard/tests/test_dashboard.py -v
uv run ruff check apps/dashboard/views.py apps/dashboard/tests/test_dashboard.py
uv run ruff format --check apps/dashboard/views.py apps/dashboard/tests/test_dashboard.py
uv run mypy apps/dashboard
```

Ao final, rode o quality gate completo do `AGENTS.md`:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório final obrigatório

Crie relatório temporário em:

```text
/tmp/ats-web-slice-001-fix-dashboard-counters-report.md
```

O relatório deve conter:

- resumo do que foi implementado;
- lista de arquivos alterados;
- snippets antes/depois de `_compute_summary()`;
- testes ajustados (antes/depois);
- novos testes adicionados;
- comandos executados e resultados;
- confirmação de que os 4 bugs foram corrigidos;
- confirmação de atualização de `tasks.md`;
- commit hash e push, quando realizados.

Na resposta final, informe exatamente:

```text
REPORT_PATH=/tmp/ats-web-slice-001-fix-dashboard-counters-report.md
```

Depois pare e peça confirmação explícita antes de iniciar qualquer outro slice.
