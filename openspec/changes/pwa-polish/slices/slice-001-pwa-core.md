# Slice 1: PWA core — manifest, ícone, service worker, meta tags

## Objetivo

Tornar o app instalável com manifest.json, ícone, service worker e meta tags PWA.

## Arquivos

### 1. `static/manifest.json` — novo

```json
{
  "name": "ATS — Sistema de Triagem Hospitalar",
  "short_name": "ATS",
  "description": "Sistema de Triagem de Endoscopia Digestiva Alta",
  "start_url": "/",
  "display": "standalone",
  "theme_color": "#0b4263",
  "background_color": "#ffffff",
  "icons": [
    { "src": "/static/icons/icon.svg", "sizes": "any", "type": "image/svg+xml" },
    { "src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

### 2. `static/icons/icon.svg` — novo

SVG simples: escudo/cruz hospitalar com "ATS" em texto.
Cores: `#0b4263` (primary), `#ffffff` (fundo).

### 3. `static/icons/icon-192.png` e `icon-512.png` — novos

Gerados a partir do SVG. Se conversão não for viável, usar SVG como único ícone
e remover as entradas PNG do manifest.

### 4. `static/js/sw.js` — novo

Service worker mínimo:
- Install: pré-cache de assets estáticos (CSS, JS, manifest, ícones)
- Fetch: cache-first para `/static/`, network-first para HTML
- Activate: limpar caches antigos

### 5. `static/js/app.js` — modificado

Remover placeholder e adicionar registro real do service worker:

```javascript
// Service Worker registration
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/js/sw.js').catch(() => {});
  });
}
```

### 6. `templates/base.html` — modificado

Adicionar meta tags PWA após as existentes:
```html
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="ATS">
<link rel="apple-touch-icon" href="/static/icons/icon-192.png">
```

### 7. `config/urls.py` — modificado (opcional)

Se `manifest.json` não for servido via static, adicionar view.
Melhor approach: servir como static file com `STATIC_URL=/static/` e
usar `<link rel="manifest" href="{% static 'manifest.json' %}">` no base.html.

## Critérios de sucesso

- [ ] `manifest.json` válido e acessível
- [ ] Service worker registra sem erros
- [ ] Meta tags PWA completas no `<head>`
- [ ] Ícone visível como favicon/touch icon
- [ ] Chrome DevTools → Application → Manifest mostra app instalável
- [ ] Lighthouse PWA audit ≥ 80
- [ ] ruff + mypy + pytest clean

## Arquivos: ideal ≤ 6
