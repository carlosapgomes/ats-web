# Relatório Slice 001: Detector documental e renderização no relatório médico

## Resumo

Implementado detector de ingestão cáustica/corrosiva no texto extraído do PDF, com renderização de alerta visual no relatório técnico da triagem (tela de decisão médica).

## Arquivos alterados

1. `apps/doctor/presenters.py` — Adicionado `source_text` ao dataclass, funções auxiliares de detecção, e `clinical_alert_lines` no contexto
2. `apps/doctor/views.py` — Passagem de `source_text=case.extracted_text or ""` ao presenter
3. `templates/doctor/decision.html` — Renderização dos alertas no `report-meta`
4. `apps/doctor/tests/test_presenter.py` — 11 novos testes de detecção

## Antes e Depois

### Antes (presenter.py)

```python
@dataclass
class DoctorReportPresenter:
    structured_data: dict[str, Any] = field(default_factory=dict)
    summary_text: str = ""
    suggested_action: dict[str, Any] = field(default_factory=dict)
    recent_denial_context: dict[str, Any] | None = None
```

### Depois (presenter.py)

```python
@dataclass
class DoctorReportPresenter:
    structured_data: dict[str, Any] = field(default_factory=dict)
    summary_text: str = ""
    suggested_action: dict[str, Any] = field(default_factory=dict)
    recent_denial_context: dict[str, Any] | None = None
    source_text: str = ""  # <-- NOVO
```

### Antes (views.py)

```python
presenter = DoctorReportPresenter(
    structured_data=case.structured_data or {},
    summary_text=case.summary_text or "",
    suggested_action=case.suggested_action or {},
    recent_denial_context=recent_denial_ctx,
)
```

### Depois (views.py)

```python
presenter = DoctorReportPresenter(
    structured_data=case.structured_data or {},
    summary_text=case.summary_text or "",
    suggested_action=case.suggested_action or {},
    recent_denial_context=recent_denial_ctx,
    source_text=case.extracted_text or "",  # <-- NOVO
)
```

### Antes (template: report-meta sem alertas)

```html
<div class="report-meta mb-3 small text-muted">
  <div>{{ report.context.procedure }}</div>
  <div>{{ report.context.origin }}</div>
  {% for line in report.context.transfusion_lines %}<div>{{ line }}</div>{% endfor %}
  {% for line in report.context.tracked_exam_lines %}<div>{{ line }}</div>{% endfor %}
  {% if report.context.pediatric %}<div>{{ report.context.pediatric }}</div>{% endif %}
</div>
```

### Depois (template: report-meta com alertas)

```html
<div class="report-meta mb-3 small text-muted">
  ...
  {% for line in report.context.clinical_alert_lines %}
  <div class="alert alert-warning py-1 px-2 mb-1 small">{{ line }}</div>
  {% endfor %}
</div>
```

## Estrutura da detecção (`presenters.py`)

Módulo com funções puras testáveis:

- `_detect_caustic_ingestion(text)` — função principal, retorna `list[str]` com alertas
- `_has_caustic_keyword_near_ingestion(text)` — detecta keyword + verbo de ingestão próximos
- `_extract_time_from_text(text)` — extrai expressão temporal literal

### Padrões cobertos

**Termos positivos**: `cáustic`, `corrosiv`, `soda cáustica`, `ácido`

**Verbos de ingestão**: `ingeriu`, `ingestão`, `ingestão de`, `ingerir`, `ingerido`

**Padrões de tempo**: `há [X] [unidade]`, `há cerca de [X]`, `há aproximadamente [X]`, `em DD/MM/AAAA`

**Negação**: 4 padrões regex para negação explícita

## Testes adicionados (11)

| Teste | Descrição |
|---|---|
| `test_alert_detects_soda_caustica_with_relative_time` | "soda cáustica há 3 semanas" → alerta + tempo |
| `test_alert_detects_corrosive_substance_with_approximate_time` | "substância corrosiva há cerca de 10 dias" → alerta + tempo |
| `test_alert_detects_acid_ingestion_with_date` | "ácido em 12/05/2026" → alerta + data |
| `test_alert_without_time_uses_fallback` | "produto corrosivo" → alerta + "não informado" |
| `test_alert_absent_when_no_event` | texto sem ingestão → sem alerta |
| `test_alert_ignores_explicit_negation` | "nega ingestão de cáustico" → sem alerta |
| `test_alert_ignores_sem_ingestao_negation` | "Sem ingestão de corrosivos" → sem alerta |
| `test_alert_ignores_nao_ingeriu_negation` | "Não ingeriu soda cáustica" → sem alerta |
| `test_alert_shows_corrosive_acid_time_fallback` | "História de ingestão de ácido" → alerta + fallback |
| `test_source_text_default_empty_maintains_compatibility` | sem `source_text` → `[]` |
| `test_text_report_includes_clinical_alert_lines` | `build_text_report` inclui alertas |

## Gates de autoavaliação

1. **Onde o detector lê o texto fonte?** → `DoctorReportPresenter.source_text`, populado pela view com `case.extracted_text`
2. **Quais termos positivos são cobertos?** → `cáustic`, `corrosiv`, `soda cáustica`, `ácido` (proximidade com verbo de ingestão)
3. **Quais padrões de tempo são cobertos?** → `há [X] [unidade]`, `há cerca de [X]`, `há aproximadamente [X]`, `em DD/MM/AAAA`
4. **Como negações simples são evitadas?** → 4 regex de negação verificados antes da detecção positiva
5. **O código alterou `suggested_action`, policy, FSM ou persistência?** → Não. Apenas `report.context.clinical_alert_lines` no presenter
6. **O alerta aparece sem abrir JSON/texto extraído?** → Sim, renderizado inline no `report-meta` com `.alert-warning`
7. **Algum arquivo fora dos esperados foi alterado?** → Não. Apenas os 4 arquivos previstos

## Quality Gate

- `uv run ruff check .` ✅
- `uv run ruff format --check .` ✅
- `uv run mypy .` ✅
- `uv run pytest` ✅ (1178 passed)
