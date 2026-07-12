# Design: Visualizador PDF interno para PWA mobile com PDF.js

## Estado atual

O projeto é Django SSR com Bootstrap 5.3 e Vanilla JS. Não há SPA nem DRF.

Pontos atuais de PDF principal:

- `templates/doctor/decision.html`
  - mobile: `<a href="doctor:serve_pdf" target="_blank">`;
  - desktop: collapse com `<embed src="doctor:serve_pdf" type="application/pdf">`.
- `templates/intake/case_detail.html`
  - mobile: `<a href="pdf_url" target="_blank">`;
  - desktop: `<embed src="pdf_url">`.
- `templates/intake/closed_case_detail.html`
  - mesmo padrão para `closed_case_pdf`.
- `templates/scheduler/context_detail.html`
  - mobile: `<a href="pdf_url" target="_blank">`;
  - desktop: `<embed src="pdf_url">`.
- Dashboard usa `templates/intake/case_detail.html` parametrizado com `pdf_url=dashboard:case_pdf`.

Esse padrão é aceitável no desktop, mas ruim no PWA mobile porque `target="_blank"` pode abrir uma navegação sem controles de aba/voltar.

## Decisões

### D1. Manter embed nativo no desktop

Não substituir o desktop por PDF.js neste change.

Motivos:

- UX desktop atual é boa;
- menor risco;
- menor custo de renderização client-side;
- preserva comportamento já validado pelos usuários.

Implementação esperada:

```html
<a class="d-md-none" href="...pdf-viewer...">Visualizar PDF</a>
<button class="d-none d-md-inline-flex" ...>Visualizar PDF</button>
<div class="collapse d-none d-md-block ou collapse normal controlado pelo botão desktop">
  <embed src="...pdf protegido..." type="application/pdf">
</div>
```

O link mobile não deve usar `target="_blank"`.

### D2. Criar página interna de viewer mobile por superfície

Cada app deve ter rota própria para manter boundaries e permissões claras:

```text
doctor:<case_id>/pdf-viewer/                       → doctor:pdf_viewer
intake:<case_id>/pdf-viewer/                       → intake:pdf_viewer
intake:closed-cases/<case_id>/pdf-viewer/          → intake:closed_case_pdf_viewer
dashboard:<case_id>/pdf-viewer/                    → dashboard:pdf_viewer
scheduler:processed/<case_id>/pdf-viewer/          → scheduler:processed_pdf_viewer
```

Para anexos PDF no Slice 004:

```text
doctor:cases/<case_id>/attachments/<attachment_id>/viewer/
intake:<case_id>/attachments/<attachment_id>/viewer/
intake:closed-cases/<case_id>/attachments/<attachment_id>/viewer/  # somente se já houver rota/fonte autorizada coerente
```

A rota do viewer renderiza HTML; a rota existente de PDF continua servindo o binário.

### D3. Usar template compartilhado SSR

Criar template compartilhado, por exemplo:

```text
templates/pdf_viewer/mobile_pdf_viewer.html
```

Contexto mínimo:

```python
{
    "viewer_title": "PDF original",
    "case": case,
    "pdf_url": reverse("doctor:serve_pdf", args=[case.case_id]),
    "back_url": validated_next_or_canonical_url,
    "back_label": "← Voltar ao caso",
    "fallback_pdf_url": same_as_pdf_url,
}
```

A página deve conter:

- botão/link “Voltar” no topo;
- título curto e contexto seguro do caso, quando disponível;
- área de carregamento;
- container de páginas/canvas;
- alerta de erro com fallback “Abrir PDF original”;
- botão/link “Voltar” no rodapé.

O botão voltar deve apontar para uma URL conhecida/validada. Não depender somente de JavaScript ou `history.back()`.

### D4. PDF.js core com Vanilla JS

Preferência técnica:

```text
static/vendor/pdfjs/pdf.mjs
static/vendor/pdfjs/pdf.worker.mjs
static/js/pdf-viewer.js
```

`static/js/pdf-viewer.js` deve exportar/inicializar funções pequenas, por exemplo:

```javascript
initPdfViewer({ pdfjsLib, pdfUrl, container, statusEl, errorEl, scale })
createPagePlaceholder(pageNumber)
renderPageWhenVisible(pageNumber)
renderPage(pageNumber)
```

O template pode usar `<script type="module">` para importar PDF.js e o módulo do viewer.

Não adicionar framework JS, bundler ou npm pipeline. Se a versão do PDF.js exigir adaptação, o relatório do slice deve registrar:

- versão usada;
- fonte dos arquivos vendorizados;
- hash/checksum se viável;
- motivo de qualquer alternativa a `static/vendor/pdfjs/`.

### D5. Renderização progressiva/lazy para PDFs longos

Evitar renderizar todas as páginas pesadas de uma vez em celulares.

Comportamento desejado:

1. `pdfjsLib.getDocument(pdfUrl)` carrega o documento.
2. Criar placeholders para as páginas.
3. Usar `IntersectionObserver` para renderizar páginas quando se aproximam da viewport.
4. Fallback sem `IntersectionObserver`: renderizar primeira página e depois processar as demais sequencialmente com pequenas pausas.
5. Evitar rerender da mesma página se o usuário rolar para cima/baixo.

Não implementar zoom avançado neste change. Usar escala responsiva simples baseada na largura do container.

### D6. Segurança e autorização

Regras:

- Viewer HTML deve exigir o mesmo papel ativo da superfície (`doctor`, `nir`, `scheduler`, `manager/admin`).
- Viewer não deve expor caminho físico nem `MEDIA_URL` direto.
- Viewer deve usar a rota protegida de PDF (`serve_pdf`, `closed_case_pdf`, `case_pdf`, `processed_pdf`, `serve_attachment`).
- Não relaxar permissões existentes.
- Se a view do viewer aceitar `next`, validar com `url_has_allowed_host_and_scheme` e fallback para URL canônica.
- Adicionar `Cache-Control: no-store` nas respostas de PDF tocadas por cada slice, mantendo `Content-Type: application/pdf`.
- Evitar incluir dados sensíveis desnecessários no HTML do viewer. Nome do paciente pode aparecer se já aparece na tela anterior e a rota tem a mesma autorização.

Observação: se o implementador identificar autorização excessivamente ampla em rota existente, não fazer hardening amplo dentro deste change sem abrir follow-up. Pode, porém, tornar a rota do viewer mais restrita que a rota binária, desde que não quebre o fluxo.

### D7. Fallback de erro

A página deve mostrar mensagem clara se PDF.js falhar:

```text
Não foi possível renderizar este PDF no visualizador interno.
Você pode tentar abrir o PDF original.
```

O fallback “Abrir PDF original” pode abrir a rota protegida do PDF. Em mobile/PWA, isso ainda pode ter limitação, mas é melhor do que uma tela quebrada.

### D8. Testabilidade

Sem browser E2E neste projeto, então os testes devem focar contratos determinísticos:

- rota do viewer exige login/papel;
- viewer retorna 200 para usuário autorizado;
- viewer contém `data-pdf-url`/config equivalente apontando para a rota protegida correta;
- viewer contém dois links de voltar;
- viewer contém fallback de PDF original;
- template da tela de origem usa viewer no link mobile;
- template da tela de origem preserva `<embed>` desktop com a rota binária;
- link mobile não usa `target="_blank"`;
- resposta binária de PDF preserva `Content-Type: application/pdf` e ganha `Cache-Control: no-store`.

Testes de JavaScript podem ser por inspeção estática mínima (`IntersectionObserver`, tratamento de erro, canvas), se útil, mas não devem substituir testes de contrato Django.

## Plano por slice

### Slice 001 — Médico / PDF principal

Entrega a primeira vertical end-to-end:

- vendor/static PDF.js;
- template compartilhado de viewer;
- rota `doctor:pdf_viewer`;
- link mobile em `templates/doctor/decision.html`;
- desktop unchanged com `<embed>`;
- testes em `apps/doctor/tests/` e, se útil, teste estático de JS.

### Slice 002 — NIR e dashboard / PDFs principais

Reusa o viewer compartilhado:

- rotas `intake:pdf_viewer`, `intake:closed_case_pdf_viewer`, `dashboard:pdf_viewer`;
- contexto `mobile_pdf_viewer_url` ou equivalente nas views;
- templates compartilhados `intake/case_detail.html` e `intake/closed_case_detail.html` usando viewer no mobile;
- testes intake/dashboard.

### Slice 003 — CHD/scheduler / PDF principal processado

Reusa o viewer compartilhado:

- rota `scheduler:processed_pdf_viewer`;
- `templates/scheduler/context_detail.html` usa viewer no mobile quando `pdf_url` existir;
- preservar autorização restrita de `scheduler_processed_pdf`;
- testes scheduler.

### Slice 004 — Anexos PDF

Reusa o viewer para anexos PDF:

- médico: anexos PDF em `doctor/decision.html`;
- NIR operacional: anexos PDF em `intake/case_detail.html`;
- NIR histórico: somente se já houver rota autorizada adequada para arquivo histórico;
- preservar imagens como estão;
- testes de contratos de anexo.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Expor PDF para papel indevido | Rotas de viewer por app + reutilizar PDF URL protegida + testes de autorização |
| Quebrar UX desktop | Não tocar no embed desktop além do mínimo + testes de regressão HTML |
| Travar celular com PDF longo | Lazy rendering com `IntersectionObserver` e fallback sequencial |
| CDN indisponível/ambiente intranet | Preferir PDF.js vendorizado em `static/vendor/pdfjs/` |
| Open redirect via `next` | Validar `next` ou usar URL canônica |
| Cache de PDF sensível | `Cache-Control: no-store` nas rotas PDF tocadas |
| Escopo crescer para viewer completo | YAGNI: sem zoom, thumbnails, busca, impressão customizada |

## Rollback

Rollback por Git revert do slice. Não há migration nem alteração de dados. Ao reverter:

- links mobile voltam ao comportamento anterior ou ao último slice estável;
- rotas de viewer deixam de existir;
- PDFs armazenados permanecem intactos.
