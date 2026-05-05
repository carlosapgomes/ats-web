# Slice 4: Scope Detection

> **Status**: TODO
> **Depende de**: Slice 1 (app pipeline)
> **Change**: `openspec/changes/pipeline-llm/`

---

## Leitura Obrigatória Antes de Implementar

1. `AGENTS.md` — regras do projeto
2. `docs/DOMAIN_ANALYSIS.md` — seção 6.4 (scope detection)
3. Legado `application/services/process_pdf_case_service.py` — funções `_detect_*`, `build_scope_gated_manual_review_payload`

---

## Handoff para Implementador (LLM com contexto zero)

### Contexto

Policy engine portado. Agora portamos a detecção de escopo: identificar se o exame é EDA.

### Sua Tarefa

Portar a lógica de scope detection do `process_pdf_case_service.py` do legado:
- Detecção de subtipo EDA por keywords (gastrostomia, dilatação, corpo estranho)
- Detecção de EDA genérico
- Classificação final: `eda`, `non_eda`, `unknown`
- Se `non_eda` ou `unknown` → gerar payload de `manual_review_required`

### Arquivos a Criar

```
apps/pipeline/scope_detection.py              # Portar
apps/pipeline/tests/test_scope_detection.py   # Testes
```

### Detalhes Técnicos

#### Funções a portar

Do legado `process_pdf_case_service.py`:

- `build_scope_gated_manual_review_payload(case_id, agency_record_number, llm1_structured_data, cleaned_text)` → `dict | None`
- `_extract_preop_exam_type(llm1_structured_data)` → `str | None`
- `_detect_supported_eda_scope_keyword(llm1_structured_data, cleaned_text)` → `(subtype, term)`
- `_detect_explicit_eda_scope_keyword(llm1_structured_data, cleaned_text)` → `(bool, term)`
- `_normalize_scope_keyword_text(value)` → `str`
- `_contains_scope_keyword(normalized_text, term)` → `bool`
- Todos os helpers associados

#### Keywords (portar fielmente)

```python
_SCOPE_GASTROSTOMY_TERMS = ("gtt", "gastrostomia", "gastrostomy", "confeccao de gtt", "programar gtt")
_SCOPE_ESOPHAGEAL_DILATION_TERMS = ("dilatacao esofagica", "dilatacao de esofago", "dilatacao do esofago")
_SCOPE_FOREIGN_BODY_TERMS = ("corpo estranho", "retirada de corpo estranho")
_SCOPE_EXPLICIT_EDA_TERMS = (
    "endoscopia digestiva alta",
    "solicitacao de endoscopia digestiva alta",
    "endoscopia digestiva alta - eda",
    "videoendoscopia digestiva alta",
    "endoscopia digestiva superior",
)
```

#### Lógica principal

```python
def classify_exam_scope(
    llm1_structured_data: dict[str, object],
    cleaned_text: str,
    case_id: str,
    agency_record_number: str,
) -> dict[str, object] | None:
    """Returns None if EDA (proceed with LLM2).
    Returns manual_review payload if non_eda or unknown."""
```

### Testes (portar todos)

1. Gastrostomia keyword → subtype gastrostomy → EDA
2. Dilatação esofágica keyword → subtype esophageal_dilation → EDA
3. Corpo estranho keyword → subtype foreign_body → EDA
4. EDA explícito (texto completo) → EDA
5. EDA acrônimo com contexto de solicitação → EDA
6. Non-EDA explícito (CPRE, colonoscopia) → non_eda → manual_review
7. Unknown exam type → unknown → manual_review
8. Subtipo do LLM1 usado como fallback
9. Normalização de acentos e case
10. Palavras parciais não matching (ex: "edac" não deve match "eda")

### Critérios de Sucesso

```bash
uv run pytest apps/pipeline/tests/test_scope_detection.py -v
uv run pytest -v  # zero regressão
```

### Relatório

Gere `/tmp/slice-pipeline-004-report.md`.
Informe `REPORT_PATH=/tmp/slice-pipeline-004-report.md`.
