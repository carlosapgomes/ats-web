# Slice 3: Policy Engine — Reconciliation + Support Synthesis

> **Status**: ✅ DONE
> **Depende de**: Slice 2 (eda_preop_policy)
> **Change**: `openspec/changes/pipeline-llm/`

---

## Leitura Obrigatória Antes de Implementar

1. `AGENTS.md` — regras do projeto
2. `docs/DOMAIN_ANALYSIS.md` — seção 6.2 (reconciliation), 6.3 (support synthesis)
3. Legado `domain/policy/eda_policy.py` — reconciliation
4. Legado `domain/policy/eda_recommendation_synthesis.py` — support synthesis

---

## Handoff para Implementador (LLM com contexto zero)

### Contexto

`eda_preop_policy.py` portado. Agora portamos as outras duas peças do policy engine.

### Sua Tarefa

Portar fielmente:
1. `reconcile_eda_policy()` do legado `eda_policy.py`
2. `synthesize_eda_support_context()` do legado `eda_recommendation_synthesis.py`

### Arquivos a Criar

```
apps/pipeline/policy/eda_policy.py                      # Portar
apps/pipeline/policy/eda_recommendation_synthesis.py    # Portar
apps/pipeline/tests/test_eda_policy.py                  # Testes reconciliation
apps/pipeline/tests/test_eda_recommendation_synthesis.py # Testes synthesis
```

### Detalhes Técnicos

#### eda_policy.py — Reconciliation

Funções a portar:
- `reconcile_eda_policy(precheck, llm2)` → `EdaPolicyResult`
- Dataclasses: `EdaPolicyPrecheckInput`, `Llm2PolicyAlignmentInput`, `Llm2SuggestionInput`, `EdaPolicyContradiction`, `EdaPolicyResult`

Regras de reconciliation:
1. `excluded_request` → força deny
2. `foreign_body` → labs_ok e ecg_ok viram "not_required"
3. `required_labs_missing_or_failed` → força deny
4. `required_ecg_missing` → força deny
5. Contradições registradas explicitamente

#### eda_recommendation_synthesis.py — Support Synthesis

Função a portar:
- `synthesize_eda_support_context(structured_data)` → `EdaSupportContext`

Regras:
- `cardiovascular_risk == "moderate_high"` → `anesthesist_icu`
- `asa_bucket == "III ou mais"` → `anesthesist`
- Resto → `none`

Dataclasses: `EdaSupportContext`

### Testes (portar todos)

#### Reconciliation:

1. Accept aceito — sem contradições
2. Excluded request força deny + contradição registrada
3. Foreign body → labs e ECG viram not_required
4. Labs missing força deny
5. ECG missing força deny
6. Labs pass com foreign body → not_required (não deny)
7. Múltiplas contradições registradas

#### Support Synthesis:

1. ASA I-II + low cardiovascular → none
2. ASA III + low cardiovascular → anesthesist
3. ASA insufficient_data + moderate_high → anesthesist_icu
4. ASA I-II + moderate_high → anesthesist_icu
5. Cardiovascular unknown → none (sem ASA III+)
6. ASA display text: "I-II", "III ou mais", "não foi possível estimar..."

### Critérios de Sucesso

```bash
uv run pytest apps/pipeline/tests/ -v
uv run pytest -v  # zero regressão
```

### Relatório

Gere `/tmp/slice-pipeline-003-report.md`.
Informe `REPORT_PATH=/tmp/slice-pipeline-003-report.md`.
