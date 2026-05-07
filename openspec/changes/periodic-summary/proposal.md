# Proposal: Resumo Periódico

**Change ID**: `periodic-summary`
**Fase**: 8 — Resumo Periódico
**Risco**: PROFISSIONAL (novo modelo, cron job, queries agregadas, template — sem mudança em modelos existentes)
**Dependências**: Fase 6 (dashboard supervisor)

## Objetivo

Geração automática de resumos operacionais periódicos, persistidos no banco,
com exibição no dashboard do supervisor. Substitui o "Room-4 summary" do legado
(Matrix → banco de dados + template SSR).

## Escopo

### Funcionalidades

1. **Modelo `SupervisorSummary`** — persiste métricas agregadas por janela
   - window_start, window_end (UTC)
   - Métricas: pacientes recebidos, processados, avaliados, aceitos agendamento, vinda imediata, recusados, em andamento
   - Status: pending → sent (idempotência)
   - Timestamps: created_at, sent_at

2. **Cron job django-q2** — executa a cada hora (configurável)
   - Resolve janela anterior baseada em cutoffs (ex: 07h, 13h, 19h, 01h)
   - Agrega métricas dos cases na janela
   - Persiste resumo (idempotente: não cria duplicata para mesma janela)
   - Marca como "sent" após persistir

3. **Função de agregação** — queries sobre Case/CaseEvent na janela
   - Pacientes recebidos: cases criados na janela
   - Processados: cases com `structured_data` preenchido na janela
   - Avaliados: cases com decisão médica na janela
   - Aceitos agendamento: `doctor_decision=accept` + `admission_flow=scheduled`
   - Vinda imediata: `doctor_decision=accept` + `admission_flow=immediate`
   - Recusados: `doctor_decision=deny` ou `APPT_DENIED`
   - Em andamento: cases criados na janela ainda não finalizados

4. **Exibição no dashboard** — card de último resumo + histórico
   - Card no dashboard mostrando último resumo gerado
   - Página dedicada com histórico de resumos (paginação)

### Referência legada

- `supervisor_summary_scheduler_service.py` — resolve janela via cutoffs
- `post_room4_summary_service.py` — agrega métricas e renderiza
- `SupervisorSummaryMetrics` — dataclass com 11 contadores

## Fora de escopo

- Notificações in-app (Fase 8.5 — futuro)
- Prior case lookup (Fase 9)
- PWA (Fase 10)
- LLM para gerar resumo (métricas numéricas suficientes)
