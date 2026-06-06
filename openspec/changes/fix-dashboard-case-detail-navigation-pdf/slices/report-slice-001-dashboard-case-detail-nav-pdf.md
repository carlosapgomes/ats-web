# Relatório Slice 001 — Detalhe gerencial sem navegação NIR e com PDF para manager/admin

## Status

**Concluído** — quality gate verde, 129 testes nos apps tocados passando.

## Resumo

Parametrização do template compartilhado `templates/intake/case_detail.html` para atender
tanto o contexto operacional (NIR) quanto o contexto gerencial (dashboard manager/admin),
além de criação de rota dedicada de PDF para dashboard.

## Arquivos tocados (6)

| Arquivo | Tipo de mudança |
|---|---|
| `apps/dashboard/views.py` | Nova view `dashboard_case_pdf`, parametrização de contexto em `dashboard_case_detail` |
| `apps/dashboard/urls.py` | Nova rota `<uuid:case_id>/pdf/` → `dashboard:case_pdf` |
| `templates/intake/case_detail.html` | Uso de variáveis de contexto (`show_intake_nav`, `back_url`, `back_label`, `pdf_url`) |
| `apps/intake/views.py` | Parametrização de contexto em `case_detail` (NIR) |
| `apps/dashboard/tests/test_dashboard.py` | 14 novos testes (navegação, PDF URL, endpoint PDF) |
| `apps/intake/tests/test_case_detail.py` | 4 novos testes de regressão NIR |

## Snippets antes/depois

### 1. apps/dashboard/views.py — Nova view `dashboard_case_pdf`

**Antes:** Não existia.

**Depois:**
```python
@login_required
@role_required("manager", "admin")
@xframe_options_sameorigin
def dashboard_case_pdf(request: HttpRequest, case_id: uuid.UUID) -> HttpResponseBase:
    case = get_object_or_404(Case, case_id=case_id)
    if not case.pdf_file:
        raise Http404("PDF não encontrado para este caso.")
    return FileResponse(
        case.pdf_file.open("rb"),
        content_type="application/pdf",
    )
```

### 2. apps/dashboard/views.py — Contexto parametrizado em `dashboard_case_detail`

**Antes:**
```python
return render(request, "intake/case_detail.html", {"can_confirm_receipt": False, ...})
```

**Depois:**
```python
return render(request, "intake/case_detail.html", {
    "can_confirm_receipt": False,
    ...
    "show_intake_nav": False,
    "back_url": reverse("dashboard:index"),
    "back_label": "← Voltar ao dashboard",
    "pdf_url": reverse("dashboard:case_pdf", args=[case.case_id]),
})
```

### 3. apps/dashboard/urls.py — Nova rota PDF

**Antes:**
```python
path("<uuid:case_id>/", views.dashboard_case_detail, name="case_detail"),
```

**Depois:**
```python
path("<uuid:case_id>/", views.dashboard_case_detail, name="case_detail"),
path("<uuid:case_id>/pdf/", views.dashboard_case_pdf, name="case_pdf"),
```

### 4. templates/intake/case_detail.html — Nav condicional

**Antes:**
```html
{% block nav %}
<nav class="app-nav mt-3" aria-label="Navegação">
  <ul class="nav nav-pills gap-2">
    <li class="nav-item">
      <a class="nav-link" href="{% url 'intake:home' %}">Novo Encaminhamento</a>
    </li>
    <li class="nav-item">
      <a class="nav-link" href="{% url 'intake:my_cases' %}">Meus Casos</a>
    </li>
  </ul>
</nav>
{% endblock %}
```

**Depois:**
```html
{% block nav %}
{% if show_intake_nav %}
<nav class="app-nav mt-3" aria-label="Navegação">
  <ul class="nav nav-pills gap-2">
    <li class="nav-item">
      <a class="nav-link" href="{% url 'intake:home' %}">Novo Encaminhamento</a>
    </li>
    <li class="nav-item">
      <a class="nav-link" href="{% url 'intake:my_cases' %}">Meus Casos</a>
    </li>
  </ul>
</nav>
{% endif %}
{% endblock %}
```

### 5. templates/intake/case_detail.html — Back button parametrizado

**Antes:**
```html
<a href="{% url 'intake:my_cases' %}" class="btn btn-outline-secondary">Voltar para lista</a>
<a href="{% url 'intake:my_cases' %}" class="btn btn-hospital-outline">← Voltar para lista</a>
```

**Depois:**
```html
<a href="{{ back_url }}" class="btn btn-outline-secondary">{{ back_label }}</a>
<a href="{{ back_url }}" class="btn btn-hospital-outline">{{ back_label }}</a>
```

### 6. templates/intake/case_detail.html — PDF URL parametrizada

**Antes:**
```html
<embed src="{% url 'intake:serve_pdf' case.case_id %}" ...>
<a href="{% url 'intake:serve_pdf' case.case_id %}" ...>Abrir em nova aba</a>
```

**Depois:**
```html
<embed src="{{ pdf_url }}" ...>
<a href="{{ pdf_url }}" ...>Abrir em nova aba</a>
```

### 7. apps/intake/views.py — Contexto NIR parametrizado

**Antes:** Sem as variáveis `show_intake_nav`, `back_url`, `back_label`, `pdf_url`.

**Depois:**
```python
return render(request, "intake/case_detail.html", {
    ...
    "show_intake_nav": True,
    "back_url": reverse("intake:my_cases"),
    "back_label": "← Voltar para lista",
    "pdf_url": reverse("intake:serve_pdf", args=[case.case_id]),
})
```

## Decisões de implementação

- **Template único mantido**: Conforme design.md, a parametrização via contexto mostrou-se
  segura e suficiente. Não foi necessário criar `templates/dashboard/case_detail.html`.
- **Rota de PDF gerencial não bloqueia CLEANED**: Diferente da rota NIR, a rota gerencial
  permite acesso a casos em qualquer status, consistente com a natureza de auditoria do dashboard.
- **`@xframe_options_sameorigin`**: Aplicado na nova rota para permitir embed no mesmo site.

## Validação

```text
ruff check .       → All checks passed!
ruff format --check . → 144 files already formatted
mypy .             → Success: no issues found in 156 source files
pytest             → 1079 passed, 545 warnings in 20.72s
```

## Critérios de sucesso (DoD)

- [x] Manager não vê `Novo Encaminhamento` nem `Meus Casos` no detalhe dashboard
- [x] Admin não vê `Novo Encaminhamento` nem `Meus Casos` no detalhe dashboard
- [x] Detalhe dashboard mostra retorno ao dashboard
- [x] Detalhe dashboard usa `dashboard:case_pdf` e não `intake:serve_pdf`
- [x] Manager/admin acessam `dashboard:case_pdf`
- [x] Papéis não gerenciais não acessam `dashboard:case_pdf`
- [x] Rota gerencial retorna 404 para caso sem PDF
- [x] NIR continua vendo abas NIR e rota `intake:serve_pdf` no detalhe intake
- [x] NIR mantém botão "Confirmar Recebimento" para WAIT_R1_CLEANUP_THUMBS
