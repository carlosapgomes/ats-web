# ADR-0002: Emails transacionais para autenticação e cadastro

## Status

Accepted

## Contexto

O projeto ATS Web foi definido originalmente com notificações apenas in-app, sem email/SMS/push. Essa restrição continua adequada para notificações operacionais do fluxo de triagem, mas novos requisitos de segurança e operação exigem emails transacionais:

- recuperação de senha a partir da tela de login;
- confirmação de cadastro com link de definição/redefinição de senha;
- suporte a usuários que acessam por URL pública e usuários restritos à intranet hospitalar;
- uso do domínio já configurado no AWS SES.

O sistema é um monolito Django SSR. A autenticação já usa `django.contrib.auth`, usuários customizados em `apps/accounts`, papéis multi-role e restrição de intranet para `nir`/`scheduler`.

## Decisao

Permitir **emails transacionais estritamente relacionados a autenticação, segurança de conta e cadastro**, mantendo notificações operacionais do ATS exclusivamente in-app.

A implementação deve:

- reutilizar infraestrutura nativa do Django sempre que possível:
  - `django.core.mail`;
  - views/forms/tokens nativos de password reset/change quando aplicável;
  - backend SMTP configurável;
- enviar emails de forma síncrona neste primeiro change;
- usar AWS SES via SMTP, sem dependências extras como `django-anymail` neste momento;
- configurar remetente, SMTP, timeout e URLs por variáveis de ambiente;
- usar `PUBLIC_APP_BASE_URL` para usuários com qualquer papel público (`doctor`, `manager`, `admin`);
- usar `INTERNAL_APP_BASE_URL` para usuários que possuem apenas papéis restritos à intranet (`nir`, `scheduler`);
- manter usuários criados com senha temporária manual, enviando link para redefinição/validação de senha;
- considerar a conta verificada para este change quando o usuário usa token válido e redefine a senha, sem criar campo separado `email_verified_at`.

Variáveis de ambiente previstas:

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

## Alternativas Consideradas

1. **Manter proibição total de email**
   - Vantagens: menor superfície de ataque, nenhuma dependência operacional de SMTP/SES.
   - Desvantagens: não atende recuperação de senha nem ativação segura de cadastro.
   - Por que não escolhida: os fluxos de conta exigem canal transacional externo ao app.

2. **Usar somente notificações in-app para cadastro/senha**
   - Vantagens: preserva arquitetura anterior.
   - Desvantagens: usuário sem acesso não consegue recuperar senha; cadastro inicial depende de canal manual inseguro.
   - Por que não escolhida: recuperação de acesso precisa funcionar antes do login.

3. **Usar biblioteca especializada/API SES (`django-anymail` ou boto3)**
   - Vantagens: melhor suporte a status de entrega, bounce, complaint e metadados.
   - Desvantagens: adiciona dependência e complexidade antes de haver necessidade comprovada.
   - Por que não escolhida: SMTP nativo do Django atende o MVP transacional com menor escopo.

4. **Criar confirmação de email própria com `email_verified_at`**
   - Vantagens: separa verificação de email da redefinição de senha.
   - Desvantagens: exige novo estado/campo, tokens próprios e fluxos adicionais.
   - Por que não escolhida: para o primeiro change, redefinição com token nativo é suficiente e mais simples.

## Consequencias

- Positivas:
  - recuperação de senha passa a usar fluxo familiar e seguro do Django;
  - cadastro ganha validação prática de acesso ao email;
  - menor customização por reaproveitar componentes nativos;
  - SES fica configurável por ambiente sem acoplar código à AWS.

- Negativas/Trade-offs:
  - o sistema passa a depender de SMTP/SES para alguns fluxos de conta;
  - envio síncrono pode aumentar latência em requests de reset/cadastro;
  - links internos com certificado self-signed podem gerar aviso no navegador;
  - o texto anterior “sem email” em documentação precisa ser reinterpretado como “sem notificações operacionais por email”.

- Riscos e Mitigações:
  - abuso do formulário “esqueci minha senha”: aplicar rate limit simples no POST;
  - enumeração de usuários: manter comportamento nativo de não revelar se email existe;
  - link errado para usuários intranet-only: centralizar regra de base URL e cobrir com testes;
  - falhas SES/SMTP em produção: configurar via env vars e testar em branch antes do merge;
  - escopo crescer para gestão avançada de emails: manter bounce/retry/auditoria detalhada fora deste change inicial.
