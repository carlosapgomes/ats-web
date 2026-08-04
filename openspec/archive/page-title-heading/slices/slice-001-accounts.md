# Slice 1: Migrar módulo `accounts` para `{% block page_title %}`

## Objetivo

Converter os templates do módulo `accounts` que fazem override de `{% block subtitle %}` para o novo `{% block page_title %}` com `<h1 class="page-title">`.

## Arquivos (2 templates + 1 teste)

- `templates/accounts/notifications.html` — tem `<h2>` no conteúdo (linha 21): avaliar consolidação.
- `templates/accounts/manual.html`.
- `tests/test_page_title.py` — extensão com teste de caracterização.

## Handoff / prompt para implementador (contexto zero)

> Para cada template abaixo, substitua:
>
> ```html
> {% block subtitle %}TEXTO{% endblock %}
> ```
> por:
> ```html
> {% block page_title %}<h1 class="page-title">TEXTO</h1>{% endblock %}
> ```
>
> Preservando o `TEXTO` exatamente (incluindo filtros/variáveis).
>
> **`templates/accounts/notifications.html`**: o `subtitle` atual é `"Minhas Notificações"`. Há um `<h2>` na linha 21 — verifique se ele é redundante com o novo `<h1>`; se sim, ajuste o `<h2>` para um subtítulo descritivo ou remova (decisão: preservar o `<h2>` se ele trouxer informação adicional; caso seja só "Notificações", remover para evitar duplicação).
>
> **`templates/accounts/manual.html`**: o `subtitle` é `"Manual de Uso"`. Migração direta.

## TDD

### RED

Estender `tests/test_page_title.py`:

```python
def test_notifications_has_page_title_h1(rf):
    from django.test import Client
    # renderiza via client (precisa de URL configurada) OU via render_to_string com contexto
    # alternativa: teste de string no template
    from pathlib import Path
    content = Path("templates/accounts/notifications.html").read_text()
    assert '{% block page_title %}<h1 class="page-title">' in content
    assert '{% block subtitle %}' not in content

def test_manual_has_page_title_h1():
    from pathlib import Path
    content = Path("templates/accounts/manual.html").read_text()
    assert '{% block page_title %}<h1 class="page-title">Manual de Uso</h1>{% endblock %}' in content
    assert '{% block subtitle %}' not in content
```

### GREEN

Aplicar a migração nos 2 templates.

### REFACTOR

Consolidar o `<h2>` de `notifications.html` se redundante.

## Critérios de sucesso

- [ ] 2 templates migrados; nenhum `{% block subtitle %}` restante no módulo.
- [ ] `<h1 class="page-title">` presente em ambos.
- [ ] Testes novos passam; `uv run pytest` verde.
- [ ] Sem `<h1>` duplicado.
- [ ] Quality gate completo.

## Gates de autoavaliação

- [ ] Verifiquei que `notifications.html` não ficou com `<h1>` e `<h2>` redundantes.
- [ ] Commit rastreável (`refactor(accounts): migrate page titles to h1`).
