# Slice 002 — Conectores instrumentais (`via`/`por`/`através de`) no vínculo variação↔base

## Objetivo

O vínculo local que qualifica termos ambíguos (`dilatacao`, `argonio`) como
variação atual da base passa a aceitar, além de `com`/`e`, os conectores
`via`, `por`, `através de` e `com uso de`. Comportamento observável com o
relatório-exemplo real (após o Slice 001): a ocorrência de `dilatacao` em
"DILATAÇÃO DE ANASTOMOSE COLORRETAL VIA RETOSSIGMOIDOSCOPIA FLEXIVEL" passa a
`current_request` com `linked_base=True`, produzindo
`rectosigmoidoscopy_dilation` no conjunto detectado.

Depende do Slice 001 (a base `retossigmoidoscopia` precisa estar
`current_request` pelo contexto de seção para o vínculo estender a variação).

## Contexto necessário

- `apps/pipeline/scope_detection.py` — ler antes:
  - `_LINK_SEPARATOR_PATTERN = re.compile(r"\b(?:com|e)\b")` (~1244): único
    separador aceito hoje entre ocorrência da base e termo da variação;
  - `_linked_base_in_clause` (~1309): testa o separador no texto ENTRE as
    duas ocorrências, nos dois sentidos (base antes ou depois da variação) —
    não precisa mudar, só o pattern do separador;
  - passe de vínculo em `detect_procedure_occurrences` (~1380-1405): variação
    `mention` com base `current_request` na mesma cláusula + separador →
    variação vira `current_request`;
  - `_qualify_variation_occurrences` (~1419): demotion para `mention` de
    termo ambíguo sem `linked_base` — intocada neste slice;
  - `_DILATION_BLOCKED_SITE_TERMS` (~1207): `coledoco`/`via biliar` —
    permanece bloqueando dilatação como achado anatômico.
- Texto normalizado: sem acentos — `através de` vira `atraves de`;
  escrever os padrões sobre o texto normalizado.
- `apps/pipeline/tests/test_rectosigmoidoscopy_pipeline_v4.py` — atenção a
  `test_dilation_without_local_link_is_not_a_variation` (fixture
  "Paciente encaminhado para dilatação de anastomose colorretal." sem
  conector): deve continuar passando.
- `design.md` deste change: decisões D2 e D6.

## Requisitos verificáveis

- **R1** — `_LINK_SEPARATOR_PATTERN` casa `via`, `por`, `atraves de`,
  `com uso de` e mantém `com`/`e` (word boundaries preservadas).
- **R2** — Teste com o trecho fiel do relatório-exemplo (base promovida pela
  seção do Slice 001 + `dilatacao ... via retossigmoidoscopia flexivel` na
  mesma cláusula): `rectosigmoidoscopy_dilation` com qualificação
  `current_request` e `linked_base=True`; a ocorrência `eda_dilation` do mesmo
  texto (sem base EDA na cláusula) permanece `mention`.
- **R3** — Teste de ordem invertida sem seção ("Solicito dilatação de
  estenose via retossigmoidoscopia"): variação `current_request` com verbo de
  solicitação + conector (não depende do Slice 001).
- **R4** — Teste negativo: `dilatacao` sem base da família na mesma cláusula
  (com qualquer conector novo) continua `mention` (demotion preservada);
  `dilatacao de coledoco` continua bloqueada.
- **R5** — Teste de integração da detecção v4 com o texto-exemplo completo:
  `detect_requested_procedures_v4` devolve `rectosigmoidoscopy_dilation` com
  `strong`/`any` verdadeiros (item determinístico, sem LLM1).

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/pipeline/scope_detection.py
  - apps/pipeline/tests/test_report_body_clues.py   # estende o arquivo do Slice 001

allowed_incidental_files: []

out_of_scope:
  - reconciliação/precedências (Slice 003) — o conjunto
    {colonoscopy, rectosigmoidoscopy_dilation} continua fail-closed na matriz
    até o Slice 003
  - gate de item estruturado (Slice 004); exibição (Slice 005)
  - novos termos de vocabulário (anastomose, estenose, plasma de argonio)
  - mudanças em _linked_base_in_clause além do pattern do separador
```

Escalar ao parent se: o novo conector exigir mudança em
`_linked_base_in_clause`/`_qualify_variation_occurrences`; ou se testes
existentes de vínculo quebrarem além dos previstos.

## Matriz requisito -> arquivo -> teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `apps/pipeline/scope_detection.py` | coberto indiretamente por R2/R3/R4 |
| R2 | `apps/pipeline/scope_detection.py` | `test_report_body_clues.py::test_via_link_in_justificativa_example` |
| R3 | `apps/pipeline/scope_detection.py` | `test_report_body_clues.py::test_via_link_without_section` |
| R4 | `apps/pipeline/scope_detection.py` | `test_report_body_clues.py::test_unlinked_and_blocked_terms_stay_mention` |
| R5 | `apps/pipeline/scope_detection.py` | `test_report_body_clues.py::test_v4_detection_detects_combined_example` |

## Plano de testes do slice

### RED

1. `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/pipeline/tests/test_report_body_clues.py -q`
   — falha esperada: os testes novos de `via`/`por` falham porque
   `linked_base` vem `False` (separador atual não casa `via`) e a variação é
   demovida a `mention`.

### GREEN

2. Estender `_LINK_SEPARATOR_PATTERN` em `apps/pipeline/scope_detection.py`.
3. Repetir o comando do passo 1 — resultado esperado: exit code 0.

### Verificação do slice

4. `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/pipeline/tests/test_rectosigmoidoscopy_pipeline_v4.py apps/pipeline/tests/test_scope_detection.py apps/pipeline/tests/test_eda_package_pipeline_v4.py apps/pipeline/tests/test_report_body_clues.py -q`
   — esperado: exit 0 (inclui o teste de vínculo ausente e os de `com`/`e`).
5. `uv run ruff check apps/pipeline/scope_detection.py apps/pipeline/tests/test_report_body_clues.py && uv run ruff format --check apps/pipeline/scope_detection.py apps/pipeline/tests/test_report_body_clues.py`
6. `uv run mypy apps/pipeline`

## Critérios de aceitação

- [ ] R1-R5 provados (testes novos verdes).
- [ ] Demotion de termo ambíguo sem vínculo e bloqueio de sítio preservados (R4).
- [ ] Suítes de regressão do plano verdes sem edição.
- [ ] Nenhum arquivo fora de `expected_files` alterado.
