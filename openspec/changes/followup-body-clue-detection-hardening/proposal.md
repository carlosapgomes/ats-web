# Proposal: Hardening pós-rc da detecção de pistas no corpo do relatório

**Change ID:** `followup-body-clue-detection-hardening`

**Origem:** backlog de P2s/residuais do change `detect-report-body-procedure-clues`
(registrado antes do arquivamento, a pedido do dono, após avaliação de risco:
nenhum item bloqueia o deploy do rc; itens condicionais a sinais do smoke).

**Branch de implementação:** a definir quando acionado (item 1 é candidato a
QUICK; itens 2-3 a slices pequenos).

## Why

O change `detect-report-body-procedure-clues` entregou detecção de pistas no
corpo do relatório com defesa em profundidade (seção → vínculo → precedência
de família → gate de conflito → pistas ao NIR → prompt LLM). A análise de
riscos residuais concluiu que **nenhum P2 bloqueia o deploy**: todos falham
fechado (NIR review), são cosméticos ou são inerentes à validação do rc.
Este change registra o backlog para que os itens não se percam no
arquivamento, cada um com **gatilho observável no smoke do rc** — sem
implementar nada antes da evidência de produção.

## What Changes (itens condicionais; executar apenas sob o gatilho)

1. **Simplificação do card de revisão NIR (EXECUTADO — decisão do dono durante
   o smoke do rc.2, 2026-09-26)**: a listagem crua de pistas
   (`Pistas detectadas no corpo do relatório`) confundia mais do que
   informava (tokens duplicados sob múltiplas identidades, excerpt = termo
   casado, ruído de outras famílias). O card volta a exibir apenas
   Tipo declarado / Tipo detectado / Motivo da revisão, e o **motivo passa a
   informar a origem da detecção** quando disponível (ex.: "Origem da
   detecção: Justificativa da Transferência"). O payload
   `detected_body_clues` (schema 2.1) PERMANECE em `suggested_action`/eventos
   para auditoria — apenas deixa de ser renderizado. Sem mudança na detecção,
   reconciliação de conjuntos, precedências ou gate de conflito (apenas o
   `reason_text` ganha o sufixo de origem derivado das `section`s das
   ocorrências atuais do conjunto detectado).
2. **Ancoragem de terminadores de seção** — hoje os terminadores da seção
   `Justificativa da Transferência` casam como substring sem exigir `:`
   (`scope_detection.py`, `_first_section_terminator`/`_SECTION_TERMINATOR_LABELS`),
   então uma palavra narrativa (ex.: "encaminhamento", "complemento") no meio
   da Justificativa trunca o span e perde a promoção (falso negativo; a
   defesa em profundidade ainda cobre via prompt+gate de conflito).
   Correção: exigir `:` (ou âncora de início de linha) nos terminadores.
   *Gatilho:* smoke do rc mostrar caso-alvo terminando em `proceed` sem
   detecção da família (span truncado materializando o risco).
   *Nota de risco:* mudança de matching exige testes com layout real
   multi-página; a direção de falha do endurecimento é falso positivo →
   NIR review (fail-closed).
2. **Avisos múltiplos do médico a partir de `procedure_precedence_rules`** —
   no cenário combinado (variação + família), o aviso ao médico mostra só a
   regra mais significativa (variação); a absorção do guarda-chuva aparece
   apenas na lista de auditoria. Correção: o presenter renderizar um aviso
   por regra aplicada.
   *Gatilho:* feedback do médico querendo visibilidade da supressão de
   colonoscopia no cenário combinado.
3. **Polimento NIR/consistência** — pinar em teste o texto do
   `reason_text` dos reasons de revisão (agora incluindo o sufixo de origem
   do item 1 — regressões de copy devem quebrar teste). *(A label traduzida
   de seção no card caiu: sem listagem, não há o que traduzir; a origem
   traduzida vive agora no motivo.)*
   *Gatilho:* oportunidade de polimento ou feedback NIR de legibilidade.

## Impacto por item (estimado)

- Item 1 (executado): `apps/pipeline/procedure_reconciliation.py` (sufixo de
  origem no reason_text) + `apps/intake/views.py` +
  `templates/intake/case_detail.html` (remoção da listagem) + testes
  (`test_report_body_clues.py`, `test_exam_type_correction.py`) — 5 arquivos.
- Item 2 (ancoragem): `apps/pipeline/scope_detection.py` +
  `test_report_body_clues.py` (2 arquivos; QUICK/slice único).
- Item 3 (avisos múltiplos): `apps/doctor/presenters.py` + teste de copy
  (2 arquivos).
- Item 4 (polimento): testes de copy/payload (≤2 arquivos).

## Não-goals

- Variantes ortográficas de retossigmoidoscopia e vocabulário novo
  (`plasma de argonio`, `APC`, `PEG`, sítios de dilatação) — continuam fora,
  como no change pai (exigem design próprio de risco de falso positivo).
- Rework do extrator do Motivo; cadeia fechada `_REQUEST_LIST_TERM_SOURCE`.
- Qualquer implementação antes da evidência do smoke do rc.

## Sucesso

- Backlog rastreável pós-arquivamento do change pai (este change é a fonte
  única dos residuals conhecidos).
- Cada item, quando acionado, executa com contexto zero (gatilho + escopo +
  blast radius aqui registrados; slice detalhado na hora).
