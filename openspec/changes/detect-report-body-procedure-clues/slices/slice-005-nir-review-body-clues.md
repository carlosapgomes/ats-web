# Slice 005 — Pistas do corpo na revisão NIR (payload 2.1 + card de correção)

## Objetivo

O payload de revisão NIR passa a carregar `detected_body_clues` (procedimento,
qualificação traduzida, seção de origem e excerpt limitado das ocorrências
detectadas no corpo do relatório), e o card de correção de tipo exibe essas
pistas ao NIR **no momento da seleção do novo conjunto** — fechando o ciclo:
detecção no corpo (Slices 001/002) → revisão fundamentada → correção →
reprocessamento que prossegue (Slice 003).

Este é o slice que materializa o pedido do usuário: no intake a seleção e o
upload são simultâneos (não há momento de pré-visualização); o ponto útil é a
revisão NIR.

## Contexto necessário

- `apps/pipeline/procedure_reconciliation.py` — ler antes:
  - `build_v2_review_payload` (~437): monta o payload enxuto (schema 2.0,
    conjuntos + reason + `evidence_spans` do LLM1 via
    `_project_review_evidence_spans`, cap 5);
  - `_project_review_evidence_spans` (~418): padrão de projeção com limites
    explícitos.
- `apps/pipeline/orchestrator.py:538-563` — gate de revisão NIR: chama
  `build_v2_review_payload(..., evidence_spans=_collect_v4_evidence_spans(
  result1.structured_data))`, mescla `procedure_precedence`, grava
  `case.suggested_action` e evento `EDA_SCOPE_GATED_MANUAL_REVIEW`.
- `ProcedureOccurrence` (`apps/pipeline/scope_detection.py:1248`): campos
  `procedure_type`, `qualification` (`current_request|historical|negated|
  mention`), `excerpt`, `linked_base`, `section` (Slice 001).
- `apps/cases/models.py` — `ProcedureType` é TextChoices: label pt-BR via
  `ProcedureType(valor).label`.
- `apps/intake/views.py:901-923` — `correction_form_context` montado quando
  `is_exam_type_correction_eligible(case)`; lê `suggested` de
  `case.suggested_action`.
- `templates/intake/case_detail.html:364+` — card "Correção de Tipo de
  Exame": hoje exibe declarado/detectado/motivo + combobox canônico.
- AGENTS §8: vocabulário CSS novo exigiria `app.css` no blast radius + guarda
  — este slice usa SOMENTE classes Bootstrap existentes (`list-group`,
  `list-group-item`, `badge text-bg-*`, `blockquote`/`blockquote-footer`,
  `small`) para não criar vocabulário novo.
- `apps/intake/tests/test_exam_type_correction.py` e
  `apps/pipeline/tests/test_slice_002_pipeline.py` — padrões de teste do
  card e do payload.
- `design.md` deste change: decisão D5.

## Requisitos verificáveis

- **R1** — Novo helper puro `project_body_clues(occurrences)` em
  `procedure_reconciliation.py`: devolve
  `[{procedure_type, procedure_label, qualification, qualification_label,
  section, excerpt}]` ordenado `current_request` primeiro (ordem restante:
  canônica do tipo), cap 8 entradas, `excerpt` truncado a 200 chars;
  qualificações traduzidas (`current_request`→`Solicitação atual`,
  `mention`→`Menção`, `historical`→`Histórico`, `negated`→`Negado`).
  **Exclui ocorrências com `section="motivo_da_solicitacao"`** (marcação do
  Slice 001: a evidência do Motivo não é pista do corpo; declarado/detectado
  já estão no card). Sem ocorrências → lista vazia.
- **R2** — `build_v2_review_payload` ganha parâmetro `body_clues: Any = None`
  e inclui `"detected_body_clues": [...]` (projetado com cap/limites);
  `schema_version` sobe para `"2.1"`. Campos existentes permanecem
  (compatibilidade aditiva).
- **R3** — `apps/pipeline/orchestrator.py` passa
  `body_clues=project_body_clues(occurrences)` no gate de revisão NIR
  (occurrences já computadas no passo 2 do pipeline).
- **R4** — `apps/intake/views.py` inclui no `correction_form_context` as
  pistas: `"body_clues"` lido de
  `suggested.get("detected_body_clues", [])` (payload sem o campo → lista
  vazia; card legado inalterado).
- **R5** — `templates/intake/case_detail.html` renderiza, dentro do card de
  correção e APENAS quando `correction_form_context.body_clues` não vazio,
  a seção "Pistas detectadas no corpo do relatório": cada pista com
  `procedure_label`, badge da `qualification_label`, seção (quando presente)
  e `excerpt` em citação visual — somente classes Bootstrap existentes, sem
  CSS/JS novos.
- **R6** — Teste do payload (pipeline): revisão gerada com ocorrências do
  relatório-exemplo contém `schema_version == "2.1"` e
  `detected_body_clues` com a pista de `rectosigmoidoscopy_dilation`
  (qualificação `current_request`, seção
  `justificativa_da_transferencia`, excerpt do texto).
- **R7** — Teste da view (intake): caso em manual review elegível com
  `detected_body_clues` no `suggested_action` → resposta do detalhe contém o
  título da seção, o label do procedimento e o excerpt; payload sem o campo
  → resposta NÃO contém o título (compatibilidade); pista com `section ==
  "motivo_da_solicitacao"` nunca aparece na projeção (filtro de R1).
- **R8** — Contrato inalterado: POST do combobox (`exam_type`), chaves de
  seleção, elegibilidade e fluxo de correção/reprocessamento seguem
  idênticos (suítes existentes verdes sem edição).
- **R9** — Teste ponta a ponta das funções puras encadeadas (sem LLM/banco):
  texto-exemplo real → `detect_procedure_occurrences` →
  `detect_requested_procedures_v4` → `reconcile_detected_procedures`
  (declarado `colonoscopy` → `nir_review`/`exam_type_mismatch`;
  declarado `rectosigmoidoscopy_dilation` → `proceed`) →
  `project_body_clues` + `build_v2_review_payload` contém a pista de
  `rectosigmoidoscopy_dilation` da Justificativa e NÃO contém pista do
  Motivo.

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/pipeline/procedure_reconciliation.py
  - apps/pipeline/orchestrator.py
  - apps/intake/views.py
  - templates/intake/case_detail.html
  - apps/pipeline/tests/test_report_body_clues.py        # estende (payload)
  - apps/intake/tests/test_exam_type_correction.py       # estende (view)

allowed_incidental_files: []

justificativa_blast_radius: 6 arquivos (acima da heurística <= 5) — o card de
correção é a única superfície onde as pistas agregam valor (upload e seleção
são simultâneos por desenho do produto); a cadeia payload (pipeline) →
contexto (view) → render (template) não é decomponível sem slice horizontal
sem valor observável. Testes novos ficam em 2 arquivos já usados pelo change.

out_of_scope:
  - qualquer mudança em CSS/JS (sem vocabulário novo — AGENTS §8)
  - alterar POST/validação/elegibilidade do card
  - exibir pistas em outras superfícies (filas, doctor, my_cases)
  - schema LLM/prompt
  - persistência nova (as pistas vivem no suggested_action, como o payload atual)
```

Escalar ao parent se: precisar de CSS novo, mudar o POST/chaves, tocar
outras superfícies ou persistir pistas fora de `suggested_action`.

## Matriz requisito -> arquivo -> teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `apps/pipeline/procedure_reconciliation.py` | `test_report_body_clues.py::test_project_body_clues_*` |
| R2 | `apps/pipeline/procedure_reconciliation.py` | `test_report_body_clues.py::test_review_payload_2_1_carries_clues` |
| R3 | `apps/pipeline/orchestrator.py` | `test_report_body_clues.py::test_orchestrator_review_payload_has_clues` |
| R4 | `apps/intake/views.py` | `apps/intake/tests/test_exam_type_correction.py::test_correction_card_shows_body_clues` |
| R5 | `templates/intake/case_detail.html` | idem R4 (assert de título/label/excerpt na resposta) |
| R6 | — | `test_review_payload_2_1_carries_clues` |
| R7 | — | `::test_correction_card_without_clues_unchanged` |
| R8 | — | suítes de regressão do plano |
| R9 | — | `test_report_body_clues.py::test_end_to_end_example_flow` |

## Plano de testes do slice

### RED

1. `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/pipeline/tests/test_report_body_clues.py -q`
   — falha esperada: `test_project_body_clues_*` falha com ImportError/AttributeError
   (helper não existe); `test_review_payload_2_1_carries_clues` falha porque o
   payload vem `schema_version == "2.0"` sem `detected_body_clues`.
2. `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/intake/tests/test_exam_type_correction.py -q`
   — falha esperada: `test_correction_card_shows_body_clues` falha porque a
   resposta não contém o título da seção de pistas.

### GREEN

3. Implementar R1-R5 (ordem sugerida: R1 → R2 → R3 → R4 → R5).
4. Repetir os comandos dos passos 1-2 — resultado esperado: exit code 0.

### Verificação do slice

5. `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/pipeline/tests/test_report_body_clues.py apps/pipeline/tests/test_slice_002_pipeline.py apps/pipeline/tests/test_rectosigmoidoscopy_pipeline_v4.py apps/intake/tests/test_exam_type_correction.py apps/intake/tests/test_slice_005_nir_correction_and_response.py -q`
   — esperado: exit 0 (payloads e card existentes intactos).
6. `uv run ruff check apps/pipeline/procedure_reconciliation.py apps/pipeline/orchestrator.py apps/intake/views.py apps/pipeline/tests/test_report_body_clues.py apps/intake/tests/test_exam_type_correction.py && uv run ruff format --check apps/pipeline/procedure_reconciliation.py apps/pipeline/orchestrator.py apps/intake/views.py apps/pipeline/tests/test_report_body_clues.py apps/intake/tests/test_exam_type_correction.py`
7. `uv run mypy apps/pipeline apps/intake`
8. `grep -c "class=\|style=" templates/intake/case_detail.html` antes/depois
   — sanity check opcional de que nenhuma classe nova foi introduzida (R5);
   em caso de dúvida, diff do template limitado ao bloco do card.

## Critérios de aceitação

- [ ] R1-R9 provados (testes novos verdes; suítes de regressão verdes).
- [ ] Pistas visíveis no card de correção com label/qualificação/seção/excerpt
      (R5/R7); caso legado sem pistas renderiza inalterado (R7).
- [ ] Sem CSS/JS novos; sem mudança de contrato POST (R8).
- [ ] Nenhum arquivo fora de `expected_files` alterado.
