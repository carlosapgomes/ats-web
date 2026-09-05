# Tasks: Desabilitar causa quando realizado

## Slice vertical

- [x] Slice 001 — Fieldset de causa desabilitável + JS por radio performed (`slices/slice-001-disable-cause-when-performed.md`)

## Preflight

- [x] Working tree limpa em `main` @ `76ee230` (BASE_REF); produção em v0.6.0-rc.1 com dados íntegros (bug é só visual)

## Definition of Done

- [x] Com "Realizado" marcado, causa/submotivo/texto ficam desabilitados e desmarcados; voltar a "Não realizado" reabilita.
- [x] Template renderiza `data-followup-reason-section`; teste de template adicionado.
- [x] Suíte dashboard verde (358 passed); node --check ok.
- [x] Commit atômico + archive (ADR-0005) + push.

## Registro de execução

- Bug constatado em produção (v0.6.0-rc.1, ocorrência 4960219): dados no banco íntegros (server normaliza); falha puramente visual.
- Deviação aprovada pelo parent em execução: slice citava valores "True"/"False" para os radios performed; valores reais do ChoiceField são `"yes"`/`"no"` (worker verificou via shell render; slice corrigido).
- 1 rodada de review: **OK with notes** — P2 diferida: teste `reason_section` conta marcadores globalmente (não prova 1 por bloco/aninhamento).
