# Proposal: Dashboard Supervisor

**Change ID**: `dashboard-supervisor`
**Fase**: 6 — Dashboard Supervisor
**Risco**: PROFISSIONAL (nova app, views, templates, queries agregadas — sem mudança em modelos)
**Dependências**: Fases 3-5 (doctor, scheduler, resultado NIR)

## Objetivo

Dashboard gerencial para managers e admins com métricas operacionais do período,
lista de todos os casos com filtros, e acesso ao detalhe de qualquer caso.

## Escopo

### Funcionalidades

1. **Dashboard** (`/dashboard/`) — métricas do dia:
   - Summary cards: Total Hoje, Aceitos, Negados, Em Andamento
   - Sub-métricas: aguardando por etapa (fila médica, agendamento, confirmação)
   - Fluxo de admissão: agendamento vs vinda imediata
   - Tempo médio: upload→decisão, decisão→agendamento, ciclo total

2. **Tabela de todos os casos** — na mesma página `/dashboard/`:
   - Colunas: Paciente, Registro, Idade, Status, Etapa, Enviado, Ações
   - Filtros: status (dropdown), data início/fim (date pickers)
   - Paginação (25 por página)
   - Botão "Ver" → redireciona para detalhe do caso (view genérica)

3. **Detalhe do caso (admin)** — acessível por manager/admin:
   - Reutilizar a view de case_detail mas sem restrição de `created_by`
   - Mostra timeline completa com todos os CaseEvents
   - Sem botão "Confirmar Recebimento" (só NIR confirma)

4. **Redirecionamento** — manager/admin → `/dashboard/` no home_view

### Mock de referência

- `demo-reference/admin/dashboard.html` — dashboard com summary cards, sub-métricas, tabela com filtros e paginação

## Fora de escopo

- CRUD de usuários (Fase 7)
- Gestão de prompts (Fase 7)
- Auditoria avançada (Fase 7)
- Notificações (Fase 8)
- PWA (Fase 10)
