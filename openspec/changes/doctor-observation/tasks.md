# Tasks: Observação médica opcional no caso

## Status

Change criado para implementação por LLM com contexto zero.

## Slices

- [x] Slice 001 — Captura e persistência da observação médica (`slices/slice-001-captura-persistencia-observacao-medica.md`)
- [ ] Slice 002 — Visibilidade para NIR, supervisor e admin (`slices/slice-002-visibilidade-nir-supervisor-admin.md`)
- [ ] Slice 003 — Visibilidade para agendador (`slices/slice-003-visibilidade-agendador.md`)

## Definition of Done do Change

- [ ] Campo `Case.doctor_observation` opcional criado com limite de 500 caracteres.
- [ ] Migration criada e testada.
- [ ] Formulário de decisão médica exibe campo opcional de observação.
- [ ] Formulário aceita observação vazia.
- [ ] Formulário rejeita observação acima de 500 caracteres.
- [ ] Submit médico persiste a observação no caso.
- [ ] NIR vê badge nos cards quando há observação médica.
- [ ] NIR vê texto completo no detalhe do caso.
- [ ] Manager/admin veem texto completo no detalhe do caso via dashboard.
- [ ] Agendador vê badge na fila quando há observação médica.
- [ ] Agendador vê texto completo na tela de confirmação/ciência operacional.
- [ ] Casos sem observação não exibem badge nem card vazio.
- [ ] Testes relevantes adicionados/atualizados em cada slice.
- [ ] Quality gate do `AGENTS.md` executado em cada slice ou justificativa registrada quando parcial.
- [ ] Relatório temporário de cada slice gerado e `REPORT_PATH` informado.
- [ ] Commit e push realizados por slice.
