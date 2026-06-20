# Tasks: Corrigir prior-case lookup após fechamento

## Slice vertical

- [x] Slice 001 — Lookup por campos estáveis de decisão, não por status transitório (`slices/slice-001-prior-case-lookup-decision-fields.md`)

## Definition of Done do change

- [x] Lookup continua usando `agency_record_number` como chave principal de agrupamento.
- [x] Lookup retorna vazio para `agency_record_number` vazio ou em branco.
- [x] Lookup exclui o caso atual por `case_id`.
- [x] Negativa médica é identificada por `doctor_decision="deny"` e `doctor_decided_at` dentro da janela.
- [x] Negativa de agendamento é identificada por `appointment_status="denied"` e `appointment_decided_at` dentro da janela.
- [x] Lookup não depende de `Case.status` para encontrar prior cases.
- [x] Lookup encontra negativa médica recente mesmo após o caso avançar para `CLEANED` ou outro estado posterior.
- [x] Lookup encontra negativa de agendamento recente mesmo após o caso avançar para `CLEANED` ou outro estado posterior.
- [x] Janela de 7 dias usa data da decisão, não `created_at`.
- [x] Caso fora da janela por data da decisão não é contado, mesmo se `created_at` for recente.
- [x] Caso dentro da janela por data da decisão é contado, mesmo se `created_at` for antigo.
- [x] Prior case retornado é a negativa mais recente por `decided_at`, não por `created_at`.
- [x] `prior_denial_count_7d` conta corretamente as negativas dentro da janela.
- [x] `PriorCaseSummary.decision`, `decided_at`, `reason`, `decided_by` e `decided_by_role` continuam corretos.
- [x] Nome do paciente não é usado como critério de matching neste change.
- [x] Data externa da Secretaria não é introduzida como critério neste change.
- [x] FSM não é alterada.
- [x] Nenhuma migration é criada.
- [x] Nenhuma UI/template/view é alterada.
- [x] Testes relevantes foram escritos antes da implementação passar (TDD RED → GREEN → REFACTOR).
- [x] Clean code aplicado: funções pequenas, nomes claros, sem acoplamento desnecessário, DRY, YAGNI.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatório markdown temporário criado com snippets antes/depois, evidências de testes e resposta aos gates de autoavaliação.
- [x] Este `tasks.md` atualizado ao concluir o slice.
- [x] Commit e push realizados após implementação.

## Notas para implementadores

- Não alterar matching para nome de paciente.
- Não alterar extração de `agency_record_number`.
- Não alterar prompts LLM.
- Não adicionar relação formal entre casos neste change.
- Não implementar reabertura/reconsideração neste change.
- Não tocar views/templates/UI salvo descoberta crítica justificada no relatório.
