# PWA Core — Relatório de Implementação (Slice 001)

## Resumo

Tornar o app instalável com manifest.json, ícone, service worker e meta tags PWA.

## Arquivos criados

| Arquivo | Descrição |
|---|---|
| `static/manifest.json` | Manifest PWA com name, short_name, icons, display standalone |
| `static/icons/icon.svg` | SVG vetorial: escudo médico + cruz + texto ATS (512×512) |
| `static/icons/icon-192.png` | PNG 192×192 gerado do SVG via ImageMagick |
| `static/icons/icon-512.png` | PNG 512×512 gerado do SVG via ImageMagick |
| `static/js/sw.js` | Service worker: cache-first para `/static/`, network-first para navegação, limpeza de caches antigos |

## Arquivos modificados

### `static/js/app.js` — antes

```javascript
/* ATS Web — Vanilla JavaScript */

// Placeholder for future PWA service worker registration
// and other client-side enhancements.
```

### `static/js/app.js` — depois

```javascript
/* ATS Web — Vanilla JavaScript */

// Service Worker registration
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/js/sw.js').catch(() => {});
  });
}
```

### `templates/base.html` — antes

```html
    <meta name="theme-color" content="#0b4263">
    <title>{% block title %}ATS{% endblock %}</title>
    ...
    <!-- PWA manifest -->
    <link rel="manifest" href="/manifest.json">
```

### `templates/base.html` — depois

```html
    <meta name="theme-color" content="#0b4263">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="ATS">
    <link rel="apple-touch-icon" href="{% static 'icons/icon-192.png' %}">
    <title>{% block title %}ATS{% endblock %}</title>
    ...
    <!-- PWA manifest -->
    <link rel="manifest" href="{% static 'manifest.json' %}">
```

Mudanças:
- Meta tags Apple PWA adicionadas (capable, status-bar, title)
- Apple touch icon adicionado
- Link do manifest corrigido de `/manifest.json` para `{% static 'manifest.json' %}`

## Quality Gate

| Verificação | Resultado |
|---|---|
| `ruff check` | ✅ All checks passed |
| `ruff format --check` | ✅ 111 files already formatted |
| `mypy .` | ✅ Success: no issues found in 119 source files |
| `pytest` | ✅ 532 passed |

## Critérios de sucesso

- [x] `manifest.json` válido e acessível em `/static/manifest.json`
- [x] Service worker registra via `app.js` no evento `load`
- [x] Meta tags PWA completas no `<head>` (theme-color, apple-mobile-web-app-*)
- [x] Ícone SVG + PNGs como favicon/touch icon
- [ ] Chrome DevTools → Application → Manifest mostra app instalável (requer browser)
- [ ] Lighthouse PWA audit ≥ 80 (requer browser)
- [x] ruff + mypy + pytest clean

## Artefatos

Branch: `main` (diretamente)
