# Tasks: Detecção de pistas de procedimentos no corpo do relatório

## 0. Precondições do change

- [x] 0.1 Criar `feature/detect-report-body-procedure-clues` a partir do
  `main`, registrar `BASE_REF` e confirmar working tree adequada (idem
  convenção do change anterior: baseline confiável = gate pós-merge do main;
  reexecutar suíte completa só se a tree divergir). Neste host o pytest exige
  `POSTGRES_TEST_HOST_PORT=55433` (porta 5433 pertence a outro projeto).
  *(BASE_REF `212014d`; working tree limpa exceto `.pi/reports/*` não
  rastreados por convenção e o diretório do change. A tree do main DIVERGIU
  do último gate registrado (rc.1): o merge das affordances visuais
  (`212014d`) veio depois, sem gate pós-merge registrado — suíte completa
  executada uma única vez como baseline: ruff `All checks passed!`, format
  `290 files already formatted`, mypy `Success: no issues found in 320
  source files`, pytest `4456 passed` (146,55 s), node combobox `16 pass /
  0 fail`. Banco de testes `ats-web-test-db-1` healthy na 55433.)*
- [x] 0.2 `openspec validate --strict detect-report-body-procedure-clues`
  verde antes do primeiro slice.
  *(Verde após 5 rodadas de review independente com emendas — última
  execução pós-emenda final; specs delta `procedure-neutral-analysis` e
  `exam-type-correction` validam em `--strict`.)*

## 1. Slices

- [x] 1.1 Implementar o Slice 001
  (`slices/slice-001-justificativa-section-context.md`): seção
  `Justificativa da Transferência` como contexto de solicitação atual no
  detector (upgrade `mention`→`current_request` dentro do span da seção,
  campo `section` na ocorrência incluindo a marcação do campo Motivo,
  correção habilitante de offsets absolutos de cláusula,
  negações/históricos intocados).
  *(2 rodadas de review; rodada 1 `BLOCK` com 1 P1 — fixture do Motivo sem
  terminador `Unid.` e sem assert do endpoint do span — corrigido com
  fixture reordenada ao layout real + testes discriminantes do endpoint e
  de ocorrência pós-`Unid. Origem`; rodada 2 `OK with notes`. P2 adiados:
  terminadores de seção casam como substring sem exigir `:` — risco
  fail-safe documentado; variação ambígua promovida pela seção e demovida
  pelo vínculo local (interação coberta no Slice 002). Focado: 192 passed,
  ruff/format ok, mypy apps/pipeline ok.)*
- [x] 1.2 Implementar o Slice 002
  (`slices/slice-002-via-link-separators.md`): conectores `via`/`por`/
  `atraves de`/`com uso de` no vínculo variação↔base; o
  relatório-exemplo passa a detectar `rectosigmoidoscopy_dilation` atual.
  *(1 rodada de review, veredito `OK` sem achados; RED confirmado com 5
  falhas pelos motivos previstos; regressão 204 passed incluindo os testes
  de vínculo ausente e colédoco sem edição; suíte completa executada pelo
  worker como segurança extra: 4491 passed; ruff/format/mypy ok. P2
  adiados: nenhum deste slice.)*
- [x] 1.3 Implementar o Slice 003
  (`slices/slice-003-family-umbrella-precedence.md`): precedência
  `family_umbrella_over_colonoscopy` na reconciliação — caso corrigido para
  `rectosigmoidoscopy_dilation` reprocessa e prossegue (fim do loop de
  revisão); declarado `colonoscopy` vira `exam_type_mismatch` claro.
  *(1 rodada de review, veredito `OK` sem achados; guarda de não-vacuidade
  do worker (>=1 ocorrência current de colonoscopy em vez de all() vacuo)
  endossada pelo reviewer frente a D6; dict de precedência preservado +
  campo aditivo procedure_precedence_rules fiado nos 3 destinos;
  presenter com copy própria da família; 1 teste do Slice 001 editado com
  justificativa (desfecho mismatch previsto no R3, intenção preservada);
  187 passed nas suítes de regressão + suíte completa 4501 passed pelo
  worker; ruff/format/mypy ok. 5 dos 6 arquivos orçados.)*
- [x] 1.4 Implementar o Slice 004
  (`slices/slice-004-structured-item-conflict-gate.md`): item estruturado do
  LLM1 contraditado por ocorrência não-atual gera
  `nir_review`/`conflicting_procedure_evidence` (nunca `proceed`
  silencioso); reason code elegível para correção no intake.
  *(1 rodada de review, veredito `OK` sem achados. 2 desvios aprovados
  pelo parent durante a implementação (escalonamento do worker, sem nova
  decisão de produto): (a) correção de blast radius — a chave por tipo
  `conflicting` (design D4, todos os tipos) exige ajustar literals de
  igualdade exata de dict em test_eda_package_pipeline_v4.py (6) e
  test_gastrostomy_infection_review.py (3), além dos in-scope (10+6);
  (b) 3 testes de integração que codificavam o contrato antigo "item
  contraditado = invisível" tiveram SOMENTE outcomes ajustados ao novo
  contrato da spec (reason/detected/detection_status; fixtures
  preservados). Focado: 265 passed; suíte completa 4509 passed; ruff/
  format/mypy ok. Nota residual: união fora da matriz pula projeção e
  deixa rows pending — consequência documentada da guarda de projeção.)*
- [x] 1.5 Implementar o Slice 005
  (`slices/slice-005-nir-review-body-clues.md`): payload de revisão 2.1 com
  `detected_body_clues` e card de correção exibindo as pistas no momento da
  seleção do novo conjunto.
  *(1 rodada de review, veredito `OK` sem achados; desvio menor documentado:
  reuso do constant _MOTIVO_DA_SOLICITACAO_SECTION já existente em
  procedure_reconciliation.py (Slice 003) em vez de import de
  scope_detection — evita acoplamento e mantém o blast radius; seção
  renderizada como identificador canônico (justificativa_da_transferencia),
  sem section_label traduzida — nota P2 potencial de UX futura. Template
  só com classes Bootstrap existentes (verificado por grep de classes no
  diff); Focado: 232 passed; suíte completa 4526 passed; ruff/format/mypy
  ok.)*

- [x] 1.6 Implementar o Slice 006
  (`slices/slice-006-llm1-body-section-prompt.md`, emenda aprovada pelo
  usuário): prompt LLM1 v4 instrui que Justificativa da Transferência e
  Complemento da Solicitação são fontes legítimas de solicitação atual, com
  field_path canônicos recomendados — guidance no conteúdo canônico (nova
  versão via seed) e no sufixo sempre anexado do renderizador; guardrails
  preservados; deploy exige re-rodar seed_prompts.
  *(1 rodada de review, veredito `OK` sem achados; desvio menor documentado:
  teste de bump do seed renomeado/estendido para os 4 nomes neutros (adapt/
  extend, semântica llm2 inalterada); RED com 4 falhas pelos motivos
  previstos; focado 182 passed + apps/pipeline+apps/llm 841 passed; ruff/
  format/mypy ok. Risco residual: comportamento do modelo valida-se no rc
  (versão de prompt por evento para atribuição); janela deploy→seed coberta
  pelo sufixo garantido.)*

## 2. Gate final e encerramento

- [x] 2.1 Gate global: `uv run ruff check . && uv run ruff format --check .`
  e `uv run mypy .` e `POSTGRES_TEST_HOST_PORT=55433 uv run pytest`.
  *(Re-executado após a emenda do Slice 006: ruff `All checks passed!`;
  format `291 files already formatted`; mypy `Success: no issues found in
  321 source files`; pytest `4530 passed` (152,18 s; baseline 4456 → +74
  testes do change; primeira execução pós-slices 001-005: 4526 passed);
  node combobox `16 pass / 0 fail`; `openspec validate --strict` válido.)*
- [x] 2.2 `openspec validate --strict` do change; commit dos artefatos de
  planejamento junto ao encerramento (política do projeto).
  *(`Change is valid` em --strict; deltas de spec
  `procedure-neutral-analysis` e `exam-type-correction` entregues no diretório
  do change — promoção aos specs acontece no arquivamento, fora deste fluxo.)*
- [x] 2.3 Relatório sumário do change para avaliação antes do arquivamento.
  *(Relatório consolidado entregue na sessão do planner: slices, rodadas de
  review, commits f7990bf/b065832/b40e1ed/78a5420/e48d2f2/5383d64,
  validações, P2s adiados e desvios documentados.)*
- [x] 2.4 Backlog pós-rc registrado em change dedicado
  `followup-body-clue-detection-hardening` (3 itens gated por gatilhos do
  smoke: ancoragem de terminadores, avisos múltiplos de precedência ao
  médico, polimento de label/copy). Avaliação de risco documentada lá:
  nenhum item bloqueia o deploy do rc.
