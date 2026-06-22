# Relatório: Esconder aba "Auditoria" das nav pills

## Objetivo

Esconder visualmente a aba/nav pill "Auditoria" nas telas de supervisor/administrador para go-live, mantendo a funcionalidade e a página `/dashboard/summaries/` intactas.

## Mudanças Realizadas

### Templates (6 arquivos)

Em cada template, o `<li class="nav-item">` da Auditoria recebeu `hidden`:

**Antes:**
```html
<li class="nav-item">
    <a href="#" class="nav-link" onclick="return false;">Auditoria</a>
</li>
```

**Depois:**
```html
<li class="nav-item" hidden>
    <a href="#" class="nav-link" onclick="return false;">Auditoria</a>
</li>
```

Arquivos alterados:
- `templates/dashboard/index.html`
- `templates/admin_ui/user_list.html`
- `templates/admin_ui/user_form.html`
- `templates/admin_ui/prompt_list.html`
- `templates/admin_ui/prompt_create.html`
- `templates/admin_ui/prompt_detail.html`

**Não modificado:** `templates/dashboard/summaries.html` — página de resumos permanece acessível via URL direta.

### Testes (3 arquivos)

Ajustes cosméticos para alinhar docstrings/comentários ao novo comportamento:

- `apps/dashboard/tests/test_dashboard.py`: docstring `"Nav pill 'Auditoria' aparece (placeholder)."` → `"Nav pill 'Auditoria' oculta (hidden placeholder)."`
- `apps/admin_ui/tests/test_prompts_crud.py`: adicionado comentário `# Auditoria está oculta (hidden), mas o texto ainda está no HTML`
- `apps/admin_ui/tests/test_users_crud.py`: mesmo comentário

As asserções `assert "Auditoria" in content` permanecem válidas porque o texto ainda está no HTML (apenas oculto pelo atributo `hidden`).

## Validação

- **Ruff:** `uv run ruff check .` → All checks passed
- **Testes:** `uv run pytest apps/dashboard/tests/test_dashboard.py apps/admin_ui/tests/` → **192 passed**

## Critérios de Sucesso

- [x] Aba "Auditoria" não aparece visualmente (atributo `hidden` no `<li>`)
- [x] Nenhuma funcionalidade existente quebrada (192 testes passando)
- [x] Rotas e página de resumos continuam intactas (`summaries.html` não modificado)
- [x] Alteração mínima e reversível (apenas 1 atributo HTML por template)
- [x] Qualidade: ruff + pytest verdes
