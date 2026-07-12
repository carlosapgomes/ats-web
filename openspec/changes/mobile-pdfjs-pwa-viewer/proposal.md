# Proposal: Visualizador PDF interno para PWA mobile com PDF.js

**Change ID**: `mobile-pdfjs-pwa-viewer`  
**Fase**: polimento UX/PWA e hardening de visualização de documentos  
**Risco**: PROFISSIONAL com cuidado de segurança — altera navegação de PDFs sensíveis em múltiplas superfícies, mas não muda banco, FSM, pipeline ou permissões de negócio.  
**Classificação**: `classify-change-risk` automático em 2026-07-12 sugeriu CRITICAL com baixa confiança; classificação manual adotada: PROFISSIONAL/FEATURE com `design.md` obrigatório. Justificativa: a mudança toca rotas/templates protegidos e dados sensíveis, porém reutiliza as autorizações existentes, é reversível por Git e não altera persistência.

## Problema

Hoje a experiência de visualização de PDF é boa no desktop: os templates usam `<embed type="application/pdf">` dentro da própria tela do caso.

No mobile, porém, o embed nativo não é confiável. Para contornar isso, os templates usam links `target="_blank"` para abrir o PDF em uma nova aba. Isso quebra o fluxo quando o sistema é instalado como PWA na tela inicial: os controles de abas/navegação do navegador desaparecem e o usuário pode não conseguir voltar para a tela do caso.

O impacto prático é maior para médicos, NIR e CHD porque o PDF é parte central da decisão/consulta operacional.

## Objetivo

Criar um visualizador interno de PDF para mobile/PWA usando PDF.js, preservando o embed nativo no desktop.

Fluxo desejado:

```text
Tela do caso no PWA mobile
→ usuário toca em “Visualizar PDF”
→ navega para uma página interna do app
→ PDF renderizado via PDF.js
→ botões “Voltar” no topo e no final retornam à tela anterior/canônica
```

## Escopo incluído

- Manter o visualizador desktop atual com `<embed>`.
- Trocar links mobile de PDF principal para uma página interna do app, sem `target="_blank"`.
- Criar template SSR compartilhado para a página de visualização mobile.
- Usar Vanilla JS + PDF.js, sem framework frontend e sem SPA.
- Vendorizar PDF.js em `static/vendor/pdfjs/` ou documentar justificativa técnica equivalente no relatório do slice.
- Renderizar páginas em `<canvas>` com lazy rendering/controle de carga para PDFs longos.
- Mostrar botão “Voltar” no topo e no rodapé.
- Usar URL de retorno conhecida/validada; não depender apenas de `history.back()`.
- Reutilizar rotas protegidas existentes de PDF como fonte do documento.
- Preservar autorização por papel em cada superfície.
- Adicionar fallback visível para abrir o PDF original quando PDF.js falhar.
- Adicionar `Cache-Control: no-store` nas respostas de PDF tocadas por cada slice, quando ainda ausente.
- Cobrir por testes Django/pytest o contrato HTML, rotas, autorização e regressão desktop.

## Escopo fora

- Não criar API REST, DRF, SPA, WebSocket ou SSE.
- Não alterar `Case`, `CaseAttachment`, FSM, migrations, pipeline LLM ou storage.
- Não trocar o visualizador desktop por PDF.js.
- Não implementar OCR, busca textual dentro do PDF, zoom avançado, thumbnails, impressão ou download customizado.
- Não expor arquivos via `MEDIA_URL` público.
- Não relaxar permissões existentes de PDF.
- Não fazer refactor amplo de templates não relacionados.

## Dimensionamento dos slices

A implementação deve ser dividida em slices verticais e enxutos:

1. **Slice 001 — Médico / PDF principal**  
   Entrega end-to-end o viewer mobile para a decisão médica, incluindo a infraestrutura compartilhável de PDF.js.

2. **Slice 002 — NIR e dashboard / PDFs principais**  
   Reusa o viewer para detalhe NIR operacional, detalhe NIR histórico (`CLEANED`) e detalhe gerencial do dashboard.

3. **Slice 003 — CHD/scheduler / PDF principal processado**  
   Reusa o viewer para o detalhe de `Processados Hoje` do CHD, preservando autorização restrita do PDF processado.

4. **Slice 004 — PDFs de anexos clínicos**  
   Reusa o padrão para anexos PDF do médico/NIR, eliminando nova aba mobile também em documentos suplementares.

Esse dimensionamento evita um slice horizontal de “infraestrutura pura” e garante valor de usuário ao fim de cada etapa.

## Critérios de sucesso do change

- Desktop continua usando `<embed>` para PDFs principais.
- Mobile/PWA deixa de abrir PDFs principais em nova aba nas superfícies cobertas.
- A página interna do viewer tem botão “Voltar” no topo e no rodapé.
- PDF.js renderiza PDFs em canvas com fallback claro em caso de erro.
- Rotas de PDF continuam protegidas por papel e não usam `MEDIA_URL` direto.
- URLs de retorno são validadas ou derivadas de rotas canônicas.
- Respostas de PDF tocadas pelo change usam `Cache-Control: no-store`.
- Testes relevantes passam e comprovam que o desktop não regrediu.
- Cada slice gera relatório markdown temporário para revisão por terceiro LLM.
