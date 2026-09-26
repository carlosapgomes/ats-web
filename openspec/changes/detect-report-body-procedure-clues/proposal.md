# Proposal: Detecção de pistas de procedimentos no corpo do relatório

**Change ID:** `detect-report-body-procedure-clues`

**Branch de implementação:** `feature/detect-report-body-procedure-clues`

**Risco:** CRÍTICO — altera qualificação de ocorrências e reconciliação do
pipeline de detecção (fail-closed precisa continuar fail-closed) e o payload
de revisão NIR consumido pela UI de correção.

## Why

Após o rc `v0.10.0-rc.1`, casos reais da Central Estadual de Regulação
(SUREM) demonstraram que o campo `Motivo da Solicitação:` traz apenas o exame
base (ex.: `Endoscopia Digestiva Baixa - Colonoscopia`) porque a central não
oferece subtipos. O procedimento realmente pretendido (ex.: Retossigmoidoscopia
flexível com dilatação de anastomose) aparece **no corpo do relatório**,
tipicamente em `Justificativa da Transferência:`. Investigação executada sobre
o código (com simulação empírica do detector real sobre um relatório real)
comprovou:

1. A string `justificativa da transferencia` não existe em nenhuma linha de
   código de produção — nenhum prompt, schema, parser ou detector conhece a
   seção. O único campo parseado como fonte de pedido atual é
   `Motivo da Solicitação:`
   (`apps/pipeline/scope_detection.py:453-465`).
2. Ocorrências no corpo só viram detecção se qualificadas como
   `current_request`, o que exige verbo de solicitação ou rótulo imediatamente
   antes (`scope_detection.py:243-254`). O `.` de uma oração intermediária
   separa o rótulo do procedimento (`_CLAUSE_BOUNDARY_PATTERN`, `:208`).
3. O conector que vincula variação↔base é apenas `com|e`
   (`_LINK_SEPARATOR_PATTERN`, `:1244`). A redação clínica comum
   "DILATAÇÃO DE ANASTOMOSE **VIA** RETOSSIGMOIDOSCOPIA FLEXIVEL" não vincula.
4. O gate do item estruturado (`scope_detection.py:1558-1563`) descarta
   silenciosamente o item reportado pelo LLM1 quando existe mera *menção* do
   termo no corpo — e se a declaração NIR coincide com o Motivo, o caso
   **prossegue** (falha aberta) em vez de ir à revisão.
5. Quando a família Retossigmoidoscopia é detectada, a colonoscopia derivada
   do alias guarda-chuva do Motivo (`endoscopia digestiva baixa`) colide na
   matriz (`{colonoscopy, rectosigmoidoscopy_*}` fora de
   `ALLOWED_PROCEDURE_SETS`), gerando `unsupported_procedure_combination`
   genérico — inclusive para casos já corrigidos pelo NIR (loop de revisão).

Resultado observado no relatório-exemplo: declarado `colonoscopy` →
`action=proceed` silencioso; declarado `rectosigmoidoscopy_dilation` →
`nir_review` com motivo enganoso; item estruturado correto do LLM1 →
descartado.

O intake não pode compensar: a seleção do tipo e o upload são simultâneos
(extração do PDF é assíncrona), não há momento de pré-visualização. O ponto
onde as pistas agregam valor é a **revisão NIR**: exibir, no card de correção,
as pistas detectadas no corpo do relatório para fundamentar a seleção.

## What Changes

- **Contexto de seção:** ocorrências de identidades do catálogo dentro da
  seção `Justificativa da Transferência:` (delimitada por rótulos conhecidos e
  pelo cabeçalho de página do relatório) qualificadas como mera menção passam a
  `current_request`; negações e históricos permanecem intocados. Ocorrências
  ganham rótulo de seção para exibição — inclusive as do campo
  `Motivo da Solicitação` (proveniência que distingue o guarda-chuva do Motivo
  do mesmo termo citado no corpo). Inclui correção habilitante de offsets
  absolutos na iteração de cláusulas (bug pré-existente: cláusulas repetidas
  entre páginas misturavam contextos).
- **Conectores de vínculo:** `via`, `por`, `através de` e `com uso de` passam
  a vincular variação↔base na mesma cláusula (hoje só `com`/`e`), mantendo a
  demotion de termos ambíguos sem vínculo.
- **Precedência de família:** quando exatamente uma identidade da família
  Retossigmoidoscopia tem ocorrência atual e toda evidência atual de
  Colonoscopia provém do alias guarda-chuva do Motivo
  (`endoscopia digestiva baixa`), a Colonoscopia é suprimida do conjunto
  detectado (regra auditada, mesmo formato das precedências existentes).
- **Gate de conflito do item estruturado:** item estruturado do LLM1
  contraditado por ocorrência não-atual gera `nir_review` com
  `conflicting_procedure_evidence` (novo reason code elegível para correção) —
  nunca prosseguimento silencioso.
- **Pistas na revisão NIR:** o payload de revisão ganha
  `detected_body_clues` (procedimento, qualificação, seção, excerpt —
  limitado) e o card de correção de tipo exibe essas pistas no momento da
  seleção do novo conjunto.

## Capabilities

### Modified Capabilities

- `procedure-neutral-analysis`: contexto de seção, conectores de vínculo,
  precedência de família e gate de conflito do item estruturado na detecção e
  reconciliação.
- `exam-type-correction`: card de correção exibe as pistas detectadas no
  corpo do relatório; novo reason code elegível.

## Impact

- **Pipeline (determinístico):** `apps/pipeline/scope_detection.py`
  (seção/vínculo/gate), `apps/pipeline/procedure_reconciliation.py`
  (precedência de família, conflito, payload 2.1), `apps/pipeline/orchestrator.py`
  (passagem de conflito e clues).
- **Intake/UI:** `apps/intake/services.py` (reason code elegível),
  `apps/intake/views.py` + `templates/intake/case_detail.html` (exibição das
  pistas; apenas classes Bootstrap existentes, sem vocabulário CSS novo).
- **Sem impacto pretendido:** FSM, catálogo/matriz de combinações, prompts
  LLM, schemas LLM 4.0, declaração NIR (`declared_by_nir` intocado),
  priority signals, filas/agendamento, analytics.

## Sucesso

- O relatório-exemplo real (Motivo `EDB - Colonoscopia` + Justificativa com
  `DILATAÇÃO DE ANASTOMOSE COLORRETAL VIA RETOSSIGMOIDOSCOPIA FLEXIVEL`)
  detecta `rectosigmoidoscopy_dilation` com ocorrência atual via detector
  determinístico, sem depender do LLM1.
- Caso declarado `colonoscopy` vai à revisão NIR com
  `exam_type_mismatch` e pistas visíveis; corrigido para
  `rectosigmoidoscopy_dilation` e reprocessado, prossegue (sem loop).
- Item estruturado do LLM1 contraditado por menção nunca mais permite
  `proceed` quando declarado == detectado-by-Motivo.
- Negações/históricos dentro da Justificativa continuam sem criar
  solicitação atual; termos ambíguos sem vínculo continuam menção.
- Toda nova regra falha na direção NIR review (fail-closed), nunca na
  direção de prosseguimento silencioso.

## Fora de escopo (explícito)

- Alterações de prompt LLM1/LLM2 (indicar a Justificativa como fonte de
  evidence span) — change futuro; o gate de conflito deste change já cria o
  landing zone seguro para isso.
- Variantes ortográficas (ex.: `retosigmoidoscopia`) e novos termos de
  vocabulário (`plasma de argonio`, `APC`, `PEG`, sítios de dilatação).
- Rework do extrator do Motivo (terminadores frágeis).
- Ampliação da cadeia fechada `_REQUEST_LIST_TERM_SOURCE`.
- Sugestão automática de tipo no momento do upload (seleção e upload são
  simultâneos por desenho do produto).
