# Proposal: Resultado Final NIR + Fechamento

**Change ID**: `nir-result-closure`
**Fase**: 5 — Resultado Final NIR + Fechamento
**Risco**: PROFISSIONAL (modifica views e template existentes do intake, adiciona resultado final + cleanup automático)
**Dependências**: Fase 3 (doctor queue) + Fase 4 (scheduler queue)

## Objetivo

O NIR visualiza o resultado final do caso (agendamento confirmado, negado, recusa médica,
falha) na tela de detalhe, e confirma o recebimento para concluir e limpar o caso.

## Escopo

### Funcionalidades

1. **Resultado final por tipo** — seção no `case_detail` que mostra dados específicos:
   - **Aceito (agendado)**: data/hora, suporte, fluxo agendamento
   - **Aceito (imediato)**: médico, suporte, "Vinda Imediata"
   - **Negado pelo agendador**: motivo
   - **Negado pelo médico**: motivo
   - **Falha no processamento**: causa

2. **Auto-transição para WAIT_R1_CLEANUP_THUMBS** — quando o resultado final fica disponível
   (APPT_CONFIRMED, APPT_DENIED, DOCTOR_DENIED, FAILED), o sistema avança automaticamente
   para `WAIT_R1_CLEANUP_THUMBS` via `final_reply_posted()`. Isso sinaliza ao NIR que há
   resultado para ver.

3. **Botão "Confirmar Recebimento"** — já existe no `case_detail` template e `confirm_receipt`
   view. Verificar que funciona para todos os cenários.

4. **Timeline enriquecida** — eventos do doctor e scheduler já aparecem na timeline.
   Adicionar labels para os novos eventos.

5. **Top Info enriquecido** — nome do paciente extraído de `structured_data` (alinhado ao mock).

### Mock de referência

- `demo-reference/nir/case-detail.html` — topo com status badge "AGENDAMENTO CONFIRMADO" +
  data agendada, timeline com eventos doctor/scheduler, botão confirmar

## Fora de escopo

- Dashboard (Fase 6)
- Notificações in-app (Fase 8)
- Prior case lookup (Fase 9)
- PWA (Fase 10)
