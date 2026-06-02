# Slice 007: Dashboard — bugfix de timezone em métricas do dia

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`, monolito Django SSR. Os slices 001–006 da change `shared-work-queue-leases` já devem estar implementados. Antes do hardening final, há um bug pré-existente de timezone que quebra testes do dashboard e deve ser corrigido de forma isolada.

Leia obrigatoriamente:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/shared-work-queue-leases/proposal.md`
4. `openspec/changes/shared-work-queue-leases/design.md`
5. Este arquivo

Implemente **somente este slice**. Use TDD: RED → GREEN → REFACTOR.

## Contexto do bug

Falhas observadas em `TestDashboardSummaryFixed`:

```text
timezone.now().date() retorna data UTC (ex.: 2026-06-01)
enquanto o dia operacional/local ainda é 2026-05-31.
O filtro created_at__date=today não encontra casos criados "hoje" no fuso local.
```

Causa provável em `apps/dashboard/views.py`:

```python
today = timezone.now().date()
today_cases = Case.objects.filter(created_at__date=today)
```

O mesmo padrão existe em `_compute_admission_flow()`.

## Objetivo do slice

Corrigir métricas do dashboard que dependem de “hoje” para usar o **dia local configurado no Django**, não a data UTC de `timezone.now().date()`.

Fluxo entregue:

```text
Servidor está em instante UTC já no dia seguinte
→ fuso local ainda está no dia anterior
→ caso criado no dia local atual deve contar em Total Hoje / Aceitos / Negados / Em andamento / Fluxo de admissão
```

## Escopo funcional

- Corrigir `_compute_summary()` para filtrar casos do dia local.
- Corrigir `_compute_admission_flow()` pelo mesmo critério.
- Preferir helper pequeno e testável para intervalo do dia local.
- Adicionar testes de regressão cobrindo fronteira UTC/local.
- Manter comportamento de contagem existente, mudando apenas a definição correta de “hoje”.

## Fora de escopo

- Alterar locks/leases.
- Alterar filas NIR/médico/agendador.
- Alterar templates do dashboard.
- Refatorar todo o dashboard.
- Alterar filtros manuais `date_from`/`date_to`, salvo se um teste demonstrar bug diretamente relacionado e o ajuste for pequeno.
- Alterar settings globais de timezone.

## Arquivos prováveis

Mantenha o slice enxuto:

1. `apps/dashboard/views.py`
2. `apps/dashboard/tests/test_dashboard.py`
3. `openspec/changes/shared-work-queue-leases/tasks.md` ao final

Se tocar outros arquivos, justificar no relatório.

## Plano TDD obrigatório

### RED — testes primeiro

Adicionar teste de regressão antes da correção.

Sugestão:

1. Usar `timezone.override("America/Sao_Paulo")` ou timezone local configurado do projeto.
2. Simular `timezone.now()` em um instante como:

```text
2026-06-01 02:30 UTC
```

Nesse instante, em `America/Sao_Paulo`, a data local ainda é:

```text
2026-05-31 23:30
```

3. Criar caso com `created_at` dentro do dia local `2026-05-31`.
4. Demonstrar que `_compute_summary()` conta esse caso como `total_today`.
5. Demonstrar que `_compute_admission_flow()` também usa o mesmo dia local para aceitos/agendado/imediato.
6. Opcionalmente criar caso no dia local anterior ou seguinte e provar que ele não entra.

Se os testes existentes `TestDashboardSummaryFixed` já reproduzem o bug, mantenha-os e acrescente pelo menos um teste explícito de fronteira UTC/local para evitar regressão futura.

### GREEN — implementação mínima

Evite `timezone.now().date()` para dia operacional.

Opção recomendada, mais robusta e index-friendly:

```python
from datetime import datetime, time, timedelta


def _local_day_bounds(day: date | None = None) -> tuple[datetime, datetime]:
    local_day = day or timezone.localdate()
    current_tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(local_day, time.min), current_tz)
    end = start + timedelta(days=1)
    return start, end
```

Então:

```python
start, end = _local_day_bounds()
today_cases = Case.objects.filter(created_at__gte=start, created_at__lt=end)
```

Aplicar também em `_compute_admission_flow()`.

Se preferir `timezone.localdate()` + `created_at__date`, justifique no relatório. A abordagem por intervalo é preferida porque evita ambiguidades de cast de data no banco e tende a usar índice de `created_at` melhor.

### REFACTOR

- Manter helper pequeno e local ao módulo.
- Não alterar semântica de `accepted`, `denied`, `in_progress`.
- Não criar abstração genérica de datas para o projeto inteiro neste slice.

## Critérios de aceitação

- [ ] `_compute_summary()` usa dia local, não `timezone.now().date()` UTC.
- [ ] `_compute_admission_flow()` usa o mesmo critério de dia local.
- [ ] Teste de regressão cobre fronteira UTC/local.
- [ ] `TestDashboardSummaryFixed` passa.
- [ ] Não houve alteração em FSM, locks ou templates.
- [ ] Slice toca poucos arquivos.
- [ ] `tasks.md` atualizado ao final.

## Gates de autoavaliação

Responder no relatório:

1. O que exatamente causava o bug de timezone?
2. Por que a solução usa `timezone.localdate()` ou intervalo local?
3. `_compute_summary()` e `_compute_admission_flow()` usam a mesma regra?
4. O teste falharia antes da correção?
5. Algum comportamento fora do dashboard foi alterado? Não deveria.

## Comandos de validação mínimos

```bash
uv run pytest apps/dashboard/tests/test_dashboard.py::TestDashboardSummaryFixed -q
uv run pytest apps/dashboard/tests -q
uv run ruff check apps/dashboard
uv run ruff format --check apps/dashboard
uv run mypy apps/dashboard
```

Se possível, rode o quality gate completo:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório final obrigatório

Criar relatório temporário em:

```text
/tmp/ats-web-slice-007-dashboard-localdate-bugfix-report.md
```

O relatório deve conter:

- resumo do bug e da correção;
- arquivos alterados;
- snippets antes/depois;
- testes adicionados/alterados;
- comandos executados e resultados;
- riscos/observações;
- confirmação de atualização de `tasks.md`;
- commit hash e push, quando realizados.

Resposta final obrigatória:

```text
REPORT_PATH=/tmp/ats-web-slice-007-dashboard-localdate-bugfix-report.md
```

Depois pare e peça confirmação explícita antes do Slice 008.

## Prompt pronto para implementador

```text
Read AGENTS.md, PROJECT_CONTEXT.md and shared-work-queue-leases OpenSpec, especially slices/slice-007-dashboard-localdate-bugfix.md.
Implement ONLY Slice 007 using TDD.
Fix the dashboard timezone bug where _compute_summary() and _compute_admission_flow() use timezone.now().date() UTC instead of the local operational day. Add regression tests around a UTC/local date boundary. Prefer a small local-day bounds helper and created_at__gte/created_at__lt filters. Do not touch locks, FSM, queues or templates.
Run validations, update tasks.md, create /tmp/ats-web-slice-007-dashboard-localdate-bugfix-report.md with snippets, commit and push, then reply REPORT_PATH and stop.
```
