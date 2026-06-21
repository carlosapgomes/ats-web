# Slice 001: Fluxo NIR de reenvio corrigido explícito

## Contexto zero para implementador

O ATS é um monolito Django SSR. O NIR envia PDFs de relatórios pelo app `apps/intake`. Cada PDF principal cria um `Case`. Anexos clínicos (`CaseAttachment`) já existem e pertencem a um único `Case`.

O sistema já tem prior-case lookup automático para detectar negativa recente pelo mesmo `agency_record_number`, mas isso cobre apenas reenvios genéricos. Este slice cria o caminho explícito:

```text
NIR parte de um caso anterior
→ informa motivo obrigatório
→ envia novo PDF principal + anexos próprios opcionais
→ sistema cria novo Case
→ novo Case referencia o anterior
→ eventos auditáveis registram a relação
```

O caso anterior não deve ser sobrescrito, reaberto ou ter status alterado. O novo caso deve seguir o pipeline normal como qualquer upload novo.

## Objetivo do slice

Entregar verticalmente:

```text
NIR abre formulário de reenvio corrigido de um caso existente
→ envia motivo + novo PDF
→ novo Case é criado com corrects_case apontando para o anterior
→ novo Case entra em R1_ACK_PROCESSING e enfileira extração
→ eventos ficam nos dois casos
→ anexos do caso anterior não são copiados
```

A visibilidade refinada para médico/detalhes fica para o Slice 002. Este slice deve, porém, criar dados e eventos corretos para permitir essa visualização depois.

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/cases/models.py`
2. `apps/cases/migrations/<nova_migration>.py`
3. `apps/intake/services.py`
4. `apps/intake/views.py`
5. `apps/intake/urls.py`
6. `templates/intake/corrected_resubmission.html`
7. `apps/intake/tests/test_corrected_resubmission.py` ou arquivo de testes equivalente
8. `openspec/changes/corrected-case-resubmission-linkage/tasks.md` ao concluir

Este slice pode tocar mais de 5 arquivos porque é o menor fluxo vertical real: modelo + serviço + rota + UI + testes. Não tocar doctor/templates médicos neste slice.

## Requisitos funcionais

### R1. Campos no Case

Adicionar campos opcionais em `apps/cases/models.py::Case`:

```python
corrects_case = models.ForeignKey(
    "self",
    null=True,
    blank=True,
    on_delete=models.PROTECT,
    related_name="corrected_by_cases",
)
correction_reason = models.TextField(blank=True)
correction_created_by = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    null=True,
    blank=True,
    on_delete=models.PROTECT,
    related_name="case_corrections_created",
)
correction_created_at = models.DateTimeField(null=True, blank=True)
```

Criar migration.

Não criar novo estado FSM.

### R2. Serviço de domínio

Criar serviço em `apps/intake/services.py`, por exemplo:

```python
def create_corrected_resubmission(
    *,
    original_case: Case,
    pdf_file: UploadedFile,
    user: AccountsUser,
    correction_reason: str,
    attachments: list[UploadedFile] | None = None,
) -> Case:
    ...
```

O serviço deve:

1. rejeitar `correction_reason` vazio ou só espaços;
2. validar o PDF com `validate_single_file`;
3. validar anexos com `validate_attachments(attachments, pdf_count=1)` ou validação equivalente existente;
4. criar novo `Case` com:
   - `created_by=user`;
   - `corrects_case=original_case`;
   - `correction_reason` normalizado/stripado;
   - `correction_created_by=user`;
   - `correction_created_at=timezone.now()`;
5. salvar `pdf_file` do novo caso;
6. executar transição `start_processing(user=user)` e salvar;
7. enfileirar extração com `enqueue_pdf_extraction(new_case.case_id)`;
8. criar anexos no novo caso se enviados, usando `create_case_attachment` e `record_attachment_event` existentes;
9. registrar eventos de correção nos dois casos.

### R3. Eventos auditáveis

Registrar no novo caso:

```text
CASE_CORRECTION_CREATED
```

Payload mínimo:

```json
{
  "original_case_id": "...",
  "original_agency_record_number": "...",
  "correction_reason": "...",
  "created_by_id": "..."
}
```

Registrar no caso anterior:

```text
CASE_MARKED_SUPERSEDED
```

Payload mínimo:

```json
{
  "corrected_case_id": "...",
  "corrected_agency_record_number": "...",
  "correction_reason": "...",
  "created_by_id": "..."
}
```

Não alterar status do caso anterior.

### R4. Não herdar documentos/dados

O novo caso não deve copiar do anterior:

- `pdf_file`;
- anexos;
- `extracted_text`;
- `structured_data`;
- `summary_text`;
- `suggested_action`;
- decisão médica;
- decisão de agendamento;
- eventos.

Apenas o vínculo e metadados de correção devem ser salvos.

### R5. View e rota NIR

Adicionar rota em `apps/intake/urls.py`:

```python
path("<uuid:case_id>/corrected-resubmission/", views.corrected_resubmission, name="corrected_resubmission")
```

Criar view `corrected_resubmission` com `@login_required` e `@role_required("nir")`.

Comportamento:

- GET:
  - busca `original_case` por `case_id`;
  - renderiza template `intake/corrected_resubmission.html`.
- POST:
  - lê `correction_reason`;
  - lê exatamente 1 arquivo `pdf_file` ou `pdf_files` conforme decisão do implementador;
  - lê anexos opcionais `attachment_files`;
  - exige confirmação explícita, se o template tiver checkbox;
  - chama o serviço;
  - em sucesso, mensagem success e redirect para `intake:case_detail` do novo caso;
  - em erro, mensagem warning e re-render do formulário.

### R6. Formulário/template

Criar `templates/intake/corrected_resubmission.html`.

Conteúdo mínimo:

- contexto do caso anterior:
  - paciente;
  - `agency_record_number`;
  - status atual;
  - data de envio;
- textarea obrigatório:

```text
Motivo do reenvio corrigido
```

- input de novo PDF principal, single file, obrigatório;
- input de anexos opcionais PDF/JPEG/PNG;
- checkbox obrigatório:

```text
Confirmo que este é um novo envio corrigido e que os documentos/anexos do caso anterior não serão herdados.
```

- botão `Enviar caso corrigido`;
- link de volta.

Não precisa reutilizar todo o JS de upload. O backend deve ser a fonte de verdade para validação.

### R7. Pontos de entrada mínimos

Neste slice, adicionar ao menos um caminho operacional para abrir o formulário.

Preferência:

- botão/link em `templates/intake/case_detail.html` para casos operacionais acessíveis.

Se também adicionar botão na busca de encerrados neste slice, ótimo, mas a integração visual completa pode ficar para Slice 002. O endpoint deve funcionar para casos `CLEANED`, mesmo que o link em closed search venha depois.

## TDD obrigatório

Antes da implementação, criar testes falhando.

Arquivo sugerido:

```text
apps/intake/tests/test_corrected_resubmission.py
```

### Testes mínimos

1. `test_corrected_resubmission_get_requires_nir_role`
   - usuário sem papel NIR não acessa.

2. `test_corrected_resubmission_get_renders_original_case_context`
   - GET como NIR mostra paciente/registro do caso anterior e campo de motivo.

3. `test_post_requires_correction_reason`
   - POST sem motivo não cria caso.

4. `test_post_requires_single_pdf`
   - POST sem PDF não cria caso.

5. `test_post_creates_new_case_linked_to_original`
   - POST válido cria novo caso;
   - `new_case.corrects_case == original_case`;
   - `correction_reason`, `correction_created_by`, `correction_created_at` preenchidos.

6. `test_post_does_not_modify_original_status_or_decision_fields`
   - status/decisão do caso anterior permanecem iguais.

7. `test_post_does_not_copy_original_attachments`
   - original tem anexo;
   - novo caso não recebe esse anexo automaticamente.

8. `test_post_saves_new_attachments_only_on_new_case`
   - anexos enviados no reenvio aparecem só no novo caso.

9. `test_post_records_correction_events_on_both_cases`
   - novo caso tem `CASE_CORRECTION_CREATED`;
   - original tem `CASE_MARKED_SUPERSEDED`.

10. `test_new_case_enqueued_for_pdf_extraction`
    - mockar/patch `enqueue_pdf_extraction` e garantir chamada com `new_case.case_id`.

### RED esperado

Antes da implementação, os testes devem falhar por ausência de campos/rota/serviço.

Registrar no relatório:

- comando executado para RED;
- nomes dos testes falhando;
- resumo da falha.

## Orientações de implementação

### Clean code

- Business logic no serviço, não na view.
- View deve orquestrar request/response, messages e redirects.
- Helpers pequenos para registrar eventos se necessário.
- Nomes explícitos: `original_case`, `corrected_case`, `correction_reason`.

### DRY

- Reusar validações existentes de PDF/anexos.
- Reusar criação de anexo existente (`create_case_attachment`, `record_attachment_event`).
- Não duplicar lógica de hash/storage.

### YAGNI

Não implementar neste slice:

- card médico;
- comunicação/thread por caso;
- encerramento automático do caso anterior;
- reabertura do caso anterior;
- cópia de anexos;
- matching por nome/CPF/CNS;
- API REST;
- busca avançada de versões.

## Critérios de sucesso

- [ ] Migration criada para campos de correção.
- [ ] GET do formulário funciona para NIR.
- [ ] POST válido cria novo caso vinculado ao anterior.
- [ ] Motivo é obrigatório.
- [ ] Novo PDF é obrigatório e validado.
- [ ] Anexos opcionais usam limites existentes.
- [ ] Novo caso entra em `R1_ACK_PROCESSING` e extração é enfileirada.
- [ ] Caso anterior não muda de status/decisão.
- [ ] Anexos do caso anterior não são copiados.
- [ ] Eventos são registrados nos dois casos.
- [ ] Testes novos passam.
- [ ] Quality gate completo passa.

## Gates de autoavaliação

Responder no relatório:

1. Qual teste prova que o caso anterior não é alterado?
2. Qual teste prova que anexos antigos não são herdados?
3. Qual teste prova que anexos novos pertencem só ao novo caso?
4. Onde está a regra de negócio principal: service ou view?
5. O novo caso passa pelo mesmo pipeline de upload normal? Como foi provado?
6. Algum estado FSM novo foi criado? Se sim, está errado.
7. Algum documento/evento/decisão do caso anterior foi copiado? Se sim, justificar; idealmente não.

## Relatório obrigatório

Criar relatório temporário, por exemplo:

```text
/tmp/corrected-case-resubmission-linkage-slice-001-report.md
```

O relatório deve conter:

- resumo da implementação;
- arquivos alterados;
- evidência do RED;
- evidência do GREEN;
- snippets antes/depois;
- resultados do quality gate;
- respostas aos gates de autoavaliação;
- justificativa para qualquer arquivo extra tocado.

Responder ao final com:

```text
REPORT_PATH=/tmp/corrected-case-resubmission-linkage-slice-001-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/corrected-case-resubmission-linkage/proposal.md, design.md, tasks.md and slices/slice-001-explicit-corrected-resubmission-flow.md.
Implement ONLY Slice 001.
Use TDD: first add failing tests for the explicit corrected resubmission NIR flow, then implement the minimal code.
Keep the slice vertical and lean. Business rules belong in apps/intake/services.py, not templates/views.
Add optional correction fields to Case with a migration. Add a NIR GET/POST route to create a corrected resubmission from an original case. The POST must require correction_reason and one new PDF, create a new Case linked to the original, enqueue normal PDF extraction, save only newly uploaded attachments, and record CASE_CORRECTION_CREATED / CASE_MARKED_SUPERSEDED events.
Do not alter FSM. Do not reopen or overwrite the original case. Do not copy original PDF, attachments, decisions, extracted data, suggested_action or events. Do not implement doctor UI or case communication in this slice.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/corrected-case-resubmission-linkage/tasks.md for Slice 001 when complete.
Create /tmp/corrected-case-resubmission-linkage-slice-001-report.md with RED/GREEN evidence, snippets, quality gate results and self-evaluation answers.
Commit and push.
Return REPORT_PATH=<path> and stop.
```
