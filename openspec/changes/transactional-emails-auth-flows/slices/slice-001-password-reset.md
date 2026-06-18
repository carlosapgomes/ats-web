# Slice 001: Password reset transacional end-to-end

## Status

- [ ] Pending

## Contexto zero para implementador

O ATS Web é um monolito Django SSR. Autenticação customizada atual fica em `apps/accounts/views.py`, `apps/accounts/forms.py`, `apps/accounts/urls.py` e `templates/accounts/login.html`. O projeto deve reutilizar infraestrutura nativa do Django e enviar emails via `django.core.mail` configurável para AWS SES SMTP.

Este slice entrega somente o fluxo “esqueci minha senha”. Não implemente perfil nem email de cadastro aqui.

Leia antes de implementar:

- `AGENTS.md`
- `PROJECT_CONTEXT.md`
- `docs/adr/ADR-0002-emails-transacionais-autenticacao-cadastro.md`
- `openspec/changes/transactional-emails-auth-flows/proposal.md`
- `openspec/changes/transactional-emails-auth-flows/design.md`
- `openspec/changes/transactional-emails-auth-flows/tasks.md`
- este slice

## Objetivo do slice

Entregar fluxo vertical:

```text
Usuário abre login
→ clica “Esqueci minha senha”
→ informa email
→ recebe resposta genérica
→ email é enviado pelo backend Django
→ usuário acessa token válido
→ define nova senha
→ volta para login com mensagem de sucesso
```

## Arquivos esperados

Mantenha o mínimo necessário. Prováveis arquivos:

1. `config/settings/base.py`
2. `config/settings/dev.py`
3. `config/settings/test.py`
4. `config/settings/prod.py`
5. `apps/accounts/urls.py`
6. `apps/accounts/views.py` ou novo módulo pequeno em `apps/accounts/`
7. `templates/accounts/login.html`
8. `templates/accounts/password_reset_form.html`
9. `templates/accounts/password_reset_done.html`
10. `templates/accounts/password_reset_confirm.html`
11. `templates/accounts/password_reset_complete.html`
12. `templates/accounts/email/password_reset_subject.txt` e/ou email body equivalente
13. `apps/accounts/tests/test_password_reset.py`

Justifique no relatório se tocar arquivos adicionais.

## Requisitos funcionais

### R1. Configuração de email

Adicionar settings por env vars, com defaults seguros:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=email-smtp.us-east-2.amazonaws.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
DEFAULT_FROM_EMAIL=no-reply@chd.projetoshgrs.com
PASSWORD_RESET_TIMEOUT=86400
```

Preferências:

- test: `django.core.mail.backends.locmem.EmailBackend`;
- dev: console ou file backend, sem enviar email real por padrão;
- prod: SMTP configurável.

### R2. Views nativas Django

Usar `PasswordResetView`, `PasswordResetDoneView`, `PasswordResetConfirmView`, `PasswordResetCompleteView` com templates próprios do projeto.

Rotas sugeridas:

```python
path("password-reset/", ..., name="password_reset")
path("password-reset/done/", ..., name="password_reset_done")
path("reset/<uidb64>/<token>/", ..., name="password_reset_confirm")
path("reset/done/", ..., name="password_reset_complete")
```

### R3. Link no login

Adicionar link visível em `templates/accounts/login.html` para `password_reset`.

### R4. Anti-enumeração

Manter comportamento seguro: POST com email existente ou inexistente mostra resposta genérica. Não revelar se o email está cadastrado.

### R5. Rate limit simples

Aplicar somente ao POST de password reset. Sem dependência nova.

Critério mínimo:

- limitar por IP e/ou email normalizado em janela curta;
- não revelar se o bloqueio ocorreu por email existente;
- cobrir por teste.

Use cache Django. Se cache locmem já for default em testes, aproveite.

### R6. Mostrar senha

Adicionar opção “mostrar senha” com Vanilla JS somente em:

- login;
- tela de confirmação de nova senha (`password_reset_confirm`).

Não aplicar globalmente em todos os forms.

## TDD obrigatório

Antes de implementar, adicionar testes falhando.

### Testes mínimos

1. `test_login_page_links_to_password_reset`
   - GET login contém link para reset.

2. `test_password_reset_page_renders`
   - GET reset retorna 200 e renderiza formulário.

3. `test_password_reset_post_existing_email_sends_email_without_enumeration`
   - criar usuário ativo com email;
   - POST email;
   - redirect/sucesso genérico;
   - `mail.outbox` contém email.

4. `test_password_reset_post_unknown_email_uses_same_success_response`
   - POST email inexistente;
   - resposta igual ou semanticamente genérica;
   - não vaza “email não encontrado”.

5. `test_password_reset_token_allows_password_change`
   - extrair link ou gerar uid/token nativo;
   - POST nova senha válida;
   - login com senha nova funciona.

6. `test_invalid_password_reset_token_is_rejected`
   - token inválido não altera senha.

7. `test_password_reset_post_is_rate_limited`
   - exceder limite definido;
   - assert comportamento bloqueado/genérico;
   - assert não envia emails ilimitados.

8. `test_login_and_reset_confirm_include_password_visibility_toggle`
   - assert elementos/atributos esperados sem depender de framework JS.

## Critérios de sucesso

- [ ] TDD seguido: testes falham antes e passam depois.
- [ ] Settings de email são configuráveis por env vars.
- [ ] Test usa locmem backend.
- [ ] Fluxo usa token/view nativos do Django.
- [ ] Login tem link de reset.
- [ ] Resposta não enumera usuários.
- [ ] Rate limit simples cobre POST de reset.
- [ ] Login e reset confirm têm mostrar senha em Vanilla JS.
- [ ] Não implementa perfil nem cadastro.
- [ ] Quality gate do AGENTS.md passa.

## Gates de autoavaliação

Responder no relatório:

1. Quais views nativas do Django foram usadas?
2. Onde o rate limit está centralizado e qual teste prova?
3. O fluxo revela se o email existe? Qual teste prova que não?
4. Como dev/test/prod configuram backend de email?
5. O botão mostrar senha usa apenas Vanilla JS?
6. O slice tocou mais de 5 arquivos? Justifique verticalmente.

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
Read AGENTS.md, PROJECT_CONTEXT.md, docs/adr/ADR-0002-emails-transacionais-autenticacao-cadastro.md, openspec/changes/transactional-emails-auth-flows/proposal.md, design.md, tasks.md and slices/slice-001-password-reset.md.
Implement ONLY Slice 001.
Use vertical slicing and TDD: first add failing tests for password reset, rate limit and password visibility toggle, then implement minimal code.
Reuse Django native PasswordResetView/Done/Confirm/Complete and django.core.mail. Configure SMTP/SES via env vars with test locmem backend. Add link on login. Add simple cache-based rate limit only to POST password reset. Preserve anti-enumeration behavior. Add Vanilla JS show-password only on login and reset confirm.
Do not implement profile/password change or registration email in this slice.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/transactional-emails-auth-flows/tasks.md when this slice is complete.
Create a detailed temporary markdown report with before/after snippets, commit and push.
Return REPORT_PATH=<path> and stop. Do not start Slice 002 without explicit confirmation.
```
