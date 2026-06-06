# Proposal: Aba Decididos Hoje na fila médica

**Change ID**: `doctor-decided-today-tab`
**Fase**: ajuste de UX/operacional médico pós-Fase 3
**Risco**: PROFISSIONAL (altera navegação e consultas da fila médica; adiciona detalhe read-only para médico)
**Dependências**: `doctor-queue`, `nir-result-closure`, `fix-dashboard-case-detail-navigation-pdf`

## Problema

Na tela padrão do médico (`/doctor/`), os pills de navegação mostram:

- `Pendentes`
- `Decididos Hoje`
- `Histórico`

Porém:

1. `Decididos Hoje` é apenas texto visual (`<span>`), não uma aba/rota funcional.
2. A seção de decididos hoje até existe no partial da fila, mas aparece abaixo dos pendentes e depende de uma query incompatível com o fluxo real:
   - a query filtra apenas `DOCTOR_ACCEPTED` e `DOCTOR_DENIED`;
   - após a decisão, o caso normalmente avança para `WAIT_APPT`, `WAIT_R1_CLEANUP_THUMBS`, `CLEANED`, `APPT_CONFIRMED` ou `APPT_DENIED`.
3. `Histórico` é placeholder herdado do mock, sem rota, view, comportamento ou escopo formal anterior.
4. O médico não tem um caminho read-only claro para revisar detalhes completos de um caso que ele decidiu hoje, como supervisor/admin conseguem pelo dashboard.

## Objetivo

Implementar corretamente a aba `Decididos Hoje` na fila médica, remover a aba placeholder `Histórico`, e permitir que o médico abra os detalhes completos read-only dos casos decididos hoje.

## Escopo

### Funcionalidades

1. **Navegação funcional na fila médica**
   - `Pendentes` permanece como aba padrão.
   - `Decididos Hoje` vira aba/link funcional.
   - `Histórico` é removido da navegação médica.

2. **Lista correta de decididos hoje**
   - Listar casos decididos pelo médico logado no dia local atual.
   - Usar fonte imutável da decisão (`doctor`, `doctor_decision`, `doctor_decided_at`) em vez do status FSM transitório.
   - Incluir casos mesmo que já tenham avançado para scheduler, confirmação, cleanup ou cleaned.

3. **Detalhe read-only para médico**
   - A lista de `Decididos Hoje` deve oferecer ação `Ver detalhes`.
   - O detalhe deve usar o mesmo padrão visual/funcional que supervisor/admin veem no dashboard:
     - stepper;
     - resultado final quando aplicável;
     - timeline;
     - PDF original;
     - sem botões operacionais de NIR/scheduler/admin.
   - O médico só pode abrir detalhes de casos que ele próprio decidiu.

4. **Polling/partial coerente**
   - O auto-refresh da fila deve respeitar a aba ativa.
   - A aba de decididos hoje não deve misturar pendentes e decididos na mesma visualização.

## Fora de escopo

- Histórico multi-dia ou busca por período para médicos.
- Filtros avançados, paginação ou exportação da lista médica.
- Permitir que médico veja casos decididos por outros médicos.
- Alterar dashboard de supervisor/admin.
- Alterar fluxo de decisão médica ou transições FSM.

## Critérios de sucesso

- `/doctor/` mostra somente pills `Pendentes` e `Decididos Hoje`.
- `Histórico` não aparece mais na navegação médica.
- Clicar em `Decididos Hoje` mostra somente casos decididos hoje pelo médico logado.
- Casos aceitos que já avançaram para `WAIT_APPT`, `APPT_CONFIRMED`, `WAIT_R1_CLEANUP_THUMBS` ou `CLEANED` continuam aparecendo em `Decididos Hoje`.
- Casos negados que já avançaram para cleanup/cleaned continuam aparecendo em `Decididos Hoje`.
- Cada item decidido hoje permite abrir detalhe read-only.
- Médico não acessa detalhe de caso decidido por outro médico.
- Quality gate do AGENTS.md passa.
