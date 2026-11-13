# Tasks — Pós-Procedimento para o Agendador

**Change:** `grant-scheduler-post-procedure-access`
**Estado:** S1 e S2 aceitos; gate final do change pendente.
**BASE_REF de investigação:** `befc5c50c0499acd86ed0e3d29a97380ab95f70c`.

As decisões do solicitante permanecem em `proposal.md`. Aplicação de `openspec-vertical-change-writer`: **dois slices verticais**, cada um com autorização, interface, testes e documentação do próprio fluxo. A justificativa e o estado intermediário estão em `design.md`, D6. As deltas descrevem o alvo após S2; não promover nem declarar o change concluído em S1.

## 0. Preflight de implementação

- [x] 0.1 Reconstruir contexto por `AGENTS.md`, `PROJECT_CONTEXT.md`, proposal/design/deltas e contrato S1; verificar branch/tree e mudanças concorrentes. Registrar baseline dos gates e focused de S1, distinguindo falhas preexistentes de regressões.

## 1. Slices verticais — executar em sequência

- [x] 1.1 **S1 — Pesquisar, registrar e atualizar desfechos, sem acesso gerencial.** Contrato: [`slices/slice-001-scheduler-post-procedure.md`](slices/slice-001-scheduler-post-procedure.md). Verificar S1.R1–R6: RED/GREEN da política/menu/lista/formulário; elegíveis globais e versões entre autores; navegação operacional; negativas gerenciais/rede; histórico analítico/CSV ainda bloqueados e sem link para scheduler; manual/contexto/testes do comportamento parcial. Relatório: `/tmp/sirhosp-slice-001-report.md`.
- [x] 1.2 **S2 — Consultar histórico, resumos e filtros e exportar CSV.** Depende de S1 aceito e confirmação para continuar. Contrato: [`slices/slice-002-scheduler-followup-history-export.md`](slices/slice-002-scheduler-followup-history-export.md). Verificar S2.R1–R5: RED no estado aceito de S1; liberação dos dois endpoints e sub-aba operacional; paridade de dados/filtros/CSV; corrente apenas e zero writes; remoção do comportamento transitório e documentação completa; regressão do registro e do isolamento. Relatório: `/tmp/sirhosp-slice-002-report.md`.

## 2. Integração final do change

- [ ] 2.1 Após S2, conferir focused cumulativo e gates globais de `AGENTS.md`, `openspec validate grant-scheduler-post-procedure-access --strict --no-interactive` e percurso completo menu → busca → registro/atualização → histórico → CSV → negativa gerencial; registrar comandos/exit codes e evidências, sem adiar testes dos slices para este gate.
- [ ] 2.2 Revisar cobertura das duas deltas, relatórios e ausência de condição/texto/teste transitório de S1. Antes do arquivamento, decidir/registrar necessidade de ADR para a ampliação da política de acesso e atualizar o Purpose das duas specs canônicas ao promover as deltas. Manter aberto enquanto houver bloqueios; este plano não autoriza merge, archive, release ou deploy.

## Evidências de execução

- Preflight: duas falhas de testes preexistentes corrigidas com autorização explícita; commit `9f7e332`, revisão independente válida e baseline completo de 4.755 testes passando.
- S1: aceito pelo controlador em 2026-11-13, revisão independente `OK with notes` (1/2 rodadas, zero P0/P1); focused 1.013 e suite global 4.793 passando, lint/format/mypy/OpenSpec verdes. Dois P2 de profundidade dos testes registrados sem reabrir implementação. Receipt: `/tmp/pi-openspec-ats-web-grant-scheduler-post-procedure-access-78x58z1s/slices/001/acceptance.json`; relatórios de implementação/revisão e logs no mesmo subtree externo. Smoke visual não executado; runtime via Django client verificado conforme contrato.

- S2: aceito pelo controlador em 2026-11-13, revisão independente `OK with notes` (1/2 rodadas, zero P0/P1); focused 1.024 e suite global 4.804 passando, lint/format/mypy/OpenSpec verdes. P2 de comentário transitório em teste, profundidade de paridade/imutabilidade e realismo do ator de agendamento registrados sem reabrir implementação. Receipt: `/tmp/pi-openspec-ats-web-grant-scheduler-post-procedure-access-78x58z1s/slices/002/acceptance.json`; logs/relatórios no mesmo subtree. Runtime via Django client verificado; smoke visual não executado.

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

Próximo trabalho implementável: **somente S1**, após preflight. Cada contrato é autocontido, com R numerados, evidência RED, critérios binários, condições de escalada e prompt para worker fresh. Aplicam-se os gates, entrega/relatório e a stop rule do repositório. O sucessor recebe S1 aceito e seu relatório, não o contexto desta conversa. Sem execução de S2 na mesma passagem, sem escopo novo de concorrência, URLs ou rede.
