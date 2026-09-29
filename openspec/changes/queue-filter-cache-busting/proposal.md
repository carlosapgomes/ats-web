# Proposal: Cache-busting nos JS das filas (`{% static %}` com hash)

**Change ID:** `queue-filter-cache-busting`

**Tipo:** mini fix (1 slice, 2 templates), correção duradoura do incidente pós-rc.8

**BASE_REF:** `cfae1847d74d382eb8ade8c8fe4b0ed3b6f557f7` (`main`, pós `v0.10.0-rc.8`)

## Why

Após o deploy da `v0.10.0-rc.8`, as filas do scheduler e do médico exibiram o
filtro `<select>` sem labels (só contagens) e sem filtrar. Investigação em
produção (`eon:/srv/apps/chd`) provou código íntegro (backend com labels,
origem servindo o JS novo, CDN convergido) e causa-raiz em **cache**: os dois
templates referenciam o JS com URL fixa hardcoded:

```html
<script src="/static/js/scheduler_queue_filter.js"></script>
<script src="/static/js/doctor_queue_filter.js"></script>
```

enquanto o projeto já usa em produção
`whitenoise.storage.CompressedManifestStaticFilesStorage`
(`config/settings/prod.py:37`), que gera URLs com hash **somente** para quem
usa a tag `{% static %}` (padrão já adotado nos demais templates, ex.:
`scheduler/confirm.html:230`). Com URL fixa, o Cloudflare (`max-age=14400` na
borda) e os browsers seguraram o **JS velho dos radios** contra o **HTML novo
do `<select>`** — e essa combinação produz exatamente os sintomas observados
(`updateCounts` antigo apaga os labels das options; `getSelectedType` antigo
nunca casa e o filtro fica preso em `all`).

## What Changes

**Slice 001 — script tags das filas via `{% static %}`:**
- `templates/scheduler/queue.html` e `templates/doctor/queue.html`: adicionar
  `{% load static %}` (padrão dos demais templates filhos; `load` do `base.html`
  não propaga ao filho) e trocar os dois `src` hardcoded por
  `{% static 'js/scheduler_queue_filter.js' %}` /
  `{% static 'js/doctor_queue_filter.js' %}`.
- Em produção isso rende URLs com hash (`scheduler_queue_filter.<hash>.js`),
  imutáveis por deploy — HTML novo sempre carrega o JS do mesmo deploy.
  Em testes/dev (storage sem manifest), rende a mesma URL de antes: zero
  mudança de comportamento local.

## Decisões de design (sem `design.md` separado — mini fix)

- **Seguir o padrão existente, não inventar versão:** `{% static %}` + manifest
  já é a infraestrutura do projeto; querystrings `?v=` manuais seriam um
  segundo mecanismo redundante.
- **Só os 2 templates das filas:** grep mostra que são as **únicas**
  referências hardcoded (`src="/static/` / `href="/static/`) em `templates/`;
  todo o resto já usa `{% static %}`.
- **Sem mudança em settings/storage/CDN:** o manifest já opera em prod; o
  problema era só os 2 templates não o utilizarem.

## Non-goals

- Mudança em settings, WhiteNoise, Cloudflare, views, JS, catálogo, FSM,
  migrations, prompts, CSS.
- Purga de cache do CDN/browser (transitório, já convergido).
- Unificação dos JS das filas ou qualquer refactor além das 2 tags.

## Sucesso

- HTML renderizado das duas filas referencia os JS com hash em prod
  (URL muda a cada deploy que toque no arquivo).
- Próximo deploy que altere JS das filas não serve mais JS velho contra HTML
  novo — fim da classe de incidente.
- Zero regressão: suíte verde; `ruff`/`mypy` limpos.
