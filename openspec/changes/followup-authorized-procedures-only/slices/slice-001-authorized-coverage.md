# Slice 001 — Cobertura de follow-up restrita a rows autorizadas

## Objetivo

O follow-up de um caso decidido cobre somente as rows `CaseProcedure`
autorizadas: validador aceita POST sem desfecho para rows negadas (troca ou
aprovação parcial), formulário exibe apenas blocos autorizados, evento espelha
somente o que foi gravado, e versões históricas exaustivas continuam
renderizando intactas no histórico/CSV.

## Contexto necessário

- `docs/adr/ADR-0007-cobertura-de-follow-up-restrita-a-procedimentos-autorizados.md`
- `design.md` deste change (D1–D6)
- Delta spec `specs/supervisor-appointment-follow-up/spec.md` deste change
- Fontes: `apps/cases/followup.py` (`_validate_outcomes`,
  `record_case_follow_up`), `apps/dashboard/views.py` (`followup_form`,
  `_followup_procedure_order`), `apps/cases/models.py`
  (`CaseProcedure.doctor_disposition`, `ProcedureFollowUp`)
- Como construir caso de troca em teste: ver
  `apps/doctor/tests/test_specialized_procedure_swap.py` (troca persiste
  origem `denied` + destino `approved` atomicamente) e
  `apps/dashboard/tests/test_followup_form_view.py` (fixtures de elegibilidade)

## Requisitos verificáveis

- **R1:** `_validate_outcomes` deriva o universo das rows
  `doctor_disposition == "approved"`; cobertura exigida apenas sobre elas;
  desfecho para row não autorizada é rejeitado (fail-closed); regras
  condicionais de causa permanecem idênticas.
- **R2:** `followup_form` constrói blocos somente das rows autorizadas, na
  ordem canônica (`_followup_procedure_order`); estado defensivo sem rows
  autorizadas mostra aviso (sem campos) e rejeita POST.
- **R3:** caso de troca (EDA negada + Ecoendoscopia autorizada): POST cobrindo
  somente a Ecoendoscopia cria versão 1 com uma `ProcedureFollowUp` e evento
  `FOLLOWUP_RECORDED` espelhando somente a row autorizada; aprovação parcial
  (EDA aprovada + Colonoscopia negada) idem.
- **R4:** versão histórica exaustiva (gravada antes da mudança, cobrindo row
  negada) continua renderizando por completo no histórico/CSV; nova versão
  (update) de caso legado segue a regra nova (apenas rows autorizadas).
- **R5:** nenhum arquivo de modelo/migration é criado ou alterado; nenhuma
  reescrita de dados.

## Escopo e blast radius

```yaml
expected_files:
  - apps/cases/followup.py
  - apps/dashboard/views.py
  - apps/cases/tests/test_followup_services.py
  - apps/dashboard/tests/test_followup_form_view.py
  - apps/dashboard/tests/test_followup_history.py
allowed_incidental_files:
  - apps/dashboard/tests/test_followup_list_view.py
file_cap: 6
out_of_scope:
  - modelo/migrations de follow-up e backfill
  - analytics/manager, filas CHD/NIR/doctor (change ativo)
  - marcador visual de "não autorizado" no formulário (disparidade vive na
    camada de decisão — ADR-0007)
  - novas categorias de desfecho
```

Escalar antes de editar se: precisar tocar qualquer arquivo fora da lista;
descobrir que a mudança exige migration; ou encontrar ambiguidade na spec.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `apps/cases/followup.py` | `test_followup_services.py`: troca sem desfecho da negada aceita; parcial idem; desfecho para negada rejeitado; caso sem aprovadas rejeitado; causais intactos |
| R2/R3 | `apps/dashboard/views.py` | `test_followup_form_view.py`: GET exibe só bloco autorizado (troca e parcial); POST aceito cria versão+evento só com autorizada; zero-aprovadas → aviso+POST rejeitado |
| R4 | `test_followup_history.py` | versão legada exaustiva renderiza íntegra (tabela/CSV); update cria v2 só com autorizadas; listagem não regrediu |
| R5 | — | `git status --short` sem migrations novas; diff não toca `models.py` |

## RED

1. Escrever primeiro os novos testes (serviço + formulário + histórico).
2. Comando: `uv run pytest apps/cases/tests/test_followup_services.py apps/dashboard/tests/test_followup_form_view.py -q`
3. Falha esperada (antes da implementação): os testes novos de troca/parcial
   falham por **assertion/ValueError de cobertura** — hoje o validador exige
   desfecho para a row negada e o formulário exibe bloco dela. Falha de
   import/collection **não** vale como RED.

## GREEN / verificação local

- Mesmo comando do RED com exit code 0.
- `uv run pytest apps/cases/tests/test_followup_services.py apps/dashboard/tests/test_followup_form_view.py apps/dashboard/tests/test_followup_history.py -q` — exit 0.
- `uv run pytest apps/cases apps/dashboard -q` — exit 0 (regressão dos módulos).
- `uv run ruff check apps/cases/followup.py apps/dashboard/views.py` e `uv run ruff format --check` nos mesmos — exit 0.
- `uv run mypy apps/cases/followup.py apps/dashboard/views.py` — exit 0.
- `git status --short` — nenhum arquivo de migration; diff limitado ao blast radius.

## Critérios de aceitação

- [ ] R1–R5 provados com RED→GREEN.
- [ ] Caso simples (todas as rows aprovadas) tem comportamento idêntico ao atual (regressão verde).
- [ ] Nenhuma migration; nenhum dado reescrito.
- [ ] Histórico de era mista renderiza como gravado.

## Handoff

Gerar `REPORT_PATH=/tmp/followup-authorized-procedures-only-slice-001-report.md`.
Parar.
