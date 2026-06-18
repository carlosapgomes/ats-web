# Design: Emails transacionais para autenticação e cadastro

## Estado atual

- Autenticação customizada fica em `apps/accounts` com `login_view`, `logout_view`, `switch_role` e `home_redirect`.
- Usuário customizado (`apps/accounts/models.py::User`) herda `AbstractUser` e possui M2M `roles`.
- Papéis públicos: `doctor`, `manager`, `admin`.
- Papéis restritos à intranet: `nir`, `scheduler`.
- Middleware de intranet permite bypass quando usuário possui qualquer papel não restrito.
- Gestão de usuários fica em `apps/admin_ui`; criação usa `UserCreateForm` e senha temporária manual.
- Templates são SSR Django + Bootstrap 5.3 + Vanilla JS.
- A documentação anterior proíbe emails; ADR-0002 limita a exceção a emails transacionais de conta.

## Decisões

### D1. Reutilizar auth nativo do Django

Usar as views/forms/tokens nativos para reset e troca de senha sempre que possível:

- `PasswordResetView`
- `PasswordResetDoneView`
- `PasswordResetConfirmView`
- `PasswordResetCompleteView`
- `PasswordChangeForm`/`PasswordChangeView`
- `PasswordResetTokenGenerator`
- `django.core.mail`

Se for necessário criar subclasses/wrappers, devem ser mínimos e motivados por template, rate limit ou base URL customizada.

### D2. Envio SMTP síncrono

O primeiro change usa envio síncrono com backend Django configurável. Não usar `django-q2` para email neste momento.

### D3. Configuração por env vars

Variáveis previstas:

```env
PUBLIC_APP_BASE_URL=https://chd.projetoshgrs.com
INTERNAL_APP_BASE_URL=https://10.17.175.38
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=email-smtp.us-east-2.amazonaws.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
DEFAULT_FROM_EMAIL=no-reply@chd.projetoshgrs.com
PASSWORD_RESET_TIMEOUT=86400
```

Ohio/SES é exemplo (`us-east-2`), mas `EMAIL_HOST` deve ser totalmente configurável.

### D4. Rate limit simples para password reset

Aplicar apenas no POST de “esqueci minha senha”. Sem dependência nova.

Opção preferida: cache Django com chaves por IP e por email normalizado. Exemplo conceitual:

```text
password_reset:ip:<ip>
password_reset:email:<normalized-email>
```

Se limite exceder, responder com a mesma página de sucesso genérica quando possível, para evitar enumeração e reduzir spam.

### D5. Mostrar senha com Vanilla JS pequeno e reutilizável

Implementar botão/ícone de olho somente onde escopado:

- Slice 1: login + reset confirm.
- Slice 2: password change.

Não sair procurando todos os forms do sistema.

### D6. Perfil mantém sessão atual

No fluxo de troca de senha autenticado, seguir padrão Django: após senha válida, chamar `update_session_auth_hash` ou usar `PasswordChangeView` corretamente para manter a sessão atual.

Não invalidar manualmente outras sessões neste change.

### D7. Cadastro usa token nativo de reset

Ao criar usuário pela tela administrativa, manter senha temporária manual e enviar email automático com link para redefinir/validar senha.

A conta é considerada verificada para este change quando o usuário usa token válido e redefine a senha. Não criar `email_verified_at`.

### D8. Seleção centralizada de base URL

Criar helper testável, por exemplo:

```python
PUBLIC_ROLE_NAMES = {"doctor", "manager", "admin"}

def get_account_action_base_url(user: User) -> str:
    role_names = set(user.roles.values_list("name", flat=True))
    if role_names & PUBLIC_ROLE_NAMES:
        return settings.PUBLIC_APP_BASE_URL
    return settings.INTERNAL_APP_BASE_URL
```

Regra:

```text
Tem doctor, manager ou admin? -> URL pública
Só tem nir/scheduler?         -> URL interna
```

Usuário sem papéis é edge case administrativo; preferir URL pública ou documentar escolha no relatório. Sugestão: URL pública por segurança operacional, salvo decisão contrária em testes.

### D9. Integração no create administrativo

Integrar no fluxo real `apps/admin_ui.views.user_create` após `form.save()` e `roles` persistidos, para que a seleção de URL observe os papéis finais.

Se o envio falhar, o comportamento deve ser explícito e testado. Sugestão inicial: exibir `messages.warning/error` para o admin, manter usuário criado e registrar log; não rollbackar criação por falha SMTP, pois senha temporária manual ainda existe.

## Arquivos previstos por slice

### Slice 001 — password reset

- `config/settings/base.py`
- `config/settings/dev.py`
- `config/settings/test.py`
- `config/settings/prod.py`
- `apps/accounts/urls.py`
- `apps/accounts/views.py` ou novo módulo pequeno de auth views/forms se necessário
- `templates/accounts/login.html`
- templates `templates/accounts/password_reset*.html`
- `apps/accounts/tests/test_password_reset.py` ou equivalente

Justificar no relatório se tocar mais arquivos.

### Slice 002 — perfil e alteração de senha

- `apps/accounts/urls.py`
- `apps/accounts/views.py`
- `templates/accounts/profile.html`
- `templates/accounts/password_change*.html` se necessário
- `templates/base.html`
- `apps/accounts/tests/test_profile_password_change.py`

### Slice 003 — email automático de cadastro

- `apps/accounts/services.py` ou módulo equivalente coeso
- `apps/admin_ui/views.py`
- templates de email em `templates/accounts/email/` ou padrão Django equivalente
- `apps/admin_ui/tests/test_users_crud.py` ou novo arquivo focado
- `apps/accounts/tests/test_email_services.py`

## Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| Mudança contradiz “sem email” | ADR-0002 limita exceção a conta/autenticação; notificações operacionais seguem in-app |
| Enumeração de usuários | Usar comportamento nativo genérico do Django |
| Spam no reset | Rate limit simples no POST |
| Link interno/público errado | Helper centralizado com matriz de testes por papel |
| SES indisponível/lento | Envio síncrono aceito no MVP; falha no cadastro não deve apagar usuário |
| Certificado interno self-signed | Documentar risco; uso restrito à intranet |
| Slice grande demais | Implementar em slices verticais independentes e parar após cada um |

## Fluxo de branch/deploy

1. Criar branch local `feat/transactional-emails-auth-flows`.
2. Implementar um slice por vez.
3. Rodar gates.
4. Gerar relatório temporário do slice.
5. Commit rastreável e push para `origin`.
6. Teste realista em produção via pull do branch.
7. Ajustes se necessário.
8. Merge futuro em `main`.
