# Slice 1: App admin_ui + gestão de usuários

## Objetivo

Criar o app `apps/admin_ui/` com CRUD de usuários, proteções e templates.

## Arquivos a criar

### 1. `apps/admin_ui/` (app scaffold)
- `__init__.py`
- `apps.py` (`AdminUiConfig`)
- `urls.py` — namespace `admin_ui`
- `views.py` — user_list, user_create, user_update, user_block, user_unblock
- `forms.py` — UserCreateForm, UserUpdateForm
- `decorators.py` — `@admin_or_manager_required`

### 2. `config/urls.py`
Adicionar `path("admin-ui/", include("apps.admin_ui.urls"))`

### 3. `config/settings/base.py`
Adicionar `"apps.admin_ui"` em `INSTALLED_APPS`

### 4. `templates/admin_ui/user_list.html`
- Tabela: username, email, papéis (badges), status, ações
- Filtros: status (dropdown), papel (dropdown), busca (input)
- Botões: Criar Usuário, Bloquear/Desbloquear, Editar
- Nav pills: Dashboard / Prompts / Usuários (ativo) / Auditoria

### 5. `templates/admin_ui/user_form.html`
- Form: username (readonly se edit), email, password (só create), papéis (checkboxes)
- Estilo Bootstrap, campo de papel como checkboxes inline

### 6. Proteções
- Não pode bloquear a si mesmo (`request.user.pk == user.pk → error`)
- Não pode bloquear o último admin ativo (se bloquear fica sem admin)
- Manager pode ver mas não criar/editar/bloquear (só admin)
- `account_status="removed"` → soft delete (`is_active=False`)

### 7. Dashboard nav pills
Atualizar `templates/dashboard/index.html`: link "Usuários" → `{% url 'admin_ui:user_list' %}`

## Critérios de sucesso

- [ ] App admin_ui registrado e acessível
- [ ] `/admin-ui/users/` retorna 200 para admin
- [ ] Manager pode ver lista mas não criar/editar
- [ ] Criar usuário com username, email, password, papéis
- [ ] Editar usuário (email, papéis)
- [ ] Bloquear/desbloquear usuário (POST)
- [ ] Proteção: não auto-bloquear
- [ ] Proteção: não bloquear último admin
- [ ] Filtros e busca funcionam
- [ ] Template estende `base.html`
- [ ] Testes: ~15
- [ ] ruff + mypy + pytest clean

## Arquivos: ideal ≤ 8
