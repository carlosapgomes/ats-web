<!-- markdownlint-disable MD013 MD014 MD022 MD026 MD031 MD032 MD040 MD060 -->

# Relatório — Slice 001: Polimento UX do dashboard

## Resumo

Implementado o Slice 001 do change `dashboard-metrics-search-ux`:
- Duração humana em `_fmt_duration()` (minutos para < 60, horas/minutos para ≥ 60)
- Labels visíveis para `date_from` e `date_to` no formulário "Todos os Casos"

## Arquivos tocados

1. `apps/dashboard/views.py` — atualização de `_fmt_duration()`
2. `templates/dashboard/index.html` — adição de labels com `for`/`id`
3. `apps/dashboard/tests/test_dashboard.py` — novos testes

Nenhum outro arquivo foi tocado. Justificativa: os 3 arquivos esperados pelo slice.

## Snippets antes/depois

### 1. `_fmt_duration()` em `apps/dashboard/views.py`

**Antes:**
```python
def _fmt_duration(td: timedelta | None) -> str:
    """Formata timedelta para minutos."""
    if td:
        return f"{int(td.total_seconds() // 60)} min"
    return "—"
```

**Depois:**
```python
def _fmt_duration(td: timedelta | None) -> str:
    """Formata timedelta para minutos ou horas/minutos.

    Retorna:
        valor ausente    → "—"
        < 60 min         → "N min"
        60 min           → "1 h"
        65 min           → "1 h 05 min"
        1100 min         → "18 h 20 min"
        timedelta(0)     → "0 min"
    """
    if td is None:
        return "—"
    total_minutes = int(td.total_seconds() // 60)
    if total_minutes < 60:
        return f"{total_minutes} min"
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if minutes == 0:
        return f"{hours} h"
    return f"{hours} h {minutes:02d} min"
```

### 2. Labels no template `templates/dashboard/index.html`

**Antes:**
```html
<input type="date" name="date_from" class="form-control form-control-sm" style="width:auto;"
       value="{{ date_from }}" placeholder="Data início">
<input type="date" name="date_to" class="form-control form-control-sm" style="width:auto;"
       value="{{ date_to }}" placeholder="Data fim">
```

**Depois:**
```html
<div class="d-inline-flex flex-column align-items-start">
  <label for="date_from" class="form-label form-label-sm mb-0 small text-muted">Data inicial</label>
  <input type="date" name="date_from" id="date_from" class="form-control form-control-sm" style="width:auto;"
         value="{{ date_from }}" placeholder="Data início">
</div>
<div class="d-inline-flex flex-column align-items-start">
  <label for="date_to" class="form-label form-label-sm mb-0 small text-muted">Data final</label>
  <input type="date" name="date_to" id="date_to" class="form-control form-control-sm" style="width:auto;"
         value="{{ date_to }}" placeholder="Data fim">
</div>
```

### 3. Testes em `apps/dashboard/tests/test_dashboard.py`

**Adicionados:**
```python
class TestDashboardFmtDuration:
    """Testes para _fmt_duration do polimento de UX."""
    # 6 testes: None→—, 59 min, 60 min→1h, 65 min→1h05min, 1100 min→18h20min, timedelta(0)→0 min

class TestDashboardDateLabels:
    """Testes para labels visíveis de date_from e date_to."""
    # 2 testes: labels presentes no HTML, for/id associados corretamente
```

## Resultados do quality gate

| Comando | Resultado |
|---|---|
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 175 files already formatted |
| `uv run mypy .` | Success: no issues found in 194 source files |
| `uv run pytest` | 1725 passed |

## Autoavaliação (gates)

### 1. Qual teste prova que `1100 min` virou formato em horas?

`test_fmt_duration_1100_min` em `TestDashboardFmtDuration`:
```python
result = _fmt_duration(timedelta(minutes=1100))
assert result == "18 h 20 min"
```

### 2. Qual teste prova que `timedelta(0)` não virou `—`?

`test_fmt_duration_zero` em `TestDashboardFmtDuration`:
```python
result = _fmt_duration(timedelta(0))
assert result == "0 min"
```
Isso funciona porque a nova implementação testa `td is None` em vez de `if td:` (que tratava `timedelta(0)` como falsy).

### 3. Os labels são visíveis ou apenas `visually-hidden`? Por quê?

**Visíveis.** O requisito R2 diz "labels visíveis". Eles são exibidos com classe `small text-muted` acima de cada input, empilhados verticalmente com `d-inline-flex flex-column`. O layout Bootstrap responsivo é preservado.

### 4. Quais arquivos foram tocados e por quê?

- `apps/dashboard/views.py`: atualizar `_fmt_duration()` para formato humano
- `templates/dashboard/index.html`: adicionar labels com `for`/`id` nos inputs de data
- `apps/dashboard/tests/test_dashboard.py`: adicionar testes de TDD

### 5. Houve alteração de query, FSM ou permissão? Se sim, está errado.

**Não.** Nenhuma query, FSM ou permissão foi alterada. Apenas formatação de saída e markup do template.

### 6. O relatório contém snippets antes/depois dos pontos principais?

Sim, nesta seção acima.

## Critérios de sucesso

- [x] Testes foram escritos antes da implementação e falharam inicialmente (RED confirmado)
- [x] Durações menores que 60 minutos continuam em minutos
- [x] Durações de 60 minutos ou mais aparecem em horas/minutos
- [x] `timedelta(0)` aparece como `0 min`
- [x] Inputs de data têm labels visíveis e acessíveis (`for`/`id`)
- [x] Layout Bootstrap continua responsivo
- [x] Nenhuma funcionalidade fora do slice foi alterada
- [x] Quality gate do `AGENTS.md` passa

## Status dos slices

- [x] Slice 001 — Polimento UX: labels mobile e duração humana
- [ ] Slice 002 — Métricas do dashboard por data selecionada
- [ ] Slice 003 — Busca server-side indexada por nome ou registro
- [ ] Slice 004 — Busca dinâmica progressiva após 3 caracteres
