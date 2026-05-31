# Tasks: Observação médica opcional no caso

## Status

Change concluído em 3 slices verticais com relatórios temporários, testes e quality gates por slice.

## Slices

- [x] Slice 001 — Captura e persistência da observação médica (`slices/slice-001-captura-persistencia-observacao-medica.md`)
- [x] Slice 002 — Visibilidade para NIR, supervisor e admin (`slices/slice-002-visibilidade-nir-supervisor-admin.md`)
- [x] Slice 003 — Visibilidade para agendador (`slices/slice-003-visibilidade-agendador.md`)

## Definition of Done do Change

- [x] Campo `Case.doctor_observation` opcional criado com limite de 500 caracteres.
- [x] Migration criada e testada.
- [x] Formulário de decisão médica exibe campo opcional de observação.
- [x] Formulário aceita observação vazia.
- [x] Formulário rejeita observação acima de 500 caracteres.
- [x] Submit médico persiste a observação no caso.
- [x] NIR vê badge nos cards quando há observação médica.
- [x] NIR vê texto completo no detalhe do caso.
- [x] Manager/admin veem texto completo no detalhe do caso via dashboard.
- [x] Agendador vê badge na fila quando há observação médica.
- [x] Agendador vê texto completo na tela de confirmação/ciência operacional.
- [x] Casos sem observação não exibem badge nem card vazio.
- [x] Testes relevantes adicionados/atualizados em cada slice.
- [x] Quality gate do `AGENTS.md` executado em cada slice ou justificativa registrada quando parcial.
- [x] Relatório temporário de cada slice gerado e `REPORT_PATH` informado.
- [x] Commit e push realizados por slice.
