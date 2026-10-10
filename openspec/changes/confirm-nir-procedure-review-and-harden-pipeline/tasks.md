# Tasks — Confirmação NIR e pipeline seguro

Planejamento via `openspec-vertical-change-writer`. Execução autorizada pelo owner via change-loop em 2026-10-09. Uma change, **dois slices verticais**; ordem por risco. O controller avança automaticamente apenas após aceite do slice anterior, sem push/merge/archive/deploy.

## 0. Contrato e precondições

- [x] 0.1 Owner revisar/aceitar ADR-0012 e design D1–D9 antes da implementação da autoridade humana; evidência: aceite técnico explícito do owner em 2026-10-09: “confirmo o aceite técnico da ADR-0012 e do design D1–D9 e autorizo registrar 0.1 como concluida”. ADR-0012 registrada como Accepted. A autorização change-loop cobre S1 e S2 na ordem aprovada, sujeitos a review/aceite, sem autorização de publicação.

O produto está aprovado nesta conversa; esta task registra revisão do contrato técnico, não reabre a discussão da autoridade humana. S1 não depende da política nova. Gates/DoD e responsabilidades permanentes permanecem em AGENTS.md. Owner/controller atualiza tasks após review, faz commit/push e informa relatório; worker não altera esses artefatos de controle.

## 1. S1 — Artefato não persistível tem desfecho confiável

- [x] 1.1 Implementar somente S1 com TDD, guard de U+0000, handler limpo e propagação de falha secundária; verificar R1–R6 do contrato, testes PostgreSQL/fault-injection e Linha do Tempo com PIPELINE_FAILED; entregar relatório READY_FOR_REVIEW.
  Contract: `slices/slice-001-persistable-output-and-auditable-failure.md`.
  Aceite do controller: S1 ACCEPTED após 2 rodadas fresh; segunda revisão `OK with notes`, sem P0/P1/P2 pendentes. Bloqueadores de concorrência/atomicidade e diagnóstico com chave NUL corrigidos. PostgreSQL real: rejeição→handler, rollback de desfecho parcial e conflito de row lock em conexões separadas; SSR de falha e fronteira task provados. Gate do parent na versão reparada: `uv run pytest` **4645 passed**, ruff/check-format/mypy/diff-check PASS. Relatório: `/tmp/sirhosp-slice-001-report.md`; recibo: `/tmp/ats-web-confirm-nir-execution/slice-001/receipt.md`. Marcação pelo daemon django-q2 inferida da propagação síncrona, não observada em worker ao vivo.

Documentação e testes desta unidade fazem parte do próprio S1. A evidência deve demonstrar que o handler não retorna sucesso com desfecho não persistido, não apenas que uma função detecta NUL.

## 2. S2 — Revisão humana define análise e fica visível

- [x] 2.1 Após S1 aceito e confirmação explícita do owner, implementar S2 end-to-end: mesmo/outro procedimento, consentimento/fonte/reserva, eventos/linha do tempo, conjunto fechado/policy e aviso médico; verificar R1–R10 com fixtures sintéticas, SSR/no-JS e regressões; entregar relatório READY_FOR_REVIEW.
  Contract: `slices/slice-002-human-confirmation-to-doctor-with-timeline.md`.
  Aceite do controller: S2 ACCEPTED após 2 rodadas + exceção P2 autorizada pelo owner. Round-1 BLOCK (consentimento truthy + justificativa na URL); round-2 `OK with notes`, zero P0/P1, um P2 (lease/token sem preservação da tentativa). Exceção autorizada: reparo mínimo nos 2 ramos + 5 testes de regressão, revisão extra restrita `OK`, sem P0/P1. Parent reexecutou focados: 35 + 73 passed, ruff/check-format PASS, diff-check clean, sem mutação do reviewer. Relatórios: `/tmp/sirhosp-slice-002-report.md` e `/tmp/sirhosp-slice-002-p2-repair-report.md`; revisão final: `/tmp/ats-web-confirm-nir-execution/slice-002/review-round-2/final-independent-review.md`.

Blast radius transversal >5 arquivos aprovado no design D9: nenhuma saída parcial “só botão”/“só backend” conta como conclusão. Testes e manual do usuário atualizados no S2, não adiados ao gate final.

## 3. Gate integrado do change — owner/controller

- [x] 3.1 Revisar evidências S1+S2 e rodar gates globais AGENTS.md + `openspec validate confirm-nir-procedure-review-and-harden-pipeline --strict --no-interactive`; verificar autoridade humana não dispensa guard/erro do S1 e que legados sem consentimento permanecem automáticos; registrar resultado em relatório de fechamento.
  Gate do controller em dc42cb8: `uv run pytest` **4708 passed** (177.53s); ruff check/format PASS (303 arquivos); mypy PASS (333 arquivos); openspec strict valid; diff-check clean. Confirmação humana não dispensa policy S1 (CPRE negada sem imagem, NUL falha segura) e legados sem consentimento seguem automáticos (R10 verde, sem backfill). Relatório: `/tmp/ats-web-confirm-nir-execution/change-closure-report.md`. Status: READY_FOR_HUMAN_FINAL_REVIEW; sem push/deploy/recuperação de produção.

Este gate não cria terceiro slice de implementação nem substitui testes próprios de S1/S2. Publicação/deploy e recuperação dos UUIDs reais NÃO fazem parte da autorização desta etapa. Atualizar PROJECT_CONTEXT/specs canônicas apenas no momento apropriado de execução/archive, sem afirmar implantação antes dela.

## Mapa de requisitos e evidência

| Contrato | Delta / design | Evidência obrigatória |
| --- | --- | --- |
| S1 R1–R2 | procedure-neutral-analysis: persistibilidade; D7 | Unit recursivo + E2E LLM1/LLM2 antes de writes |
| S1 R3–R4 | procedure-neutral-analysis: falha auditável; D7 | PostgreSQL rejeitando save + falha no handler propagada ao task |
| S1 R5–R6 | D7/D8 | estado concorrente não regredido; erros sem raw/SQL; regressões rc.10 |
| S2 R1–R3 | nir-procedure-review + exam-type-correction; D1–D3 | POST mesma/troca, consentimento, reserva, double submit/cleanup |
| S2 R4–R6 | procedure-neutral-analysis + combination-policy; D4–D5 | duas passadas → WAIT_DOCTOR, seleção ausente, conjunto LLM2 exato, policy negativa preservada |
| S2 R7–R8 | nir-procedure-review; D6 | HTML da Linha do Tempo/aviso médico, autor/labels/texto escapado e pós-encerramento |
| S2 R9–R10 | D2/D3/D8 | fonte/revisão stale, recovery enqueue, eventos legados sem autoridade e sem backfill |

## Revisão independente futura

Quando execução/review forem autorizados, reviewer com contexto fresh confere os testes e superfícies observáveis, não só o resumo do worker. Especial atenção: evento confirmado realmente consumido; escolha ausente do LLM1; NUL que derruba o próprio handler; timeline com autor e seleção, não só label genérico. Este planejamento não lança subagentes nem escolhe modelos.
