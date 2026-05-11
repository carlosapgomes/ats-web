# Design: PWA e Polish

## Decisões

### D1: manifest.json como static file

Arquivo `static/manifest.json` servido via Django view genérica ou `STATIC_URL`.
Usar view simples em `config/urls.py` para servir na raiz (`/manifest.json`).

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
    { "src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

### D2: Ícones SVG → PNG

Criar ícone SVG simples (logo ATS — cruz hospitalar estilizada com "ATS") e
converter para PNG nos tamanhos necessários. Se conversão não for possível no CI,
usar SVG diretamente com fallback.

Na prática: ícone SVG em `static/icons/` + referência no manifest.
O service worker pode cachear o SVG.

### D3: Service worker — estratégia simples

`static/js/sw.js`:

```javascript
const CACHE_NAME = 'ats-v1';
const STATIC_ASSETS = [
  '/static/css/app.css',
  '/static/js/app.js',
  '/static/js/upload.js',
  '/static/js/decision.js',
  '/static/js/scheduler_confirm.js',
  '/manifest.json',
];

// Install: cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
});

// Fetch: cache-first para assets, network-first para páginas
self.addEventListener('fetch', (event) => {
  if (event.request.url.includes('/static/')) {
    // Cache-first for static assets
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
  }
  // Network-first for everything else (HTML pages)
});
```

Registro em `app.js`:
```javascript
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/static/js/sw.js');
}
```

### D4: Meta tags PWA no base.html

Completar as meta tags já existentes:

```html
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="ATS">
<link rel="apple-touch-icon" href="/static/icons/icon-192.png">
```

### D5: Badges de contagem — context processor

Criar context processor em `apps/accounts/context_processors.py` (já existe)
que adiciona `queue_counts` ao contexto:

```python
def queue_counts(request):
    if not request.user.is_authenticated:
        return {}
    active_role = request.session.get("active_role")
    if active_role == "doctor":
        count = Case.objects.filter(status=CaseStatus.WAIT_DOCTOR).count()
        return {"queue_count": count}
    if active_role == "scheduler":
        count = Case.objects.filter(status=CaseStatus.WAIT_APPT).count()
        return {"queue_count": count}
    return {}
```

Exibir no header do `base.html` como badge ao lado do nome do papel.

### D6: Responsividade — verificação e ajustes

- Tabelas já usam `table-responsive` (verificar todas)
- Botões: adicionar `min-height` via CSS para touch-friendly (44px)
- Cards: já empilham via grid Bootstrap
- Forms: verificar campos em mobile

## Arquivos previstos

| Arquivo | Tipo |
|---------|------|
| `static/manifest.json` | novo |
| `static/icons/icon.svg` | novo |
| `static/icons/icon-192.png` | novo (ou apenas SVG) |
| `static/icons/icon-512.png` | novo (ou apenas SVG) |
| `static/js/sw.js` | novo |
| `static/js/app.js` | modificado (registrar SW) |
| `templates/base.html` | modificado (meta tags + badge) |
| `apps/accounts/context_processors.py` | modificado (queue_counts) |
| `config/settings/base.py` | modificado (context processor) |
| `static/css/app.css` | modificado (touch-friendly) |

## Orçamento de testes

- Context processor queue_counts: ~4
- Manifest view (se usar view): ~2
- Meta tags no base.html: ~2
- Responsividade (CSS): ~0 (visual)
- Total estimado: ~8 novos testes
