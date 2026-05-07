# Slice 2: Gestão de prompts

## Objetivo

CRUD de prompts com versionamento, ativação/desativação e templates.

## Arquivos a criar

### 1. `apps/admin_ui/views.py` — adicionar views de prompts
- `prompt_list` — lista agrupada por nome
- `prompt_create` — criar nova versão
- `prompt_detail` — visualizar versão
- `prompt_activate` — ativar versão (POST)
- `prompt_deactivate` — desativar versão (POST)

### 2. `apps/admin_ui/forms.py` — adicionar PromptCreateForm
- name (ChoiceField com os 4 nomes: llm1_system, llm1_user, llm2_system, llm2_user)
- content (Textarea grande)

### 3. `templates/admin_ui/prompt_list.html`
- Cards agrupados por nome
- Cada card: nome, versão ativa destacada, total versões, botão "Nova Versão"
- Expandir mostra histórico de versões com botões ativar/desativar
- Nav pills: Dashboard / Prompts (ativo) / Usuários / Auditoria

### 4. `templates/admin_ui/prompt_create.html`
- Form: nome (dropdown), content (textarea com monospace)
- Version auto-incrementado (lógica na view)

### 5. `templates/admin_ui/prompt_detail.html`
- Metadata: nome, versão, status, criado em, atualizado por
- Conteúdo em `<pre>` com estilo monospace
- Botões: Ativar / Desativar / Voltar

### 6. Dashboard nav pills
Atualizar link "Prompts" → `{% url 'admin_ui:prompt_list' %}`

## Lógica de versionamento

```python
# Criar nova versão
latest = PromptTemplate.objects.filter(name=name).order_by("-version").first()
new_version = (latest.version + 1) if latest else 1
PromptTemplate.objects.create(name=name, version=new_version, content=content, is_active=True, updated_by=user)
# is_active=True desativa as outras via clean()
```

## Critérios de sucesso

- [ ] `/admin-ui/prompts/` retorna 200 para admin
- [ ] Lista agrupada por nome com versão ativa destacada
- [ ] Criar nova versão com auto-incremento
- [ ] Ativar versão desativa as demais do mesmo nome
- [ ] Desativar versão
- [ ] Visualizar conteúdo da versão
- [ ] Manager pode ver mas não criar/editar
- [ ] Template estende `base.html`
- [ ] Testes: ~10
- [ ] ruff + mypy + pytest clean

## Arquivos: ideal ≤ 6
