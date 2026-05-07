# Slice 1: App admin_ui + gestão de usuários — Relatório de Implementação

## Resumo

Criação do app `apps/admin_ui/` com CRUD de usuários, proteções (manager vs admin,
auto-bloqueio, último admin) e templates Bootstrap.

## Arquivos Criados

### `apps/admin_ui/__init__.py`
App scaffold.

### `apps/admin_ui/apps.py`
`AdminUiConfig` — registra app com `name="apps.admin_ui"`.

### `apps/admin_ui/decorators.py`
- `admin_or_manager_required` — manager pode ler, admin pode tudo
- `admin_required` — só admin

### `apps/admin_ui/forms.py`
- `UserCreateForm` — username, email, password, roles (checkboxes)
- `UserUpdateForm` — email readonly, username readonly (exibido), roles editáveis

### `apps/admin_ui/views.py`
- `user_list` — tabela com filtros (status, papel) e busca (username/email)
- `user_create` — POST cria usuário com hash de senha
- `user_update` — POST atualiza email e papéis
- `user_block` — POST: `account_status="blocked"`, `is_active=False`
- `user_unblock` — POST: `account_status="active"`, `is_active=True`
- Proteções: não auto-bloquear, não bloquear último admin

### `apps/admin_ui/urls.py`
Namespace `admin_ui:` com 5 URLs de usuário.

### `apps/admin_ui/tests/test_users_crud.py`
43 testes organizados em 8 classes:
- Access Control (14 testes)
- User List (8 testes)
- User Create (6 testes)
- User Update (5 testes)
- User Block (5 testes)
- User Unblock (3 testes)
- Nav Pills (2 testes)

### `templates/admin_ui/user_list.html`
Tabela com badges de papel/status, filtros inline, botão criar/bloquear/editar.
Nav pills: Dashboard, Prompts, Usuários (ativo), Auditoria.

### `templates/admin_ui/user_form.html`
Formulário com username readonly (edição), password (só create), checkboxes inline
para papéis. Nav pills com link ativo para Usuários.

## Arquivos Modificados

### `config/urls.py`
Adicionado: `path("admin-ui/", include("apps.admin_ui.urls"))`

### `config/settings/base.py`
Adicionado `"apps.admin_ui"` em `INSTALLED_APPS`

### `pyproject.toml`
Adicionados mypy overrides para `apps.admin_ui.*`

### `templates/dashboard/index.html`
Nav pill "Usuários" agora linka para `{% url 'admin_ui:user_list' %}`

## Antes vs Depois

**Antes:** Dashboard nav pills "Usuários" era placeholder (`href="#" onclick="return false;"`)

**Depois:** `<a href="{% url 'admin_ui:user_list' %}" class="nav-link">Usuários</a>`

## Qualidade

- Ruff: ✅ All checks passed
- Formatter: ✅ 106 files already formatted
- Mypy: ✅ no issues found in 112 source files
- Testes: ✅ 441 passed (43 novos + 398 existentes)
