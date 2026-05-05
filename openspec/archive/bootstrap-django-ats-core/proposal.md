# Proposal: Bootstrap Django ATS Core

## Why

O projeto ats-web é greenfield. Precisamos criar a fundação do sistema Django
que servirá de base para todos os fluxos operacionais. Sem esta fundação, nenhum
fluxo (intake, decisão médica, agendamento) pode ser implementado.

A análise de domínio está documentada em `docs/DOMAIN_ANALYSIS.md` e a decisão
arquitetural em `docs/adr/ADR-0001-arquitetura-django-web-ssr-ats-triagem-eda.md`.

## What Changes

- Criar estrutura inicial do projeto Django com `uv` e `pyproject.toml`.
- Criar modelo `User` customizado com suporte a multi-role (M2M `Role` + `active_role` na sessão).
- Criar modelo `Case` com FSM de 17 estados via django-fsm.
- Criar modelo `CaseEvent` (auditoria append-only).
- Criar modelo `PromptTemplate` (versionado, 1 ativo por nome).
- Criar middleware de restrição de intranet (valida IP contra `INTRANET_IP_RANGE`).
- Criar login/logout com seleção de papel ativo.
- Criar troca de papel via avatar/perfil.
- Configurar PostgreSQL 17+, django-q2, pytest, ruff, mypy.
- Configurar Bootstrap 5.3 + templates base.

## Capabilities

### New Capabilities

- `user-auth-multirole`: autenticação session-based com multi-role e seleção de papel ativo.
- `case-fsm`: modelo Case com máquina de estados de 17 estados via django-fsm.
- `case-audit`: auditoria append-only via CaseEvent.
- `intranet-guard`: middleware de restrição de acesso por IP para papéis nir/scheduler.
- `prompt-management`: modelo PromptTemplate versionado.

### Modified Capabilities

(nenhum — projeto greenfield)

## Impact

- Infraestrutura: projeto Django do zero com `uv`, PostgreSQL, django-q2.
- Modelos: User, Role, Case, CaseEvent, PromptTemplate.
- Middleware: intranet guard.
- Views: login, logout, troca de papel.
- Templates: base layout com Bootstrap 5.3, header com avatar e badge de papel.
- Settings: configuração por ambiente (dev/prod), env vars.
- Testes: suite de testes inicial com pytest-django.

## Risk Assessment

**Level:** CRITICAL (HIGH/ARCH)

- Dados persistidos: +1 (novos modelos, migrações)
- Autenticação/Autorização: +1 (sistema de login, multi-role)
- Segurança: +1 (restrição de intranet, middleware)
- Rollback caro: +1 (fundação do projeto — tudo depende disso)
- **Total: 4+ pontos → CRITICAL**

ADR obrigatório: `docs/adr/ADR-0001-arquitetura-django-web-ssr-ats-triagem-eda.md` (já criado).
