# Relatório Follow-up Slice 001: Hardening do detector de ingestão cáustica/corrosiva

## Resumo

Endurecido o detector documental para suportar texto sem acentos (comum em PDFs extraídos) e eliminar falso positivo de `soda cáustica` isolada sem contexto de ingestão.

## Arquivos alterados

1. `apps/doctor/presenters.py` — Adicionado `import unicodedata`, helper `_normalize_caustic_text()`, keywords/patterns normalizados sem acento, remoção do fallback de `soda cáustica` isolada
2. `apps/doctor/tests/test_presenter.py` — 7 novos testes de hardening

## Antes e Depois

### Antes: keywords com acentos literais

```python
_CAUSTIC_KEYWORDS: set[str] = {"cáustic", "corrosiv", "soda cáustica", "ácido"}
_INGESTION_VERBS: set[str] = {"ingeriu", "ingestão", "ingestão de", "ingerir", "ingerido"}
```

### Depois: keywords sem acento (matching sobre texto normalizado)

```python
_CAUSTIC_KEYWORDS: set[str] = {"caustic", "corrosiv", "soda caustica", "acido"}
_INGESTION_VERBS: set[str] = {"ingeriu", "ingestao", "ingerir", "ingerido"}
```

### Antes: sem normalização, matching direto em `text.lower()`

```python
text_lower = text.lower()
if "soda cáustica" in text_lower:
    return True
```

### Depois: normalização NFD + remoção de combining chars

```python
def _normalize_caustic_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    stripped_accents = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    normalized = stripped_accents.lower()
    return " ".join(normalized.split())
```

### Antes: negação exigia "de" após "sem ingestão"

```python
re.compile(r"sem\s+ingestão\s+de\s+(corrosiv|cáustic)", ...)
```

### Depois: negação adicional para "sem ingestão" sem "de"

```python
re.compile(r"sem\s+(relato\s+de\s+)?ingestao[\s,;.:!?]", ...)
```

### Antes: tempo só `há` acentuado

```python
re.compile(r"há\s+(cerca\s+de\s+|...)...")
```

### Depois: `h[aá]` cobre ambos

```python
re.compile(r"h[aá]\s+(cerca\s+de\s+|...)...", ...)
```

## Testes adicionados (7)

| Teste | Descrição |
|---|---|
| `test_alert_detects_unaccented_soda_caustica_with_time` | "soda caustica ha 3 semanas" → alerta + "ha 3 semanas" |
| `test_alert_detects_unaccented_ingestao_corrosiva_with_time` | "ingestao de substancia corrosiva ha cerca de 10 dias" → alerta + tempo |
| `test_alert_detects_unaccented_acid_ingestion_with_date` | "ingestao de acido em 12/05/2026" → alerta + data |
| `test_alert_ignores_unaccented_negation` | "nega ingestao de caustico" → sem alerta |
| `test_alert_ignores_unaccented_nao_ingeriu_soda_caustica` | "Nao ingeriu soda caustica" → sem alerta |
| `test_alert_ignores_soda_caustica_contact_without_ingestion` | "Contato com soda cáustica, sem ingestão" → sem alerta |
| `test_alert_ignores_soda_caustica_burn_without_ingestion` | "Queimadura por soda caustica" → sem alerta |

## Gates de autoavaliação

1. **Qual helper normaliza texto e como remove acentos?** → `_normalize_caustic_text()` usa `unicodedata.normalize("NFD", value)` e remove caracteres de categoria `Mn` (combining marks), depois lowercase e collapse whitespace
2. **A detecção positiva e as negações usam texto normalizado?** → Sim, `_detect_caustic_ingestion` normaliza o texto antes de passar para `_has_caustic_keyword_near_ingestion` e para os patterns de negação
3. **`soda cáustica` ainda dispara alerta sem contexto de ingestão?** → Não. O fallback `if "soda cáustica" in text_lower: return True` foi removido. Agora segue a mesma regra de proximidade com verbo de ingestão.
4. **Quais testes provam suporte a texto sem acento?** → `test_alert_detects_unaccented_*` (3 testes) + `test_alert_ignores_unaccented_*` (2 testes)
5. **Quais testes provam que contato/queimadura por soda cáustica não dispara alerta?** → `test_alert_ignores_soda_caustica_contact_without_ingestion` e `test_alert_ignores_soda_caustica_burn_without_ingestion`
6. **O código alterou decisão, policy, FSM, schema, prompt ou persistência?** → Não. Apenas o detector de ingestão cáustica no presenter foi endurecido.
7. **Algum arquivo fora dos esperados foi alterado?** → Não. Apenas `presenters.py` e `test_presenter.py`.

## Quality Gate

- `uv run ruff check .` ✅
- `uv run ruff format --check .` ✅
- `uv run mypy .` ✅
- `uv run pytest` ✅ (1185 passed)
