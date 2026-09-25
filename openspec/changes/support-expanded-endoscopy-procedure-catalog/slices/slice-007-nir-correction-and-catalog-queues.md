# Slice 007 — Correção, resposta e filas NIR pelo catálogo

## Objetivo

Completar a jornada NIR após o upload: combobox em correção/reenvio, reprocessamento 4.0, acompanhamento/encerrados com filtro exato e resposta final das três dimensões para todas as identidades.

## Contexto necessário

- `design.md`: D9–D12;
- specs `exam-type-correction`, `exam-type-intake-routing`, `searchable-procedure-selection` e requisitos NIR de analytics;
- `apps/intake/views.py`, `forms.py`, `services.py`;
- templates `intake/case_detail.html`, `corrected_resubmission.html`, `my_cases.html`, `closed_cases_search.html`;
- JS do combobox e filtros NIR existentes;
- testes de correção/reenvio/resposta/filtros existentes.

## Requisitos verificáveis

- **R1:** correção e reenvio usam o mesmo combobox/selection keys do catálogo, preservam seleção em erro e rejeitam alias/texto livre/conjunto proibido sem persistência parcial.
- **R2:** correção elegível mantém UUID/documentos/texto, invalida derivados, registra anterior/novo e agenda exatamente um reprocessamento 4.0 sem anexos; `WAIT_DOCTOR+` continua bloqueado.
- **R3:** reenvio cria novo caso somente com a seleção escolhida e não altera original.
- **R4:** cards/detalhes/resposta final projetam labels e declarado/detectado/autorizado/razões, com uma identidade por pacote e duas rows só no combinado.
- **R5:** operacionais/encerrados filtram por código atômico exato ou `eda_colonoscopy`; EDA simples não entra no filtro de variação e polling preserva parâmetros.
- **R6:** flags preexistentes continuam limitando somente seus intakes; nenhuma flag nova é criada.

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/intake/forms.py
  - apps/intake/views.py
  - apps/intake/services.py
  - templates/intake/case_detail.html
  - templates/intake/corrected_resubmission.html
  - templates/intake/my_cases.html
  - templates/intake/closed_cases_search.html
  - static/js/procedure_combobox.js
  - apps/intake/tests/test_expanded_procedure_correction.py
  - apps/intake/tests/test_expanded_nir_queues.py
allowed_incidental_files:
  - partial de seleção/filtro compartilhado
  - JS NIR existente diretamente responsável por polling/filtro
out_of_scope:
  - filas médica/CHD
  - analytics gerencial
  - policy/detecção nova
```

Se correção exigir reextração de PDF/anexo, mudança de elegibilidade/FSM ou nova flag, parar e escalar.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1–R3 | forms/views/services/templates | `test_expanded_procedure_correction.py` |
| R4–R5 | views/templates/filtro | `test_expanded_nir_queues.py` |
| R6 | options/flags | testes parametrizados + `rg` |

## RED

```bash
uv run pytest \
  apps/intake/tests/test_expanded_procedure_correction.py \
  apps/intake/tests/test_expanded_nir_queues.py -q
node --test static/js/tests/procedure_combobox.test.js
```

Criar testes antes. Falha esperada: radios/listas atuais não cobrem catálogo e filtros/resposta omitirem identidades novas. Incluir POST manipulado, 3.0→4.0, fila exatamente uma vez e EDA vs EDA+GTT.

## GREEN / verificação local

```bash
uv run pytest \
  apps/intake/tests/test_expanded_procedure_correction.py \
  apps/intake/tests/test_expanded_nir_queues.py \
  apps/intake/tests/test_exam_type_correction.py \
  apps/intake/tests/test_corrected_resubmission.py \
  apps/intake/tests/test_specialized_final_response.py \
  apps/intake/tests/test_my_cases.py -q
node --test static/js/tests/procedure_combobox.test.js
uv run ruff check apps/intake
uv run ruff format --check apps/intake
```

Check de ausência de radios de procedimento nas três superfícies migradas:

```bash
rg -n 'type="radio"[^>]*name="exam_type"' \
  templates/intake/case_detail.html templates/intake/corrected_resubmission.html
```

Resultado esperado: nenhuma ocorrência relativa ao seletor de procedimento (radios não relacionados devem ser classificados no relatório).

## Critérios de aceitação

- [ ] R1–R3: correção/reenvio pesquisáveis, atômicos e com um reprocessamento 4.0.
- [ ] R4: três dimensões/razões e labels são completas.
- [ ] R5: filtros são exatos e preservam polling/busca.
- [ ] R6: somente flags preexistentes continuam operando.

## Handoff

Implementar somente a jornada NIR. Entregar relatório e parar; não tocar filas médica/CHD nem dashboard. Reviewer confere especialmente reprocessamento único, ausência de anexos e igualdade exata nos filtros.
