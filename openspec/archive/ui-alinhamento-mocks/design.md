# Design: Alinhamento Visual com Mocks de Referência

## Decisões

### D1: CSS — merge do mock para dentro de app.css

O `demo-reference/css/styles.css` é a fonte de verdade visual. Mergear todas as
classes que faltam em `static/css/app.css`, mantendo o que já existe e adicionando:

- `.decision-section` / `.decision-radio-group` (prepara Fase 3)
- `.demo-toast` / `.show` (toast de feedback)
- `.summary-box` / `.summary-label` / `.summary-value`
- `.notif-badge` com `data-count`
- `.patient-name` em case cards
- `.waiting-time` / `.waiting-time.urgent`
- `.pulse-dot` animation
- Responsive breakpoints completos
- Login page styles (`.sirhosp-public-bg` etc. — verificar se já existe)

CSS vars `--hospital-*` são idênticas entre mock e app.css — não precisa tocar.

### D2: Templates — alinhar estrutura HTML com mocks

Cada template Django deve usar as **mesmas classes CSS** e **mesma estrutura DOM**
que o mock correspondente. As diferenças permitidas são apenas:
- `{% extends "base.html" %}` em vez de HTML completo
- `{% csrf_token %}` em forms
- Variáveis de template (`{{ case.agency_record_number }}`) em vez de dados hardcoded
- Blocos Django (`{% block content %}`) em vez de conteúdo fixo

### D3: JS estático — corrigir serving

O problema do `upload.js` 404 é que o `runserver` serve estáticos automaticamente
em DEBUG=True, mas o arquivo `app.css` referencia `/static/css/app.css` — confirmar
que `STATIC_URL = "static/"` e que os arquivos estão em `static/`.

Se necessário, rodar `collectstatic` ou confirmar que `django.contrib.staticfiles`
está em `INSTALLED_APPS` (já está).

### D4: .env loading — adicionar python-dotenv no settings

```python
from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")
```

Linha a adicionar no topo de `config/settings/base.py`, antes de qualquer
`os.environ.get()`. A dependência `python-dotenv` já está no `pyproject.toml`.

### D5: home_view — redirect por papel

```python
def home_view(request):
    active_role = request.session.get("active_role")
    if not active_role:
        return redirect("/switch-role/")
    if active_role == "nir":
        return redirect("intake:home")
    # TODO: doctor → doctor queue, scheduler → scheduler queue, etc.
    return redirect("intake:home")  # fallback temporário
```

Já implementado em sessão anterior, mas precisa de teste.

### D6: INTRANET_IP_RANGE — suportar múltiplos CIDR

```python
def _is_intranet_ip(client_ip):
    ip_range = getattr(settings, "INTRANET_IP_RANGE", None)
    if not ip_range:
        return False
    addr = ipaddress.ip_address(client_ip)
    for cidr in ip_range.split(","):
        cidr = cidr.strip()
        if cidr and addr in ipaddress.ip_network(cidr, strict=False):
            return True
    return False
```

Já implementado em sessão anterior, mas precisa de testes.

### D7: Sem new apps, sem new models

Este change toca apenas: templates, CSS, JS, settings, middleware, views de redirect.
Zero migrations, zero models, zero new apps.
