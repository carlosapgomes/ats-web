# Slice 001: Médico — PDF principal com viewer mobile interno

## Handoff para implementador LLM com contexto zero

Você está no projeto ATS Web, um monolito Django SSR sem SPA/DRF. Leia antes de codar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/mobile-pdfjs-pwa-viewer/proposal.md`
4. `openspec/changes/mobile-pdfjs-pwa-viewer/design.md`
5. `openspec/changes/mobile-pdfjs-pwa-viewer/tasks.md`
6. `openspec/changes/mobile-pdfjs-pwa-viewer/specs/mobile-pdf-viewer/spec.md`
7. Este arquivo

Implemente **somente este slice** usando TDD: RED → GREEN → REFACTOR. Mantenha o slice vertical e enxuto.

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
- `next` é usado sem validação/fallback canônico;
- `Cache-Control: no-store` exigido pelo slice ficou ausente;
- PDF.js/viewer foi declarado pronto sem teste/inspeção que comprove carregamento do JS/template;
- relatório temporário não foi criado no caminho exigido.


## Objetivo do slice

Entregar o primeiro fluxo end-to-end do novo viewer:

```text
Médico abre tela de decisão
→ no mobile toca “Visualizar PDF Original”
→ navega para página interna do app
→ PDF renderiza via PDF.js
→ botão Voltar no topo/rodapé retorna à decisão
```

Desktop deve continuar usando o `<embed>` atual em `templates/doctor/decision.html`.

## Contexto técnico atual

Arquivos relevantes hoje:

- `templates/doctor/decision.html`
  - mobile usa link direto para `{% url 'doctor:serve_pdf' case.case_id %}` com `target="_blank"`;
  - desktop usa collapse + `<embed src="{% url 'doctor:serve_pdf' case.case_id %}" type="application/pdf">`.
- `apps/doctor/urls.py`
  - já tem `path("<uuid:case_id>/pdf/", views.serve_pdf, name="serve_pdf")`.
- `apps/doctor/views.py::serve_pdf`
  - retorna `FileResponse(..., content_type="application/pdf")` com `@role_required("doctor")` e `@xframe_options_sameorigin`.

## Escopo funcional

### R1. Criar infraestrutura mínima compartilhável do viewer

Criar template compartilhado, por exemplo:

```text
templates/pdf_viewer/mobile_pdf_viewer.html
```

Criar JS vanilla, por exemplo:

```text
static/js/pdf-viewer.js
```

Vendorizar PDF.js em:

```text
static/vendor/pdfjs/pdf.mjs
static/vendor/pdfjs/pdf.worker.mjs
```

Se não for possível vendorizar exatamente esses arquivos, registre no relatório uma justificativa técnica e mantenha a solução sem framework JS/bundler.

### R2. Criar rota médica de viewer

Adicionar em `apps/doctor/urls.py`:

```text
<uuid:case_id>/pdf-viewer/ → doctor:pdf_viewer
```

Criar view em `apps/doctor/views.py`, por exemplo `pdf_viewer`:

- exige login e papel ativo `doctor`;
- busca o `Case` por `case_id`;
- retorna 404 se não houver `pdf_file`;
- renderiza `templates/pdf_viewer/mobile_pdf_viewer.html`;
- passa `pdf_url=reverse("doctor:serve_pdf", args=[case.case_id])`;
- passa `back_url` validado:
  - se houver `next` seguro: usar;
  - senão: `reverse("doctor:decision", args=[case.case_id])`;
- não expõe caminho físico nem `MEDIA_URL`.

Use `url_has_allowed_host_and_scheme` se aceitar `next`.

### R3. Trocar somente o link mobile da decisão médica

Em `templates/doctor/decision.html`:

- o link visível em mobile (`d-md-none`) deve apontar para `doctor:pdf_viewer` com `next` para a página atual;
- remover `target="_blank"` desse link mobile;
- manter o controle desktop (`d-none d-md-flex`) e o `<embed>` usando `doctor:serve_pdf`.

### R4. PDF.js renderiza com controle de carga

`static/js/pdf-viewer.js` deve:

- inicializar a partir de dados/args do template;
- carregar `pdfUrl` com PDF.js;
- renderizar páginas em `<canvas>`;
- usar `IntersectionObserver` para lazy rendering;
- ter fallback sequencial se `IntersectionObserver` não existir;
- evitar rerender da mesma página;
- exibir erro/fallback se PDF.js falhar.

YAGNI: não criar zoom avançado, thumbnails, busca textual, impressão customizada ou download customizado.

### R5. Segurança/caching do PDF médico

Atualizar `serve_pdf` médico para incluir:

```http
Cache-Control: no-store
```

Preservar `Content-Type: application/pdf` e `@xframe_options_sameorigin`.

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/doctor/urls.py`
2. `apps/doctor/views.py`
3. `templates/doctor/decision.html`
4. `templates/pdf_viewer/mobile_pdf_viewer.html` (novo)
5. `static/js/pdf-viewer.js` (novo)
6. `static/vendor/pdfjs/*` (novos artefatos vendorizados)
7. `apps/doctor/tests/test_views.py` ou novo teste em `apps/doctor/tests/`
8. `tests/test_pdf_viewer_static.py` somente se optar por teste estático do JS/vendor
9. `openspec/changes/mobile-pdfjs-pwa-viewer/tasks.md`

Se precisar tocar mais arquivos, justifique no relatório.

## TDD obrigatório

### RED

Antes de implementar, adicione testes falhando. Cobertura mínima sugerida:

1. `test_doctor_pdf_viewer_requires_login_or_role`
   - sem login redireciona/bloqueia;
   - usuário sem role doctor não acessa.
2. `test_doctor_pdf_viewer_renders_internal_page_for_authorized_doctor`
   - status 200;
   - contém URL `doctor:serve_pdf` em atributo/config do viewer;
   - contém dois links/botões “Voltar”;
   - contém fallback “Abrir PDF original” ou texto equivalente.
3. `test_doctor_decision_mobile_pdf_link_uses_internal_viewer`
   - HTML contém URL `doctor:pdf_viewer`;
   - o link mobile não usa `target="_blank"`;
   - HTML ainda contém `<embed` com URL `doctor:serve_pdf`.
4. `test_doctor_pdf_response_has_no_store_cache_control`
   - `doctor:serve_pdf` retorna `Content-Type: application/pdf`;
   - header `Cache-Control` contém `no-store`.
5. Teste estático opcional, mas recomendado:
   - `static/js/pdf-viewer.js` contém `IntersectionObserver`;
   - contém tratamento de erro/fallback.

Registre no relatório o comando RED e os testes falhando.

### GREEN

Implemente o mínimo para os testes passarem.

### REFACTOR

- Extraia helpers pequenos apenas se reduzirem duplicação real.
- Não criar abstrações genéricas para fontes de PDF ainda não usadas.
- Não alterar FSM, models, migrations, pipeline LLM ou templates de outros papéis.

## Checks de inspeção obrigatórios antes de concluir

Além dos testes automatizados, execute e cole o resultado/resumo no relatório:

```bash
rg -n "doctor:serve_pdf|doctor:pdf_viewer|target=\"_blank\"|<embed" templates/doctor/decision.html
rg -n "pdf_viewer|serve_pdf|Cache-Control|no-store|url_has_allowed_host_and_scheme" apps/doctor/views.py apps/doctor/urls.py
rg -n "IntersectionObserver|getDocument|canvas|catch|error" static/js/pdf-viewer.js
find static/vendor/pdfjs -maxdepth 1 -type f -print
```

Interprete os resultados no relatório: explique qual ocorrência de `target="_blank"`, se houver, não pertence ao link mobile do PDF principal; se pertencer, o slice está incompleto.

## Critérios de sucesso do slice

- [ ] Médico autorizado abre `doctor:pdf_viewer` com 200.
- [ ] Usuário sem autorização não abre o viewer médico.
- [ ] Viewer médico usa `doctor:serve_pdf` como fonte protegida.
- [ ] Viewer tem botão “Voltar” no topo e no rodapé.
- [ ] Link mobile da decisão médica usa viewer interno e não nova aba.
- [ ] Desktop da decisão médica preserva `<embed>` com `doctor:serve_pdf`.
- [ ] PDF.js está disponível de forma compatível com static files.
- [ ] JS usa lazy rendering ou controle progressivo de carga.
- [ ] `doctor:serve_pdf` inclui `Cache-Control: no-store`.
- [ ] Nenhum framework JS/bundler foi introduzido.
- [ ] `tasks.md` atualizado ao concluir o slice.

## Gates de autoavaliação

Responder no relatório:

1. Qual rota interna o mobile médico usa para visualizar PDF?
2. Qual rota protegida fornece o binário PDF para o PDF.js?
3. O link mobile ainda tem `target="_blank"`? Esperado: não.
4. O desktop ainda usa `<embed>`? Onde isso foi testado?
5. Como a URL `next` foi validada? Qual fallback canônico é usado?
6. Como o viewer lida com PDFs longos?
7. O que acontece se PDF.js falhar?
8. Onde está o PDF.js vendorizado e qual versão/fonte foi usada?
9. Alguma permissão foi relaxada? Esperado: não.
10. Alguma migration/model/FSM/pipeline foi alterada? Esperado: não.

## Relatório obrigatório

Criar relatório temporário:

```text
/tmp/mobile-pdfjs-pwa-viewer-slice-001-report.md
```

O relatório deve conter:

- resumo da implementação;
- arquivos alterados;
- evidência RED: comando, testes falhando e resumo das falhas;
- evidência GREEN: comandos e testes passando;
- snippets antes/depois do link mobile e do embed desktop;
- snippet da view/rota nova;
- evidência de `Cache-Control: no-store`;
- resultado do quality gate;
- respostas aos gates de autoavaliação;
- justificativa para qualquer arquivo extra tocado.

Responder ao final com:

```text
REPORT_PATH=/tmp/mobile-pdfjs-pwa-viewer-slice-001-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/mobile-pdfjs-pwa-viewer/{proposal.md,design.md,tasks.md,specs/mobile-pdf-viewer/spec.md,slices/slice-001-doctor-primary-pdf-viewer.md} first.
Implement ONLY Slice 001. Follow the DeepSeek4-Flash protocol in this file: plan, RED real, GREEN mínimo, inspection checks, full quality gate and evidence report. Use TDD: write failing tests first, then implement the minimum, then refactor safely. If any required test/check/gate is missing or failing, report INCOMPLETE and do not update tasks.md or commit.
Deliver the doctor primary PDF mobile/PWA viewer: mobile link in templates/doctor/decision.html must navigate to an internal doctor:pdf_viewer page, while desktop must keep the existing embed using doctor:serve_pdf.
Create a shared SSR viewer template and Vanilla JS PDF.js renderer with lazy/progressive rendering and fallback. Prefer vendored PDF.js under static/vendor/pdfjs/. Do not add a JS framework, bundler, DRF, models, migrations, FSM or pipeline changes.
Validate any next URL and fallback to doctor:decision. Add Cache-Control: no-store to the doctor PDF binary response.
Run ruff check, ruff format --check, mypy and pytest. Update tasks.md. Create /tmp/mobile-pdfjs-pwa-viewer-slice-001-report.md with RED/GREEN evidence, snippets, quality gate results and self-eval answers. Commit and push. Reply with REPORT_PATH and stop for planner review.
```
