# Design: Administração

## Decisões

### D1: Novo app `apps/admin_ui/`

Nome `admin_ui` para evitar conflito com `django.contrib.admin`. App dedicado para
views de gestão de usuários e prompts.

### D2: URL namespace `admin_ui:`

```
/admin-ui/users/              → admin_ui:user_list
/admin-ui/users/create/       → admin_ui:user_create
/admin-ui/users/<int:pk>/     → admin_ui:user_update
/admin-ui/users/<int:pk>/block/   → admin_ui:user_block (POST)
/admin-ui/users/<int:pk>/unblock/ → admin_ui:user_unblock (POST)

/admin-ui/prompts/            → admin_ui:prompt_list
/admin-ui/prompts/create/     → admin_ui:prompt_create
/admin-ui/prompts/<uuid:pk>/  → admin_ui:prompt_detail
/admin-ui/prompts/<uuid:pk>/activate/ → admin_ui:prompt_activate (POST)
/admin-ui/prompts/<uuid:pk>/deactivate/ → admin_ui:prompt_deactivate (POST)
```

### D3: Access control — manager + admin

Decorator que verifica `active_role` in `("manager", "admin")`.
Manager pode ver tudo mas só admin pode criar/editar/bloquear usuários e prompts.

### D4: User CRUD

**UserList**: tabela com filtros (status, papel) e busca por username/email.
**UserCreate**: form com username, email, password (hash via `set_password`), papéis (checkboxes).
**UserUpdate**: form com email, papéis. Username readonly.
**UserBlock/Unblock**: POST, altera `account_status` + `is_active`.
  - Proteção: não pode bloquear a si mesmo
  - Proteção: não pode bloquear o último admin ativo

### D5: Prompt CRUD

**PromptList**: agrupa por nome, mostra versão ativa + total de versões. Click expande histórico.
**PromptCreate**: form com name (dropdown dos 4 nomes existentes) + content (textarea grande).
  Version auto-increment: `version = max(version for name) + 1`. Ativo por padrão.
**PromptDetail**: mostra conteúdo em `<pre>`, botões ativar/desativar.
**PromptActivate/Deactivate**: POST, usa métodos `activate()`/`deactivate()` do modelo.

Nomes de prompt existentes: `llm1_system`, `llm1_user`, `llm2_system`, `llm2_user`.

### D6: Templates

Todos estendem `base.html`. Estilo consistente com dashboard:
- Cards com tabelas Bootstrap
- Filtros inline
- Botões com `btn-hospital`
- Nav pills: Dashboard / Prompts (ativo) / Usuários / Auditoria

### D7: home_view + nav pills

- Dashboard nav pills "Prompts" → `/admin-ui/prompts/`
- Dashboard nav pills "Usuários" → `/admin-ui/users/`
- Templates admin_ui incluem mesmas nav pills

## Arquivos previstos

| Arquivo | Tipo |
|---------|------|
| `apps/admin_ui/__init__.py` | novo |
| `apps/admin_ui/apps.py` | novo |
| `apps/admin_ui/urls.py` | novo |
| `apps/admin_ui/views.py` | novo (users + prompts) |
| `apps/admin_ui/forms.py` | novo |
| `apps/admin_ui/decorators.py` | novo |
| `templates/admin_ui/user_list.html` | novo |
| `templates/admin_ui/user_form.html` | novo |
| `templates/admin_ui/prompt_list.html` | novo |
| `templates/admin_ui/prompt_create.html` | novo |
| `templates/admin_ui/prompt_detail.html` | novo |
| `config/urls.py` | modificado |
| `config/settings/base.py` | modificado (INSTALLED_APPS) |
| `templates/dashboard/index.html` | modificado (nav pills links) |

## Orçamento de testes

- User CRUD (list, create, update, block, unblock, proteções): ~15
- Prompt CRUD (list, create, detail, activate, deactivate): ~10
- Access control (manager vs admin vs outros): ~5
- Redirects: ~2
- Total estimado: ~32 novos testes
