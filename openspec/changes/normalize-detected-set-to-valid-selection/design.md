# Design: Conjunto detectado normalizado para seleção válida

Decisão arquitetural: **ADR-0011** (`docs/adr/ADR-0011-conjunto-detectado-
normalizado-para-selecao-valida.md`, Proposed — aceite é pré-condição 0.1).
Evidência completa da investigação: `.pi/reports/detected-set-normalization-
investigation-2026-09-26.md`. Revisão de planejamento (2 revisores
independentes, vereditos BLOCK) incorporada: P0 do discriminador, normalização
apenas de conjuntos fora da matriz, mecanismo do evento na passada de
resolução, extensão ao branch "covered-but-unsupported" e inventário de
testes regenerado por tipo de mudança.

## D1. `best_covering_selection()` — semântica exata

Função pura em `apps/cases/procedures.py`, junto de `selection_key()`:

- Entrada: coleção arbitrária de identidades do catálogo (multiset tolerado;
  dedupe exato primeiro). Saída: `SelectionKey` da **seleção válida mais
  completa que cobre o conjunto**, ou `INVALID_SELECTION_KEY` quando nenhuma
  combinação de `ALLOWED_PROCEDURE_SETS` cobre. Vazio → `invalid` (divergência
  deliberada de `selection_key(()) == ""`; D2 exige declaração não-vazia, então
  a comparação nunca produz igualdade com vazio).
- Regras de cobertura (determinísticas, na ordem):
  1. singleton exato → a própria chave;
  2. `{eda, colonoscopy}` exato → `eda_colonoscopy`;
  3. base contida em pacote presente → o pacote absorve a base:
     `{eda, eda_gastrostomy|eda_capsule|eda_dilation}` → pacote;
     `{rectosigmoidoscopy, rectosigmoidoscopy_dilation|…_argon}` → pacote;
  4. mais de uma variação da mesma base, variação + colonoscopia (exceto o
     par), dois especializados, valor desconhecido (sozinho ou misto), ou
     qualquer conjunto não coberto → `invalid` (desconhecido nunca é filtrado
     para fabricar validade).
- "Mais completa" = seleção que cobre TODAS as identidades do conjunto; a
  matriz atual não produz ambiguidade (cobertura, quando existe, é única);
  ambiguidade residual → `invalid` (nunca arbitrário).
- A relação base⊂pacote ganha constante autoritativa **em
  `apps/cases/procedures.py`** (`PROCEDURE_PACKAGE_BASES`), **importada** por
  `apps/pipeline/procedure_reconciliation.py` no lugar do mapa local
  `_VARIATION_BASE_TYPES` (direção de import já existente cases←pipeline;
  elimina drift de mapa duplicado — acha P2 da revisão).

## D2. Regra de resolução declarado-aware — com discriminador de evidência atual

Aplicada em **dois pontos** de `reconcile_detected_procedures`, sempre com o
conjunto detectado bruto do ponto (`union`):

```
proceed com declared  ⟺  (1) any_set ≠ ∅
                        (2) declared é seleção canônica válida não-vazia
                        (3) selection_key(declared) == best_covering_selection(union)
```

- **Ponto A — branch de conflito** (`:481-491`, `union = any ∪ conflicting`):
  antes de construir o `nir_review`.
- **Ponto B — matriz do detectado** (`:535-543`, após as três precedências
  de `:501-532`; `union = any_set` pós-precedência): mesma regra antes de
  retornar `unsupported_procedure_combination` (fecha o beco
  "covered-but-unsupported": LLM alega `eda_dilation` sem NENHUMA ocorrência
  textual; `any={eda, eda_dilation}` não colapsa por precedência e é coberto
  por `eda_dilation`; declarado `eda_dilation` ⇒ prossegue). O branch de
  matriz do DECLARADO (`:493-499`) permanece intocado (declarado inválido
  continua revisão — o intake já impede, mas a defesa permanece).

**Por que o discriminador (1) é necessário (P0 da revisão):** sem ele, a
regra reabre o fail-open que o gate fecha — quando a única evidência é o item
contraditado e `union == declared` (ex.: texto "Nao solicito capsula
endoscopica neste momento." + declarado `eda_capsule`), a 1ª passada
prosseguiria em silêncio com um procedimento NEGADO. Com `any=∅` exigido,
essa classe permanece `nir_review` (testes
`test_negated_capsule_…`, `test_historical_capsule_…`,
`test_non_current_occurrence_overrides_the_structured_item` **não mudam**).
Quando `any ≠ ∅` e declarado == cobertura máxima, o prosseguimento NÃO é
silencioso: o conflito/evidência bruta fica no evento de auditoria (D3) e o
médico revisa o caso a jusante.

**Mudanças de desfecho intencionais (re-baseline com justificativa):**
- `test_historical_dilation_with_declared_package_returns_to_nir` (421-441):
  "Solicito EDA." atual + dilatação histórica + declarado `eda_dilation` ⇒
  passa a **prosseguir** (é exatamente o pass-2 do caso real 26/09; a
  correção do NIR resolve).
- `test_structured_item_without_current_occurrence_does_not_suppress`
  (264-277): declarado `eda_dilation`, `any={eda, eda_dilation}` ⇒ passa a
  **prosseguir** (Ponto B).
Em ambos: assert novo do evento com a evidência bruta (D3).

`best == invalid` nunca iguala declaração válida ⇒ conjuntos não cobertos
(dois pacotes, variação+colonoscopia, especializados) permanecem fail-closed.

## D3. Evidência bruta na auditoria; normalizado só fora da matriz no payload

- `ProcedureReconciliationResult` ganha campo **`conflicting_evidence_types`
  (e, no Ponto B, o union bruto)**: o orchestrator grava
  `CASE_PROCEDURES_DETECTED` com o **union bruto** independentemente do
  desfecho (na passada de resolução, `reconciliation.detected_procedure_types`
  carrega o declarado — por isso o evento NÃO pode derivar dele; mecanismo
  explícito, P1 da revisão).
- `build_v2_review_payload` normaliza `detected_procedures` **somente quando
  o conjunto detectado NÃO pertence a `ALLOWED_PROCEDURE_SETS`**, e mapeia a
  chave de volta com `procedure_types_for_selection()` — o par válido
  `{eda, colonoscopy}` continua saindo como `["eda","colonoscopy"]` (nunca a
  chave interna `eda_colonoscopy` vaza para a UI; P1 da revisão). Conjuntos
  já válidos e não-cobertos (`invalid`) passam inalterados.
- `_detection_origin_suffix` continua recebendo o union bruto para computar
  "Origem da detecção" (a normalização é só no writer; assert novo pina).
- `detected_exam_type` legado pode ser `"mixed"` em artefatos antigos —
  leitores toleram ambos (nota de compatibilidade).

## D4. Label sem duplicação (`views.py:191-209`)

Regra anti-duplicação em `_correction_detected_label`: base contida em ao
menos um pacote presente não é listada separadamente; identidades restantes
juntam-se com `" + "`; dois ou mais pacotes completos juntam-se com `" e "`.
A função continua nunca levantando. **Nota de superfície (P2 da revisão):**
no caso real, a tabela por-procedimento da página segue derivada de rows
declared ("Declarado, não detectado na análise" para o pacote) enquanto o
card exibe o detectado normalizado — divergência consciente e registrada na
ADR; alinhamento da tabela fica como follow-up deliberado.

## D5. Interseções e não-mudanças

- Precedências de detecção automática (ADR-0008; ADR-0010 dec.4) intocadas:
  colapso base→pacote na detecção continua exigindo ocorrência
  `current_request` com vínculo (`_apply_variation_precedence` inalterado —
  só troca a origem do mapa de bases por `PROCEDURE_PACKAGE_BASES`).
- `_partition_procedures` (duplicata exata → `unsupported_procedure_
  combination`) inalterado e continua ANTES do Ponto A.
- `strong`/`any` do item contraditado permanecem falsos; sem item
  estruturado o desfecho não muda.
- Risco residual registrado (ADR): se o LLM1 abandonar o item estruturado no
  reprocessamento, `declared={eda_dilation}` vs `any={eda}` cai em
  `exam_type_mismatch` e o caso NÃO prossegue (saída: re-corrigir para EDA).
  A alegação "fim do beco sem saída" é condicionada à reprodução do item
  pelo LLM1 no mesmo texto.

## D6. Deltas de spec (neste change)

- `procedure-neutral-analysis` — MODIFIED do requirement do gate: payload
  normalizado (só fora da matriz), evento bruto, resolução com discriminador
  (`any ≠ ∅` + `declared == best`) e cenário novo de coincidência sem
  evidência atual que permanece fail-closed.
- `exam-type-correction` — MODIFIED: cenário de resolução (com evidência
  atual) + cenário de coincidência negada/histórica que reentra na revisão.
- `procedure-combination-policy` — MODIFIED: matriz aplica-se ao conjunto
  normalizado na decisão/exibição; cenário da base absorvida; cenário do
  Ponto B (item sem ocorrência textual + declaração do pacote prossegue com
  evidência atual).

## D7. Inventário de testes regenerado (por tipo de mudança)

**Desfecho MUDA (re-baseline intencional, D2; nomes pós-implementação):**
- `apps/pipeline/tests/test_eda_package_pipeline_v4.py:426`
  `test_historical_dilation_with_declared_package_reaches_the_doctor`
  (→ proceed + evento bruto);
- `…:265` `test_declared_package_covers_the_union_at_the_detected_matrix`
  (→ proceed no Ponto B);
- `apps/pipeline/tests/test_rectosigmoidoscopy_pipeline_v4.py` (~:305)
  — renomeado no mesmo padrão — o simétrico reto (regra genérica; lacuna do
  inventário original reconhecida pelo planner durante a implementação).

**Desfecho NÃO muda (guardas do discriminador; adicionar asserts de
imutabilidade onde barato):**
- `…:447-478` cápsula negada; `…:479-496` cápsula histórica (ambas `any=∅`,
  `union==declared`); `apps/pipeline/tests/test_rectosigmoidoscopy_pipeline_
  v4.py:233-247` (reto, `any=∅`).

**Payload-only (normalização quando fora da matriz):** os asserts de
`payload["detected_procedures"]` cujo conjunto tem cobertura válida —
421-441 (`{"eda","eda_dilation"}` → `["eda_dilation"]`). **Inalterados:**
unions não-cobertos (`:285,297`; `test_report_body_clues.py:741,774,819`;
`test_rectosigmoidoscopy_pipeline_v4.py:349,483`;
`test_gastrostomy_infection_review.py:257` — `best=invalid`, payload
permanece o union) e asserts de `result.detected_procedure_types` em testes
unitários de reconciliação (o result continua carregando o bruto).

**Novos:** tabela verdade do helper (slice 001); regressão e2e do beco sem
saída (correção → proceed + evento bruto + sem novo nir_review); coincidência
negada/histórica permanece revisão; par válido `{eda,colonoscopy}` no payload
permanece `["eda","colonoscopy"]`; origem da detecção preservada; labels
(slice 003).

## D8. Dimensionamento

3 slices: (001) helper + `PROCEDURE_PACKAGE_BASES` + tabela verdade —
fundação isolada; (002) regra D2 nos dois pontos + payload D3 + evento bruto
+ re-baselines e guardas de D7; (003) label D4. Não fragmentar além.
