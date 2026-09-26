# Slice 001 — Seção `Justificativa da Transferência` como contexto de solicitação

## Objetivo

O detector determinístico passa a qualificar como `current_request` ocorrências
de identidades do catálogo que caem como mera menção dentro da seção
`Justificativa da Transferência:` do relatório de regulação, e a marcar nessas
ocorrências o rótulo da seção (`section`). Negações e históricos dentro da
seção permanecem intocados. Comportamento observável com o
relatório-exemplo real: a ocorrência `retossigmoidoscopia` (hoje `mention`)
passa a `current_request`.

## Contexto necessário

- `apps/pipeline/scope_detection.py` — ler antes:
  - `_normalize_scope_keyword_text` (sem acento, minúsculo, espaços
    colapsados — todas as funções do slice operam sobre esse texto);
  - `detect_procedure_occurrences` (~1330): coleta ocorrências por cláusula
    com `_PROCEDURE_OCCURRENCE_PATTERNS`, classifica via
    `_classify_occurrence`, e SÓ DEPOIS faz o passe de vínculo
    (`current_types_by_clause` → `linked_base` → upgrade da variação);
  - `ProcedureOccurrence` (~1248): dataclass frozen com
    `procedure_type, qualification, excerpt, start, end, linked_base`;
  - `_QUALIFICATION_MENTION` / `_QUALIFICATION_CURRENT` (constantes);
  - `_CLAUSE_BOUNDARY_PATTERN` (~208): `[.;!?]` + `\n` delimitam cláusulas —
    por isso um rótulo seguido de oração intermediária não ancora o
    procedimento (motivo deste slice).
- Layout real do relatório (fonte do fixture): página com
  `Justificativa da Transferência:` seguida do texto do médico; a seção
  termina no cabeçalho da página seguinte (`RELATÓRIO DE OCORRÊNCIAS`) ou em
  rótulos operacionais como `Informado por`, `Motivo da Solicitação`,
  `Complemento da Solicitação`, `Resumo Clínico`, `Hipótese do Diagnóstico`,
  `Encaminhamento`, `Mot. Solicit.`, `Unid. Origem`.
- `apps/pipeline/tests/test_rectosigmoidoscopy_pipeline_v4.py` — padrão dos
  testes existentes do detector v4 (fixtures sintéticas de uma linha).
- `design.md` deste change: decisões D1 e D6.
- Regra do projeto: teste novo falha primeiro (RED→GREEN→REFACTOR); sem
  alteração de comportamento fora do especificado.

## Requisitos verificáveis

- **R1** — Nova função pura em `scope_detection.py` (ex.:
  `_justificativa_section_spans(normalized_text) -> tuple[tuple[int, int], ...]`)
  que devolve os spans da seção no texto normalizado: início no rótulo
  `justificativa da transferencia:` e término no primeiro terminador seguinte
  (cabeçalho de página `relatorio de ocorrencias` OU um dos rótulos
  operacionais conhecidos listados no design D1). Sem rótulo → tupla vazia.
  **Seção sem terminador → span até o fim do texto** (decisão D1, com teste).
- **R1b** — Correção habilitante (bug pré-existente): a iteração de cláusulas
  em `detect_procedure_occurrences` passa a usar offsets absolutos
  (cursor/`finditer` em vez de `normalized_text.find(clause)`, hoje
  `scope_detection.py:1346`) e `current_types_by_clause` passa a ser keying
  por INTERVALO da cláusula (hoje por texto, `:1377`). Teste de
  caracterização: cláusula idêntica repetida em duas seções/páginas produz
  ocorrências com offsets distintos e sem vazamento de contexto entre elas.
  *Justificativa: pré-requisito para membership de seção correto em
  relatórios reais, que repetem boilerplate entre páginas; sem isso os spans
  de R2 classificam ocorrências na seção errada.*
- **R2** — Em `detect_procedure_occurrences`, ocorrências com `start` dentro
  de um span da seção e qualificação `mention` passam a `current_request`
  ANTES do passe de vínculo (para que a base promovida estenda o vínculo à
  variação na mesma cláusula — o vínculo em si é o Slice 002, não implementar
  aqui).
- **R3** — Ocorrências `historical`/`negated` dentro da seção NÃO são
  promovidas; ocorrências fora da seção sem contexto de pedido continuam
  `mention`.
- **R4** — `ProcedureOccurrence` ganha campo `section: str = ""` (default,
  backward compatível); ocorrências com `start` dentro do span recebem
  `section="justificativa_da_transferencia"` (qualificação promovida ou não).
  O MESMO mecanismo marca o campo `Motivo da Solicitação:` (início no rótulo,
  término no primeiro terminador) com `section="motivo_da_solicitacao"` —
  proveniência exigida pela regra D3/slice-003 e pelo filtro do slice-005.
  Como a dataclass é frozen, usar o mesmo estilo de
  `replace_occurrence_link` (constrói nova instância).
- **R5** — Testes de caracterização com fixture multi-seção fiel ao layout
  real (Motivo com `Endoscopia Digestiva Baixa - Colonoscopia` terminado por
  `Unid.`; Justificativa com oração intermediária terminada em `.` antes do
  nome do procedimento; terminador de página `RELATÓRIO DE OCORRÊNCIAS`),
  cobrindo: promoção da base da família, histórico/negação dentro da seção
  não promovidos, ocorrência fora da seção continua `mention`,
  `section` preenchido apenas dentro do span (inclusive
  `motivo_da_solicitacao` no campo Motivo), e cláusula repetida entre duas
  seções com offsets distintos (R1b).
- **R5b** — Testes de direção de falha (design D6), no escopo DESTE slice:
  Justificativa citando família DIVERGENTE do declarado → reconciliação
  `nir_review` (neste slice o conjunto misto
  `{colonoscopy, rectosigmoidoscopy}` falha fechado na matriz — resultado
  já observável e seguro). O desfecho `proceed` para família COINCIDENTE
  com o declarado depende da precedência do Slice 003 e é provado lá
  (`test_corrected_family_case_proceeds`); aqui, apenas a detecção da
  coincidência é afirmada (ocorrência `current_request` da família).
- **R6** — Regressão preservada: suíte existente
  `test_rectosigmoidoscopy_pipeline_v4.py` e `test_scope_detection.py`
  continuam verdes sem edição (nenhum fixture existente usa
  `Justificativa da Transferência`).

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/pipeline/scope_detection.py
  - apps/pipeline/tests/test_report_body_clues.py   # novo

allowed_incidental_files: []

out_of_scope:
  - conectores de vínculo além de com/e (Slice 002)
  - reconciliação/precedências (Slice 003)
  - gate de item estruturado (Slice 004)
  - exibição/UI (Slice 005)
  - qualquer mudança em prompts, schemas LLM, catálogo ou matriz
  - import de apps.intake (terminadores ficam locais em scope_detection)
```

Escalar ao parent (não ampliar o slice) se: precisar mudar
`_classify_occurrence` ou os padrões globais de request/negação/histórico;
tocar reconciliação; ou se os fixtures existentes quebrarem por razão não
prevista em R6.

## Matriz requisito -> arquivo -> teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `apps/pipeline/scope_detection.py` | `test_report_body_clues.py::test_justificativa_span_*` |
| R1b | `apps/pipeline/scope_detection.py` | `test_report_body_clues.py::test_repeated_clause_offsets_*` |
| R2 | `apps/pipeline/scope_detection.py` | `test_report_body_clues.py::test_mention_inside_justificativa_becomes_current` |
| R3 | `apps/pipeline/scope_detection.py` | `test_report_body_clues.py::test_historical_and_negated_inside_section_not_promoted` / `::test_outside_section_stays_mention` |
| R4 | `apps/pipeline/scope_detection.py` | `test_report_body_clues.py::test_occurrence_carries_section_label` |
| R5 | `apps/pipeline/tests/test_report_body_clues.py` | o próprio arquivo |
| R6 | — | comandos de regressão do plano abaixo |

## Plano de testes do slice

### RED (escreva os testes primeiro; confirme a falha pelo motivo esperado)

1. `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/pipeline/tests/test_report_body_clues.py -q`
   — falha esperada: `test_mention_inside_justificativa_becomes_current`
   falha porque a ocorrência de `retossigmoidoscopia` vem `mention`
   (comportamento atual); `test_occurrence_carries_section_label` falha
   porque `ProcedureOccurrence` não tem `section` (AttributeError);
   `test_repeated_clause_offsets_*` falha porque a segunda ocorrência da
   cláusula repetida vem com offset da primeira (comportamento atual de
   `find(clause)`).

### GREEN

2. Implementar R1, R1b, R2-R4 em `apps/pipeline/scope_detection.py` (spans
   de seção + correção de offsets + promoção antes do passe de vínculo +
   campo `section` com marcação de Motivo).
3. Repetir o comando do passo 1 — resultado esperado: exit code 0.

### Verificação do slice (regressão local, não suíte completa)

4. `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/pipeline/tests/test_rectosigmoidoscopy_pipeline_v4.py apps/pipeline/tests/test_scope_detection.py apps/pipeline/tests/test_eda_package_pipeline_v4.py -q`
   — esperado: exit 0 (R6).
5. `uv run ruff check apps/pipeline/scope_detection.py apps/pipeline/tests/test_report_body_clues.py && uv run ruff format --check apps/pipeline/scope_detection.py apps/pipeline/tests/test_report_body_clues.py`
6. `uv run mypy apps/pipeline`

## Critérios de aceitação

- [ ] R1-R5b provados pelos testes novos (verde).
- [ ] R6 provado pelas suítes de regressão (verde, sem edição).
- [ ] Nenhum arquivo fora de `expected_files` alterado.
- [ ] Promoção só ocorre dentro do span e só sobre `mention`.
