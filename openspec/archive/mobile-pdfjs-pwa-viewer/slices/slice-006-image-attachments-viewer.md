# Slice 006: Anexos imagem — viewer interno mobile para PNG/JPEG

## Handoff para implementador LLM com contexto zero

Leia antes de codar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/mobile-pdfjs-pwa-viewer/proposal.md`
4. `openspec/changes/mobile-pdfjs-pwa-viewer/design.md`
5. `openspec/changes/mobile-pdfjs-pwa-viewer/tasks.md`
6. `openspec/changes/mobile-pdfjs-pwa-viewer/specs/mobile-pdf-viewer/spec.md`
7. `openspec/changes/mobile-pdfjs-pwa-viewer/slices/slice-003b-consolidate-pdf-viewer-next-validation.md`
8. `openspec/changes/mobile-pdfjs-pwa-viewer/slices/slice-004-pdf-attachments-viewer.md`
9. `openspec/changes/mobile-pdfjs-pwa-viewer/slices/slice-005-closed-case-attachment-pdf-viewer.md`
10. Este arquivo

Implemente **somente este Slice 006** usando TDD: RED → GREEN → REFACTOR. Este slice antecipa o mesmo problema PWA que já foi corrigido para PDFs: anexos de imagem (`image/jpeg`, `image/png`) ainda podem abrir via `target="_blank"` no mobile.

Assuma que:

- PDF continua usando PDF.js e rotas de `*_attachment_pdf_viewer` já implementadas;
- `apps.cases.navigation.resolve_safe_next_url` já existe;
- rotas binárias protegidas de anexos já existem para doctor, NIR operacional e NIR histórico;
- o Slice 005 já criou `intake:closed_case_attachment` para anexos históricos.

## Protocolo obrigatório para implementador DeepSeek4-Flash

Este slice será implementado por um modelo rápido e com tendência a concluir cedo demais. Portanto, siga este protocolo literalmente. **Se qualquer item abaixo falhar, o slice está INCOMPLETO**: não marque `tasks.md`, não faça commit/push e responda com bloqueio + evidência.

1. **Plano antes de editar**: escreva no relatório uma mini matriz `Requisito → arquivo(s) → teste(s)`. Não implemente requisito sem teste ou justificativa explícita.
2. **RED real**: crie/ajuste testes primeiro e rode o subconjunto alvo. Pelo menos um teste novo deve falhar pelo motivo esperado. Se o teste passar antes da implementação, ele não prova o comportamento; corrija o teste.
3. **GREEN mínimo**: implemente somente o necessário para os testes do slice passarem. Não faça refactor amplo, não toque em apps fora do escopo e não antecipe slices futuros.
4. **Verificação por inspeção**: além dos testes, rode buscas `rg`/inspeções descritas neste slice para comprovar os contratos críticos do slice.
5. **Quality gate completo**: execute exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` e `uv run pytest`. Se algum comando falhar, o slice não está pronto.
6. **Relatório com evidência, não opinião**: cole comandos executados, resumo das saídas, testes RED/GREEN, snippets antes/depois e respostas objetivas aos gates. Inclua também `Handoff para verificador` com: arquivos alterados, comandos exatos para rerun, riscos/limitações e checklist dos requisitos R1..Rn. Inclua uma seção final `Status: COMPLETE` somente se todos os critérios estiverem comprovados.

### Condições automáticas de INCOMPLETO

Marque como incompleto se ocorrer qualquer uma destas situações:

- teste planejado não foi escrito ou não foi executado;
- quality gate completo não foi executado;
- qualquer teste/lint/mypy falhou;
- `tasks.md` foi marcado apesar de falha ou pendência;
- link mobile de imagem em doctor/intake operacional/intake histórico continuar usando `target="_blank"`;
- desktop deixar de renderizar imagem inline com `<img>`;
- viewer de imagem aceitar PDF ou outro tipo não `image/jpeg`/`image/png`;
- viewer usa `MEDIA_URL`, caminho físico do arquivo ou URL sem autorização;
- `next` é usado sem `apps.cases.navigation.resolve_safe_next_url` e fallback canônico;
- autorização existente de anexos for relaxada;
- rota histórica de imagem aceitar caso fora de `_is_historical_scope_nir(case)`;
- relatório temporário não foi criado no caminho exigido.

## Objetivo do slice

Criar uma página interna simples para visualização mobile/PWA de anexos imagem, sem biblioteca externa:

```text
Usuário toca anexo PNG/JPEG no mobile
→ navega para página interna do app
→ vê imagem com <img class="img-fluid">
→ botão Voltar no topo e no rodapé retorna ao caso
```

A solução é propositalmente simples. **Não usar PDF.js, canvas, zoom avançado, galeria, crop, rotação ou biblioteca JS.**

## Contexto técnico atual

Templates com anexos imagem:

- `templates/doctor/decision.html`
  - mobile imagem ainda usa link direto para `doctor:serve_attachment` com `target="_blank"`;
  - desktop imagem usa `<img src="doctor:serve_attachment">` dentro do collapse.
- `templates/intake/case_detail.html`
  - mobile imagem ainda usa link direto para `intake:serve_attachment` com `target="_blank"`;
  - desktop imagem usa `<img src="intake:serve_attachment">`.
- `templates/intake/closed_case_detail.html`
  - após Slice 005, imagem histórica usa `intake:closed_case_attachment`;
  - mobile imagem ainda pode usar `target="_blank"`;
  - desktop imagem usa `<img src="intake:closed_case_attachment">`.

Rotas binárias protegidas:

- doctor operacional: `doctor:serve_attachment`;
- NIR operacional: `intake:serve_attachment`;
- NIR histórico: `intake:closed_case_attachment`.

## Escopo funcional

### R1. Criar template compartilhado de image viewer

Criar:

```text
templates/image_viewer/mobile_image_viewer.html
```

Contexto mínimo:

```python
{
    "viewer_title": "Anexo de imagem",
    "case": case,
    "attachment": attachment,
    "image_url": protected_binary_route,
    "fallback_image_url": protected_binary_route,
    "back_url": resolved_safe_next_or_fallback,
    "back_label": "← Voltar ao caso",
}
```

O template deve conter:

- botão/link “Voltar” no topo;
- título curto;
- nome do arquivo;
- `<img src="{{ image_url }}" class="img-fluid" alt="{{ attachment.original_filename }}">`;
- fallback “Abrir imagem original” apontando para rota protegida;
- botão/link “Voltar” no rodapé.

Não adicionar JS. Se usar CSS inline mínimo para `max-height`, manter simples e justificar no relatório.

### R2. Criar viewer de imagem para médico

Adicionar em `apps/doctor/urls.py`:

```text
cases/<uuid:case_id>/attachments/<uuid:attachment_id>/image-viewer/ → doctor:attachment_image_viewer
```

Criar view em `apps/doctor/views.py`:

- `@login_required`;
- `@role_required("doctor")`;
- reutilizar a mesma autorização de `doctor:serve_attachment`, preferencialmente helper já existente `_get_doctor_attachment_or_404`;
- aceitar somente `attachment.content_type in {"image/jpeg", "image/png"}`;
- rejeitar PDF e outros tipos com 404;
- usar `image_url=reverse("doctor:serve_attachment", args=[case.case_id, attachment.attachment_id])`;
- usar `resolve_safe_next_url(request, reverse("doctor:decision", args=[case.case_id]))`.

### R3. Criar viewer de imagem para NIR operacional

Adicionar em `apps/intake/urls.py`:

```text
<uuid:case_id>/attachments/<uuid:attachment_id>/image-viewer/ → intake:attachment_image_viewer
```

Criar view em `apps/intake/views.py`:

- `@login_required`;
- `@role_required("nir")`;
- reutilizar a mesma autorização de `intake:serve_attachment`, preferencialmente `_get_nir_attachment_or_404`;
- manter bloqueio de `CLEANED` para operacional;
- aceitar somente `image/jpeg` e `image/png`;
- usar `image_url=reverse("intake:serve_attachment", args=[case.case_id, attachment.attachment_id])`;
- usar `resolve_safe_next_url(request, reverse("intake:case_detail", args=[case.case_id]))`.

### R4. Criar viewer de imagem para NIR histórico

Adicionar em `apps/intake/urls.py`:

```text
closed-cases/<uuid:case_id>/attachments/<uuid:attachment_id>/image-viewer/ → intake:closed_case_attachment_image_viewer
```

Criar view em `apps/intake/views.py`:

- `@login_required`;
- `@role_required("nir")`;
- reutilizar autorização histórica de Slice 005, preferencialmente `_get_closed_case_attachment_or_404`;
- exigir `_is_historical_scope_nir(case)` via helper existente;
- aceitar somente `image/jpeg` e `image/png`;
- usar `image_url=reverse("intake:closed_case_attachment", args=[case.case_id, attachment.attachment_id])`;
- usar `resolve_safe_next_url(request, reverse("intake:closed_case_detail", args=[case.case_id]))`.

### R5. Atualizar links mobile de imagem nos templates

Atualizar:

- `templates/doctor/decision.html`;
- `templates/intake/case_detail.html`;
- `templates/intake/closed_case_detail.html`.

Comportamento esperado:

- se `att.content_type == "application/pdf"`: manter viewer PDF existente;
- se `att.content_type` for imagem (`image/jpeg` ou `image/png`, ou condição template compatível com `"image" in att.content_type`): mobile usa o viewer de imagem correspondente, sem `target="_blank"`;
- para outros tipos não suportados, se existirem, pode manter link direto protegido com `target="_blank"`;
- desktop mantém collapse + `<img>` inline para imagens;
- botão desktop “Abrir em nova aba” pode permanecer, mas deve usar rota protegida correta.

### R6. Testar contratos e regressões

Adicionar testes para:

- viewer renderiza para imagem JPEG/PNG autorizada;
- viewer rejeita PDF;
- viewer rejeita tipo não suportado, se fixture simples for viável;
- viewer usa rota binária protegida correta;
- viewer tem dois links “Voltar”;
- viewer rejeita `next=https://evil.example/...`;
- links mobile de imagem nos 3 templates usam viewer interno e não `target="_blank"`;
- desktop preserva `<img>` inline nos 3 templates;
- autorização/supressão/histórico continuam preservados.

## Arquivos esperados

Idealmente tocar apenas:

1. `templates/image_viewer/mobile_image_viewer.html` (novo)
2. `apps/doctor/urls.py`
3. `apps/doctor/views.py`
4. `templates/doctor/decision.html`
5. `apps/doctor/tests/test_attachment_views.py`
6. `apps/intake/urls.py`
7. `apps/intake/views.py`
8. `templates/intake/case_detail.html`
9. `templates/intake/closed_case_detail.html`
10. `apps/intake/tests/test_supplemental_attachment_views.py` ou `apps/intake/tests/test_closed_case_attachment_viewer.py`
11. `openspec/changes/mobile-pdfjs-pwa-viewer/tasks.md`

Se tocar mais arquivos, justificar no relatório. Não tocar PDF.js, templates de PDF viewer, models, migrations, FSM ou pipeline.

## Fora de escopo

Não implementar neste slice:

- zoom avançado;
- galeria/carrossel;
- rotação/crop/anotações;
- download customizado;
- suporte a GIF/BMP/WebP/TIFF;
- OCR;
- alteração do upload/validação de anexos;
- acesso histórico para doctor/scheduler/dashboard.

## TDD obrigatório

### RED

Antes de implementar, adicione testes falhando. Sugestão objetiva:

1. `test_doctor_image_attachment_mobile_link_uses_internal_viewer`
   - link mobile de imagem usa `doctor:attachment_image_viewer`;
   - não tem `target="_blank"` no link mobile da imagem;
   - desktop contém `<img` com `doctor:serve_attachment`.

2. `test_doctor_attachment_image_viewer_renders_for_authorized_doctor`
   - contém URL `doctor:serve_attachment` como `image_url`;
   - contém nome do arquivo;
   - contém dois “Voltar”.

3. `test_doctor_attachment_image_viewer_404_for_pdf_attachment`.

4. `test_intake_image_attachment_mobile_link_uses_internal_viewer`.

5. `test_intake_attachment_image_viewer_renders_for_authorized_nir`.

6. `test_intake_attachment_image_viewer_blocks_cleaned_case`.

7. `test_closed_case_image_attachment_mobile_link_uses_internal_viewer`.

8. `test_closed_case_attachment_image_viewer_renders_for_authorized_nir`.

9. `test_closed_case_attachment_image_viewer_404_for_pdf_attachment`.

10. `test_image_viewer_rejects_external_next` em pelo menos uma superfície, idealmente nas três se simples.

Registre no relatório o comando RED e as falhas esperadas.

### GREEN

Implementar o mínimo para os testes passarem.

### REFACTOR

- Se a checagem de MIME duplicar muito, criar helper pequeno, por exemplo `_is_supported_image_attachment(attachment)`.
- Não criar classe genérica de viewer.
- Não tocar no viewer PDF.
- Não alterar autorização existente.

## Checks de inspeção obrigatórios antes de concluir

Além dos testes automatizados, execute e cole o resultado/resumo no relatório:

```bash
rg -n "attachment_image_viewer|closed_case_attachment_image_viewer|target=\"_blank\"|<img|<embed" templates/doctor/decision.html templates/intake/case_detail.html templates/intake/closed_case_detail.html
rg -n "attachment_image_viewer|closed_case_attachment_image_viewer|resolve_safe_next_url|image/jpeg|image/png|serve_attachment|closed_case_attachment" apps/doctor/views.py apps/intake/views.py apps/doctor/urls.py apps/intake/urls.py
rg -n "mobile_image_viewer|image_url|fallback_image_url|Voltar|<img" templates/image_viewer/mobile_image_viewer.html
rg -n "attachment_image_viewer|closed_case_attachment_image_viewer|evil.example|target=\"_blank\"|<img" apps/doctor/tests/*.py apps/intake/tests/*.py
```

Interpretação obrigatória no relatório:

- links mobile de imagem nas 3 superfícies devem usar viewer interno e não `target="_blank"`;
- `target="_blank"` remanescente só é aceitável em botão desktop “Abrir em nova aba” ou fallback justificado;
- `<img>` desktop deve permanecer nos templates;
- viewer deve usar `resolve_safe_next_url`;
- viewer não deve usar PDF.js.

## Critérios de sucesso do slice

- [ ] Médico mobile abre anexo JPEG/PNG em viewer interno.
- [ ] NIR operacional mobile abre anexo JPEG/PNG em viewer interno.
- [ ] NIR histórico mobile abre anexo JPEG/PNG em viewer interno.
- [ ] Links mobile de imagem não usam `target="_blank"`.
- [ ] Desktop preserva `<img>` inline para imagens.
- [ ] Viewer de imagem tem “Voltar” no topo e rodapé.
- [ ] Viewer de imagem usa rota protegida do anexo, não `MEDIA_URL`.
- [ ] Viewer aceita somente `image/jpeg` e `image/png`.
- [ ] Viewer rejeita PDF.
- [ ] Viewer usa `resolve_safe_next_url` e rejeita `next` externo.
- [ ] Autorizações existentes de doctor/NIR operacional/NIR histórico foram preservadas.
- [ ] Nenhum model/migration/FSM/pipeline/PDF.js foi alterado.
- [ ] `tasks.md` atualizado ao concluir.

## Gates de autoavaliação

Responder no relatório:

1. Quais rotas de image viewer foram criadas?
2. Qual template compartilhado renderiza a imagem?
3. Quais MIME types são aceitos?
4. Como o viewer rejeita PDF?
5. Qual rota binária protegida cada viewer usa?
6. Como o `next` é validado?
7. Onde está testado que `evil.example` não aparece?
8. Onde está testado que links mobile de imagem não usam `target="_blank"`?
9. Onde está testado que desktop preserva `<img>`?
10. Alguma autorização/model/migration/FSM/PDF.js foi alterada? Esperado: não.

## Relatório obrigatório

Criar:

```text
/tmp/mobile-pdfjs-pwa-viewer-slice-006-report.md
```

O relatório deve conter:

- `Status: COMPLETE` ou `Status: INCOMPLETE`;
- matriz requisito → arquivo(s) → teste(s);
- evidência RED;
- evidência GREEN;
- snippets antes/depois dos links mobile de imagem nas 3 superfícies;
- snippet do template `mobile_image_viewer.html`;
- resultado dos checks de inspeção obrigatórios;
- resultado do quality gate completo;
- respostas aos gates de autoavaliação;
- `Handoff para verificador` com arquivos alterados, comandos para rerun, riscos/limitações e checklist R1..R6.

Responder ao final com:

```text
REPORT_PATH=/tmp/mobile-pdfjs-pwa-viewer-slice-006-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/mobile-pdfjs-pwa-viewer/{proposal.md,design.md,tasks.md,specs/mobile-pdf-viewer/spec.md,slices/slice-006-image-attachments-viewer.md} first.
Implement ONLY Slice 006. Follow the DeepSeek4-Flash protocol in this file: plan, RED real, GREEN mínimo, inspection checks, full quality gate and evidence report. If any required test/check/gate is missing or failing, report INCOMPLETE and do not update tasks.md or commit.
Deliver internal mobile/PWA image viewers for PNG/JPEG attachments in doctor, NIR operational and NIR historical surfaces. Create a simple shared template with <img>, top/bottom Voltar, fallback original link, and no JS/PDF.js. Update mobile image attachment links to use viewer routes without target=_blank; preserve desktop inline <img>.
Use apps.cases.navigation.resolve_safe_next_url for back_url. Reuse existing attachment authorization helpers/routes. Accept only image/jpeg and image/png; reject PDF and other types. Do not touch models, migrations, FSM, pipeline, upload/suppression logic, dashboard, scheduler or PDF.js.
Run quality gate, update tasks.md only if all checks pass, create /tmp/mobile-pdfjs-pwa-viewer-slice-006-report.md, commit and push. Reply with REPORT_PATH and stop.
```
