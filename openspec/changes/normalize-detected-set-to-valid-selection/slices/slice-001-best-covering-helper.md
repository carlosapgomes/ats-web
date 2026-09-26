# Slice 001 — Helper puro `best_covering_selection` com tabela-verdade exaustiva

## Objetivo

Entregar a função pura `best_covering_selection()` em `apps/cases/procedures.py`
— a seleção válida mais completa que cobre um conjunto detectado arbitrário
(ADR-0011 D1) — isolada e exaustivamente testada, sem ainda tocar pipeline/UI.
É slice fundação: a semântica de cobertura é o risco central do change;
isolá-la reduz o estado simultâneo dos slices seguintes (justificativa de
slice preparatório aceita pelo design D8).

## Contexto necessário

- `apps/cases/procedures.py` — catálogo (`PROCEDURE_CATALOG` ~52-126),
  `ALLOWED_PROCEDURE_SETS` (~151), `SELECTION_KEYS` (~157),
  `INVALID_SELECTION_KEY` (~161), `_ordered_supported` (~167-182),
  `selection_key()` total (~491-508), `procedure_types_for_selection()`
  (~513-526). (Nota: NÃO existe `normalize_detected_set` em `procedures.py` —
  relatório de investigação menciona símbolo inexistente; ignorar.)
- O mapa base→variações hoje vive em `apps/pipeline/procedure_reconciliation.py`
  como `_VARIATION_BASE_TYPES` (~106-113); este slice cria a versão
  autoritativa `PROCEDURE_PACKAGE_BASES` em `apps/cases/procedures.py` (o
  slice 002 troca o import no pipeline).
- `design.md` deste change: D1 (regras exatas, incluindo sentinela de vazio =
  `invalid`), D8. ADR-0011 — decisão e alternativas.

## Requisitos verificáveis

- **R1** — `best_covering_selection(procedure_types)` pública, pura, total:
  aceita coleção arbitrária (incl. duplicatas e valores fora do catálogo),
  devolve `SelectionKey`.
- **R2** — Tabela verdade (unit tests parametrizados cobrindo TODOS os casos):
  - singleton exato → própria chave (todas as 10 identidades);
  - `{eda, colonoscopy}` → `eda_colonoscopy`;
  - base + seu pacote → pacote, para TODOS os pares: `{eda, eda_gastrostomy}`,
    `{eda, eda_capsule}`, `{eda, eda_dilation}`,
    `{rectosigmoidoscopy, rectosigmoidoscopy_dilation}`,
    `{rectosigmoidoscopy, rectosigmoidoscopy_argon}`;
  - conjunto vazio → `INVALID_SELECTION_KEY` (divergência deliberada de
    `selection_key(()) == ""` — documentada na docstring);
  - duas variações da mesma base (`{eda_capsule, eda_dilation}`,
    `{eda, eda_capsule, eda_dilation}`) → `invalid`;
  - variação + colonoscopia → `invalid`;
  - dois especializados (`{echoendoscopy, cpre}`) → `invalid`;
  - especializado + convencionais (`{eda, echoendoscopy}`) → `invalid`
    (função é pura: precedências de detecção acontecem ANTES, fora do
    helper — documentar na docstring);
  - duplicatas exatas (`["eda","eda"]`) → tratadas como `{"eda"}` → `eda`;
  - valor fora do catálogo sozinho (`"unknown"`) ou misto (`{"eda","unknown"}`)
    → `invalid` (desconhecido não é filtrado para fabricar validade).
- **R2b** — `PROCEDURE_PACKAGE_BASES` exportada de `apps/cases/procedures.py`
  com conteúdo equivalente ao `_VARIATION_BASE_TYPES` do pipeline (assert de
  equivalência no teste — guarda anti-drift; a troca de import no pipeline é
  do slice 002).
- **R3** — Docstring documenta: pureza, ordem de regras, relação com
  `selection_key` (normalização de exibição/decisão; evidência bruta fica na
  auditoria) e a fronteira com precedências de detecção.
- **R4** — mypy estrito ok; sem imports de `apps.pipeline` no **código de
  produção** de `apps/cases` (import em ARQUIVO DE TESTE é aceitável para o
  pin anti-drift de R2b — precedente: testes de intake/doctor importam
  pipeline; direção cases←pipeline não cria ciclo).

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/cases/procedures.py
  - apps/cases/tests/test_best_covering_selection.py   # ajustar ao layout real de testes do app

allowed_incidental_files: []

out_of_scope:
  - qualquer arquivo de apps/pipeline ou apps/intake
  - mudanças em selection_key/ALLOWED_PROCEDURE_SETS existentes
  - normalização "e"/"+" de labels (slice 003)
```

Escalar ao parent se: a tabela verdade revelar ambiguidade não decidível por
D1 (ex.: dois pacotes cobrindo o mesmo conjunto), ou se precisar importar de
`apps.pipeline`.

## Matriz requisito -> arquivo -> teste/check

| Requisito | Arquivo(s) | Teste/check |
| --- | --- | --- |
| R1/R2 | `apps/cases/procedures.py`, `apps/cases/tests/test_best_covering_selection.py` | pytest parametrizado (todos os casos de R2) |
| R3 | `apps/cases/procedures.py` | docstring presente (inspeção/review) |
| R4 | idem | `uv run mypy apps/cases` |

## Plano de testes do slice

### RED

- comando: `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/cases/tests/test_best_covering_selection.py -q`
- falha esperada: `ImportError`/`AttributeError` — a função não existe.

### GREEN / verificação local

- O mesmo comando → exit 0 (todos os casos parametrizados passando).
- `uv run mypy apps/cases` → exit 0.
- `uv run ruff check apps/cases && uv run ruff format --check apps/cases/procedures.py apps/cases/tests/test_best_covering_selection.py` → exit 0.
- Regressão próxima: `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/cases/tests/ -q` → exit 0.

Suíte completa NÃO roda neste slice (gate final do change).

## Critérios de aceitação

- [ ] R1-R4 verdes com os comandos acima (exit 0).
- [ ] Tabela verdade de R2 coberta por testes (nenhum caso listado sem assert).
- [ ] Zero imports de `apps.pipeline` no código de produção de `apps/cases`.
- [ ] Blast radius dentro do `expected_files`.

## Contrato de handoff

Worker com contexto fresco: leia `design.md` (D1/D8) e a ADR-0011 antes de
editar. TDD RED→GREEN→REFACTOR. Não toque em `tasks.md`, não commit/push.
Reviewer: BEHAVIOR/TESTS/SCOPE/DESIGN; P2 isolado não reabre ciclo.
