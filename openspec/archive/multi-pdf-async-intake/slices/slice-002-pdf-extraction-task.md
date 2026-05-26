# Slice 002 — Task Assíncrona de Extração PDF

## Handoff para Implementador LLM

Leia:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/multi-pdf-async-intake/proposal.md`
4. `openspec/changes/multi-pdf-async-intake/design.md`
5. `openspec/changes/multi-pdf-async-intake/slices/slice-001-q2-clusters-and-compose.md`
6. Este arquivo.

Implemente somente este slice, assumindo que o cluster `pdf` já está configurado.

## Problema

A extração de texto de PDF ocorre dentro da request web em `intake_home`. Para lotes de 20–30 PDFs, isso é inadequado. Precisamos de uma task dedicada que processe um `Case` já criado e avance a FSM em background.

## Objetivo

Criar task idempotente de extração PDF em `apps/intake/tasks.py`, roteada para cluster `pdf`, que:

1. inicia extração;
2. extrai texto;
3. salva dados extraídos;
4. avança para `LLM_STRUCT`;
5. enfileira pipeline LLM no cluster `llm`.

Neste slice, ainda não alterar a view de upload para usar a task.

## Escopo Preferencial

Arquivos prováveis:

- `apps/intake/tasks.py` — novo
- `apps/intake/tests/test_pdf_extraction_task.py` — novo
- `apps/intake/pdf_utils.py` — apenas se necessário
- `apps/cases/models.py` — apenas se faltar transição FSM de falha indispensável
- `apps/pipeline/tasks.py` — apenas se necessário para integração já prevista no slice 001

Evite tocar em templates/JS/view neste slice.

## Requisitos Funcionais

1. Criar `enqueue_pdf_extraction(case_id)` usando `async_task(..., q_options={"cluster": "pdf"})`.
2. Criar `execute_pdf_extraction(case_id_str)`.
3. Se `Case` não existir, a task deve falhar de forma clara.
4. Se `Case` estiver após `LLM_STRUCT`, a task deve retornar sem reprocessar.
5. Se `Case` não tiver `pdf_file`, marcar falha controlada e registrar evento.
6. Para caso em `R1_ACK_PROCESSING`, executar:
   - `start_extraction(user=None ou system)`;
   - `extract_pdf_text(case.pdf_file.path)`;
   - `strip_watermark_and_extract_record(...)`;
   - persistir `extracted_text`, `agency_record_number`, `agency_record_extracted_at`;
   - `extraction_complete(success=True, user=None ou system)`;
   - `enqueue_pipeline(case.case_id)`.
7. Em erro de extração, mover para `FAILED` usando transição existente, se houver, e registrar `CaseEvent` com erro resumido.
8. A task deve ser segura para retry e não deve enfileirar pipeline duas vezes em cenário simples de reexecução após sucesso.

## TDD — Testes RED Esperados

Antes de implementar, crie testes que falhem:

1. `enqueue_pdf_extraction` chama `async_task` com cluster `pdf`.
2. `execute_pdf_extraction` em caso `R1_ACK_PROCESSING` extrai texto, salva campos e deixa status `LLM_STRUCT`.
3. Após sucesso, `enqueue_pipeline` é chamado uma vez.
4. Caso sem `pdf_file` vira `FAILED` ou registra falha controlada conforme FSM existente.
5. Caso já em `LLM_STRUCT` não reextrai e não chama `enqueue_pipeline` novamente.
6. Exceção de `extract_pdf_text` gera evento de falha e estado final seguro.

Use mocks para evitar depender de PDFs reais em todos os testes. Inclua ao menos um teste de integração leve com PDF gerado por PyMuPDF se já houver fixture semelhante.

## Critérios de Sucesso

- Extração PDF pode rodar fora da request.
- Task preserva FSM e auditoria.
- Pipeline LLM continua sendo enfileirada após extração bem-sucedida.
- Sem alteração de UX ainda.

## Comandos de Validação Focados

```bash
uv run pytest apps/intake/tests/test_pdf_extraction_task.py apps/pipeline/tests -q
uv run ruff check apps/intake apps/pipeline
uv run mypy apps/intake apps/pipeline
```

## Relatório Obrigatório

Crie:

```text
/tmp/ats-web-slice-002-pdf-extraction-task-report.md
```

Inclua:

- task criada;
- fluxo FSM antes/depois;
- estratégia de idempotência;
- testes executados;
- riscos pendentes.

Responda com:

```text
REPORT_PATH=/tmp/ats-web-slice-002-pdf-extraction-task-report.md
```

## Stop Rule

Não implemente upload múltiplo na view nem JS neste slice.
