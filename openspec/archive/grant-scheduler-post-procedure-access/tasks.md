# Tasks — Pós-Procedimento para o Agendador

**Change:** `grant-scheduler-post-procedure-access`
**Estado:** S1 e S2 aceitos; gate final verde; pronto para revisão humana final. Sem push, merge, archive ou deploy.
**BASE_REF de investigação:** `befc5c50c0499acd86ed0e3d29a97380ab95f70c`.

As decisões do solicitante permanecem em `proposal.md`. Aplicação de `openspec-vertical-change-writer`: **dois slices verticais**, cada um com autorização, interface, testes e documentação do próprio fluxo. A justificativa e o estado intermediário estão em `design.md`, D6. As deltas descrevem o alvo após S2; não promover nem declarar o change concluído em S1.

## 0. Preflight de implementação

- [x] 0.1 Reconstruir contexto por `AGENTS.md`, `PROJECT_CONTEXT.md`, proposal/design/deltas e contrato S1; verificar branch/tree e mudanças concorrentes. Registrar baseline dos gates e focused de S1, distinguindo falhas preexistentes de regressões.

## 1. Slices verticais — executar em sequência

- [x] 1.1 **S1 — Pesquisar, registrar e atualizar desfechos, sem acesso gerencial.** Contrato: [`slices/slice-001-scheduler-post-procedure.md`](slices/slice-001-scheduler-post-procedure.md). Verificar S1.R1–R6: RED/GREEN da política/menu/lista/formulário; elegíveis globais e versões entre autores; navegação operacional; negativas gerenciais/rede; histórico analítico/CSV ainda bloqueados e sem link para scheduler; manual/contexto/testes do comportamento parcial. Relatório: `/tmp/sirhosp-slice-001-report.md`.
- [x] 1.2 **S2 — Consultar histórico, resumos e filtros e exportar CSV.** Depende de S1 aceito e confirmação para continuar. Contrato: [`slices/slice-002-scheduler-followup-history-export.md`](slices/slice-002-scheduler-followup-history-export.md). Verificar S2.R1–R5: RED no estado aceito de S1; liberação dos dois endpoints e sub-aba operacional; paridade de dados/filtros/CSV; corrente apenas e zero writes; remoção do comportamento transitório e documentação completa; regressão do registro e do isolamento. Relatório: `/tmp/sirhosp-slice-002-report.md`.

## 2. Integração final do change

- [x] 2.1 Após S2, conferir focused cumulativo e gates globais de `AGENTS.md`, `openspec validate grant-scheduler-post-procedure-access --strict --no-interactive` e percurso completo menu → busca → registro/atualização → histórico → CSV → negativa gerencial; registrar comandos/exit codes e evidências, sem adiar testes dos slices para este gate.
- [x] 2.2 Revisar cobertura das duas deltas, relatórios e ausência de condição/texto/teste transitório de S1. Antes do arquivamento, decidir/registrar necessidade de ADR para a ampliação da política de acesso e atualizar o Purpose das duas specs canônicas ao promover as deltas. Manter aberto enquanto houver bloqueios; este plano não autoriza merge, archive, release ou deploy.

## Evidências de execução

- Preflight: duas falhas de testes preexistentes corrigidas com autorização explícita; commit `9f7e332`, revisão independente válida e baseline completo de 4.755 testes passando.
- S1: aceito pelo controlador em 2026-11-13, revisão independente `OK with notes` (1/2 rodadas, zero P0/P1); focused 1.013 e suite global 4.793 passando, lint/format/mypy/OpenSpec verdes. Dois P2 de profundidade dos testes registrados sem reabrir implementação. Receipt: `/tmp/pi-openspec-ats-web-grant-scheduler-post-procedure-access-78x58z1s/slices/001/acceptance.json`; relatórios de implementação/revisão e logs no mesmo subtree externo. Smoke visual não executado; runtime via Django client verificado conforme contrato.

- S2: aceito pelo controlador em 2026-11-13, revisão independente `OK with notes` (1/2 rodadas, zero P0/P1); focused 1.024 e suite global 4.804 passando, lint/format/mypy/OpenSpec verdes. P2 de comentário transitório em teste, profundidade de paridade/imutabilidade e realismo do ator de agendamento registrados sem reabrir implementação. Receipt: `/tmp/pi-openspec-ats-web-grant-scheduler-post-procedure-access-78x58z1s/slices/002/acceptance.json`; logs/relatórios no mesmo subtree. Runtime via Django client verificado; smoke visual não executado.

- Gate final adicional, executado pelo controlador após os commits dos slices: suite completa **4.804 passed**, focused cumulativo **1.024 passed**, ruff check/format, mypy, Django check e OpenSpec strict verdes, todos com exit 0 e sem mutação autoral. Logs/manifest/results: `/tmp/pi-openspec-ats-web-grant-scheduler-post-procedure-access-78x58z1s/final-gates/initial/`. Nenhum ciclo de reparo final necessário.
- Revisão final de escopo: deltas/contratos preservados, isolamento gerencial e rede mantidos; notas P2 não bloqueantes permanecem no checkpoint. O registro de política de acesso em ADR é recomendado antes de um futuro arquivamento; criação/aceite dessa ADR e atualização de Purpose na promoção das specs são condições futuras, não executadas nem autorizadas aqui. O checkbox 2.2 registra a revisão/rastreabilidade da execução, não afirma archive ou promoção canônica.
- Condição pré-arquivamento cumprida em 2026-11-13 com autorização explícita do owner: **ADR-0013** (`docs/adr/ADR-0013-ampliacao-acesso-pos-procedimento-agendador.md`, Accepted) registra a ampliação da política de acesso; arquivamento do change com promoção das deltas às specs canônicas e atualização do Purpose de `supervisor-appointment-follow-up` e `supervisor-followup-history` executados na mesma data, após a publicação de `v0.11.0-rc.1`.

## Rastreabilidade das specs para as entregas

| Contrato final | Primeira evidência / conclusão |
| --- | --- |
| Registro por procedimento, busca de todos os elegíveis e versões entre papéis | S1.R2–R3; regressão em S2.R4 |
| Matriz de acesso e navegação operacional de lista/formulário | S1.R1–R2; ampliação para histórico/CSV em S2.R1–R2 |
| Dashboard e demais superfícies continuam negados; rede inalterada | S1.R4–R5; regressão em S2.R4 |
| Duas sub-abas disponíveis e histórico/CSV com paridade | S2.R1–R3; em S1 indisponibilidade explícita em S1.R1–R2 |
| Manual/contexto/testes de documentação | S1.R6 (parcial real) e S2.R5 (contrato completo) |

## Validação do planejamento

Validar após qualquer edição: `openspec validate grant-scheduler-post-procedure-access --strict --no-interactive`. Conferir que ambos os contratos existem, os links resolvem e nenhum item de implementação foi marcado como concluído. O status OpenSpec de artefatos completos indica **planejamento**, não feature entregue.

Não foram executados gates Python ou smoke da aplicação neste redimensionamento; nenhuma alteração de código ou spec foi necessária.

## Handoff

**Nenhum slice de implementação restante nesta execução.** S1 e S2 foram aceitos em sequência pelo controlador, com revisões independentes e gates completos; evidências externas e commits estão no checkpoint `/tmp/pi-openspec-ats-web-grant-scheduler-post-procedure-access-78x58z1s/controller-state.json`. Próxima ação: revisão humana final. Não iniciar outro change ou executar push, merge, archive/promoção de specs, publicação ou deploy sem autorização separada.
