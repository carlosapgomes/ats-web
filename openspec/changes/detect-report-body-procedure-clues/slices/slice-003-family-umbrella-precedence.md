# Slice 003 — Precedência de família absorve o guarda-chuva do Motivo

## Objetivo

A reconciliação passa a suprimir `colonoscopy` do conjunto detectado quando a
família Retossigmoidoscopia tem exatamente uma identidade atual e toda
evidência atual de colonoscopia provém do alias guarda-chuva
`endoscopia digestiva baixa` (nunca do termo explícito). Comportamentos
observáveis com o relatório-exemplo real (após Slices 001+002):

- NIR declarou `rectosigmoidoscopy_dilation` → reconciliação devolve
  `proceed` (hoje: loop de `unsupported_procedure_combination` a cada
  reprocessamento);
- NIR declarou `colonoscopy` → `nir_review` com `exam_type_mismatch` claro
  (hoje: `unsupported_procedure_combination` genérico);
- evento/payload registram a regra `family_umbrella_over_colonoscopy` no
  mesmo formato de proveniência das precedências existentes.

Depende dos Slices 001+002 (a família precisa ser detectada com ocorrência
atual pelo corpo do relatório).

## Contexto necessário

- `apps/pipeline/procedure_reconciliation.py` — ler antes:
  - `reconcile_detected_procedures` (~274): ordem atual — validação de
    catálogo/duplicatas → `_apply_specialized_precedence` →
    `_apply_variation_precedence` → validação da matriz
    (`ALLOWED_PROCEDURE_SETS`) → matriz declarado×detectado;
  - `_apply_variation_precedence` (~142) e
    `_current_request_variation_types` (~113): regime de proveniência por
    ocorrência `current_request` (com `linked_base` para termos ambíguos) —
    a nova regra segue o MESMO regime;
  - `ProcedureReconciliationResult` (~203): campos de precedência
    (`precedence_applied`, `selected_specialized_type`, ...,
    `variation_precedence_applied`, `selected_variation_type`,
    `suppressed_base_types`);
  - `serialize_procedure_precedence` (~431): formato enxuto
    `{rule, selected, suppressed}` para evento/payload.
- Ocorrência atual de colonoscopia no relatório-exemplo: o rótulo do Motivo
  ancora o PRIMEIRO termo — excerpt `endoscopia digestiva baixa`
  (guarda-chuva); o token `colonoscopia` do mesmo campo fica `mention`.
  `ProcedureOccurrence.excerpt` é o texto casado pelo pattern (ver
  `_COLONOSCOPY_TERM_PATTERN`, `apps/pipeline/scope_detection.py:534-537`).
- `apps/pipeline/orchestrator.py:507-563`: evento
  `CASE_PROCEDURES_DETECTED` e payload de revisão já consomem
  `serialize_procedure_precedence(reconciliation)` — a nova regra entra
  automaticamente se registrada no mesmo formato.
- `design.md` deste change: decisões D3 e D6.

## Requisitos verificáveis

- **R1** — Nova função `_apply_family_umbrella_precedence(*, any_set,
  occurrences)` em `procedure_reconciliation.py`, chamada após
  `_apply_variation_precedence` e antes da validação da matriz. Condições
  (todas): (a) exatamente uma identidade em
  `{rectosigmoidoscopy, rectosigmoidoscopy_dilation,
  rectosigmoidoscopy_argon}` presente no conjunto; (b) essa identidade tem
  ocorrência `current_request` (com `linked_base` quando variação de termo
  ambíguo — reutilizar o regime de `_current_request_variation_types`);
  (c) `colonoscopy` presente no conjunto, toda ocorrência `current_request`
  de colonoscopia tem excerpt `endoscopia digestiva baixa` E `section ==
  "motivo_da_solicitacao"` (proveniência do Slice 001; NÃO aceita
  guarda-chuva atual citado no corpo, cujo `section` é
  `justificativa_da_transferencia` ou vazio — nesse caso o conflito segue
  fail-closed na matriz). Efeito: remove `colonoscopy` e registra a redução.
- **R2** — `ProcedureReconciliationResult` ganha campos
  `family_umbrella_precedence_applied: bool = False`,
  `selected_family_type: str = ""`, `suppressed_umbrella_types:
  tuple[str, ...] = ()`; `serialize_procedure_precedence` MANTÉM o dict
  único com a regra mais significativa (ordem especializada → variação →
  família — consumidores atuais dependem do formato dict, inclusive casos já
  persistidos em `suggested_action`). NOVO helper separado
  `serialize_procedure_precedence_rules(reconciliation)` devolve a lista com
  TODAS as reduções aplicadas na mesma ordem (`[]` quando nenhuma) — helper
  separado porque o orchestrator atribui o retorno do serializer atual
  direto a `procedure_precedence` (design D3). Testes existentes de metadado
  (dict) continuam válidos; testes novos pinam a lista.
- **R3** — Teste unitário da regra com o conjunto pós-Slice-002 do
  relatório-exemplo (`{colonoscopy, rectosigmoidoscopy_dilation}`, ocorrências
  do fixture): resultado `proceed` quando declarado
  `rectosigmoidoscopy_dilation`; `nir_review`/`exam_type_mismatch` quando
  declarado `colonoscopy`; em ambos o conjunto detectado final é
  `(rectosigmoidoscopy_dilation,)`.
- **R4** — Testes negativos de proveniência: (i) ocorrência atual de
  colonoscopia com excerpt explícito (`colonoscopia`) → regra NÃO aplica;
  (ii) guarda-chuva `endoscopia digestiva baixa` ATUAL FORA do Motivo (ex.:
  citado na Justificativa, `section` ≠ `motivo_da_solicitacao`) → regra NÃO
  aplica — em ambos o conjunto permanece `{colonoscopy,
  rectosigmoidoscopy_*}` e falha fechado na matriz
  (`unsupported_procedure_combination`).
- **R5** — Teste negativo: família presente apenas como `mention` (sem
  ocorrência atual) → regra não aplica (regime de proveniência).
- **R6** — Teste de compatibilidade: reconciliações que não envolvem a família
  Retossigmoidoscopia produzem resultados idênticos aos atuais (snapshot das
  suítes existentes deve permanecer verde sem edição).
- **R6b** — Wiring no orchestrator (`apps/pipeline/orchestrator.py`, três
  destinos): o campo aditivo `procedure_precedence_rules` (lista de R2) é
  gravado (i) no payload do evento `CASE_PROCEDURES_DETECTED` (~511-523),
  (ii) no payload de revisão NIR (~545-550) e (iii) na sugestão final
  `suggested_action` (~723-726) — sempre ao lado do `procedure_precedence`
  dict existente, que mantém o comportamento atual. Teste de contrato cobre
  os três destinos com o cenário-alvo (variação + família aplicadas
  simultaneamente: dict = variação, lista = [variação, família]).
- **R7** — Presenter do doctor (`apps/doctor/presenters.py`,
  `_build_precedence_notice` ~334): branch de copy própria para
  `rule == "family_umbrella_over_colonoscopy"` (ex.: "O relatório
  apresentou também solicitação de {suprimidos}. O sistema priorizou
  {selecionado} porque a Justificativa/Motivo descreve o procedimento da
  família correspondente. Revise o texto original e ajuste a decisão se
  necessário."). Sem o branch, o dict da família cairia na copy de
  especializado (texto equivocado ao médico). Testes de copy estendidos em
  `apps/doctor/tests/test_rectosigmoidoscopy_report.py` (padrão dos
  existentes em `test_eda_package_report.py` R6).

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/pipeline/procedure_reconciliation.py
  - apps/pipeline/orchestrator.py
  - apps/doctor/presenters.py
  - apps/pipeline/tests/test_report_body_clues.py   # estende (integração)
  - apps/pipeline/tests/test_rectosigmoidoscopy_pipeline_v4.py  # apenas se precisar registrar a nova regra em testes existentes de precedência
  - apps/doctor/tests/test_rectosigmoidoscopy_report.py  # copy do presenter (R7)

Nota: 6 arquivos (acima da heurística <= 5). `apps/doctor/presenters.py`
entra porque a regra nova pode aplicar em casos que prosseguem ao médico —
sem o branch de copy (R7) o aviso renderizaria texto de especializado; sem
aviso, o médico perderia a informação da supressão.
`apps/pipeline/orchestrator.py` entra porque o campo aditivo de R2 precisa
de wiring explícito nos três destinos (R6b) — o serializer atual é atribuído
direto a `procedure_precedence` e não propaga a lista sozinho. Sem mudanças
em FSM/policy do doctor; mudanças no orchestrator são estritamente aditivas
(um campo novo por destino).

allowed_incidental_files: []

out_of_scope:
  - alterar _apply_specialized_precedence/_apply_variation_precedence
  - gate de item estruturado (Slice 004); exibição (Slice 005)
  - detecção/scope_detection (Slices 001/002 já entregues)
  - catálogo/matriz ALLOWED_PROCEDURE_SETS
  - EDA-guarda-chuva (nenhum alias análogo existe para EDA; não inventar)
```

Escalar ao parent se: precisar mudar as precedências existentes, o formato do
evento, ou a matriz.

## Matriz requisito -> arquivo -> teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `apps/pipeline/procedure_reconciliation.py` | `test_report_body_clues.py::test_family_umbrella_absorbs_motive_colonoscopy` |
| R2 | `apps/pipeline/procedure_reconciliation.py` | `test_report_body_clues.py::test_family_umbrella_precedence_metadata` |
| R3 | `apps/pipeline/procedure_reconciliation.py` | `test_report_body_clues.py::test_corrected_family_case_proceeds` / `::test_declared_colonoscopy_mismatches_cleanly` |
| R6b | `apps/pipeline/orchestrator.py` | `test_report_body_clues.py::test_precedence_rules_wired_in_three_destinations` |
| R7 | `apps/doctor/presenters.py` | `apps/doctor/tests/test_rectosigmoidoscopy_report.py` (copy da família) |
| R4 | `apps/pipeline/procedure_reconciliation.py` | `test_report_body_clues.py::test_explicit_colonoscopy_current_not_absorbed` / `::test_body_umbrella_current_not_absorbed` |
| R5 | `apps/pipeline/procedure_reconciliation.py` | `test_report_body_clues.py::test_family_mention_does_not_absorb` |
| R6 | — | suítes de regressão do plano |

## Plano de testes do slice

### RED

1. `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/pipeline/tests/test_report_body_clues.py -q`
   — falha esperada: os testes de precedência de família falham porque a
   reconciliação atual devolve `nir_review`/
   `unsupported_procedure_combination` para o conjunto do exemplo (sem a
   redução) e `serialize_procedure_precedence` não conhece a regra;
   `test_body_umbrella_current_not_absorbed` guarda o contrato de
   proveniência (falha se a implementação ignorar o `section`).

### GREEN

2. Implementar R1+R2 em `apps/pipeline/procedure_reconciliation.py`.
3. Repetir o comando do passo 1 — resultado esperado: exit code 0.

### Verificação do slice

4. `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/pipeline/tests/test_rectosigmoidoscopy_pipeline_v4.py apps/pipeline/tests/test_eda_package_pipeline_v4.py apps/pipeline/tests/test_slice_002_pipeline.py apps/pipeline/tests/test_report_body_clues.py apps/doctor/tests/test_rectosigmoidoscopy_report.py apps/doctor/tests/test_eda_package_report.py -q`
   — esperado: exit 0 (precedências, payloads e copies existentes intactos;
   testes de metadado dict continuam válidos — R2 é aditivo).
5. `uv run ruff check apps/pipeline/procedure_reconciliation.py apps/pipeline/orchestrator.py apps/doctor/presenters.py apps/pipeline/tests/test_report_body_clues.py apps/doctor/tests/test_rectosigmoidoscopy_report.py && uv run ruff format --check apps/pipeline/procedure_reconciliation.py apps/pipeline/orchestrator.py apps/doctor/presenters.py apps/pipeline/tests/test_report_body_clues.py apps/doctor/tests/test_rectosigmoidoscopy_report.py`
6. `uv run mypy apps/pipeline apps/doctor`

## Critérios de aceitação

- [ ] R1-R7 provados (R6b wiring, R7 copy do presenter; testes novos
      verdes; suítes de regressão verdes sem
      edição, exceto ajuste previsto em R2 de metadado single-rule).
- [ ] A regra nunca aplica com evidência atual explícita de colonoscopia
      (R4-i), nem com guarda-chuva atual fora do Motivo (R4-ii), nem sem
      ocorrência atual da família (R5).
- [ ] Metadados: dict único preservado (R2) + campo aditivo
      `procedure_precedence_rules` com a lista completa, fiado nos três
      destinos do orchestrator e testado (R6b).
- [ ] Presenter do doctor com copy própria para a regra de família (R7),
      com teste de copy.
- [ ] Nenhum arquivo fora de `expected_files` alterado.
