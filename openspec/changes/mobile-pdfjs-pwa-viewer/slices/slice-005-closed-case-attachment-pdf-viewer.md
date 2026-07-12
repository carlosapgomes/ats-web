# Slice 005: NIR histórico — anexos PDF de casos encerrados com viewer mobile interno

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
9. Este arquivo

Implemente **somente este Slice 005** usando TDD: RED → GREEN → REFACTOR. Este slice corrige a dívida de UX registrada após o Slice 004: anexos PDF no detalhe histórico NIR de casos `CLEANED` ainda abrem em nova aba porque não havia rota histórica de anexo com autorização própria.

Assuma que o Slice 003b já consolidou `next` em `apps.cases.navigation.resolve_safe_next_url` e que o Slice 004 já entregou viewer de anexos PDF para superfícies operacionais doctor/intake.

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
- anexo PDF em `closed_case_detail.html` continuar abrindo em nova aba no link mobile;
- rota histórica de anexo aceitar caso fora de `_is_historical_scope_nir(case)`;
- rota histórica de anexo aceitar usuário sem papel ativo `nir`;
- rota histórica de anexo servir anexo suprimido;
- viewer histórico de anexo aceitar arquivo não PDF;
- viewer usa `MEDIA_URL`, caminho físico do arquivo ou URL sem autorização;
- `next` é usado sem `apps.cases.navigation.resolve_safe_next_url` e fallback canônico;
- rota operacional `intake:serve_attachment` deixar de bloquear caso `CLEANED`;
- relatório temporário não foi criado no caminho exigido.

## Objetivo do slice

Entregar acesso PWA/mobile interno para anexos PDF no detalhe histórico NIR de casos encerrados:

```text
NIR abre Detalhe Histórico de caso CLEANED
→ vê anexo PDF
→ no mobile toca no anexo
→ navega para viewer interno do app
→ PDF anexo renderiza via PDF.js
→ volta ao detalhe histórico
```

Desktop deve continuar com preview inline via `<embed>`, mas usando uma rota histórica autorizada, não a rota operacional que bloqueia `CLEANED`.

## Contexto técnico atual

- `templates/intake/closed_case_detail.html` lista anexos históricos em `attachments`.
- Hoje o template usa `intake:serve_attachment` para link mobile, botão “Abrir em nova aba”, `<embed>` PDF e `<img>`.
- `apps/intake/views.py::serve_attachment` é rota **operacional** e bloqueia `CaseStatus.CLEANED`.
- `apps/intake/views.py::closed_case_detail` só permite acesso quando `_is_historical_scope_nir(case)` retorna `True` e passa `attachments = case.attachments.filter(is_suppressed=False)`.
- Já existe rota histórica para PDF principal: `intake:closed_case_pdf`.
- Este slice deve criar rota histórica equivalente para anexos, com autorização própria e escopo enxuto.

## Escopo funcional

### R1. Criar rota histórica protegida para servir anexo

Adicionar em `apps/intake/urls.py`:

```text
closed-cases/<uuid:case_id>/attachments/<uuid:attachment_id>/ → intake:closed_case_attachment
```

Criar view em `apps/intake/views.py`, por exemplo `closed_case_attachment`:

- `@login_required`;
- `@role_required("nir")`;
- `@xframe_options_sameorigin` para permitir `<embed>` same-origin;
- buscar `Case` por `case_id`;
- exigir `_is_historical_scope_nir(case)`;
- buscar `CaseAttachment` por `attachment_id`, `case=case`, `is_suppressed=False`;
- retornar `FileResponse(attachment.file.open("rb"), content_type=attachment.content_type)`;
- adicionar `Cache-Control: no-store`;
- retornar 404 quando:
  - caso não está no escopo histórico NIR;
  - anexo não pertence ao caso;
  - anexo está suprimido;
  - arquivo não existe/sem file, se aplicável.

Não alterar `intake:serve_attachment`; ela deve continuar bloqueando `CLEANED`.

### R2. Criar viewer histórico para anexo PDF

Adicionar em `apps/intake/urls.py`:

```text
closed-cases/<uuid:case_id>/attachments/<uuid:attachment_id>/viewer/ → intake:closed_case_attachment_pdf_viewer
```

Criar view em `apps/intake/views.py`, por exemplo `closed_case_attachment_pdf_viewer`:

- `@login_required`;
- `@role_required("nir")`;
- aplicar a mesma autorização da rota `closed_case_attachment`;
- retornar 404 se `attachment.content_type != "application/pdf"`;
- usar `pdf_url=reverse("intake:closed_case_attachment", args=[case.case_id, attachment.attachment_id])`;
- resolver `back_url` com `apps.cases.navigation.resolve_safe_next_url`, usando fallback `reverse("intake:closed_case_detail", args=[case.case_id])`;
- renderizar `templates/pdf_viewer/mobile_pdf_viewer.html`;
- passar `fallback_pdf_url` igual ao `pdf_url`.

Se houver duplicação entre a rota binária e o viewer, extrair helper privado pequeno no próprio `apps/intake/views.py`, por exemplo `_get_closed_case_attachment_or_404(case_id, attachment_id) -> tuple[Case, CaseAttachment]`.

### R3. Atualizar `closed_case_detail.html`

Em `templates/intake/closed_case_detail.html`:

- para `att.content_type == "application/pdf"`, o link mobile deve apontar para `intake:closed_case_attachment_pdf_viewer` com `next` para `intake:closed_case_detail`;
- o link mobile de PDF não deve usar `target="_blank"`;
- o `<embed>` desktop de PDF deve usar `intake:closed_case_attachment`;
- o botão desktop “Abrir em nova aba” para PDF pode continuar com `target="_blank"`, mas deve usar `intake:closed_case_attachment`;
- imagens devem usar `intake:closed_case_attachment` como rota histórica binária se continuarem visíveis no detalhe histórico;
- não criar viewer PDF.js para imagens.

### R4. Preservar autorização e comportamento operacional

- `intake:serve_attachment` deve continuar bloqueando caso `CLEANED`.
- A nova rota histórica só vale para NIR e casos dentro de `_is_historical_scope_nir(case)`.
- Não liberar acesso para doctor, scheduler, manager ou admin neste slice.
- Não alterar supressão, upload suplementar, FSM, models, migrations ou pipeline.

### R5. Testar regressões e contratos de PWA

Adicionar testes que provem:

- link mobile de anexo PDF em `closed_case_detail.html` usa `closed_case_attachment_pdf_viewer`;
- esse link mobile não usa `target="_blank"`;
- `<embed>` desktop usa `closed_case_attachment`;
- `closed_case_attachment` serve PDF para NIR autorizado e retorna `Content-Type` correto + `Cache-Control: no-store`;
- `closed_case_attachment` bloqueia doctor/scheduler e caso fora do escopo histórico;
- `closed_case_attachment` retorna 404 para anexo suprimido;
- viewer histórico renderiza com `closed_case_attachment` como fonte;
- viewer histórico rejeita anexo não PDF;
- viewer histórico rejeita `next=https://evil.example/...` e cai no fallback canônico;
- rota operacional `intake:serve_attachment` continua bloqueando `CLEANED`.

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/intake/urls.py`
2. `apps/intake/views.py`
3. `templates/intake/closed_case_detail.html`
4. `apps/intake/tests/test_pdf_viewer.py` ou novo `apps/intake/tests/test_closed_case_attachment_viewer.py`
5. `openspec/changes/mobile-pdfjs-pwa-viewer/tasks.md`

Se tocar mais arquivos, justificar no relatório. Não tocar `templates/intake/case_detail.html`, `templates/doctor/decision.html`, dashboard, scheduler, static JS ou PDF.js neste slice.

## Fora de escopo

Não implementar neste slice:

- viewer para imagens;
- acesso histórico de anexos para doctor/scheduler/dashboard;
- alteração de supressão, upload inicial ou upload suplementar;
- migration/model/FSM/pipeline;
- refactor amplo de anexos;
- alteração do comportamento de `intake:serve_attachment` operacional.

## TDD obrigatório

### RED

Antes de implementar, adicione testes falhando. Sugestão objetiva:

1. `test_closed_case_detail_pdf_attachment_mobile_link_uses_internal_viewer`
   - detalhe histórico contém `intake:closed_case_attachment_pdf_viewer`;
   - o link mobile de PDF não tem `target="_blank"`;
   - desktop `<embed>` usa `intake:closed_case_attachment`.

2. `test_closed_case_attachment_serves_pdf_for_authorized_nir`
   - status 200;
   - `Content-Type` do PDF;
   - `Cache-Control` contém `no-store`.

3. `test_closed_case_attachment_blocks_non_nir_roles`
   - doctor/scheduler não acessam.

4. `test_closed_case_attachment_404_for_suppressed_attachment`.

5. `test_closed_case_attachment_404_for_case_outside_historical_scope`.

6. `test_closed_case_attachment_pdf_viewer_renders_for_authorized_nir`
   - contém URL `closed_case_attachment` como `pdf_url`;
   - contém dois “Voltar”;
   - contém fallback.

7. `test_closed_case_attachment_pdf_viewer_404_for_image_attachment`.

8. `test_closed_case_attachment_pdf_viewer_rejects_external_next`
   - `evil.example` não aparece;
   - fallback `intake:closed_case_detail` aparece.

9. `test_operational_serve_attachment_still_blocks_cleaned_case`.

Registre no relatório o comando RED e as falhas esperadas.

### GREEN

Implementar o mínimo para os testes passarem.

### REFACTOR

- Use helper privado pequeno se evitar duplicação real entre rota binária e viewer.
- Reuse `resolve_safe_next_url` para `back_url`.
- Não criar abstração global de anexos históricos.
- Não alterar templates ou apps fora do escopo.

## Checks de inspeção obrigatórios antes de concluir

Além dos testes automatizados, execute e cole o resultado/resumo no relatório:

```bash
rg -n "closed_case_attachment|closed_case_attachment_pdf_viewer|serve_attachment|target=\"_blank\"|<embed" templates/intake/closed_case_detail.html
rg -n "closed_case_attachment|closed_case_attachment_pdf_viewer|resolve_safe_next_url|_is_historical_scope_nir|no-store|xframe_options_sameorigin" apps/intake/views.py apps/intake/urls.py
rg -n "serve_attachment" apps/intake/views.py apps/intake/tests/*.py
rg -n "closed_case_attachment" apps/intake/tests/*.py
```

Interpretação obrigatória no relatório:

- link mobile de PDF histórico deve usar viewer interno e não `target="_blank"`;
- `<embed>` de PDF histórico deve usar rota histórica binária, não `intake:serve_attachment`;
- `target="_blank"` remanescente só é aceitável no botão desktop “Abrir em nova aba” ou em links não-PDF justificados;
- `resolve_safe_next_url` deve ser usado no viewer;
- `intake:serve_attachment` deve continuar existindo e bloqueando `CLEANED` em teste.

## Critérios de sucesso do slice

- [ ] NIR histórico consegue abrir anexo PDF via viewer interno mobile.
- [ ] Link mobile de anexo PDF histórico não usa nova aba.
- [ ] Desktop histórico preserva `<embed>` para PDF.
- [ ] `<embed>` e imagens históricas usam rota histórica autorizada, não rota operacional que bloqueia `CLEANED`.
- [ ] Rota histórica binária tem `Cache-Control: no-store`.
- [ ] Rota histórica só permite NIR e caso em `_is_historical_scope_nir`.
- [ ] Anexo suprimido retorna 404.
- [ ] Viewer histórico rejeita anexo não PDF.
- [ ] Viewer histórico usa `resolve_safe_next_url` e rejeita `next` externo.
- [ ] `intake:serve_attachment` operacional continua bloqueando `CLEANED`.
- [ ] Nenhum model/migration/FSM/pipeline foi alterado.
- [ ] `tasks.md` atualizado ao concluir.

## Gates de autoavaliação

Responder no relatório:

1. Quais rotas históricas de anexo foram criadas?
2. Qual helper/autorização garante que o caso está no escopo histórico NIR?
3. Quais papéis foram bloqueados nos testes?
4. Como o viewer garante que apenas PDF usa PDF.js?
5. O que acontece com anexo suprimido?
6. O que acontece com `next=https://evil.example/...`?
7. A rota operacional `intake:serve_attachment` ainda bloqueia `CLEANED`? Onde está testado?
8. O desktop histórico ainda tem `<embed>`? Qual rota ele usa?
9. Algum `target="_blank"` permaneceu no link mobile de PDF histórico? Esperado: não.
10. Alguma permissão/model/migration/FSM/pipeline foi alterada? Esperado: não.

## Relatório obrigatório

Criar:

```text
/tmp/mobile-pdfjs-pwa-viewer-slice-005-report.md
```

O relatório deve conter:

- `Status: COMPLETE` ou `Status: INCOMPLETE`;
- matriz requisito → arquivo(s) → teste(s);
- evidência RED;
- evidência GREEN;
- snippets antes/depois de `closed_case_detail.html`;
- snippets das novas views/rotas;
- resultado dos checks de inspeção obrigatórios;
- resultado do quality gate completo;
- respostas aos gates de autoavaliação;
- `Handoff para verificador` com arquivos alterados, comandos para rerun, riscos/limitações e checklist R1..R5.

Responder ao final com:

```text
REPORT_PATH=/tmp/mobile-pdfjs-pwa-viewer-slice-005-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/mobile-pdfjs-pwa-viewer/{proposal.md,design.md,tasks.md,specs/mobile-pdf-viewer/spec.md,slices/slice-005-closed-case-attachment-pdf-viewer.md} first.
Implement ONLY Slice 005. Follow the DeepSeek4-Flash protocol in this file: plan, RED real, GREEN mínimo, inspection checks, full quality gate and evidence report. If any required test/check/gate is missing or failing, report INCOMPLETE and do not update tasks.md or commit.
Deliver historical NIR attachment PDF viewing for closed cases: add protected historical attachment binary route and PDF viewer route under intake closed-cases, update templates/intake/closed_case_detail.html so mobile PDF attachment links use the internal viewer without target=_blank, and desktop embeds use the historical binary route.
Use apps.cases.navigation.resolve_safe_next_url for back_url. Preserve _is_historical_scope_nir authorization, block non-NIR roles, block suppressed attachments, reject non-PDF attachments in the viewer, keep intake:serve_attachment blocking CLEANED, and add Cache-Control: no-store to the new binary route.
Do not touch models, migrations, FSM, pipeline, upload/suppression logic, dashboard, doctor, scheduler or static PDF.js. Run quality gate, update tasks.md only if all checks pass, create /tmp/mobile-pdfjs-pwa-viewer-slice-005-report.md, commit and push. Reply with REPORT_PATH and stop.
```
