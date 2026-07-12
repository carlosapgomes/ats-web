# Slice 004: Anexos PDF — viewer mobile interno para documentos clínicos anexos

## Handoff para implementador LLM com contexto zero

Leia antes de codar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/mobile-pdfjs-pwa-viewer/proposal.md`
4. `openspec/changes/mobile-pdfjs-pwa-viewer/design.md`
5. `openspec/changes/mobile-pdfjs-pwa-viewer/tasks.md`
6. `openspec/changes/mobile-pdfjs-pwa-viewer/specs/mobile-pdf-viewer/spec.md`
7. Este arquivo

Assuma que os Slices 001–003b já entregaram o viewer compartilhado para PDFs principais e consolidaram a validação de `next` em `apps.cases.navigation.resolve_safe_next_url`. Implemente **somente este slice** com TDD: RED → GREEN → REFACTOR.

## Protocolo obrigatório para implementador DeepSeek4-Flash

Este slice será implementado por um modelo rápido e com tendência a concluir cedo demais. Portanto, siga este protocolo literalmente. **Se qualquer item abaixo falhar, o slice está INCOMPLETO**: não marque `tasks.md`, não faça commit/push e responda com bloqueio + evidência.

1. **Plano antes de editar**: escreva no relatório uma mini matriz `Requisito → arquivo(s) → teste(s)`. Não implemente requisito sem teste ou justificativa explícita.
2. **RED real**: crie/ajuste testes primeiro e rode o subconjunto alvo. Pelo menos um teste novo deve falhar pelo motivo esperado. Se o teste passar antes da implementação, ele não prova o comportamento; corrija o teste.
3. **GREEN mínimo**: implemente somente o necessário para os testes do slice passarem. Não faça refactor amplo, não toque em apps fora do escopo e não antecipe slices futuros.
4. **Verificação por inspeção**: além dos testes, rode buscas `rg`/inspeções descritas neste slice para comprovar que não restaram links mobile com `target="_blank"`, que o desktop ainda tem `<embed>`, que a rota protegida correta é usada e que `Cache-Control: no-store` foi adicionado onde exigido.
5. **Quality gate completo**: execute exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` e `uv run pytest`. Se algum comando falhar, o slice não está pronto.
6. **Relatório com evidência, não opinião**: cole comandos executados, resumo das saídas, testes RED/GREEN, snippets antes/depois e respostas objetivas aos gates. Inclua também `Handoff para verificador` com: arquivos alterados, comandos exatos para rerun, riscos/limitações e checklist dos requisitos R1..Rn. Inclua uma seção final `Status: COMPLETE` somente se todos os critérios estiverem comprovados.

### Condições automáticas de INCOMPLETO

Marque como incompleto se ocorrer qualquer uma destas situações:

- teste planejado não foi escrito ou não foi executado;
- quality gate completo não foi executado;
- qualquer teste/lint/mypy falhou;
- `tasks.md` foi marcado apesar de falha ou pendência;
- `target="_blank"` permaneceu no link mobile que o slice deveria substituir;
- o `<embed>` desktop foi removido ou passou a usar a rota errada;
- viewer usa `MEDIA_URL`, caminho físico do arquivo ou URL sem autorização;
- `next` é usado sem `apps.cases.navigation.resolve_safe_next_url` e fallback canônico;
- `Cache-Control: no-store` exigido pelo slice ficou ausente;
- PDF.js/viewer foi declarado pronto sem teste/inspeção que comprove carregamento do JS/template;
- relatório temporário não foi criado no caminho exigido.


## Objetivo do slice

Eliminar o problema de nova aba mobile também para **anexos clínicos PDF** nas superfícies operacionais já autorizadas:

```text
Médico/NIR vê anexo PDF
→ no mobile toca no anexo
→ navega para viewer interno
→ PDF anexo renderiza via PDF.js
→ volta ao caso
```

Imagens (`JPEG/PNG`) devem permanecer como estão.

## Contexto técnico atual

- `templates/doctor/decision.html` lista anexos em `attachments`.
  - Mobile: link direto para `doctor:serve_attachment` com `target="_blank"`.
  - Desktop: PDF usa `<embed src="doctor:serve_attachment">`; imagem usa `<img>`.
- `templates/intake/case_detail.html` lista anexos operacionais NIR.
  - Mobile: link direto para `intake:serve_attachment` com `target="_blank"`.
  - Desktop: PDF usa `<embed src="intake:serve_attachment">`; imagem usa `<img>`.
- `templates/intake/closed_case_detail.html` também renderiza anexos, mas a rota atual `intake:serve_attachment` bloqueia `CLEANED`. Não criar nova rota histórica de anexos neste slice sem design adicional.

## Escopo funcional

### R1. Criar viewer para anexo PDF do médico

Adicionar rota em `apps/doctor/urls.py`, por exemplo:

```text
cases/<uuid:case_id>/attachments/<uuid:attachment_id>/viewer/ → doctor:attachment_pdf_viewer
```

Criar view em `apps/doctor/views.py`:

- login + `role_required("doctor")`;
- aplica a mesma autorização de `serve_attachment`;
- retorna 404 se o anexo não for PDF (`content_type != "application/pdf"`);
- retorna 404 se suprimido/inacessível;
- usa `pdf_url=reverse("doctor:serve_attachment", args=[case.case_id, attachment.attachment_id])`;
- `back_url` resolvido com `apps.cases.navigation.resolve_safe_next_url`, usando fallback `reverse("doctor:decision", args=[case.case_id])`.

Se houver duplicação com `serve_attachment`, extrair helper privado pequeno para buscar/analisar autorização do anexo.

### R2. Criar viewer para anexo PDF do NIR operacional

Adicionar rota em `apps/intake/urls.py`, por exemplo:

```text
<uuid:case_id>/attachments/<uuid:attachment_id>/viewer/ → intake:attachment_pdf_viewer
```

Criar view em `apps/intake/views.py`:

- login + `role_required("nir")`;
- segue a mesma autorização de `serve_attachment` operacional;
- bloqueia caso `CLEANED`, como a rota atual;
- retorna 404 se o anexo não for PDF;
- usa `pdf_url=reverse("intake:serve_attachment", args=[case.case_id, attachment.attachment_id])`;
- `back_url` resolvido com `apps.cases.navigation.resolve_safe_next_url`, usando fallback `reverse("intake:case_detail", args=[case.case_id])`.

### R3. Atualizar links mobile de anexos PDF

Em `templates/doctor/decision.html`:

- para `att.content_type == "application/pdf"`, link mobile deve apontar para `doctor:attachment_pdf_viewer`;
- remover `target="_blank"` do link mobile de PDF;
- para imagens, preservar comportamento atual se aplicável;
- desktop PDF mantém `<embed src="doctor:serve_attachment">`.

Em `templates/intake/case_detail.html`:

- mesmo padrão usando `intake:attachment_pdf_viewer` para PDFs;
- não mexer em ações de supressão/anexo suplementar;
- desktop PDF mantém `<embed src="intake:serve_attachment">`.

### R4. Cache-Control em anexos PDF

Adicionar `Cache-Control: no-store` em respostas de `serve_attachment` tocadas:

- `apps/doctor/views.py::serve_attachment`;
- `apps/intake/views.py::serve_attachment`.

Preservar `Content-Type` original. O header pode ser aplicado a todos os anexos servidos por essas rotas, não apenas PDFs, se for mais simples e seguro.

### R5. Não implementar histórico de anexos CLEANED

Não criar rota nova para anexos históricos/encerrados neste slice, a menos que já exista autorização clara e testes prévios. Se o implementador identificar link quebrado existente em `closed_case_detail.html`, registrar como follow-up no relatório em vez de ampliar escopo.

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/doctor/urls.py`
2. `apps/doctor/views.py`
3. `templates/doctor/decision.html`
4. `apps/intake/urls.py`
5. `apps/intake/views.py`
6. `templates/intake/case_detail.html`
7. `apps/doctor/tests/test_attachment_views.py`
8. `apps/intake/tests/test_case_detail.py` ou `apps/intake/tests/test_supplemental_attachment_views.py`
9. `openspec/changes/mobile-pdfjs-pwa-viewer/tasks.md`

Não tocar `closed_case_detail.html` salvo para remover/evitar link comprovadamente quebrado sem criar rota nova; justificar no relatório se ocorrer.

## TDD obrigatório

### RED

Adicionar testes falhando antes da implementação:

1. `test_doctor_pdf_attachment_mobile_link_uses_internal_viewer`
   - PDF anexo mobile aponta para `doctor:attachment_pdf_viewer`;
   - não usa `target="_blank"` no link mobile de PDF;
   - desktop embed ainda usa `doctor:serve_attachment`.
2. `test_doctor_attachment_pdf_viewer_renders_for_authorized_doctor`
   - contém `doctor:serve_attachment` como fonte;
   - contém dois “Voltar” e fallback.
3. `test_doctor_attachment_pdf_viewer_404_for_image_attachment`.
4. `test_intake_pdf_attachment_mobile_link_uses_internal_viewer`.
5. `test_intake_attachment_pdf_viewer_renders_for_authorized_nir`.
6. `test_intake_attachment_pdf_viewer_blocks_cleaned_case`.
7. `test_attachment_responses_have_no_store_cache_control` para doctor/intake.

Registre RED no relatório.

### GREEN

Implementar o mínimo.

### REFACTOR

- Se helper privado reduzir duplicação de autorização de anexo, crie-o no próprio arquivo de views do app.
- Não criar uma abstração global para todos os documentos.
- Não alterar modelo `CaseAttachment`.
- Não alterar fluxo de supressão/anexos suplementares.

## Checks de inspeção obrigatórios antes de concluir

Além dos testes automatizados, execute e cole o resultado/resumo no relatório:

```bash
rg -n "attachment_pdf_viewer|serve_attachment|target=\"_blank\"|<embed" templates/doctor/decision.html templates/intake/case_detail.html
rg -n "attachment_pdf_viewer|serve_attachment|content_type.*application/pdf|no-store|resolve_safe_next_url|url_has_allowed_host_and_scheme" apps/doctor/views.py apps/intake/views.py apps/doctor/urls.py apps/intake/urls.py
rg -n "serve_attachment|attachment_pdf_viewer|target=\"_blank\"" templates/intake/closed_case_detail.html
```

Interprete os resultados no relatório: links mobile de anexos PDF nos templates alterados não podem manter `target="_blank"`; imagens podem manter comportamento anterior; `closed_case_detail.html` não deve ganhar rota histórica nova de anexo sem design.

## Critérios de sucesso do slice

- [ ] Anexo PDF médico mobile usa viewer interno.
- [ ] Anexo PDF NIR operacional mobile usa viewer interno.
- [ ] Anexos imagem continuam funcionando como antes.
- [ ] Viewer de anexo rejeita conteúdo não PDF.
- [ ] Viewer de anexo preserva autorização e bloqueia suprimidos/inacessíveis.
- [ ] NIR operacional continua bloqueando anexo de caso `CLEANED`.
- [ ] Desktop preserva `<embed>` para anexos PDF.
- [ ] Rotas de anexo tocadas têm `Cache-Control: no-store`.
- [ ] Não foi criada rota histórica de anexo CLEANED sem design.
- [ ] `tasks.md` atualizado ao concluir.

## Gates de autoavaliação

Responder no relatório:

1. Quais rotas de viewer de anexo foram criadas?
2. Como a view garante que só PDF usa PDF.js?
3. A autorização de `serve_attachment` foi preservada? Onde está testada?
4. O que acontece com anexo suprimido?
5. O que acontece com anexo imagem?
6. O que acontece com anexo NIR de caso `CLEANED`?
7. Desktop ainda usa `<embed>` para PDF?
8. Algum link mobile de anexo PDF ainda usa `target="_blank"` nos templates alterados?
9. Houve alteração no fluxo de supressão ou upload suplementar? Esperado: não.
10. Foi criada rota histórica de anexo? Esperado: não neste slice.

## Relatório obrigatório

Criar:

```text
/tmp/mobile-pdfjs-pwa-viewer-slice-004-report.md
```

Incluir resumo, arquivos alterados, RED/GREEN, snippets antes/depois dos links de anexo, evidência de autorização e cache headers, quality gate e respostas aos gates.

Responder com:

```text
REPORT_PATH=/tmp/mobile-pdfjs-pwa-viewer-slice-004-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/mobile-pdfjs-pwa-viewer/{proposal.md,design.md,tasks.md,specs/mobile-pdf-viewer/spec.md,slices/slice-004-pdf-attachments-viewer.md} first. Assume previous slices are complete.
Implement ONLY Slice 004 using TDD. Follow the DeepSeek4-Flash protocol in this file: plan, RED real, GREEN mínimo, inspection checks, full quality gate and evidence report. Add internal PDF.js viewer routes for PDF attachments in doctor and operational intake surfaces. Update mobile PDF attachment links to use viewer routes without target=_blank; keep desktop embeds and image behavior unchanged. If any required test/check/gate is missing or failing, report INCOMPLETE and do not update tasks.md or commit.
Preserve attachment authorization, suppression handling, and CLEANED blocking for operational NIR. Reject non-PDF attachments in PDF viewer routes. Use apps.cases.navigation.resolve_safe_next_url for attachment viewer back_url; do not create a new next-validation helper or inline validation. Add Cache-Control: no-store to touched attachment-serving responses. Do not create historical CLEANED attachment routes, do not change models/migrations/FSM/pipeline/upload/suppression logic.
Run quality gate, update tasks.md, write /tmp/mobile-pdfjs-pwa-viewer-slice-004-report.md, commit and push. Reply with REPORT_PATH and stop.
```
