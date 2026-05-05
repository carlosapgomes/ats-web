# Slice 2: Policy Engine — EDA Preop Policy

> **Status**: DONE
> **Depende de**: Slice 1 (app pipeline criado)
> **Change**: `openspec/changes/pipeline-llm/`

---

## Leitura Obrigatória Antes de Implementar

1. `AGENTS.md` — regras do projeto
2. `docs/DOMAIN_ANALYSIS.md` — seção 6 (políticas clínicas)
3. Legado `domain/policy/eda_preop_policy.py` — **PORTAR FIELMENTE**
4. Legado `application/dto/llm1_models.py` — entender estrutura do structured_data

---

## Handoff para Implementador (LLM com contexto zero)

### Contexto

App `apps/pipeline/` criado. Agora precisamos portar o **policy engine determinístico** — a peça clínica mais crítica do sistema.

### Sua Tarefa

Portar `eda_preop_policy.py` do legado (`/home/carlos/projects/augmented-triage-system/src/triage_automation/domain/policy/eda_preop_policy.py`) para `apps/pipeline/policy/eda_preop_policy.py`, **com todos os testes**.

### Regra ABSOLUTA

> **O código do policy engine é uma regra de segurança clínica.**
> Cada threshold (HB, plaquetas, INR), cada conditional gate (ECG, RX, eco), cada perfil (hepatopatia, cardiopatia) deve ser portado **fielmente**.
> Não simplificar, não otimizar, não renomear constantes clínicas.
> Testes devem cobrir todos os paths: foreign body exception, minimum exams, thresholds por perfil, conditional gates.

### Arquivos a Criar

```
apps/pipeline/policy/__init__.py              # Criar
apps/pipeline/policy/eda_preop_policy.py      # Portar do legado
apps/pipeline/tests/test_eda_preop_policy.py  # Portar testes
```

### Detalhes Técnicos

#### Portabilidade

O legado usa funções puras com `dict[str, object]` como entrada/saída. **Zero mudança de API**.

Funções a portar (todas):
- `evaluate_eda_preop_policy(structured_data)` → `dict[str, object]`
- `_find_missing_minimum_exam()` → `(reason_code, exam_label) | None`
- `_find_missing_conditional_exam_gate()` → `(reason_code, reason_text) | None`
- `_resolve_contraindication_thresholds()` → `ContraindicationThresholds`
- `_extract_supported_eda_subtype()` → `SupportedEdaSubtype`
- `_extract_hb_value()`, `_extract_platelets_value()`, `_extract_rni_value()`
- `_is_ecg_gate_required()`, `_is_chest_xray_gate_required()`, `_is_echocardiogram_gate_required()`
- Todos os helpers (`_extract_dict`, `_extract_text`, `_extract_float`, etc.)

#### Dataclasses

Manter as dataclasses do legado:
- `EdaPreopDecision`
- `ContraindicationThresholds`

#### Thresholds (valores clínicos — NÃO ALTERAR)

| Perfil | HB mín | Plaquetas mín | INR/RNI máx |
|--------|--------|--------------|-------------|
| Geral | 7.0 | 100.000 | 1.5 |
| Hepatopatia | 7.0 | 50.000 | 1.5 |
| Cardiopatia | 8.0 | 100.000 | 1.5 |
| Hepatopatia + Cardiopatia | 8.0 | 50.000 | 1.5 |

#### Testes (portar todos)

Casos de teste mínimos obrigatórios:

1. **Foreign body exception**: subtype=foreign_body → accept, bypass exams
2. **Missing minimum exam** (cada um dos 6): Hb, plaquetas, TP/INR/RNI, TTPa, ureia, creatinina
3. **HB below threshold** (geral, hepatopatia, cardiopatia, ambos)
4. **Platelets below threshold** (por perfil)
5. **INR above threshold** (por perfil)
6. **ECG conditional gate**: age > 40, cardiovascular disease, respiratory
7. **Chest X-ray gate**: respiratory symptoms
8. **Echocardiogram gate**: structural heart risk
9. **Accept case**: all criteria met
10. **Pediatric flag**: age < 16

### Critérios de Sucesso

```bash
uv run pytest apps/pipeline/tests/test_eda_preop_policy.py -v
# Esperado: 30+ testes passando (portados do legado)
uv run pytest -v  # zero regressão
```

### Relatório

Gere `/tmp/slice-pipeline-002-report.md`.
Informe `REPORT_PATH=/tmp/slice-pipeline-002-report.md`.
