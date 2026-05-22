# Slice 003 — Backend de Upload Múltiplo

## Handoff para Implementador LLM

Leia:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/multi-pdf-async-intake/proposal.md`
4. `openspec/changes/multi-pdf-async-intake/design.md`
5. Slices 001 e 002 deste change
6. Este arquivo.

Implemente somente este slice, assumindo que `enqueue_pdf_extraction` já existe.

## Problema

A view `intake_home` aceita apenas um arquivo (`pdf_file`) e executa extração síncrona. Precisamos que o backend aceite uma lista de PDFs, crie um `Case` por arquivo e enfileire extração assíncrona sem bloquear a request.

## Objetivo

Alterar o backend do intake para upload múltiplo, mantendo compatibilidade funcional com o fluxo de um único PDF, mas removendo extração síncrona da request.

## Escopo Preferencial

Arquivos prováveis:

- `apps/intake/forms.py`
- `apps/intake/views.py`
- `apps/intake/services.py` — novo, recomendado
- `apps/intake/tests/test_upload.py` ou novo `test_multi_upload.py`

Evite tocar no JS/template neste slice, exceto mínimo necessário para nome do campo se os testes usarem renderização. A UX completa fica no slice 004.

## Requisitos Funcionais

1. A view deve ler múltiplos arquivos via `request.FILES.getlist("pdf_files")` ou nome definido no design.
2. Validar server-side:
   - ao menos 1 arquivo;
   - máximo de arquivos por lote;
   - extensão PDF;
   - tamanho por arquivo;
   - tamanho total do lote.
3. Cada PDF válido deve criar exatamente um `Case`.
4. Cada `Case` deve salvar seu `pdf_file`.
5. Cada `Case` deve transicionar `NEW → R1_ACK_PROCESSING`.
6. Cada `Case` deve chamar `enqueue_pdf_extraction(case.case_id)`.
7. A view não deve chamar `extract_pdf_text` nem `strip_watermark_and_extract_record`.
8. Se um arquivo específico for inválido antes de criar caso, ele deve ser reportado e não criar `Case`.
9. Se houver mistura de válidos e inválidos, os válidos podem ser aceitos e os inválidos reportados via messages, desde que o comportamento esteja testado.
10. Após sucesso, redirecionar para `intake:my_cases` ou página apropriada com mensagem agregada.

## TDD — Testes RED Esperados

Antes de implementar, adicione testes que falhem:

1. POST com 3 PDFs cria 3 `Case`.
2. POST com 3 PDFs chama `enqueue_pdf_extraction` 3 vezes.
3. Casos criados ficam em `R1_ACK_PROCESSING`, não em `LLM_STRUCT`.
4. View não chama `extract_pdf_text`.
5. POST com arquivo não-PDF rejeita aquele arquivo.
6. POST acima do limite de arquivos não processa ou processa conforme regra escolhida, mas sempre de forma determinística e testada.
7. Usuário sem papel NIR continua bloqueado.
8. Usuário não autenticado continua redirecionado.

## Critérios de Sucesso

- Backend aceita lote de PDFs e retorna rápido.
- Extração fica exclusivamente para a task assíncrona.
- Testes antigos de upload único são atualizados para o novo estado inicial assíncrono.
- Regras de autorização permanecem inalteradas.

## Comandos de Validação Focados

```bash
uv run pytest apps/intake/tests/test_upload.py apps/intake/tests/test_pdf_extraction_task.py -q
uv run ruff check apps/intake
uv run mypy apps/intake
```

## Relatório Obrigatório

Crie:

```text
/tmp/ats-web-slice-003-multi-upload-backend-report.md
```

Inclua:

- snippets da view antes/depois removendo extração síncrona;
- regra de validação de lote;
- testes executados;
- pendências para UI.

Responda com:

```text
REPORT_PATH=/tmp/ats-web-slice-003-multi-upload-backend-report.md
```

## Stop Rule

Não implemente preview/listagem múltipla em JS neste slice, exceto se for estritamente necessário para manter o template renderizando.
