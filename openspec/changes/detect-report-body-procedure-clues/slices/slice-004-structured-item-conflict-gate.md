# Slice 004 — Gate de conflito do item estruturado (fim da falha aberta)

## Objetivo

Quando o LLM1 reporta um procedimento estruturado (com evidence span) cujo
termo tem ocorrência **não-atual** no texto (menção/histórico/negação), a
detecção passa a sinalizar conflito e a reconciliação devolve
`nir_review` com reason `conflicting_procedure_evidence` — mesmo quando o
conjunto restante coincide com o declarado (hoje o caso **prossegue
silenciosamente** e a detecção correta do LLM é descartada). O item
contraditado continua NÃO virando detecção (`strong`/`any` falsos); ele
apenas deixa de ser invisível. O novo reason code habilita o card de
correção de tipo no intake.

Depende conceitualmente dos Slices 001-003 (que resolvem o cenário principal
de forma determinística); este slice é a rede de segurança para redações que
os conectores/seção não cobrirem mas o LLM1 capturar.

## Contexto necessário

- `apps/pipeline/scope_detection.py` — ler antes:
  - `detect_requested_procedures_v4` (~1527) e o docstring do gate (~1540):
    `present = procedure_type in current_occurrences or (procedure_type in
    structured and procedure_type not in occurrence_types)` — a segunda parte
    bloqueia o item quando existe QUALQUER ocorrência do termo;
  - `_extract_v4_structured_candidates` (~1505): tipos estruturados
    candidatos (`_V4_STRUCTURED_CANDIDATE_TYPES` = 5 variações + base
    retossigmoidoscopy);
  - `detect_requested_procedures_v3` (~846): origem dos demais tipos do dict.
- `apps/pipeline/procedure_reconciliation.py` — ler antes:
  - `reconcile_detected_procedures` (~274) — assinatura keyword-only com
    `declared`, `strong`, `any_evidence`, `occurrences`;
  - `_nir_review` (~251) e a validação R3 (catálogo/duplicatas antes de
    tudo).
- `apps/pipeline/orchestrator.py:455-471` — construção de `strong`/`any` a
  partir de `_DETECTABLE_PROCEDURE_TYPES` e chamada da reconciliação;
  `:473-505` — projeção `set_detected_procedures` (já protegida: só projeta
  conjunto vazio ou dentro de `ALLOWED_PROCEDURE_SETS`).
- `apps/intake/services.py:285-292` — `EXAM_TYPE_CORRECTION_ELIGIBLE_REASON_CODES`.
- Teste existente que codifica o comportamento atual e PRECISA ser ajustado
  (não deletado): `test_non_current_occurrence_overrides_the_structured_item`
  em `apps/pipeline/tests/test_rectosigmoidoscopy_pipeline_v4.py:200+`.
- `design.md` deste change: decisão D4 (semântica preservada: item
  contraditado não vira detecção) e D6.

## Requisitos verificáveis

- **R1** — `detect_requested_procedures_v4` computa, para cada tipo do dict
  de detecção, a chave `conflicting`: `True` somente quando o tipo está no
  payload estruturado do LLM1, tem ocorrência no texto e NÃO tem ocorrência
  `current_request`. Demais tipos: `conflicting=False`.
- **R2** — `reconcile_detected_procedures` ganha parâmetro default
  `conflicting: Any = ()`; após a validação de catálogo/duplicatas (R3) e
  ANTES de qualquer caminho `proceed`/precedência, se houver tipo conhecido
  em `conflicting`, retorna `nir_review(reason_code=
  "conflicting_procedure_evidence", reason_text=..., detected=_ordered(
  any_set | conflicting))`.
- **R3** — `apps/pipeline/orchestrator.py` extrai `conflicting` do dict de
  detecção (`.get("conflicting")` — chaves de v3 não têm o campo) e repassa à
  reconciliação.
- **R4** — `EXAM_TYPE_CORRECTION_ELIGIBLE_REASON_CODES` ganha
  `"conflicting_procedure_evidence"` (card de correção habilitado).
- **R5** — Teste do cenário da falha aberta: declarado `colonoscopy` +
  Motivo colonoscopia atual + LLM1 reporta `rectosigmoidoscopy_dilation` com
  evidence span + corpo com apenas menção do termo → reconciliação devolve
  `nir_review`/`conflicting_procedure_evidence` com
  `detected_procedure_types` contendo `rectosigmoidoscopy_dilation`; e o dict
  de detecção mantém `strong=False`/`any=False` para o tipo (R1 do
  comportamento preservado).
- **R6** — Teste de não-regressão: sem item estruturado, menção isolada
  continua sem criar identidade nem conflito (desfecho inalterado).
- **R7** — `test_non_current_occurrence_overrides_the_structured_item`
  atualizado para o novo contrato (presença do sinal `conflicting` +
  desfecho `nir_review`; manter os asserts de `strong`/`any` falsos).

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/pipeline/scope_detection.py
  - apps/pipeline/procedure_reconciliation.py
  - apps/pipeline/orchestrator.py
  - apps/intake/services.py
  - apps/pipeline/tests/test_report_body_clues.py        # estende
  - apps/pipeline/tests/test_rectosigmoidoscopy_pipeline_v4.py  # ajuste R7

allowed_incidental_files: []

out_of_scope:
  - transformar item contraditado em detecção (strong/any) — propositadamente não
  - prompts/schemas LLM
  - exibição do conflito na UI (o payload existente já carrega reason/detected;
    pistas visuais são o Slice 005)
  - alterar a projeção set_detected_procedures (guarda existente já cobre
    conjuntos fora da matriz)
```

Nota: 6 arquivos (limite da heurística <= 5) — justificativa: o reason code
elegível (intake) é o que torna a revisão acionável pelo NIR; sem ele o
gate criaria revisões sem card de correção. Registrar no relatório do slice.

Escalar ao parent se: precisar tocar FSM, eventos além do payload de revisão
existente, ou a projeção de detecção.

## Matriz requisito -> arquivo -> teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `apps/pipeline/scope_detection.py` | `test_report_body_clues.py::test_structured_item_vs_mention_flags_conflict` |
| R2 | `apps/pipeline/procedure_reconciliation.py` | `test_report_body_clues.py::test_conflicting_evidence_forces_nir_review` |
| R3 | `apps/pipeline/orchestrator.py` | `test_report_body_clues.py::test_orchestrator_passes_conflicting` (ou teste de contrato existente estendido) |
| R4 | `apps/intake/services.py` | `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/intake/tests/test_exam_type_correction.py -q` + teste novo de elegibilidade |
| R5 | — | `test_report_body_clues.py::test_fail_open_scenario_now_fail_closed` |
| R6 | — | `test_report_body_clues.py::test_mention_alone_still_inert` |
| R7 | `apps/pipeline/tests/test_rectosigmoidoscopy_pipeline_v4.py` | teste ajustado passa |

## Plano de testes do slice

### RED

1. `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/pipeline/tests/test_report_body_clues.py -q`
   — falha esperada: `test_structured_item_vs_mention_flags_conflict` falha
   porque o dict de detecção não tem `conflicting`;
   `test_conflicting_evidence_forces_nir_review`/
   `test_fail_open_scenario_now_fail_closed` falham porque a reconciliação
   devolve `proceed` (declared == detected-by-Motivo).
2. Teste novo de elegibilidade (intake) falha porque o reason code não está
   no frozenset.

### GREEN

3. Implementar R1-R4 (ordem sugerida: R1 → R2 → R3 → R4).
4. Repetir os comandos dos passos 1-2 — resultado esperado: exit code 0.
5. Ajustar `test_non_current_occurrence_overrides_the_structured_item` (R7).

### Verificação do slice

6. `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/pipeline/tests/test_rectosigmoidoscopy_pipeline_v4.py apps/pipeline/tests/test_eda_package_pipeline_v4.py apps/pipeline/tests/test_orchestrator.py apps/pipeline/tests/test_report_body_clues.py apps/intake/tests/test_exam_type_correction.py -q`
   — esperado: exit 0.
7. `uv run ruff check apps/pipeline/scope_detection.py apps/pipeline/procedure_reconciliation.py apps/pipeline/orchestrator.py apps/intake/services.py apps/pipeline/tests/test_report_body_clues.py apps/pipeline/tests/test_rectosigmoidoscopy_pipeline_v4.py && uv run ruff format --check apps/pipeline/scope_detection.py apps/pipeline/procedure_reconciliation.py apps/pipeline/orchestrator.py apps/intake/services.py apps/pipeline/tests/test_report_body_clues.py apps/pipeline/tests/test_rectosigmoidoscopy_pipeline_v4.py`
8. `uv run mypy apps/pipeline apps/intake`

## Critérios de aceitação

- [ ] R1-R7 provados (testes novos verdes; R7 ajustado e verde).
- [ ] Cenário fail-open do relatório-exemplo (com LLM reportando o tipo)
      agora termina em `nir_review` (R5).
- [ ] Item contraditado continua sem virar detecção (R1/R5 asserts de
      strong/any falsos).
- [ ] Nenhum arquivo fora de `expected_files` alterado.
