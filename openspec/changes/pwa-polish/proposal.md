# Proposal: PWA e Polish

**Change ID**: `pwa-polish`
**Fase**: 10 — PWA e Polish
**Risco**: ESSENCIAL (assets estáticos, manifest, service worker, templates — sem mudança em models/views/business logic)
**Dependências**: Todas as fases anteriores (app completo)

## Objetivo

Transformar o ATS Web em PWA instalável com refinamentos de UX para uso hospitalar
em dispositivos móveis (tablets na enfermaria, smartphones dos médicos).

## Escopo

### Funcionalidades

1. **manifest.json** — app instalável
   - name, short_name, description, start_url, display, theme_color, background_color
   - Ícones em múltiplos tamanhos (192x192, 512x512)
   - Gerado como static file servido na raiz (`/manifest.json`)

2. **Service worker mínimo** — cache de assets estáticos
   - Cache-first para CSS/JS/fonts/ícones
   - Network-first para páginas HTML
   - Versão do cache baseada em timestamp (para invalidação)

3. **Meta tags PWA** — completar o que já existe no `base.html`
   - `apple-mobile-web-app-capable`, `apple-mobile-web-app-status-bar-style`
   - `apple-touch-icon` com ícone 180x180
   - `application-name`, `msapplication-TileColor`

4. **Badges de contagem** — nas filas (header ou nav)
   - Doctor queue: badge com número de casos aguardando decisão
   - Scheduler queue: badge com número de casos aguardando agendamento
   - Context processor ou template tag para disponibilizar contagens

5. **Responsividade mobile** — ajustes finais
   - Verificar e corrigir quebras em telas pequenas (< 576px)
   - Tabelas com `table-responsive` (já parcial)
   - Cards empilhados verticalmente em mobile (já via Bootstrap grid)
   - Botões touch-friendly (min 44px)

### Estado atual

- `base.html` já tem `viewport`, `theme-color`, e `<link rel="manifest">`
- `app.js` tem placeholder para service worker
- Bootstrap grid já provê responsividade básica
- Sem manifest.json, sem service worker, sem ícones, sem apple meta tags

## Fora de escopo

- Push notifications (in-app notifications são suficientes)
- Offline data sync (hospital tem WiFi estável)
- Background sync
- Periodic background sync
- App shortcuts
