# Tasks: Exibir médico responsável e CRM downstream

## Status

Change criado para implementação por outro LLM com contexto zero.

## Slices

- [x] Slice 001 — Exibir médico responsável/CRM para NIR e Agendador (`slices/slice-001-doctor-registration-downstream-ui.md`)
  - Commit: `a85fd3e` — feat(cases): show deciding doctor downstream
  - Follow-up quick fix: `<NOVO_HASH>` — fix(intake): show terminal appointment denial correctly
  - Report: `/tmp/ats-web-slice-001-doctor-registration-downstream-ui-report.md`

## Definition of Done do Change

- [x] Existe helper padronizado para nome do usuário e registro profissional.
- [x] Existe helper padronizado para exibir o médico responsável no `Case`.
- [x] NIR vê médico responsável nos cards/listagem de "Meus Casos".
- [x] NIR vê médico responsável no detalhe/resultado final para recusa, vinda imediata, agendamento confirmado e agendamento negado.
- [x] Agendador vê médico responsável na fila de agendamento.
- [x] Agendador vê médico responsável no bloco de vinda imediata.
- [x] Agendador vê médico responsável na tela de confirmação.
- [x] Quando há CRM cadastrado, aparece `Nome — CRM 12345`.
- [x] Quando não há CRM cadastrado, aparece ao menos `Nome`.
- [x] Testes relevantes adicionados/atualizados.
- [x] Quality gate do `AGENTS.md` executado.
- [x] Relatório temporário do slice gerado e `REPORT_PATH` informado.
- [x] Commit e push realizados.
