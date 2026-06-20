# Slice 003: Email automático de cadastro/ativação via token nativo

## Status

- [x] Done

## Contexto zero para implementador

O ATS Web possui gestão própria de usuários em `apps/admin_ui`. A criação atual usa `UserCreateForm`, salva senha temporária manual e atribui papéis ao usuário. Este slice deve enviar automaticamente um email transacional após criação de usuário, com link de definição/redefinição de senha usando token nativo do Django.

A regra de URL depende dos papéis do usuário:

```text
Tem doctor, manager ou admin? -> PUBLIC_APP_BASE_URL
Só tem nir/scheduler?         -> INTERNAL_APP_BASE_URL
```

Usuários multi-role com qualquer papel público devem receber link público, porque geralmente têm função gerencial/liderança e precisam de flexibilidade.

Não implemente reenvio manual, email_verified_at, primeiro login obrigatório ou envio assíncrono.

Leia antes de implementar:

- `AGENTS.md`
- `PROJECT_CONTEXT.md`
- `docs/adr/ADR-0002-emails-transacionais-autenticacao-cadastro.md`
- `openspec/changes/transactional-emails-auth-flows/proposal.md`
- `openspec/changes/transactional-emails-auth-flows/design.md`
- `openspec/changes/transactional-emails-auth-flows/tasks.md`
- `slices/slice-001-password-reset.md` para reutilizar templates/tokens de reset
- este slice

## Objetivo do slice

Entregar fluxo vertical:

```text
Admin abre criação de usuário
→ preenche dados, senha temporária e papéis
→ salva usuário
→ sistema envia email automático
→ link usa base URL correta conforme papéis
→ token permite redefinir/validar senha
```

## Arquivos esperados

Mantenha o mínimo necessário. Prováveis arquivos:

1. `config/settings/base.py` se `PUBLIC_APP_BASE_URL`/`INTERNAL_APP_BASE_URL` ainda não existirem
2. `apps/accounts/services.py` ou novo módulo coeso equivalente
3. `apps/admin_ui/views.py`
4. templates de email em `templates/accounts/email/` ou padrão já adotado no Slice 001
5. `apps/accounts/tests/test_email_services.py`
6. `apps/admin_ui/tests/test_users_crud.py` ou novo teste focado em cadastro/email

Justifique no relatório se tocar arquivos adicionais.

## Requisitos funcionais

### R1. Base URLs por env vars

Configurar, se ainda não feito:

```env
PUBLIC_APP_BASE_URL=https://chd.projetoshgrs.com
INTERNAL_APP_BASE_URL=https://10.17.175.38
```

Remover barra final ao montar URLs para evitar `//` acidental.

### R2. Helper centralizado de URL

Criar helper testável em `apps/accounts/services.py` ou equivalente:

```python
PUBLIC_ROLE_NAMES = {"doctor", "manager", "admin"}
INTRANET_ONLY_ROLE_NAMES = {"nir", "scheduler"}

def get_account_action_base_url(user: User) -> str:
    ...
```

Regra obrigatória:

- se `user.roles` contém qualquer papel público, retornar `settings.PUBLIC_APP_BASE_URL`;
- caso contrário, retornar `settings.INTERNAL_APP_BASE_URL`.

Edge case usuário sem papéis: usar URL pública por segurança operacional, salvo justificativa explícita no relatório.

### R3. Serviço de email de cadastro

Criar serviço pequeno e coeso, por exemplo:

```python
def send_user_invitation_email(user: User) -> None:
    ...
```

Responsabilidades:

- gerar `uidb64` e token com mecanismo nativo de password reset;
- montar link absoluto usando `get_account_action_base_url(user)`;
- enviar email via `django.core.mail`;
- usar remetente `DEFAULT_FROM_EMAIL`;
- texto deve dizer que a conta foi criada e que o usuário deve definir/redefinir a senha;
- informar que o link expira conforme configuração do Django;
- não incluir senha temporária no email.

### R4. Integração no create administrativo

Integrar em `apps/admin_ui.views.user_create` após usuário e papéis estarem persistidos.

Comportamento recomendado em falha de envio:

- manter usuário criado;
- registrar log de exceção;
- mostrar `messages.warning` ou `messages.error` ao admin;
- não expor credenciais SMTP.

### R5. Envio automático

Não criar checkbox. Todo usuário criado pela tela própria deve disparar email automaticamente.

## TDD obrigatório

Antes de implementar, adicionar testes falhando.

### Testes mínimos de serviço

1. `test_get_account_action_base_url_uses_internal_for_nir_only`
2. `test_get_account_action_base_url_uses_internal_for_scheduler_only`
3. `test_get_account_action_base_url_uses_public_for_doctor`
4. `test_get_account_action_base_url_uses_public_for_manager`
5. `test_get_account_action_base_url_uses_public_for_admin`
6. `test_get_account_action_base_url_uses_public_for_nir_plus_manager`
7. `test_send_user_invitation_email_uses_expected_base_url_and_token`
   - `mail.outbox` contém link com base correta;
   - link contém uid/token ou URL de reset compatível.

### Testes mínimos de integração admin

8. `test_admin_user_create_sends_invitation_email_automatically`
   - login como admin;
   - POST create com dados válidos, senha temporária e papéis;
   - usuário é criado;
   - `mail.outbox` tem um email.

9. `test_admin_user_create_email_link_allows_password_reset`
   - extrair link ou gerar uid/token correspondente;
   - confirmar que fluxo de reset do Slice 001 aceita token e altera senha.

10. `test_admin_user_create_keeps_user_when_email_send_fails`
   - simular exceção no envio;
   - usuário permanece criado;
   - admin recebe mensagem de aviso/erro.

## Critérios de sucesso

- [ ] TDD seguido: testes falham antes e passam depois.
- [ ] Helper de URL está centralizado e coberto pela matriz de papéis.
- [ ] Criação administrativa envia email automaticamente.
- [ ] Email não contém senha temporária.
- [ ] Link usa token nativo e é válido para redefinir senha.
- [ ] Usuário só `nir`/`scheduler` recebe link interno.
- [ ] Usuário com qualquer papel público recebe link público.
- [ ] Falha SMTP não expõe segredo nem apaga usuário criado.
- [ ] Não implementa reenvio manual, fila assíncrona ou `email_verified_at`.
- [ ] Quality gate do AGENTS.md passa.

## Gates de autoavaliação

Responder no relatório:

1. Onde está centralizada a regra de URL pública/interna?
2. Qual teste cobre usuário `nir + manager` usando URL pública?
3. O email inclui senha temporária? Deve ser não.
4. O envio ocorre após roles persistidos? Onde?
5. O que acontece se SMTP falhar? Qual teste prova?
6. O token usado é nativo do Django? Onde é gerado?

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
Read AGENTS.md, PROJECT_CONTEXT.md, docs/adr/ADR-0002-emails-transacionais-autenticacao-cadastro.md, openspec/changes/transactional-emails-auth-flows/proposal.md, design.md, tasks.md, slices/slice-001-password-reset.md and slices/slice-003-registration-email.md.
Implement ONLY Slice 003.
Use vertical slicing and TDD: first add failing tests for URL selection by roles, invitation email content/link, admin user create auto-send and SMTP failure handling, then implement minimal code.
Create a small accounts email service using Django native password reset token machinery and django.core.mail. Add PUBLIC_APP_BASE_URL and INTERNAL_APP_BASE_URL settings if missing. Integrate with apps/admin_ui user_create after roles are saved. Send automatically on create. Keep temporary password behavior but never email the password. Use internal URL only when user has no public role; public URL when user has doctor/manager/admin, including multi-role.
Do not implement re-send, first-login-required, email_verified_at, async queue or operational case emails.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/transactional-emails-auth-flows/tasks.md when this slice is complete.
Create a detailed temporary markdown report with before/after snippets, commit and push.
Return REPORT_PATH=<path> and stop. Do not start Slice 004 without explicit confirmation.
```
