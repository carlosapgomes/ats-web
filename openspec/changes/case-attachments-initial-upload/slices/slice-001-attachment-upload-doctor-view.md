# Slice 001: MVP end-to-end de anexos no upload único e tela médica

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`, monolito Django SSR. Este slice inicia o change `case-attachments-initial-upload`.

Leia, nesta ordem:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/case-attachments-initial-upload/proposal.md`
4. `openspec/changes/case-attachments-initial-upload/design.md`
5. `openspec/changes/case-attachments-initial-upload/tasks.md`
6. Este arquivo
7. `apps/cases/models.py`
8. `apps/intake/services.py`
9. `apps/intake/views.py`
10. `templates/intake/intake_home.html`
11. `apps/doctor/views.py`
12. `apps/doctor/urls.py`
13. `templates/doctor/decision.html`
14. Testes existentes em `apps/intake/tests/test_upload.py`, `apps/doctor/tests/test_views.py` e `apps/cases/tests/`

Implemente **somente este slice** com TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Entregar o fluxo mínimo end-to-end:

```text
NIR seleciona exatamente 1 PDF principal + anexos PDF/JPEG/PNG
→ sistema cria Case
→ salva anexos vinculados ao Case com nomes seguros
→ registra auditoria
→ pipeline continua usando apenas o PDF principal
→ médico abre o caso em WAIT_DOCTOR
→ vê os anexos inline na tela de decisão
```

Este slice deve gerar valor operacional real mesmo que a UX ainda seja simples. O refinamento de JS condicional/preview detalhado fica para o Slice 002.

## Escopo funcional

### R1. Modelo de anexo

Criar modelo `CaseAttachment` em `apps/cases/models.py` com migration.

Campos mínimos:

```python
attachment_id: UUID primary key
case: FK Case, related_name="attachments"
file: FileField(upload_to=case_attachment_upload_to)
original_filename: CharField
stored_filename: CharField
content_type: CharField
size_bytes: PositiveBigIntegerField
sha256: CharField(64, db_index=True)
uploaded_by: FK User, PROTECT
created_at: auto_now_add
is_suppressed: BooleanField(default=False)
suppressed_at: DateTimeField(null=True, blank=True)
suppressed_by: FK User, null=True, blank=True, PROTECT
suppression_reason: TextField(blank=True)
upload_phase: CharField(default="initial")  # initial | supplemental
uploaded_when_case_status: CharField(blank=True)
note: TextField(blank=True)
```

Implementar `case_attachment_upload_to` para salvar em caminho seguro baseado em UUID:

```text
case_attachments/<case_id>/<attachment_id>.<ext>
```

Não usar o nome original como nome armazenado.

Os campos de supressão devem existir desde este slice, mas a ação de suprimir via UI será implementada no Slice 003. Todas as consultas clínicas deste slice devem exibir/servir apenas anexos com `is_suppressed=False`.

Os campos `upload_phase`, `uploaded_when_case_status` e `note` também devem existir desde este slice. Neste MVP de upload inicial, anexos criados junto com o relatório principal devem nascer com `upload_phase="initial"`, `uploaded_when_case_status` preenchido com o status atual quando salvo, e `note=""`. O fluxo de anexos complementares será implementado no Slice 004.

### R2. Configurações de limite

Adicionar settings em `config/settings/base.py`:

```python
INTAKE_MAX_ATTACHMENTS_PER_CASE = 10
INTAKE_MAX_ATTACHMENT_BYTES_PER_FILE = 20 * 1024 * 1024
INTAKE_MAX_ATTACHMENT_BYTES_PER_CASE = 200 * 1024 * 1024
```

Não reduzir os limites atuais de upload múltiplo.

### R3. Validação backend de anexos

Criar helpers pequenos e testáveis, preferencialmente em `apps/intake/services.py` ou módulo coeso no mesmo app.

Aceitar:

- `.pdf` / `application/pdf`;
- `.jpg` ou `.jpeg` / `image/jpeg`;
- `.png` / `image/png`.

Validar:

- máximo de 10 anexos;
- máximo de 20 MB por anexo;
- máximo total de 200 MB por caso;
- anexos só são aceitos se houver exatamente 1 PDF principal.

Se houver anexos e `len(pdf_files) != 1`, rejeitar anexos com mensagem clara e não associar ambiguamente.

Para upload único com anexos, se qualquer anexo for inválido, preferir não criar o caso e retornar erro ao NIR. Isso evita caso criado sem anexos que o usuário achou ter enviado.

### R4. Integração no upload NIR

Atualizar a view de upload para ler:

```python
files = request.FILES.getlist("pdf_files")
attachments = request.FILES.getlist("attachment_files")
```

Atualizar `process_uploaded_files(...)` para aceitar anexos opcionais.

No template `templates/intake/intake_home.html`, adicionar um campo simples de anexos:

```html
<input type="file" name="attachment_files" ... multiple accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png">
```

Neste slice, o campo pode ser visível de forma simples com texto explicativo. O Slice 002 fará a UX condicional robusta com JS. Mesmo assim, a validação server-side deste slice é obrigatória.

### R5. Auditoria

Para cada anexo salvo, registrar `CaseEvent`:

```text
CASE_ATTACHMENT_ADDED
```

Payload mínimo:

```json
{
  "attachment_id": "...",
  "original_filename": "...",
  "content_type": "...",
  "size_bytes": 123,
  "sha256": "..."
}
```

Não registrar conteúdo clínico completo.

### R6. Views protegidas para anexos médicos

Adicionar rota no app médico para servir anexo:

```python
path("cases/<uuid:case_id>/attachments/<uuid:attachment_id>/", views.serve_attachment, name="serve_attachment")
```

A view deve:

- exigir login e papel ativo `doctor`;
- buscar anexo ativo (`is_suppressed=False`) pelo `case_id` e `attachment_id`;
- permitir acesso se o caso está em `WAIT_DOCTOR`; ou se `case.doctor == request.user` e `doctor_decision` preenchido;
- retornar 404 para anexo inexistente ou caso sem autorização;
- responder `FileResponse` com content-type correto.

Não expor arquivo via `MEDIA_URL` público.

### R7. Visualização médica inline

Em `apps/doctor/views.py::_build_decision_context`, incluir anexos ativos (`is_suppressed=False`) ordenados por `created_at`.

Em `templates/doctor/decision.html`, após o bloco do PDF original e antes do fim da página, renderizar anexos em collapsibles:

- mostrar aviso: `Anexos enviados pelo NIR — não analisados automaticamente pela IA.`
- PDF: `<embed src="..." type="application/pdf">`;
- JPEG/PNG: `<img src="..." class="img-fluid" ...>`;
- link `Abrir em nova aba`;
- metadados: nome original, tipo, tamanho aproximado, data/hora de upload.

## Fora de escopo

- JS condicional sofisticado para mostrar anexos apenas quando há 1 PDF principal.
- Preview client-side detalhado de anexos.
- Mostrar anexos no detalhe NIR/read-only compartilhado.
- Dashboard/scheduler/admin.
- OCR/extração/LLM de anexos.
- Reabertura de caso negado.
- Novos estados FSM.

## Arquivos prováveis

Idealmente tocar apenas o necessário:

1. `apps/cases/models.py`
2. `apps/cases/migrations/00xx_caseattachment.py`
3. `config/settings/base.py`
4. `apps/intake/services.py`
5. `apps/intake/views.py`
6. `templates/intake/intake_home.html`
7. `apps/doctor/views.py`
8. `apps/doctor/urls.py`
9. `templates/doctor/decision.html`
10. testes relevantes (`apps/intake/tests/test_upload.py`, `apps/doctor/tests/test_views.py`, possivelmente `apps/cases/tests/`)
11. `openspec/changes/case-attachments-initial-upload/tasks.md` ao final

Este slice pode passar de 5 arquivos porque é a menor entrega vertical útil: modelo + upload + storage protegido + visualização médica. Não ampliar para pipeline/LLM/UI compartilhada.

## TDD obrigatório

Antes de implementar, adicionar testes falhando.

### Testes mínimos de domínio/storage

1. `test_case_attachment_upload_path_uses_case_and_attachment_uuid`
   - cria anexo;
   - verifica caminho `case_attachments/<case_id>/<attachment_id>.<ext>`;
   - garante que nome original não aparece no path.

2. `test_case_attachment_preserves_original_filename_and_metadata`
   - verifica `original_filename`, `content_type`, `size_bytes`, `sha256`, `uploaded_by`.

3. `test_case_attachment_defaults_to_active_not_suppressed`
   - novo anexo nasce com `is_suppressed=False`, sem `suppressed_at`, `suppressed_by` ou `suppression_reason`.

4. `test_initial_attachment_defaults_to_initial_upload_phase`
   - anexo criado no upload inicial nasce com `upload_phase="initial"`, `uploaded_when_case_status` preenchido e `note=""`.

### Testes mínimos de upload NIR

5. `test_single_pdf_upload_accepts_pdf_jpeg_png_attachments`
   - POST com 1 `pdf_files` + 3 anexos válidos;
   - cria 1 case;
   - cria 3 `CaseAttachment`.

6. `test_attachment_upload_records_case_event`
   - verifica `CASE_ATTACHMENT_ADDED` com payload mínimo.

7. `test_bulk_pdf_upload_rejects_attachments`
   - POST com 2 PDFs principais + 1 anexo;
   - não associa anexo ambiguamente;
   - resposta/mensagem informa que anexos só são permitidos com 1 relatório principal.

8. `test_attachment_rejects_invalid_extension`
   - `.txt` rejeitado.

9. `test_attachment_rejects_more_than_ten_files`
   - 11 anexos rejeitados.

10. `test_attachment_rejects_file_over_20mb`
   - monkeypatch do setting para tamanho baixo para não criar arquivo gigante real.

### Testes mínimos da tela médica

11. `test_doctor_decision_displays_attachment_section`
   - caso `WAIT_DOCTOR` com anexo;
   - GET tela médica;
   - contém nome original e aviso de que anexos não foram analisados pela IA.

12. `test_doctor_decision_embeds_pdf_attachment`
    - anexo PDF gera embed/link da rota protegida.

13. `test_doctor_decision_embeds_image_attachment`
    - anexo JPEG/PNG gera `<img>`.

14. `test_doctor_attachment_view_requires_authorized_case`
    - médico não acessa anexo de caso decidido por outro médico e fora de sua fila.

15. `test_doctor_attachment_view_serves_authorized_attachment`
    - médico acessa anexo de caso em `WAIT_DOCTOR`.

16. `test_doctor_attachment_view_does_not_serve_suppressed_attachment`
    - anexo com `is_suppressed=True` retorna 404/403 e não aparece na tela médica.

## Clean code / DRY / YAGNI

- Não colocar validação complexa dentro da view.
- Preferir helpers pequenos com nomes explícitos.
- Não criar serviço genérico de documentos ainda.
- Não criar campos de OCR/classificação futura.
- Não duplicar lógica de content-type em múltiplos lugares; centralizar constants/helpers.
- Não capturar exceções amplas escondendo erro sem teste.
- Não refatorar apps não relacionados.

## Critérios de aceitação

- [ ] TDD seguido: testes novos falham antes da implementação e passam após.
- [ ] `CaseAttachment` existe com migration.
- [ ] Caminho em filesystem usa UUID e evita colisão.
- [ ] Upload único aceita até 10 anexos PDF/JPEG/PNG.
- [ ] Upload bulk não associa anexos.
- [ ] Limites de tamanho/quantidade são validados no backend.
- [ ] `CASE_ATTACHMENT_ADDED` registrado por anexo.
- [ ] Médico vê anexos ativos inline em `doctor/decision.html`.
- [ ] Médico acessa anexos ativos por view protegida.
- [ ] Anexo suprimido não aparece nem é servido, mesmo antes da UI de supressão existir.
- [ ] Pipeline LLM e barreira de regulação continuam usando somente `Case.pdf_file`.
- [ ] Nenhum estado FSM novo foi criado.
- [ ] Quality gate do AGENTS.md passa.

## Gates de autoavaliação

Responder no relatório do slice:

1. Onde o código impede anexos com múltiplos PDFs principais?
2. Como o path do arquivo evita colisão e path traversal?
3. Quais testes provam PDF/JPEG/PNG aceitos?
4. Quais testes provam limites de 10 anexos e 20 MB?
5. Onde está a autorização da view protegida de anexo?
6. Onde o código filtra anexos suprimidos das telas/rotas clínicas?
7. Como você garante que anexos não entram no pipeline LLM neste slice?
8. A UI informa que anexos não foram analisados pela IA?
9. Quais arquivos foram tocados e por que o slice ainda é vertical?

## Comandos de validação mínimos

Durante desenvolvimento, rodar escopo rápido:

```bash
uv run pytest apps/intake/tests/test_upload.py apps/doctor/tests/test_views.py apps/cases/tests -q
uv run ruff check apps/cases apps/intake apps/doctor config
uv run ruff format --check apps/cases apps/intake apps/doctor config
uv run mypy apps/cases apps/intake apps/doctor config
```

Antes de finalizar, rodar quality gate completo:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório final obrigatório

Criar um relatório temporário em markdown, por exemplo:

```text
/tmp/ats-web-slice-001-case-attachments-report.md
```

O relatório deve conter:

- resumo da entrega;
- arquivos tocados;
- snippets antes/depois dos pontos críticos;
- evidências RED/GREEN dos testes;
- validações executadas e resultados;
- riscos/limitações;
- confirmação de que `tasks.md` foi atualizado;
- commit hash e confirmação de push.

Resposta final obrigatória:

```text
REPORT_PATH=/tmp/ats-web-slice-001-case-attachments-report.md
```

Depois de responder, **parar** e pedir confirmação explícita antes do próximo slice.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/case-attachments-initial-upload/proposal.md, design.md, tasks.md and slices/slice-001-attachment-upload-doctor-view.md. Implement ONLY Slice 001 using TDD (RED → GREEN → REFACTOR). Keep code clean, DRY and YAGNI.

Goal: NIR can upload exactly 1 main PDF with optional PDF/JPEG/PNG attachments; attachments are saved safely as CaseAttachment records with UUID-based paths, audited with CASE_ATTACHMENT_ADDED, and visible inline to the doctor on the decision page. Include suppression fields and upload-phase fields on CaseAttachment from the start; initial upload attachments must use upload_phase=initial. Ensure only active/non-suppressed attachments are displayed/served. Bulk main-PDF upload must continue working and must not accept ambiguous attachments. Do not process attachments via LLM/OCR. Do not alter FSM states.

Add failing tests first for model/path/metadata, upload validation, audit events, doctor inline display, and protected attachment serving. Then implement minimal code. Avoid business logic in views/templates; use small helpers/services.

Run the full quality gate: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/case-attachments-initial-upload/tasks.md when complete. Create /tmp/ats-web-slice-001-case-attachments-report.md with before/after snippets and validation evidence. Commit and push. Reply REPORT_PATH=<path> and stop.
```
