# Proposal: Administração

**Change ID**: `admin-management`
**Fase**: 7 — Administração
**Risco**: PROFISSIONAL (CRUD de usuários e prompts com proteções, sem mudança em modelos)
**Dependências**: Fase 6 (dashboard com nav pills placeholders)

## Objetivo

Interface de administração para gerenciar usuários (CRUD + papéis) e prompts LLM
(versões + ativação), acessível por manager e admin via UI dedicada.

## Escopo

### Funcionalidades

1. **Gestão de Usuários** (`/admin-ui/users/`)
   - Lista de usuários com filtros (status, papel) e busca
   - Criar novo usuário (username, email, password, papéis)
   - Editar usuário (email, papéis)
   - Bloquear/desbloquear usuário (account_status)
   - Proteções: não auto-bloquear, não deixar sistema sem admin ativo
   - Remover usuário (soft delete: account_status="removed", is_active=False)

2. **Gestão de Prompts** (`/admin-ui/prompts/`)
   - Lista de prompts agrupados por nome, com versão ativa destacada
   - Criar nova versão de prompt (name, content)
   - Ativar/desativar versão
   - Visualizar versão (content em <pre>)
   - Histórico de versões por nome

3. **Nav pills no dashboard** — links "Prompts" e "Usuários" apontam para as novas views

4. **Auditoria** — CaseEvent registra ações admin (opcional, pode ficar para depois)

### Sem mock de referência

Não há mock em `demo-reference/admin/` para gestão de usuários/prompts.
Seguir o padrão visual do dashboard (cards, tabelas Bootstrap, filtros).

## Fora de escopo

- Resumo periódico (Fase 8)
- Notificações in-app (Fase 8)
- Prior case lookup (Fase 9)
- PWA (Fase 10)
- Django admin panel (já existe, mas a UI é separada)
