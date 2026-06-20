# Slice 002: UX condicional, detalhe compartilhado e hardening operacional

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`, monolito Django SSR. Este slice continua o change `case-attachments-initial-upload` após o Slice 001.

Leia, nesta ordem:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/case-attachments-initial-upload/proposal.md`
4. `openspec/changes/case-attachments-initial-upload/design.md`
5. `openspec/changes/case-attachments-initial-upload/tasks.md`
6. `openspec/changes/case-attachments-initial-upload/slices/slice-001-attachment-upload-doctor-view.md`
7. Este arquivo
8. Arquivos modificados no Slice 001
9. `static/js/upload.js`
10. `templates/intake/intake_home.html`
11. `templates/intake/case_detail.html`
12. `apps/intake/views.py`
13. Detalhes read-only já existentes em `apps/doctor/views.py`, `apps/scheduler/views.py` e `apps/dashboard/views.py`, se necessário

Implemente **somente este slice** com TDD: RED → GREEN → REFACTOR.

## Pré-condição

O Slice 001 deve ter entregue:

- `CaseAttachment`;
- upload backend com anexos para exatamente 1 PDF principal;
- rota protegida médica;
- anexos visíveis na tela de decisão médica;
- eventos `CASE_ATTACHMENT_ADDED`.

Se Slice 001 não estiver completo, pare e reporte a pendência. Não implemente workarounds grandes neste slice.

## Objetivo do slice

Melhorar a experiência operacional e completar a visualização consistente:

```text
NIR seleciona arquivos principais
→ UI mostra anexos somente quando há exatamente 1 PDF principal
→ NIR vê preview/resumo dos anexos
→ upload respeita limites client-side e server-side
→ detalhes NIR/read-only mostram anexos na mesma ordem visual
```

Ordem visual desejada nos detalhes:

1. texto extraído;
2. PDF principal;
3. um collapsible por anexo;
4. timeline.

## Escopo funcional

### R1. UI condicional no upload

Atualizar `static/js/upload.js` e `templates/intake/intake_home.html` para que anexos sejam visíveis/habilitados somente quando há exatamente 1 PDF principal selecionado.

Comportamento:

- 0 PDFs principais: seção de anexos oculta/desabilitada;
- 1 PDF principal: seção de anexos visível/habilitada;
- >1 PDFs principais: seção de anexos oculta/desabilitada e anexos selecionados são limpos.

A UI deve comunicar:

```text
Anexos só podem ser enviados quando há exatamente um relatório principal selecionado.
```

### R2. Preview client-side de anexos

Adicionar preview simples para anexos:

- lista de nomes;
- tamanho por arquivo;
- contagem;
- tamanho total;
- thumbnail/preview para JPEG/PNG quando viável;
- preview/embed ou link/ícone claro para PDF quando viável;
- botão remover por anexo.

Validação client-side:

- extensão PDF/JPG/JPEG/PNG;
- máximo 10 anexos;
- máximo 20 MB por anexo;
- máximo 200 MB total.

A validação client-side é conveniência. A validação server-side do Slice 001 continua sendo a fonte de verdade.

Quando houver anexos selecionados, exigir checkbox antes do envio:

```text
Confirmo que revisei os anexos e que pertencem ao mesmo paciente/caso.
```

O checkbox é medida preventiva contra anexo de outro paciente. A validação server-side pode apenas exigir presença do campo quando `attachment_files` não estiver vazio; não é garantia clínica, mas força confirmação operacional.

### R3. Detalhe NIR/read-only exibe anexos

Atualizar `templates/intake/case_detail.html` e contextos necessários para exibir anexos após o PDF principal e antes da timeline.

Aplicar pelo menos ao detalhe NIR operacional (`apps/intake/views.py::case_detail`). Se o template compartilhado já for usado por médico decidido, scheduler processado ou dashboard, garantir que a inclusão não quebre essas telas.

Exibição por anexo:

- collapsible por anexo;
- PDF com `<embed>`;
- JPEG/PNG com `<img class="img-fluid">`;
- link `Abrir em nova aba`;
- metadados: nome original, tipo, tamanho aproximado, data/hora, usuário.

### R4. Rota protegida NIR para servir anexos

Se o Slice 001 criou apenas rota médica, adicionar rota NIR em `apps/intake/urls.py`/`views.py`, por exemplo:

```text
/cases/<case_id>/attachments/<attachment_id>/
```

Regras:

- login e papel ativo `nir`;
- caso não pode estar `CLEANED` pela rota operacional NIR, coerente com PDF principal;
- retornar 404 se anexo/caso não autorizado.

Se houver helper compartilhado seguro criado no Slice 001, reutilizar sem duplicar lógica.

### R5. Labels/eventos na timeline

Adicionar label/ícone para `CASE_ATTACHMENT_ADDED` nos maps de timeline se ainda não existir:

- label: `Anexo adicionado`;
- dot css: `nir` ou `system` conforme padrão existente.

### R6. Hardening de limites e mensagens

Revisar mensagens backend/frontend para ficarem consistentes:

- formato inválido;
- arquivo acima de 20 MB;
- mais de 10 anexos;
- anexos enviados com bulk upload;
- total de anexos acima de 200 MB.

Não alterar contrato do upload principal além do necessário.

### R7. Verificação prática de limite de POST no escopo de testes

Adicionar teste funcional com payload total acima de `DATA_UPLOAD_MAX_MEMORY_SIZE` via arquivos pequenos/monkeypatch quando possível, ou documentar no relatório por que o teste não é representativo.

Ponto de atenção: o upload NIR ocorre por intranet direta ao IP do servidor, não por Cloudflare. Não criar dependência ou configuração para Cloudflare.

## Fora de escopo

- OCR/LLM/classificação de anexos.
- Dashboard avançado de anexos.
- Reabrir caso negado.
- Anexos após decisão médica.
- Refatorar completamente o upload JS.
- Criar framework JS ou dependência nova.

## Arquivos prováveis

Idealmente tocar apenas:

1. `static/js/upload.js`
2. `templates/intake/intake_home.html`
3. `apps/intake/views.py`
4. `apps/intake/urls.py`
5. `templates/intake/case_detail.html`
6. testes em `apps/intake/tests/test_upload.py` e `apps/intake/tests/test_case_detail.py`
7. possivelmente testes médicos/read-only se o template compartilhado exigir ajuste
8. `openspec/changes/case-attachments-initial-upload/tasks.md` ao final

Se precisar alterar serviços/modelos do Slice 001, justificar no relatório. Evitar mudanças de domínio grandes neste slice.

## TDD obrigatório

Antes de implementar, adicionar testes falhando.

### Testes mínimos de UI/template upload

1. `test_upload_page_has_attachment_section_with_guidance`
   - seção existe;
   - texto informa que anexos exigem exatamente 1 relatório principal;
   - input `attachment_files` aceita `.pdf,.jpg,.jpeg,.png`.

2. `test_upload_js_contains_single_pdf_attachment_gate`
   - teste simples de conteúdo ou teste JS se infraestrutura existir;
   - deve provar que há lógica para exatamente 1 PDF principal.

3. `test_upload_page_requires_attachment_review_confirmation_when_attachments_present`
   - template contém checkbox de confirmação de revisão dos anexos;
   - texto menciona que anexos devem pertencer ao mesmo paciente/caso.

### Testes mínimos backend/UX de upload

4. `test_bulk_upload_with_attachments_shows_clear_error_message`
   - POST com 2 PDFs + anexo;
   - mensagem clara.

5. `test_attachment_total_size_limit_message`
   - monkeypatch de limite total baixo;
   - mensagem clara.

### Testes mínimos detalhe NIR/read-only

6. `test_intake_case_detail_renders_attachment_after_pdf_before_timeline`
   - caso operacional com anexo;
   - HTML contém PDF principal antes do anexo e anexo antes da timeline.

7. `test_intake_case_detail_embeds_pdf_attachment`
   - anexo PDF gera embed/link protegido.

8. `test_intake_case_detail_embeds_image_attachment`
   - anexo PNG/JPEG gera `<img>`.

9. `test_intake_attachment_view_serves_operational_case_attachment`
   - NIR acessa anexo de caso operacional.

10. `test_intake_attachment_view_404_for_cleaned_case`
   - rota operacional NIR não serve anexo de caso `CLEANED`.

11. `test_case_attachment_added_event_has_timeline_label`
    - timeline mostra label `Anexo adicionado`.

### Teste de regressão médica/shared

12. `test_doctor_decision_still_renders_attachments_after_shared_template_changes`
    - garante que alterações não quebraram tela médica do Slice 001.

## Clean code / DRY / YAGNI

- Reutilizar helper/contexto de anexos se já existir.
- Não duplicar renderização complexa em muitos templates; se necessário, criar partial pequeno, por exemplo `templates/cases/_attachments.html` ou similar, mas só se reduzir duplicação real.
- Não introduzir HTMX/React/Vue ou libs novas.
- Não criar abstração genérica de “document processing”.
- Não implementar OCR/LLM.
- JS deve continuar vanilla, coeso e legível.
- Preferir funções pequenas para formatar tamanho/tipo.

## Critérios de aceitação

- [ ] TDD seguido: testes novos falham antes da implementação e passam após.
- [ ] UI mostra anexos somente com exatamente 1 PDF principal selecionado.
- [ ] Selecionar bulk upload limpa/desabilita anexos.
- [ ] Preview de anexos mostra contagem/tamanho e valida limites básicos.
- [ ] Preview permite remover anexos antes do envio.
- [ ] Envio com anexos exige confirmação explícita de revisão/pertencimento ao mesmo paciente/caso.
- [ ] Backend continua validando todos os limites independentemente do JS.
- [ ] Detalhe NIR/read-only exibe anexos em ordem correta.
- [ ] Rota NIR protegida serve anexos de casos operacionais e bloqueia `CLEANED`.
- [ ] Timeline tem label para `CASE_ATTACHMENT_ADDED`.
- [ ] Tela médica do Slice 001 continua funcionando.
- [ ] Nenhum estado FSM novo foi criado.
- [ ] Nenhum processamento LLM/OCR de anexos foi implementado.
- [ ] Quality gate do AGENTS.md passa.

## Gates de autoavaliação

Responder no relatório do slice:

1. Como a UI detecta exatamente 1 PDF principal?
2. O que acontece com anexos já selecionados quando o usuário adiciona um segundo PDF principal?
3. Como o usuário pré-visualiza/remove anexos antes de enviar?
4. Como o checkbox de confirmação reduz o risco de anexo de outro paciente?
5. Quais limites são validados no client-side e quais no server-side?
6. Qual teste prova a ordem visual texto → PDF principal → anexos → timeline?
7. Qual teste prova que `CLEANED` não é servido pela rota operacional NIR?
8. Você criou partial compartilhado? Se sim, por que reduziu duplicação? Se não, por que não foi necessário?
9. Há alguma mudança em pipeline/LLM/FSM? Se sim, está errado para este slice.

## Comandos de validação mínimos

Durante desenvolvimento:

```bash
uv run pytest apps/intake/tests/test_upload.py apps/intake/tests/test_case_detail.py apps/doctor/tests/test_views.py -q
uv run ruff check apps/intake apps/doctor static
uv run ruff format --check apps/intake apps/doctor
uv run mypy apps/intake apps/doctor
```

Antes de finalizar:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório final obrigatório

Criar um relatório temporário em markdown, por exemplo:

```text
/tmp/ats-web-slice-002-case-attachments-ux-report.md
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
REPORT_PATH=/tmp/ats-web-slice-002-case-attachments-ux-report.md
```

Depois de responder, **parar** e pedir confirmação explícita antes de qualquer próximo slice.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/case-attachments-initial-upload/proposal.md, design.md, tasks.md, Slice 001, and slices/slice-002-attachment-ux-shared-detail-hardening.md. Implement ONLY Slice 002 using TDD (RED → GREEN → REFACTOR). Keep code clean, DRY and YAGNI.

Goal: make the upload UI show/enable attachments only when exactly 1 main PDF is selected, add attachment preview/removal/limits and mandatory review confirmation in vanilla JS, and show attachments in the NIR/read-only case detail after the main PDF and before the timeline. Add protected NIR attachment serving if missing. Do not implement OCR/LLM, do not alter FSM, do not add JS frameworks.

Add failing tests first for upload template/JS gate, backend messages, NIR detail rendering/order, protected attachment route, timeline label, and regression of doctor attachment display. Then implement minimal code.

Run the full quality gate: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/case-attachments-initial-upload/tasks.md when complete. Create /tmp/ats-web-slice-002-case-attachments-ux-report.md with before/after snippets and validation evidence. Commit and push. Reply REPORT_PATH=<path> and stop.
```
