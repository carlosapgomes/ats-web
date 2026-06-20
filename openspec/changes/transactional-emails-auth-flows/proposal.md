# Proposal: Emails transacionais para autenticação e cadastro

**Change ID**: `transactional-emails-auth-flows`  
**Branch**: `feat/transactional-emails-auth-flows`  
**Fase**: segurança de conta / operação realista em produção  
**Risco**: PROFISSIONAL/CRÍTICO (toca autenticação, email externo, URLs públicas/internas e fluxos de usuário)  
**ADR**: `docs/adr/ADR-0002-emails-transacionais-autenticacao-cadastro.md`

## Problema

O sistema não possui fluxos transacionais por email para recuperação de senha, alteração assistida de credenciais ou confirmação prática de cadastro. Hoje o cadastro administrativo usa senha temporária manual, e usuários que esquecem a senha dependem de intervenção fora do sistema.

O domínio já está configurado no AWS SES e o projeto precisa testar um branch em produção antes do merge em `main`.

## Objetivo

Adicionar emails transacionais mínimos, síncronos e baseados em infraestrutura nativa do Django para:

1. permitir “esqueci minha senha” na tela de login;
2. permitir perfil do usuário com alteração de senha usando senha atual;
3. enviar automaticamente email de cadastro com link de definição/redefinição de senha quando admin cria usuário;
4. gerar links públicos ou internos conforme papéis do usuário.

## Escopo

### Funcionalidades

1. **Password reset**
   - Link “Esqueci minha senha” no login.
   - Views/tokens/forms nativos do Django sempre que possível.
   - Envio por `django.core.mail`.
   - Rate limit simples apenas no POST do reset.
   - Sem revelar se email existe.
   - Botão/ícone “mostrar senha” no login e na confirmação de nova senha.

2. **Perfil e alteração de senha**
   - Tela autenticada de perfil.
   - Alteração de senha exigindo senha atual.
   - Manter sessão atual após troca, seguindo padrão Django (`update_session_auth_hash`).
   - Botão/ícone “mostrar senha” somente na tela de troca de senha.

3. **Cadastro com email automático**
   - Ao criar usuário pela tela própria de gestão administrativa, enviar email automaticamente.
   - Manter senha temporária manual existente.
   - Email contém link de definição/redefinição de senha com token nativo do Django.
   - A conta é considerada verificada para este change quando o usuário usa token válido e redefine a senha.

4. **URLs por papel**
   - Se usuário tem qualquer papel público (`doctor`, `manager`, `admin`), usar `PUBLIC_APP_BASE_URL`.
   - Se usuário tem apenas papéis restritos (`nir`, `scheduler`), usar `INTERNAL_APP_BASE_URL`.

5. **Configuração por ambiente**
   - Dev: backend console/file aceitável.
   - Test: backend locmem.
   - Prod: SMTP SES via env vars.

## Fora de escopo

- API REST, SPA ou framework JS.
- Email para notificações operacionais de casos.
- Envio assíncrono via `django-q2`.
- Reenvio manual de convite.
- Bounce/complaint tracking do SES.
- Auditoria detalhada de entrega de email.
- Campo separado `email_verified_at`.
- Primeiro login obrigatório com flag `must_change_password`.
- Invalidar todas as sessões ao trocar senha pelo perfil.

## Decisões de produto/técnicas

- Emails são permitidos apenas para fluxos transacionais de conta, conforme ADR-0002.
- SES será usado via SMTP nativo do Django.
- O remetente padrão será `no-reply@chd.projetoshgrs.com`.
- O envio será síncrono neste change.
- A URL pública padrão é `https://chd.projetoshgrs.com`.
- A URL interna padrão é `https://10.17.175.38`.
- O link interno usa HTTPS com certificado self-signed.

## Critérios de sucesso

- Usuário consegue solicitar reset de senha sem enumeração de email.
- Email de reset é enviado via backend Django configurável.
- Token nativo permite definir nova senha e redireciona para login com mensagem de sucesso.
- Rate limit simples bloqueia excesso de POST em “esqueci minha senha”.
- Usuário autenticado consegue acessar perfil e trocar senha mantendo sessão atual.
- Criação de usuário pela gestão administrativa envia email automaticamente.
- Links de cadastro usam URL interna para usuários apenas `nir`/`scheduler`.
- Links de cadastro usam URL pública para qualquer usuário com `doctor`, `manager` ou `admin`, inclusive multi-role.
- Quality gate do AGENTS.md passa.
- Cada slice gera relatório temporário, commit rastreável e push para `origin`.
