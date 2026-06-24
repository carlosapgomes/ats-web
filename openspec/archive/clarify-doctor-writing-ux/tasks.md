# Tasks: Clarificar UX de escrita na decisão médica

## Slices verticais

- [x] Slice 001 — Decisão médica sem ambiguidade (`slices/slice-001-decisao-medica-sem-ambiguidade.md`)
- [x] Slice 002 — Labels downstream alinhados (`slices/slice-002-labels-downstream-alinhados.md`)

## Definition of Done do change

- [x] Campo visual de `doctor_observation` deixa de ser apresentado como observação médica genérica.
- [x] Tela de decisão médica usa label `Orientações para agendamento/execução` ou equivalente explícito.
- [x] Campo de orientação fica associado ao fluxo de aceite.
- [x] UI orienta que pedido de documentos/dados deve usar comunicação operacional, não negativa.
- [x] Botão de saída da decisão médica passa de `Cancelar` para `Voltar sem decidir`.
- [x] Submissão `accept` continua aceitando orientação vazia.
- [x] Submissão `accept` persiste orientação de até 500 caracteres.
- [x] Submissão com orientação acima de 500 caracteres continua inválida.
- [x] Submissão `deny` exige motivo da negativa.
- [x] Submissão `deny` não persiste orientação médica enviada no POST; `doctor_observation` fica vazio para novas negativas.
- [x] Downstream troca nomenclatura visível de `Observação Médica`/`Obs. médica` para `Orientação médica`/`Orientações médicas`.
- [x] Nenhuma migration é criada sem justificativa explícita.
- [x] FSM, eventos estruturados, comunicação operacional e notificações permanecem inalterados.
- [x] Testes relevantes adicionados/ajustados antes da implementação passar.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatório markdown temporário gerado por slice, com snippets antes/depois e respostas aos gates de autoavaliação.
- [x] `REPORT_PATH=<temp-markdown-path>` informado por slice.
- [x] Commit e push realizados por slice.
