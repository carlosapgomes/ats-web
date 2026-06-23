# Tasks: Clarificar UX de escrita na decisão médica

## Slices verticais

- [x] Slice 001 — Decisão médica sem ambiguidade (`slices/slice-001-decisao-medica-sem-ambiguidade.md`)
- [ ] Slice 002 — Labels downstream alinhados (`slices/slice-002-labels-downstream-alinhados.md`)

## Definition of Done do change

- [ ] Campo visual de `doctor_observation` deixa de ser apresentado como observação médica genérica.
- [ ] Tela de decisão médica usa label `Orientações para agendamento/execução` ou equivalente explícito.
- [ ] Campo de orientação fica associado ao fluxo de aceite.
- [ ] UI orienta que pedido de documentos/dados deve usar comunicação operacional, não negativa.
- [ ] Botão de saída da decisão médica passa de `Cancelar` para `Voltar sem decidir`.
- [ ] Submissão `accept` continua aceitando orientação vazia.
- [ ] Submissão `accept` persiste orientação de até 500 caracteres.
- [ ] Submissão com orientação acima de 500 caracteres continua inválida.
- [ ] Submissão `deny` exige motivo da negativa.
- [ ] Submissão `deny` não persiste orientação médica enviada no POST; `doctor_observation` fica vazio para novas negativas.
- [ ] Downstream troca nomenclatura visível de `Observação Médica`/`Obs. médica` para `Orientação médica`/`Orientações médicas`.
- [ ] Nenhuma migration é criada sem justificativa explícita.
- [ ] FSM, eventos estruturados, comunicação operacional e notificações permanecem inalterados.
- [ ] Testes relevantes adicionados/ajustados antes da implementação passar.
- [ ] Quality gate do AGENTS.md executado:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Relatório markdown temporário gerado por slice, com snippets antes/depois e respostas aos gates de autoavaliação.
- [ ] `REPORT_PATH=<temp-markdown-path>` informado por slice.
- [ ] Commit e push realizados por slice.
