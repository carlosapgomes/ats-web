# Slice 002 — Contrato LLM 3.0 e policies especializadas

## Objetivo

Criar os contratos strict 3.0 e a avaliação determinística pura de Ecoendoscopia/CPRE, incluindo evidência abdominal tipada e pendências agregadas. Ainda não trocar o orchestrator nem liberar intake.

## Contexto necessário

- `design.md`: D5–D9
- `specs/procedure-neutral-analysis/spec.md`
- schemas 2.0 e `apps/pipeline/schemas/adapters.py`
- `apps/pipeline/policy/eda_preop_policy.py`, `eda_policy.py`
- testes atuais de strict schema/policy

## Requisitos verificáveis

- **R1:** LLM1/LLM2 3.0 aceitam quatro tipos, evidência por procedimento e igualdade verificável de conjuntos.
- **R2:** imagem separa modalidade, anatomia, achado, excerpt e data; achado `yes` exige excerpt.
- **R3:** Eco aceita somente CT/MRI abdominal/abdome superior com achado; CPRE aceita a matriz clínica aprovada.
- **R4:** imagem sem sítio, mera menção/solicitação ou sem achado não satisfaz; data não expira.
- **R5:** Eco/CPRE reutilizam base EDA sem bypass de corpo estranho.
- **R6:** todas as falhas são agregadas em ordem estável; `reason_code` primário existente permanece compatível.
- **R7:** reconciliação genérica força deny quando a policy falha e audita contradição.

## Escopo e blast radius

```yaml
expected_files:
  - apps/pipeline/schemas/llm1_v3.py
  - apps/pipeline/schemas/llm2_v3.py
  - apps/pipeline/schemas/adapters.py
  - apps/pipeline/policy/eda_preop_policy.py
  - apps/pipeline/policy/procedure_policy.py
  - apps/pipeline/policy/__init__.py
  - apps/pipeline/tests/test_llm_v3_contracts.py
  - apps/pipeline/tests/test_specialized_preop_policy.py
allowed_incidental_files:
  - apps/pipeline/tests/test_eda_preop_policy.py
file_cap: 9
out_of_scope:
  - chamadas OpenAI/orchestrator
  - prompts ou seed
  - intake/UI
  - processamento de anexos
```

Escalar se o schema exigir alterar 1.1/2.0 ou se a agregação não puder preservar motivos legados.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivos esperados | Teste/check |
| --- | --- | --- |
| R1/R2 | `llm1_v3.py`, `llm2_v3.py` | validação Pydantic + strict normalization |
| R3–R6 | `eda_preop_policy.py` | tabela parametrizada de modalidade/sítio/achado/data e múltiplas falhas |
| R7 | `procedure_policy.py` | LLM2 accept contraditório torna-se deny |
| compatibilidade | `adapters.py` | detecção/projeção 1.1/2.0/3.0 sem rewrite |

## RED

- Comando: `uv run pytest apps/pipeline/tests/test_llm_v3_contracts.py apps/pipeline/tests/test_specialized_preop_policy.py -q`
- Falha esperada: módulos 3.0 e coleção `failed_requirements` ainda não existem.

## GREEN / verificação local

- Mesmo comando RED deve passar.
- `uv run pytest apps/pipeline/tests/test_eda_preop_policy.py apps/pipeline/tests/test_eda_policy.py apps/pipeline/tests/test_slice_002_contracts.py -q`
- `uv run ruff check apps/pipeline/schemas apps/pipeline/policy apps/pipeline/tests/test_llm_v3_contracts.py apps/pipeline/tests/test_specialized_preop_policy.py`
- `uv run ruff format --check` nos arquivos Python alterados.

## Critérios de aceitação

- [ ] R1–R7 demonstrados.
- [ ] US hepatobiliar satisfaz somente CPRE; US não satisfaz Eco.
- [ ] Sítio não especificado e ausência de conclusão falham.
- [ ] Nenhum anexo/tracked exam textual participa da decisão.
- [ ] Schemas 1.1/2.0 permanecem inalterados e legíveis.

## Handoff

Gerar `REPORT_PATH=/tmp/support-independent-echoendoscopy-cpre-slice-002-report.md` com exemplos de payload válido/inválido e resultados. Parar após review; não integrar orchestrator neste slice.
