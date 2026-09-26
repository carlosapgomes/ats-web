# Design: Detecção de pistas de procedimentos no corpo do relatório

## Contexto técnico (estado atual, verificado em código)

- `detect_procedure_occurrences` (`apps/pipeline/scope_detection.py:1330`)
  normaliza o texto integral, corta em cláusulas (`[.;!?]` + `\n`), coleta
  ocorrências das 10 identidades via `_PROCEDURE_OCCURRENCE_PATTERNS` e as
  classifica por `_classify_occurrence` (prefixo/sufixo da cláusula):
  `historical`/`negated` vencem; `current_request` exige
  `_REQUEST_BEFORE_OCCURRENCE_PATTERN`, `_LABEL_BEFORE_OCCURRENCE_PATTERN`
  (`exame|procedimento|motivo da solicitacao|motivo`) ou
  `_REQUEST_AFTER_OCCURRENCE_PATTERN`; o resto é `mention`.
- Vínculo variação↔base: `_LINK_SEPARATOR_PATTERN = \b(?:com|e)\b`
  (`:1244`); base atual na mesma cláusula + separador entre as ocorrências →
  variação `mention` vira `current_request`; sem vínculo,
  `_qualify_variation_occurrences` (`:1419`) demove a `mention`.
- `detect_requested_procedures_v4` (`:1527`): para os tipos estruturados
  candidatos, `present = type in current_occurrences or (type in structured
  and type not in occurrence_types)` — menção/histórico/negação **bloqueiam**
  o item estruturado.
- `reconcile_detected_procedures`
  (`apps/pipeline/procedure_reconciliation.py:274`): valida catálogo/duplicatas,
  aplica `_apply_specialized_precedence` e `_apply_variation_precedence`
  (ambas exigem ocorrência `current_request` do tipo), valida matriz
  (`ALLOWED_PROCEDURE_SETS`) e decide `proceed`/`auto_upgrade`(só
  `{eda, colonoscopy}`)/`nir_review`.
- `orchestrator.py:455-471` constrói `strong`/`any` do dict de detecção e
  chama a reconciliação; `:538-563` monta o payload de revisão
  (`build_v2_review_payload`, `procedure_reconciliation.py:437`) com
  `evidence_spans` do LLM1, grava `suggested_action` e chama
  `scope_gate_bypass`.
- Correção de tipo: `apps/intake/services.py:285-292`
  (`EXAM_TYPE_CORRECTION_ELIGIBLE_REASON_CODES`) define quais reason codes
  habilitam o card; `apps/intake/views.py:901-923` monta
  `correction_form_context`; `templates/intake/case_detail.html:364+` renderiza
  declarado/detectado/motivo + combobox.

## Decisões

### D1 — Seção `Justificativa da Transferência` como contexto de solicitação

Nova função pura em `scope_detection.py` calcula os spans da seção no texto
normalizado: início no rótulo `justificativa da transferencia:` e término no
primeiro terminador seguinte — cabeçalho de página (`relatorio de
ocorrencias`) ou rótulo operacional conhecido (`informado por`, `motivo da
solicitacao`, `complemento da solicitacao`, `resumo clinico`, `hipotese do
diagnostico`, `encaminhamento`, `mot. solicit.`, `unid. origem`, etc.).
Lista LOCAL conservadora, parcialmente sobreposta aos rótulos que o
`apps/intake/regulation_gate.py` conhece — deliberadamente sem import
cruzado; os rótulos extras além do gate são escolha deste design.

Ocorrências com `start` dentro de um span e qualificação `mention` passam a
`current_request`. Ocorrências `historical`/`negated` **não** são promovidas
(os padrões existentes continuam sendo a rede de segurança). Ocorrências já
`current_request` permanecem. O upgrade acontece **antes** do passe de vínculo
(`current_types_by_clause`), para que a base promovida estenda o vínculo à
variação na mesma cláusula.

**Correção habilitante (offsets absolutos):** a iteração de cláusulas em
`detect_procedure_occurrences` hoje usa `normalized_text.find(clause)`
(`scope_detection.py:1346`) e agrupa `current_types_by_clause` por TEXTO da
cláusula (`:1377`) — relatórios reais repetem cláusulas idênticas entre
páginas (boilerplate `TRANSPORTE:`, `ECG: Sem Exame`, evoluções duplicadas),
deslocando offsets e misturando contextos de páginas distintas. O Slice 001
corrige a iteração para offsets absolutos (cursor/`finditer`) e keying por
INTERVALO — bug pré-existente, mas pré-requisito para membership de seção
correto (entregue no mesmo slice, com teste de caracterização de cláusula
repetida em duas seções).

**Seção sem terminador:** o span corre até o fim do texto (decisão
documentada; o relatório real termina em rótulo operacional ou próximo
cabeçalho). Teste pinna o comportamento.

O MESMO mecanismo de spans marca o campo `Motivo da Solicitação:` (início no
rótulo, término no primeiro terminador) com
`section="motivo_da_solicitacao"` — sem depender do frágil extrator de valor
`_extract_motivo_solicitacao_text` (L8 permanece fora de escopo). Essa
proveniência é o que autoriza a regra D3 a distinguir o guarda-chuva do
Motivo do guarda-chuva citado no corpo.

`ProcedureOccurrence` ganha campo default `section: str = ""` (backward
compatível com construtores diretos em testes); ocorrências dentro do span
recebem `section="justificativa_da_transferencia"` — insumo da exibição (D5),
sem consumo comportamental na reconciliação.

Justificativa clínica: a seção é onde o médico solicitante afirma o que
quer do regulador; procedimento ali nomeado é pedido atual por definição
documental. Direção de falha: falso positivo cria divergência declarado×
detectado → `nir_review` (humano decide), nunca prosseguimento silencioso.

### D2 — Conectores instrumentais no vínculo variação↔base

`_LINK_SEPARATOR_PATTERN` passa a aceitar `via`, `por`, `atraves de`,
`com uso de` além de `com`/`e` (todos com `\b`). Requisitos inalterados:
mesma cláusula, base atual, e demotion de termo ambíguo sem vínculo
(`_qualify_variation_occurrences` intocada). "DILATAÇÃO DE ANASTOMOSE
COLORRETAL VIA RETOSSIGMOIDOSCOPIA FLEXIVEL" (ordem invertida, base depois da
variação) já é suportada por `_linked_base_in_clause`, que testa o separador
nos dois sentidos.

### D3 — Precedência de família absorve o guarda-chuva do Motivo

Nova regra em `procedure_reconciliation.py`, aplicada após
`_apply_variation_precedence` e antes da validação da matriz
(`_apply_family_umbrella_precedence`):

- condições: (a) exatamente uma identidade da família Retossigmoidoscopia
  (`rectosigmoidoscopy`, `rectosigmoidoscopy_dilation`,
  `rectosigmoidoscopy_argon`) no conjunto detectado; (b) essa identidade tem
  ocorrência `current_request` (com `linked_base` quando variação de termo
  ambíguo — mesmo regime de `_current_request_variation_types`); (c)
  `colonoscopy` está no conjunto, toda ocorrência `current_request` de
  colonoscopia tem excerpt guarda-chuva (`endoscopia digestiva baixa`) E está
  marcada na seção `motivo_da_solicitacao` (D1) — nem ocorrência atual do
  termo explícito `colonoscopia`, NEM guarda-chuva atual citado no CORPO
  (Justificativa/Resumo) autorizam a supressão; nesses casos o conflito segue
  fail-closed na matriz;
- efeito: suprimir `colonoscopy` do conjunto; registrar
  `family_umbrella_over_colonoscopy` com o MESMO formato de proveniência das
  regras existentes, sem excerpt clínico.

**Contrato de metadados para precedências simultâneas (compatível):** no
cenário-alvo, `_apply_variation_precedence` (suprime a base
`rectosigmoidoscopy`) E a regra de família aplicam-se JUNTAS. O campo
`procedure_precedence` existente (dict único) é PRESERVADO para os
consumidores atuais — decisivo porque `apps/doctor/presenters.py:344-346`
(`_build_precedence_notice`) rejeita qualquer valor não-dict e porque casos
já persistidos em `suggested_action` carregam o formato dict. Novidades
aditivas: (a) `serialize_procedure_precedence` mantém o dict único com a
regra mais significativa na ordem especializada → variação → família;
(b) novo helper separado `serialize_procedure_precedence_rules` devolve a
LISTA com TODAS as reduções aplicadas (mesma ordem; `[]` quando nenhuma) —
helper separado porque o orchestrator atribui o retorno do serializer atual
direto a `procedure_precedence` em três destinos (`orchestrator.py:511-523`
evento de detecção, `:545-550` payload de revisão, `:723-726` sugestão
final), e o slice 003 fia o campo novo `procedure_precedence_rules`
explicitamente nesses três pontos (o dict legado segue com o comportamento
atual; casos persistidos sem o campo novo são tratados como ausentes);
(c) o presenter do doctor ganha branch de copy própria para a regra de
família — sem ela, um dict da regra de família cairia na copy de
especializado (texto equivocado); testes de presenter em
`apps/doctor/tests/test_eda_package_report.py` e
`test_rectosigmoidoscopy_report.py` fixam o formato dict hoje e são
estendidos, não reescritos.

Motivo `EDB - Colonoscopia` produz hoje exatamente uma ocorrência atual de
excerpt `endoscopia digestiva baixa` (o rótulo ancora o primeiro termo) — a
regra cobre o caso sem tocar no extrator do Motivo (L8 fica fora de escopo).
Se o Motivo trouxer `colonoscopia` explícito como evidência atual, a regra
não se aplica e o conflito real segue fail-closed na matriz (humano decide).

### D4 — Gate de conflito do item estruturado

`detect_requested_procedures_v4` passa a computar, para os tipos estruturados
candidatos, `conflicting = type in structured and type in occurrence_types and
type not in current_occurrences` (o caso hoje cobrado por
`test_non_current_occurrence_overrides_the_structured_item`). O dict de
detecção ganha a chave `conflicting` para todos os tipos (default `False`).

`reconcile_detected_procedures` ganha parâmetro `conflicting=()`; se
`conflicting` contiver tipo conhecido, retorna imediatamente
`nir_review(reason_code="conflicting_procedure_evidence")` com
`detected = any_set ∪ conflicting` — ANTES de qualquer caminho `proceed`
(isso fecha a falha aberta em que declarado == detectado-by-Motivo).
`orchestrator.py` extrai `conflicting` do dict de detecção e repassa.
`EXAM_TYPE_CORRECTION_ELIGIBLE_REASON_CODES` (intake) ganha o novo código
para habilitar o card de correção.

Semântica preservada: o item estruturado contraditado **não** vira detecção
(`strong`/`any` continuam `False`); ele apenas não pode mais ser invisível.

### D5 — Pistas do corpo na revisão NIR

- Novo helper puro `project_body_clues(occurrences)` em
  `procedure_reconciliation.py`: projeta ocorrências para
  `[{procedure_type, procedure_label, qualification, qualification_label,
  section, excerpt}]`, ordenadas `current_request` primeiro, cap 8 entradas,
  excerpt truncado a 200 chars. **Exclui ocorrências com
  `section="motivo_da_solicitacao"`** (a pista do Motivo não é pista do
  corpo; o card já exibe declarado/detectado). Labels de procedimento via
  `ProcedureType(...).label`; qualificações com mapa pt-BR
  (`current_request→Solicitação atual`, `mention→Menção`,
  `historical→Histórico`, `negated→Negado`).
- `build_v2_review_payload` ganha parâmetro `body_clues` e campo
  `detected_body_clues`; `schema_version` sobe para `"2.1"`
  (aditivo — consumidores existentes leem campos que continuam presentes).
- `orchestrator.py` passa `body_clues=project_body_clues(occurrences)` no
  gate de revisão NIR.
- `apps/intake/views.py` inclui `body_clues` no `correction_form_context`
  (do `suggested_action`); `templates/intake/case_detail.html` renderiza a
  lista "Pistas detectadas no corpo do relatório" no card de correção usando
  **apenas classes Bootstrap existentes** (`list-group`, `badge`,
  `blockquote-footer` — sem vocabulário CSS novo, dispensando guarda de CSS
  do AGENTS §8). Payload sem `detected_body_clues` → card inalterado
  (compatibilidade com casos já em revisão antes do deploy).

### D6 — Análise de segurança (direção de falha)

| Nova regra | Falso positivo | Falso negativo |
| --- | --- | --- |
| D1 seção | identidade extra no conjunto → mismatch/matriz → `nir_review` | volta ao comportamento atual (menção) |
| D2 conectores | variação vinculada indevidamente → conjunto fora da matriz → `nir_review` | idem |
| D3 guarda-chuva | supressão indevida exige ocorrência atual da família + colonoscopia só por guarda-chuva → pior caso: mismatch → `nir_review` | conflito real continua `unsupported_procedure_combination` |
| D4 conflito | revisão NIR extra | item invisível (comportamento atual) |

Nenhuma regra cria `proceed` com conjunto DIVERGENTE do declarado: `proceed`
só ocorre quando o conjunto reconciliado == declarado. Uma promoção falsa
(D1) só produz `proceed` quando a identidade promovida COINCIDE com a
declaração do NIR — ou seja, confirma a escolha humana; qualquer divergência
(identidade extra, conjunto fora da matriz, conflito) produz `nir_review`.
Testes pinam explicitamente: Justificativa citando família divergente do
declarado → `nir_review`; Justificativa citando família coincidente com o
declarado → `proceed` (confirmação, não desvio).
`declared_by_nir` e `set_detected_procedures` permanecem intocados (contrato
"detecção nunca altera declaração").

### D7 — Deliberadamente não feito

Prompts LLM (o gate D4 cria o landing zone seguro para future change),
variantes ortográficas/vocabulário novo, extrator do Motivo, cadeia fechada
`_REQUEST_LIST_TERM_SOURCE`, sugestão no upload (seleção e upload são
simultâneos por desenho). Ver `proposal.md` → Fora de escopo.
