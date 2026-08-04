# Design: Lista estruturada de comorbidades no relatório médico

## Estado atual verificado

### Extração LLM1

`apps/pipeline/schemas/llm1.py` define o contrato Pydantic `Llm1Response` schema `1.1`. A extração já possui:

```text
preop_screening.rulebook_signals.clinical_flags
eda.asa
eda.cardiovascular_risk
summary
```

`clinical_flags` contém flags úteis para regra/ASA, mas não uma lista textual de comorbidades.

### Prompt LLM1

`apps/pipeline/llm1_service.py` centraliza:

- `LLM1_DEFAULT_SYSTEM_PROMPT`
- `LLM1_REQUIRED_SCHEMA_INSTRUCTIONS`
- `LLM1_DEFAULT_USER_PROMPT`
- `_render_user_prompt(...)`

`_render_user_prompt(...)` é importante porque suas instruções são anexadas mesmo quando existe prompt ativo customizado no banco. Isso permite evoluir o contrato sem depender de sobrescrever prompts existentes.

### Relatório médico

`apps/doctor/presenters.py::DoctorReportPresenter` monta o relatório usado por `templates/doctor/decision.html`.

Hoje o relatório médico tem contexto (`procedure`, `origin`, transfusão, exames rastreados, pediatria, alertas clínicos) e 7 blocos técnicos. Não há item exclusivo para comorbidades.

## Decisões

### D1. Campo novo dentro de `preop_screening`

Adicionar o campo:

```python
preop_screening.comorbidities_described: list[Llm1Comorbidity]
```

Formato de cada item:

```json
{
  "name": "hipertensão arterial sistêmica",
  "source_text_hint": "HAS"
}
```

Motivos:

- Fica próximo de triagem pré-procedimento.
- Não cria top-level novo no JSON.
- Evita misturar lista textual com `clinical_flags`, que são sinais rulebook.
- Mantém `Case.structured_data` como única persistência, sem migration.

### D2. Compatibilidade com casos antigos

O campo deve ter `default_factory=list` no Pydantic para manter compatibilidade com testes/payloads que ainda não incluam o campo.

No presenter, diferenciar:

- **campo ausente**: caso antigo ou payload pré-feature → `extração de comorbidades não disponível neste caso`;
- **campo presente e lista vazia**: novo caso sem comorbidades descritas → `sem comorbidades descritas no relatório`;
- **campo presente com itens**: renderizar nomes deduplicados separados por vírgula.

### D3. Não versionar para schema `1.2` neste change

Manter `schema_version == "1.1"`, com campo opcional/default no Pydantic.

Motivo: mudança backward-compatible; versionar para `1.2` aumentaria escopo em prompts, testes, fixtures e possíveis validações sem benefício operacional imediato.

### D4. Prompt deve exigir evidência textual explícita

A instrução deve evitar inferências indevidas:

- extrair comorbidades/condições crônicas/antecedentes patológicos descritos explicitamente;
- incluir siglas expandidas quando seguro (`HAS`, `DM2`, `DRC`, etc.);
- usar `source_text_hint` com trecho/sigla do relatório;
- não inferir apenas por medicação, exame, idade, obesidade implícita ou risco;
- se o relatório disser `sem comorbidades`, `nega comorbidades` ou equivalente, retornar lista vazia;
- não incluir sintomas, indicação da EDA, exames laboratoriais ou diagnóstico agudo isolado como comorbidade crônica.

### D5. Exibição como item exclusivo de contexto, não novo bloco decisório

Para minimizar alteração visual e não reabrir o contrato dos 7 blocos técnicos, exibir no `report-meta` uma linha dedicada:

```text
Comorbidades descritas: hipertensão arterial sistêmica, diabetes mellitus tipo 2
```

Isso cria um item exclusivo e visível sem transformar o relatório de 7 blocos em 8 blocos.

### D6. Sem alteração de decisão automática

A lista é informativa para o médico. O rulebook/ASA continuam usando os campos já existentes (`clinical_flags`, `eda.asa`, `eda.cardiovascular_risk`). Este change não altera policy, reconciliação, LLM2, suporte, filas ou FSM.

## Contrato proposto

### Schema Pydantic conceitual

```python
class Llm1Comorbidity(StrictModel):
    """Explicit comorbidity/clinical background described in the source report."""

    name: str = Field(min_length=1, max_length=120)
    source_text_hint: str | None = None


class Llm1PreopScreening(StrictModel):
    ...
    comorbidities_described: list[Llm1Comorbidity] = Field(default_factory=list, max_length=20)
```

### JSON esperado

Com comorbidades:

```json
"preop_screening": {
  "exam_type": "eda",
  "has_cardiovascular_disease": "yes",
  "has_active_respiratory_symptoms": "no",
  "has_prior_respiratory_disease": "unknown",
  "has_ecg_report": "yes",
  "has_chest_xray_report": "unknown",
  "has_echocardiogram_report": "unknown",
  "hb_g_dl": 12.1,
  "platelets_per_mm3": 210000,
  "inr": 1.0,
  "comorbidities_described": [
    {"name": "hipertensão arterial sistêmica", "source_text_hint": "HAS"},
    {"name": "diabetes mellitus tipo 2", "source_text_hint": "DM2"}
  ],
  "evidence_spans": [],
  "rulebook_signals": {}
}
```

Sem comorbidades descritas:

```json
"comorbidities_described": []
```

## Presenter

Adicionar helper pequeno e testável em `DoctorReportPresenter`, por exemplo:

```python
def _build_comorbidities_line(self) -> str:
    preop = _extract_nested(self.structured_data, "preop_screening")
    if not isinstance(preop, dict) or "comorbidities_described" not in preop:
        return "Comorbidades descritas: extração de comorbidades não disponível neste caso"

    items = preop.get("comorbidities_described")
    if not isinstance(items, list) or not items:
        return "Comorbidades descritas: sem comorbidades descritas no relatório"

    names = ...  # strings não vazias, deduplicadas preservando ordem
    if not names:
        return "Comorbidades descritas: sem comorbidades descritas no relatório"
    return f"Comorbidades descritas: {', '.join(names)}"
```

Adicionar a linha ao contexto:

```python
"comorbidities_line": self._build_comorbidities_line(),
```

Renderizar em `templates/doctor/decision.html` no `report-meta`, preferencialmente após origem e antes de transfusão/exames.

## Dimensionamento de slices

### Escolha: 1 slice vertical

A entrega mínima que satisfaz o médico exige extração estruturada **e** exibição no relatório. Separar schema/prompt em um slice e UI em outro seria horizontal e produziria uma etapa intermediária sem valor visível.

Portanto o change terá **um slice vertical enxuto**:

```text
LLM1 schema + prompt → persisted structured_data → presenter → template médico
```

Arquivos esperados no slice:

1. `apps/pipeline/schemas/llm1.py`
2. `apps/pipeline/llm1_service.py`
3. `apps/pipeline/tests/test_llm1_service.py`
4. `apps/doctor/presenters.py`
5. `templates/doctor/decision.html`
6. `apps/doctor/tests/test_presenter.py`

Se o implementador tocar mais arquivos, deve justificar no relatório. Não deve criar migration.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Médico receber lista incompleta | Prompt claro com evidência textual; manter PDF/texto extraído acessível. |
| Inferência indevida de comorbidade | Instrução explícita: não inferir por medicação/exame sem diagnóstico descrito. |
| Casos antigos sem campo parecerem “sem comorbidades” | Presenter diferencia campo ausente de lista vazia. |
| Schema quebra fixtures antigas | Campo com `default_factory=list`; testes existentes devem continuar passando. |
| Scope creep para policy/ASA | Slice proíbe alterações em LLM2, policy, suporte, FSM e decisão automática. |
| Prompt ativo no DB não conter novo schema | `_render_user_prompt(...)` deve anexar a instrução/schema novo independentemente do template ativo. |

## Rollback

Rollback simples por commit revert:

- remover campo Pydantic;
- remover instruções de prompt;
- remover helper/contexto do presenter;
- remover linha do template;
- remover testes novos.

Não há migration, dados novos em tabelas, FSM ou reprocessamento histórico.
