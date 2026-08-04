# Slice 002: Perfil do usuário + alteração de senha mantendo sessão atual

## Status

- [x] Done

## Contexto zero para implementador

O ATS Web usa Django SSR, `apps/accounts` para autenticação e templates Bootstrap. Após Slice 001, o projeto já terá configuração de email e fluxo de password reset. Este slice entrega uma tela de perfil autenticada e troca de senha usando senha atual.

Importante: seguir o comportamento padrão/recomendado do Django e manter a sessão atual após alteração da senha com `update_session_auth_hash` ou `PasswordChangeView` corretamente configurada.

Não implemente email de cadastro aqui.

Leia antes de implementar:

- `AGENTS.md`
- `PROJECT_CONTEXT.md`
- `docs/adr/ADR-0002-emails-transacionais-autenticacao-cadastro.md`
- `openspec/changes/transactional-emails-auth-flows/proposal.md`
- `openspec/changes/transactional-emails-auth-flows/design.md`
- `openspec/changes/transactional-emails-auth-flows/tasks.md`
- `slices/slice-001-password-reset.md` para reaproveitar padrões de template/JS
- este slice

## Objetivo do slice

Entregar fluxo vertical:

```text
Usuário logado abre Perfil
→ visualiza dados básicos
→ informa senha atual e nova senha
→ senha é alterada
→ sessão atual permanece autenticada
→ usuário vê mensagem de sucesso
```

## Arquivos esperados

Mantenha o mínimo necessário. Prováveis arquivos:

1. `apps/accounts/urls.py`
2. `apps/accounts/views.py`
3. `templates/accounts/profile.html`
4. `templates/accounts/password_change_form.html` ou seção equivalente no perfil
5. `templates/accounts/password_change_done.html` se usar view nativa separada
6. `templates/base.html` para link no menu/avatar, se houver local adequado
7. `apps/accounts/tests/test_profile_password_change.py`

Justifique no relatório se tocar arquivos adicionais.

## Requisitos funcionais

### R1. Perfil autenticado

Criar rota autenticada, por exemplo:

```python
path("profile/", views.profile_view, name="profile")
```

A tela deve mostrar dados básicos do usuário logado, sem expor dados sensíveis:

- username;
- nome;
- email;
- papéis atribuídos, se simples de mostrar com padrão existente;
- papel ativo atual, se já houver contexto disponível.

### R2. Link para perfil

Adicionar link para perfil no menu/avatar/base template, se existir local adequado. Não redesenhar navegação inteira.

### R3. Alteração de senha

Usar infraestrutura nativa:

- `PasswordChangeView`, ou
- view própria mínima com `PasswordChangeForm`.

Deve exigir senha atual e validar nova senha conforme validators Django.

### R4. Manter sessão atual

Após senha alterada com sucesso:

- manter sessão atual autenticada;
- usar `update_session_auth_hash` se implementar view própria;
- exibir `messages.success` ou página de sucesso;
- login com senha antiga deve falhar e com senha nova deve funcionar.

Não invalidar manualmente outras sessões neste change.

### R5. Mostrar senha

Adicionar opção “mostrar senha” com Vanilla JS apenas nos campos da tela de alteração de senha.

## TDD obrigatório

Antes de implementar, adicionar testes falhando.

### Testes mínimos

1. `test_profile_requires_login`
   - usuário anônimo é redirecionado para login.

2. `test_authenticated_user_can_view_profile`
   - usuário logado vê perfil e dados básicos.

3. `test_base_navigation_links_to_profile`
   - quando autenticado, base/menu contém link para perfil, se o projeto tem menu aplicável.

4. `test_password_change_requires_current_password`
   - senha atual errada não altera senha;
   - form exibe erro.

5. `test_password_change_success_keeps_current_session`
   - POST com senha atual correta e nova senha válida;
   - response redireciona/sucesso;
   - request seguinte ainda autenticado.

6. `test_password_change_old_password_fails_new_password_works`
   - após alteração, login com senha antiga falha;
   - login com senha nova funciona.

7. `test_password_change_form_has_password_visibility_toggle`
   - assert elementos/atributos do toggle.

## Critérios de sucesso

- [ ] TDD seguido: testes falham antes e passam depois.
- [ ] Perfil exige autenticação.
- [ ] Alteração exige senha atual.
- [ ] Sessão atual permanece válida após troca.
- [ ] Login com senha antiga falha; nova senha funciona.
- [ ] Mostrar senha usa Vanilla JS e só aparece no escopo deste slice.
- [ ] Não implementa email de cadastro.
- [ ] Quality gate do AGENTS.md passa.

## Gates de autoavaliação

Responder no relatório:

1. Qual componente nativo Django foi usado para troca de senha?
2. Onde a sessão atual é preservada?
3. Qual teste prova que o usuário continua logado?
4. Qual teste prova que a senha antiga deixou de funcionar?
5. O slice alterou navegação mínima sem redesign?
6. O botão mostrar senha usa apenas Vanilla JS?

## Relatório final obrigatório

Criar markdown temporário com:

- resumo do que foi implementado;
- arquivos alterados;
- snippets antes/depois dos pontos principais;
- testes adicionados e resultado;
- comandos de quality gate e resultados;
- riscos/pendências.

Atualizar `openspec/changes/transactional-emails-auth-flows/tasks.md` ao concluir.

Fazer commit e push para `origin feat/transactional-emails-auth-flows`.

Responder com:

```text
REPORT_PATH=<temp-markdown-path>
```

Parar e pedir confirmação antes do próximo slice.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, docs/adr/ADR-0002-emails-transacionais-autenticacao-cadastro.md, openspec/changes/transactional-emails-auth-flows/proposal.md, design.md, tasks.md, slices/slice-001-password-reset.md and slices/slice-002-profile-password-change.md.
Implement ONLY Slice 002.
Use vertical slicing and TDD: first add failing tests for profile access, password change, session preservation and password visibility toggle, then implement minimal code.
Reuse Django PasswordChangeView or PasswordChangeForm. Require current password. Preserve the current session with standard Django behavior/update_session_auth_hash. Add a small profile page and minimal navigation link. Add Vanilla JS show-password only for this password change form.
Do not implement registration email or invalidate all sessions.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/transactional-emails-auth-flows/tasks.md when this slice is complete.
Create a detailed temporary markdown report with before/after snippets, commit and push.
Return REPORT_PATH=<path> and stop. Do not start Slice 003 without explicit confirmation.
```
