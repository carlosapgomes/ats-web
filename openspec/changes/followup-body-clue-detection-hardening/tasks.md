# Tasks: Hardening pós-rc da detecção de pistas no corpo do relatório

## 0. Precondições do change

- [ ] 0.1 `detect-report-body-procedure-clues` implantado como rc (incluindo
  o passo operacional `seed_prompts`) e smoke em andamento com os três
  sinais monitorados: (i) volume de `conflicting_procedure_evidence`;
  (ii) casos de `exam_type_mismatch` com pista da família no card;
  (iii) zero `PIPELINE_FAILED`.
- [ ] 0.2 Ao acionar o PRIMEIRO item: criar branch a partir do main vigente,
  registrar `BASE_REF` e baseline verde conhecida (suíte completa uma única
  vez, se a tree divergir do último gate registrado).

## 1. Itens condicionais (executar apenas sob o gatilho; ordem por valor)

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
