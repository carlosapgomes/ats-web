# Slice 002 — Resolução declarada-aware com discriminador, payload fora-da-matriz e evento bruto

## Objetivo

Implementar a regra D2 do design em **dois pontos** da reconciliação (branch
de conflito e branch de matriz/`unsupported_procedure_combination`), com o
discriminador `any_set ≠ ∅` que mantém fechada a classe de coincidência sem
evidência atual; normalizar o payload **somente** para conjuntos fora da
matriz (par válido passa inalterado); gravar o union bruto no evento de
auditoria em **todos** os desfechos; e provar com regressão end-to-end que a
correção NIR para a seleção mais completa prossegue o caso até o médico.

Pré-requisito: Slice 001 mergeado (`best_covering_selection` +
`PROCEDURE_PACKAGE_BASES` disponíveis).

## Contexto necessário

- `apps/pipeline/procedure_reconciliation.py` — branch do conflito `:481-491`
  (união `:489`); matriz do DECLARADO `:493-499` (intocada); as três
  precedências `:501-532`; **matriz do DETECTADO `:535-543` (Ponto B,
  `union = any_set` pós-precedência)**; `_partition_procedures` `:63-84`
  (duplicata exata em `:463-466`, ANTES do gate — intocado);
  `_apply_variation_precedence` `:207-228` (intocado — só troca
  `_VARIATION_BASE_TYPES` pelo import de `PROCEDURE_PACKAGE_BASES`);
  `_detection_origin_suffix` `:166-184` (continua recebendo o union bruto);
  `build_v2_review_payload` `:725-763`.
- `apps/pipeline/orchestrator.py` — montagem strong/any/conflicting
  `:458-477`; evento `CASE_PROCEDURES_DETECTED` `:523-536`; chamada do
  payload `:552-562`; guarda de projeção `:484-494`.
- `apps/intake/services.py` — `correct_case_exam_type` `:409-497`.
- `design.md`: D2 (regra + dois pontos + racional do discriminador +
  re-baselines intencionais), D3 (campo novo no result para o evento;
  normalização só fora da matriz com mapeamento de volta), D5, D7 (inventário
  por tipo de mudança).
- ADR-0011 itens 2-3.

## Requisitos verificáveis

- **R1** — Regra de resolução em AMBOS os pontos, exatamente:
  prossegue com `declared` ⟺ `any_set ≠ ∅` E `declared` é seleção canônica
  válida não-vazia E `selection_key(declared) ==
  best_covering_selection(union_bruto_do_ponto)`.
- **R2** — Guardas de coincidência (unchanged): cápsula negada
  (`test_eda_package_pipeline_v4.py:447-478`), cápsula histórica
  (`:479-496`) e reto (`test_rectosigmoidoscopy_pipeline_v4.py:233-247`)
  permanecem `nir_review`/`conflicting_procedure_evidence` (any=∅). Adicionar
  ao teste de cápsula negada um assert explícito de que a ação não muda.
- **R3** — Re-baselines intencionais (mudam desfecho, com justificativa no
  comentário do teste): `:421-441` (histórica+dilatação com pacote declarado
  → proceed; é o pass-2 do caso real) e `:264-277` (item sem ocorrência
  textual com pacote declarado → proceed no Ponto B) em
  `test_eda_package_pipeline_v4.py`, mais o **simétrico reto** em
  `test_rectosigmoidoscopy_pipeline_v4.py`
  (`TestRectosigmoidoscopyReconciliation::test_structured_item_without_
  current_occurrence_does_not_suppress` ~:305 → proceed no Ponto B;
  consequência da regra genérica D2, reconhecida pelo planner durante a
  implementação). Em `:421-441`: assert novo do evento com a união bruta.
- **R4** — Payload: `build_v2_review_payload` normaliza `detected_procedures`
  com `procedure_types_for_selection(best)` SOMENTE quando o conjunto não
  pertence a `ALLOWED_PROCEDURE_SETS` e a cobertura existe; par válido
  `{eda, colonoscopy}` permanece `["eda","colonoscopy"]` (assert novo);
  conjuntos sem cobertura permanecem o union bruto.
- **R5** — Evento: `ProcedureReconciliationResult` carrega a evidência bruta
  (ex.: campo `conflicting_evidence_types`/union) e o orchestrator grava
  `CASE_PROCEDURES_DETECTED` com o union bruto em TODOS os desfechos
  (incluindo a passada de resolução). `reconciliation.detected_procedure_
  types` na passada de resolução carrega o declarado (projeção/LLM2
  seguem dele).
- **R6** — Regressão e2e do beco sem saída (fixture SINTÉTICA, sem dados de
  paciente): Motivo "Endoscopia Digestiva Alta - EDA" atual + dilatação
  apenas não-atual + item estruturado `eda_dilation` ⇒ 1ª passada
  `nir_review` (payload `["eda_dilation"]`, evento bruto `{eda, eda_dilation}`);
  correção NIR para `eda_dilation` ⇒ reprocessamento **prossegue** até o
  fluxo pós-reconciliação, sem novo `nir_review` pelo mesmo conflito, com
  evento bruto na 2ª passada.
- **R7** — `_apply_variation_precedence` troca `_VARIATION_BASE_TYPES` pelo
  import de `PROCEDURE_PACKAGE_BASES` (sem mudança de comportamento; testes
  existentes da precedência verdes).
- **R8** — `strong`/`any` do contraditado seguem falsos; sem item estruturado
  o desfecho não muda; `_detection_origin_suffix` preserva a origem (assert
  no e2e: "Origem da detecção: Motivo da Solicitação").

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/pipeline/procedure_reconciliation.py
  - apps/pipeline/orchestrator.py
  - apps/pipeline/tests/test_eda_package_pipeline_v4.py
  - apps/pipeline/tests/test_rectosigmoidoscopy_pipeline_v4.py
  - apps/pipeline/tests/test_conflict_resolution_proceeds.py   # regressão R6 (novo)
  - apps/cases/tests/test_best_covering_selection.py           # APENAS o teste anti-drift (R7): com o mapa privado substituído pelo import, atualizar o pin de equivalência (decisão de planner pós-slice-001)

allowed_incidental_files:
  - apps/pipeline/tests/test_report_body_clues.py    # apenas se asserts de payload de união COBERTO existirem lá; uniões não-cobertas não mudam (D7)

out_of_scope:
  - label do card (slice 003) e qualquer template/view
  - scope_detection (change separado do Complemento — shelvado)
  - writers/schemas/prompts LLM, FSM, filas, analytics
  - _partition_procedures e reason unsupported para duplicata exata
```

Escalar ao parent se: consumidor do payload fora do levantamento quebrar;
desfecho proceed exigir mudança de FSM; ambiguidade na igualdade; teste de
precedência quebrar com o import de `PROCEDURE_PACKAGE_BASES`.

## Matriz requisito -> arquivo -> teste/check

| Requisito | Arquivo(s) | Teste/check |
| --- | --- | --- |
| R1 | `procedure_reconciliation.py` | `test_conflict_resolution_proceeds.py` (regra nos 2 pontos) |
| R2 | `test_eda_package_pipeline_v4.py`, `test_rectosigmoidoscopy_pipeline_v4.py` | testes existentes verdes + assert novo na cápsula negada |
| R3 | `test_eda_package_pipeline_v4.py` | re-baselines `:421-441`, `:264-277` + asserts de evento bruto |
| R4 | `procedure_reconciliation.py` | asserts de payload (normalizado/par válido/bruto) |
| R5 | `procedure_reconciliation.py`, `orchestrator.py` | asserts de evento bruto (e2e + re-baselines) |
| R6 | `test_conflict_resolution_proceeds.py` | e2e duas passadas |
| R7 | `procedure_reconciliation.py` | suíte de precedência verde |
| R8 | existentes + novo | e2e (origem) + cenários "sem item estruturado" |

## Plano de testes do slice

### RED

1. `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/pipeline/tests/test_conflict_resolution_proceeds.py -q`
   — falha esperada: sem a regra D2, a correção para `eda_dilation` reentra
   em `nir_review` (beco sem saída) e o payload carrega `["eda","eda_dilation"]`.
2. Re-baselines: ajustar `:421-441` e `:264-277` para o desfecho novo ANTES
   de implementar e rodar
   `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/pipeline/tests/test_eda_package_pipeline_v4.py -q`
   — falha esperada exatamente nesses dois testes (ação ainda `nir_review`);
   os demais do arquivo devem permanecer verdes (guardas de coincidência).

### GREEN / verificação local

- `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/pipeline/tests/test_conflict_resolution_proceeds.py apps/pipeline/tests/test_eda_package_pipeline_v4.py apps/pipeline/tests/test_rectosigmoidoscopy_pipeline_v4.py -q` → exit 0.
- `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/pipeline/tests/ -q` → exit 0 (módulo do pipeline).
- `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/intake/tests/test_exam_type_correction.py -q` → exit 0.
- `uv run mypy apps/pipeline` e `uv run ruff check apps/pipeline && uv run ruff format --check <editados>` → exit 0.

Suíte completa NÃO roda neste slice (gate final do change).

## Critérios de aceitação

- [ ] R1-R8 verdes (exit 0 nos comandos acima).
- [ ] Guardas de coincidência provando que o fail-open original permanece fechado.
- [ ] Re-baselines com justificativa e assert de evento bruto.
- [ ] Par válido no payload inalterado; normalização só fora da matriz.
- [ ] Blast radius dentro do esperado (ou escalonamento registrado).

## Contrato de handoff

Worker com contexto fresco: leia `design.md` (D2/D3/D5/D7), ADR-0011 itens
2-3 e este slice antes de editar. TDD RED→GREEN→REFACTOR. Não toque em
`tasks.md`, não commit/push. Reviewer: BEHAVIOR/TESTS/SCOPE/DESIGN; P2
isolado não reabre ciclo.
