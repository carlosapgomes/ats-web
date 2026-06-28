# Slice 4: Migrar `doctor`, `dashboard`, `admin_ui` para `{% block page_title %}`

## Objetivo

Converter os 7 templates restantes (módulos `doctor`, `dashboard`, `admin_ui`) para o novo `{% block page_title %}`.

## Arquivos (7 templates + 1 teste)

- `templates/doctor/decision.html` — contém variáveis: `"Caso {{ case.agency_record_number|default:case.case_id|truncatechars:16 }} · {{ patient_name }}"`. Página de decisão crítica; validar layout.
- `templates/doctor/queue.html` — `"Casos aguardando decisão"`.
- `templates/dashboard/index.html` — `"Visão geral de todos os casos e métricas operacionais"`.
- `templates/dashboard/summaries.html` — `"Histórico de resumos periódicos de supervisão"`.
- `templates/admin_ui/prompt_detail.html` — `"Detalhes da versão {{ prompt.version }} de {{ prompt.name }}"`.
- `templates/admin_ui/prompt_create.html` — `"Criar nova versão de prompt"`.
- `templates/admin_ui/user_form.html` — condicional: `"{% if is_create %}Criar novo usuário no sistema{% else %}Editar dados do usuário{% endif %}"`.
- `templates/admin_ui/prompt_list.html` — `"Gestão de templates de prompt para LLM"`.
- `templates/admin_ui/user_list.html` — `"Gestão de usuários do sistema"`.
- `tests/test_page_title.py` — extensão.

**Nota:** são 9 templates no total (doctor: 2, dashboard: 2, admin_ui: 5). Se passar de ~9 arquivos tocados, dividir em dois sub-commits (doctor+dashboard, depois admin_ui) — mas pode ser um slice único pois a migração é mecânica.

## Handoff / prompt para implementador (contexto zero)

> Para cada template abaixo, substitua `{% block subtitle %}TEXTO{% endblock %}` por `{% block page_title %}<h1 class="page-title">TEXTO</h1>{% endblock %}`, preservando `TEXTO` exatamente (incluindo `{{ ... }}`, `{% if %}` e `|truncatechars`).
>
> - `doctor/decision.html`: `"Caso {{ case.agency_record_number|default:case.case_id|truncatechars:16 }} · {{ patient_name }}"`
> - `doctor/queue.html`: `"Casos aguardando decisão"`
> - `dashboard/index.html`: `"Visão geral de todos os casos e métricas operacionais"`
> - `dashboard/summaries.html`: `"Histórico de resumos periódicos de supervisão"`
> - `admin_ui/prompt_detail.html`: `"Detalhes da versão {{ prompt.version }} de {{ prompt.name }}"`
> - `admin_ui/prompt_create.html`: `"Criar nova versão de prompt"`
> - `admin_ui/user_form.html`: `"{% if is_create %}Criar novo usuário no sistema{% else %}Editar dados do usuário{% endif %}"`
> - `admin_ui/prompt_list.html`: `"Gestão de templates de prompt para LLM"`
> - `admin_ui/user_list.html`: `"Gestão de usuários do sistema"`
>
> Não altere mais nada.

## TDD

### RED

Estender `tests/test_page_title.py`:

```python
REMAINING_TEMPLATES = [
    "templates/doctor/decision.html",
    "templates/doctor/queue.html",
    "templates/dashboard/index.html",
    "templates/dashboard/summaries.html",
    "templates/admin_ui/prompt_detail.html",
    "templates/admin_ui/prompt_create.html",
    "templates/admin_ui/user_form.html",
    "templates/admin_ui/prompt_list.html",
    "templates/admin_ui/user_list.html",
]

@pytest.mark.parametrize("template_rel", REMAINING_TEMPLATES)
def test_remaining_template_uses_page_title_block(template_rel):
    content = Path(template_rel).read_text()
    assert '{% block page_title %}<h1 class="page-title">' in content
    assert "{% block subtitle %}" not in content

def test_doctor_decision_preserves_case_variables():
    content = Path("templates/doctor/decision.html").read_text()
    assert "{{ case.agency_record_number|default:case.case_id|truncatechars:16 }}" in content
    assert "{{ patient_name }}" in content

def test_no_subtitle_block_remains_anywhere():
    """Após todos os slices, nenhum template deve conter {% block subtitle %}."""
    import os
    for root, dirs, files in os.walk("templates"):
        for f in files:
            if f.endswith(".html"):
                path = os.path.join(root, f)
                content = Path(path).read_text()
                assert "{% block subtitle %}" not in content, (
                    f"{path} ainda contém {{% block subtitle %}}"
                )
```

### GREEN

Migrar os 9 templates.

### REFACTOR

Confirmar que o teste `test_no_subtitle_block_remains_anywhere` passa (verificação global de fechamento do change).

## Critérios de sucesso

- [ ] 9 templates migrados.
- [ ] Teste global `test_no_subtitle_block_remains_anywhere` passa.
- [ ] Variáveis/condicionais preservadas.
- [ ] `uv run pytest` verde.
- [ ] Quality gate completo.

## Gates de autoavaliação

- [ ] Verifiquei que `doctor/decision.html` (página crítica) renderiza `<h1>` sem quebrar o card de decisão.
- [ ] Confirmei (via teste global) que nenhum template no projeto contém mais `{% block subtitle %}`.
- [ ] Commit rastreável (`refactor(doctor,dashboard,admin_ui): migrate page titles to h1`).
