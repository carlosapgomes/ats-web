# Slice 002: NIR + dashboard — PDFs principais com viewer mobile interno

## Handoff para implementador LLM com contexto zero

Leia antes de codar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/mobile-pdfjs-pwa-viewer/proposal.md`
4. `openspec/changes/mobile-pdfjs-pwa-viewer/design.md`
5. `openspec/changes/mobile-pdfjs-pwa-viewer/tasks.md`
6. `openspec/changes/mobile-pdfjs-pwa-viewer/specs/mobile-pdf-viewer/spec.md`
7. `openspec/changes/mobile-pdfjs-pwa-viewer/slices/slice-001-doctor-primary-pdf-viewer.md`
8. Este arquivo

Assuma que o Slice 001 já criou o template compartilhado do viewer, `static/js/pdf-viewer.js` e PDF.js vendorizado. Implemente **somente este slice** com TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Reusar o viewer mobile interno para PDFs principais nas superfícies que usam templates NIR/gerenciais:

```text
NIR detalhe operacional → viewer interno → voltar ao caso
NIR detalhe histórico/encerrado → viewer interno → voltar ao caso encerrado
Dashboard detalhe gerencial → viewer interno → voltar ao detalhe/dashboard
```

Desktop deve continuar usando `<embed>` nas páginas alteradas.

## Contexto técnico atual

- `templates/intake/case_detail.html` usa `pdf_url`:
  - mobile: link direto com `target="_blank"`;
  - desktop: `<embed src="{{ pdf_url }}">`.
- `templates/intake/closed_case_detail.html` segue padrão semelhante.
- `apps/intake/views.py` já passa:
  - `pdf_url=reverse("intake:serve_pdf", args=[case.case_id])` no detalhe operacional;
  - `pdf_url=reverse("intake:closed_case_pdf", args=[case.case_id])` no detalhe histórico.
- `apps/dashboard/views.py::dashboard_case_detail` renderiza `templates/intake/case_detail.html` com `pdf_url=reverse("dashboard:case_pdf", args=[case.case_id])`.

## Escopo funcional

### R1. Criar rotas de viewer para NIR operacional e histórico

Adicionar em `apps/intake/urls.py`:

```text
<uuid:case_id>/pdf-viewer/              → intake:pdf_viewer
closed-cases/<uuid:case_id>/pdf-viewer/ → intake:closed_case_pdf_viewer
```

Views em `apps/intake/views.py`:

- `pdf_viewer`:
  - login + `role_required("nir")`;
  - segue a semântica operacional de `serve_pdf`: caso não pode estar `CLEANED`;
  - usa `pdf_url=reverse("intake:serve_pdf", args=[case.case_id])`;
  - `back_url` validado ou fallback `reverse("intake:case_detail", args=[case.case_id])`.
- `closed_case_pdf_viewer`:
  - login + `role_required("nir")`;
  - segue a semântica histórica de `closed_case_detail`/`closed_case_pdf`;
  - usa `pdf_url=reverse("intake:closed_case_pdf", args=[case.case_id])`;
  - fallback `reverse("intake:closed_case_detail", args=[case.case_id])`.

### R2. Criar rota de viewer para dashboard

Adicionar em `apps/dashboard/urls.py`:

```text
<uuid:case_id>/pdf-viewer/ → dashboard:pdf_viewer
```

View em `apps/dashboard/views.py`:

- login + `role_required("manager", "admin")`;
- retorna 404 se não houver `pdf_file`;
- usa `pdf_url=reverse("dashboard:case_pdf", args=[case.case_id])`;
- aceita `next` seguro ou fallback `reverse("dashboard:case_detail", args=[case.case_id])`.

Não usar rota NIR para dashboard.

### R3. Alterar templates para usar viewer no mobile

Em `templates/intake/case_detail.html`:

- mobile PDF link deve usar uma variável de contexto, por exemplo `mobile_pdf_viewer_url`;
- sem `target="_blank"` no link mobile;
- desktop mantém `<embed src="{{ pdf_url }}" type="application/pdf">`.

Em `templates/intake/closed_case_detail.html`:

- mesmo comportamento com `mobile_pdf_viewer_url`.

As views de intake e dashboard devem passar `mobile_pdf_viewer_url` coerente com a superfície.

### R4. Cache-Control nas rotas PDF tocadas

Adicionar `Cache-Control: no-store` preservando `Content-Type: application/pdf` em:

- `apps/intake/views.py::serve_pdf`;
- `apps/intake/views.py::closed_case_pdf`;
- `apps/dashboard/views.py::dashboard_case_pdf`.

### R5. Não duplicar JS/template

Reusar o template e JS criados no Slice 001. Não criar outro viewer paralelo.

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/intake/urls.py`
2. `apps/intake/views.py`
3. `templates/intake/case_detail.html`
4. `templates/intake/closed_case_detail.html`
5. `apps/dashboard/urls.py`
6. `apps/dashboard/views.py`
7. `apps/intake/tests/test_case_detail.py` ou testes intake dedicados
8. `apps/intake/tests/test_slice_001_nir_historical_detail.py` se fizer sentido para histórico
9. `apps/dashboard/tests/test_dashboard.py`
10. `openspec/changes/mobile-pdfjs-pwa-viewer/tasks.md`

Não tocar em `static/js/pdf-viewer.js` salvo bug real encontrado e justificado.

## TDD obrigatório

### RED

Adicionar testes falhando antes da implementação:

1. `test_intake_case_detail_mobile_pdf_link_uses_internal_viewer`
   - `intake:case_detail` contém `intake:pdf_viewer`;
   - mobile link não usa `target="_blank"`;
   - embed desktop ainda usa `intake:serve_pdf`.
2. `test_intake_pdf_viewer_authorized_nir_renders`
   - viewer contém `intake:serve_pdf` como fonte;
   - contém dois “Voltar”;
   - fallback PDF presente.
3. `test_intake_closed_case_detail_mobile_pdf_link_uses_internal_viewer`
   - contém `intake:closed_case_pdf_viewer`;
   - embed desktop usa `intake:closed_case_pdf`.
4. `test_intake_closed_case_pdf_viewer_authorized_nir_renders`.
5. `test_dashboard_case_detail_mobile_pdf_link_uses_dashboard_viewer`
   - contém `dashboard:pdf_viewer`;
   - não contém `intake:pdf_viewer` para dashboard;
   - embed desktop usa `dashboard:case_pdf`.
6. `test_dashboard_pdf_viewer_authorization`
   - manager/admin acessam;
   - NIR/doctor/scheduler não acessam.
7. Testes de `Cache-Control: no-store` para as três rotas binárias tocadas.

Registre evidência RED no relatório.

### GREEN

Implementar o mínimo para passar.

### REFACTOR

- Se houver repetição de validação `next`, pode criar helper pequeno local/privado, mas evite novo módulo genérico se não necessário.
- Não alterar comportamento de autorização existente fora dos viewers.
- Não mexer em anexos neste slice.

## Critérios de sucesso do slice

- [ ] Detalhe NIR operacional mobile usa viewer interno.
- [ ] Detalhe NIR histórico mobile usa viewer interno.
- [ ] Detalhe dashboard mobile usa viewer interno do dashboard.
- [ ] Desktop preserva embeds com as rotas binárias corretas.
- [ ] Viewers usam rotas protegidas corretas para o PDF.
- [ ] `next` é validado ou fallback canônico é usado.
- [ ] Rotas PDF tocadas têm `Cache-Control: no-store`.
- [ ] Nenhuma permissão foi relaxada.
- [ ] Nenhum JS/framework/bundler novo foi criado.
- [ ] `tasks.md` atualizado ao concluir.

## Gates de autoavaliação

Responder no relatório:

1. Quais três rotas de viewer foram criadas neste slice?
2. Qual rota PDF protegida cada viewer usa?
3. Dashboard usa rota própria ou reaproveitou NIR? Esperado: rota própria dashboard.
4. O detalhe NIR operacional ainda bloqueia PDF de caso `CLEANED` na rota operacional?
5. O detalhe histórico NIR usa a rota histórica para `CLEANED`?
6. O desktop dos templates alterados ainda contém `<embed>`?
7. Algum link mobile de PDF principal ainda usa `target="_blank"` nessas superfícies?
8. Como o `next` foi validado?
9. Quais testes cobrem autorização manager/admin versus outros papéis?
10. Alguma alteração em models/migrations/FSM/pipeline? Esperado: não.

## Relatório obrigatório

Criar:

```text
/tmp/mobile-pdfjs-pwa-viewer-slice-002-report.md
```

Incluir:

- resumo;
- arquivos alterados;
- RED/GREEN;
- snippets antes/depois dos links mobile em `case_detail` e `closed_case_detail`;
- snippets das novas views/rotas;
- evidência de cache headers;
- quality gate;
- respostas aos gates;
- justificativa para arquivos extras.

Responder com:

```text
REPORT_PATH=/tmp/mobile-pdfjs-pwa-viewer-slice-002-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/mobile-pdfjs-pwa-viewer/{proposal.md,design.md,tasks.md,specs/mobile-pdf-viewer/spec.md,slices/slice-002-intake-dashboard-primary-pdf-viewer.md} first. Assume Slice 001 is complete.
Implement ONLY Slice 002 using TDD. Reuse the shared PDF.js viewer template/static from Slice 001.
Add internal mobile PDF viewer routes for intake operational case detail, intake closed-case detail, and dashboard case detail. Update the relevant templates so mobile links use viewer routes without target=_blank, while desktop embeds continue using the existing protected PDF binary routes.
Preserve permissions and route boundaries: dashboard must use dashboard PDF route, not intake. Validate next URLs or use canonical fallbacks. Add Cache-Control: no-store to intake serve_pdf, intake closed_case_pdf and dashboard case_pdf.
Do not touch attachments, models, migrations, FSM, pipeline, or add frontend frameworks. Run quality gate, update tasks.md, create /tmp/mobile-pdfjs-pwa-viewer-slice-002-report.md with evidence, commit and push. Reply with REPORT_PATH and stop.
```
