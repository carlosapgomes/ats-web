# Slice 001 Report — Presenter: filtrar ausência de exame e mostrar data em todos os exames válidos

## Resumo

Hardening determinístico do `DoctorReportPresenter._build_tracked_exam_lines()` para:
1. Não renderizar entradas de `tracked_exams` cujo `result_value` indique ausência de exame
2. Mostrar data formatada para **todos** os exames válidos com `exam_datetime_iso`, independente de `is_most_recent`
3. Manter marcador "mais recente" apenas para `is_most_recent=True`

## Arquivos alterados

1. `apps/doctor/presenters.py` — adicionado helper `_is_absent_exam_result()` e modificado `_build_tracked_exam_lines()`
2. `apps/doctor/tests/test_presenter.py` — 5 novos testes + 1 teste atualizado

## Snippets Before/After

### Before: `_build_tracked_exam_lines()`

```python
def _build_tracked_exam_lines(self) -> list[str]:
    tracked_exams = self.structured_data.get("tracked_exams")
    if not isinstance(tracked_exams, list) or not tracked_exams:
        return []

    lines: list[str] = []
    for exam in tracked_exams:
        if not isinstance(exam, dict):
            continue

        exam_label = exam.get("exam_label")
        result_value = exam.get("result_value")
        is_most_recent = exam.get("is_most_recent")
        exam_datetime = exam.get("exam_datetime_iso")

        label_str = str(exam_label).strip() if isinstance(exam_label, str) and exam_label.strip() else "exame"
        value_str = (
            str(result_value).strip() if isinstance(result_value, str) and result_value.strip() else "não informado"
        )

        line = f"{label_str}: {value_str}"
        if is_most_recent is True:
            formatted_date = _format_exam_datetime(exam_datetime)
            if formatted_date:
                line += f" (mais recente em {formatted_date})"
            else:
                line += " (recência indeterminada (sem data no laudo))"
        lines.append(line)
    return lines
```

**Problemas:**
- `"Sem exame"` era renderizado normalmente como linha de exame rastreado
- Apenas exames com `is_most_recent=True` recebiam data formatada
- Exames não recentes com `exam_datetime_iso` não mostravam data alguma

### After: `_is_absent_exam_result()` + `_build_tracked_exam_lines()`

```python
def _is_absent_exam_result(value: Any) -> bool:
    """Return True when result_value indicates absence of exam.

    Normalizes the value (lowercase, strip, remove accents) and compares
    against a conservative list of absence indicators.
    """
    if not isinstance(value, str) or not value.strip():
        return False

    normalized = value.strip().lower()
    # Remove acentos portugueses
    normalized = (
        normalized.replace("\u00e1", "a")  # á
        .replace("\u00e0", "a")  # à
        .replace("\u00e3", "a")  # ã
        .replace("\u00e2", "a")  # â
        .replace("\u00e9", "e")  # é
        .replace("\u00ea", "e")  # ê
        .replace("\u00ed", "i")  # í
        .replace("\u00f3", "o")  # ó
        .replace("\u00f4", "o")  # ô
        .replace("\u00f5", "o")  # õ
        .replace("\u00fa", "u")  # ú
        .replace("\u00e7", "c")  # ç
    )
    # Compact spaces
    normalized = " ".join(normalized.split())

    absence_values = {
        "sem exame",
        "sem exames",
        "nao realizado",
        "nao realizada",
        "nao consta",
        "ausente",
        "sem laudo",
        "sem resultado",
    }
    return normalized in absence_values


# In DoctorReportPresenter:
def _build_tracked_exam_lines(self) -> list[str]:
    tracked_exams = self.structured_data.get("tracked_exams")
    if not isinstance(tracked_exams, list) or not tracked_exams:
        return []

    lines: list[str] = []
    for exam in tracked_exams:
        if not isinstance(exam, dict):
            continue

        result_value = exam.get("result_value")
        # Skip exams whose result indicates absence
        if _is_absent_exam_result(result_value):
            continue

        exam_label = exam.get("exam_label")
        is_most_recent = exam.get("is_most_recent")
        exam_datetime = exam.get("exam_datetime_iso")

        label_str = str(exam_label).strip() if isinstance(exam_label, str) and exam_label.strip() else "exame"
        value_str = (
            str(result_value).strip() if isinstance(result_value, str) and result_value.strip() else "não informado"
        )

        line = f"{label_str}: {value_str}"

        # Always show date when available, regardless of is_most_recent
        formatted_date = _format_exam_datetime(exam_datetime)
        if formatted_date:
            line += f" (data: {formatted_date}"
            if is_most_recent is True:
                line += "; mais recente"
            line += ")"
        elif is_most_recent is True:
            # Recent but no valid date — use fallback
            line += " (recência indeterminada (sem data no laudo))"

        lines.append(line)
    return lines
```

### Exemplos de saída

| Entrada | Saída (após) |
|---------|-------------|
| `ECG: Sem exame (mais recente...` | **Filtrado** — não aparece |
| `LAB externo: HB 12,1` (não recente, com data) | `LAB externo: HB 12,1 (data: 28/05/2026 08:30)` |
| `LAB interno: HB 12,9` (recente, com data) | `LAB interno: HB 12,9 (data: 01/06/2026 00:00; mais recente)` |
| `Hb: 12.0` (recente, data inválida) | `Hb: 12.0 (recência indeterminada (sem data no laudo))` |

## Testes adicionados/alterados

### Novo: `test_tracked_exam_absent_result_is_not_rendered`
- ECG com `result_value="Sem exame"` + Hb válida → apenas Hb aparece

### Novo: `test_tracked_exam_absent_result_variants_are_not_rendered`
- Parametriza `Não realizado`, `Nao realizado`, `Não consta`, `Nao consta`, `Ausente`, `Sem laudo`, `Sem resultado`
- Todos são filtrados → lista vazia

### Novo: `test_tracked_exam_valid_not_recent_shows_date_without_recent_marker`
- Exame não recente com data → data presente, "mais recente" ausente

### Novo: `test_tracked_exam_valid_recent_shows_date_and_recent_marker`
- Exame recente com data → data presente e "mais recente" presente

### Novo: `test_tracked_exam_valid_invalid_datetime_keeps_exam_without_crashing`
- Data inválida → linha com label/valor preservados, sem exceção

### Alterado: `test_tracked_exam_not_recent_shows_date_without_recent_marker` (renomeado)
- Antes: `test_tracked_exam_not_recent_does_not_show_recent_date_marker`
- Antes: assertava que data **não** aparecia
- Agora: asserta que data **aparece** mas "mais recente" não

## Quality Gate

| Etapa | Resultado |
|-------|-----------|
| `ruff check` | ✅ All checks passed |
| `ruff format --check` | ✅ 145 files already formatted |
| `mypy` | ✅ Success: no issues found in 157 source files |
| `pytest` | ✅ 1165 passed |

## Gates de autoavaliação

### 1. Qual helper identifica ausência de exame e quais variantes cobre?

`_is_absent_exam_result()` (função standalone no módulo `presenters.py`).

Cobre 8 variantes após normalização (lowercase + remoção de acentos):
- `sem exame`, `sem exames`, `nao realizado`, `nao realizada`
- `nao consta`, `ausente`, `sem laudo`, `sem resultado`

A normalização transforma acentos (ex: `não` → `nao`, `consta` → `consta` já sem acento) e compacta espaços, depois compara por igualdade contra o set.

### 2. O filtro pode ocultar resultados válidos? Como o código evita heurística agressiva?

O filtro é **conservador** por design:
- Usa **igualdade exata** após normalização, não substring/prefixo
- A lista de valores de ausência é explícita e testada
- Valores clínicos legítimos como `"Hb 12,5; sem alterações"` ou `"Paciente sem comorbidades"` NÃO seriam filtrados porque a string inteira não é igual a nenhum termo de ausência
- Apenas valores que são **exclusivamente** um indicador de ausência de exame são filtrados

### 3. Qual teste prova que "Sem exame" não é renderizado?

`test_tracked_exam_absent_result_is_not_rendered`:
- Cria ECG com `result_value="Sem exame"` + Hb válida
- Asserta que `tracked_exam_lines` contém apenas 1 item (Hb)
- Asserta que `"ECG"` e `"Sem exame"` não estão em nenhuma linha

### 4. Qual teste prova que exame não recente com data mostra data?

`test_tracked_exam_valid_not_recent_shows_date_without_recent_marker`:
- Cria exame com `is_most_recent=False` e `exam_datetime_iso="2026-05-28T08:30:00"`
- Asserta `"28/05/2026"` e `"08:30"` na linha
- Asserta que `"mais recente"` não está na linha

E também `test_tracked_exam_not_recent_shows_date_without_recent_marker` (atualizado):
- Mesma lógica com dados diferentes

### 5. O slice alterou prompt/schema/LLM?

**Não.** Este slice altera apenas:
- `apps/doctor/presenters.py` (helper + método)
- `apps/doctor/tests/test_presenter.py` (testes)

Nenhum prompt, schema Pydantic, template, banco, view, FSM ou decisão foi alterado.

## Commits

```
feat(doctor): harden tracked exam filtering and date display in presenter

- Add _is_absent_exam_result() helper filtering 8 absence variants
- Show formatted date for ALL valid exams with exam_datetime_iso
- Keep "mais recente" marker only for is_most_recent=True
- Handle invalid datetime gracefully without crashing
- Add 5 new tests, update 1 existing test
- All 1165 tests passing, ruff/mypy clean
```

## Branch

`feat/harden-tracked-exam-reporting`
