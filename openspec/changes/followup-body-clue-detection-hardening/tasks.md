# Tasks: Hardening pós-rc da detecção de pistas no corpo do relatório

## 0. Precondições do change

- [x] 0.1 `detect-report-body-procedure-clues` implantado como rc (incluindo
  o passo operacional `seed_prompts`) e smoke em andamento com os três
  sinais monitorados: (i) volume de `conflicting_procedure_evidence`;
  (ii) casos de `exam_type_mismatch` com pista da família no card;
  (iii) zero `PIPELINE_FAILED`.
  *(rc.2 implantado em produção em 2026-09-26T02:2xZ; cenário-alvo
  confirmado pelo dono com caso real: declarado colonoscopia → detectado
  Retossigmoidoscopia + Dilatação com mismatch limpo.)*
- [x] 0.2 Branch `feature/followup-body-clue-detection-hardening` a partir do
  `main` `49871f0` (BASE_REF); baseline verde conhecida = gate do rc.2
  (4530 passed) na mesma árvore de código — reexecutar suíte completa só se
  a tree divergir (divergiu apenas em docs).

## 1. Itens condicionais (executar apenas sob o gatilho; ordem por valor)

- [x] 1.0 **Simplificar card de revisão NIR (opção B do dono)**: remover a
  listagem de pistas do card; motivo da revisão informa a origem da detecção
  (seções das ocorrências atuais do conjunto detectado); payload
  `detected_body_clues` mantido para auditoria; spec delta atualizada
  (REMOVED do requisito de listagem + ADDED do motivo com origem).
  *Gatilho: feedback do dono no smoke do rc.2 (a listagem crua confundia).*
  *(1 rodada de review, veredito `OK` sem achados; sufixo aplicado
  uniformemente a TODOS os nir_review (conforme spec); focado 206 passed;
  suíte completa 4541 passed (baseline rc.2 4530, +11); ruff/format/mypy
  ok. Nota: o sufixo persiste no reason_text e aparece nas superfícies que
  exibem motivo — pretendido; pinnar copy segue no item de polimento.)*
- [ ] 1.1 **Ancorar terminadores de seção** (`:` ou início de linha) em
  `apps/pipeline/scope_detection.py` + `test_report_body_clues.py` — TDD com
  fixture multi-seção real contendo palavra-terminadora no meio da
  narrativa da Justificativa (hoje trunca o span).
  *Gatilho: smoke mostra caso-alvo em `proceed` sem detecção da família
  (span truncado).*
- [ ] 1.2 **Avisos múltiplos do médico** a partir de
  `procedure_precedence_rules` em `apps/doctor/presenters.py` + teste de
  copy — um aviso por redução aplicada (variação E família no cenário
  combinado).
  *Gatilho: feedback do médico.*
- [ ] 1.3 **Polimento NIR/consistência**: label traduzida da seção no card
  (`apps/intake/views.py` + `templates/intake/case_detail.html`) e
  `reason_text` de `conflicting_procedure_evidence` pinado em teste
  (payload/pipeline).
  *Gatilho: oportunidade de polimento ou feedback NIR.*

## 2. Gate final e encerramento (após quaisquer itens executados)

- [ ] 2.1 Gate global do repositório (ruff/format/mypy/pytest com
  `POSTGRES_TEST_HOST_PORT=55433`) + `openspec validate --strict` deste
  change; specs atualizadas conforme os itens entregues.
- [ ] 2.2 Se NENHUM gatilho disparar no horizonte do rc: registrar a decisão
  (ex.: "smoke limpo, itens arquivados por ausência de evidência") e
  arquivar este change sem implementação — registro explícito de que os
  residuals foram avaliados e não se materializaram.
