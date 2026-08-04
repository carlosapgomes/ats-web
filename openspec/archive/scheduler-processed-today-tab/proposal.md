# Proposal: Aba Processados Hoje na fila do agendador

**Change ID**: `scheduler-processed-today-tab`
**Fase**: ajuste de UX/operacional agendador pós-Fase 4
**Risco**: PROFISSIONAL (altera navegação e consultas da fila do agendador; adiciona detalhe read-only para agendador)
**Dependências**: `scheduler-queue`, `nir-result-closure`, `fix-dashboard-case-detail-navigation-pdf`

## Problema

Na tela principal do agendador (`/scheduler/`), a navegação mostra:

- `Pendentes`
- `Confirmados Hoje`
- `Histórico`

Porém:

1. `Confirmados Hoje` é apenas texto visual (`<span>`), não uma aba funcional.
2. O nome `Confirmados Hoje` é semanticamente incorreto: o agendador pode confirmar ou recusar. A lista desejada é de casos **processados hoje**, independentemente do resultado.
3. `Histórico` é placeholder herdado do mock, sem rota, view, comportamento ou escopo formal implementado.
4. A seção atual de confirmados hoje fica abaixo da fila e usa uma tabela mínima, sem caminho claro para ver detalhes completos read-only do caso.
5. O agendador deve conseguir rever os detalhes dos casos que processou hoje, sem alterar nada, no mesmo padrão visual usado por supervisor/admin.

## Objetivo

Corrigir a tela principal do agendador para:

- remover a aba placeholder `Histórico`;
- substituir `Confirmados Hoje` por uma aba funcional `Processados Hoje`;
- listar cards de pacientes processados hoje pelo agendador logado, incluindo confirmados e recusados;
- permitir abrir detalhe read-only de cada caso processado.

## Escopo

### Funcionalidades

1. **Navegação funcional**
   - `Pendentes` permanece como aba padrão.
   - `Processados Hoje` vira aba/link funcional.
   - `Histórico` é removido.

2. **Lista correta de processados hoje**
   - Listar casos processados pelo agendador logado no dia local atual.
   - Incluir tanto `appointment_status="confirmed"` quanto `appointment_status="denied"`.
   - Usar campos imutáveis do processamento (`scheduler`, `appointment_status`, `appointment_decided_at`) em vez de depender só do status FSM.

3. **Cards de processados hoje**
   - Exibir cards, não tabela mínima.
   - Mostrar paciente, registro, decisão do agendador, data/hora agendada quando houver, motivo quando recusado, suporte/fluxo e médico responsável quando disponíveis.

4. **Detalhe read-only para agendador**
   - Cada card deve ter ação `Ver detalhes`.
   - O detalhe deve seguir o padrão de supervisor/admin:
     - stepper;
     - resultado final quando aplicável;
     - timeline;
     - PDF original;
     - sem botões de alteração.
   - O agendador só pode abrir detalhes de casos que ele próprio processou.

5. **Polling/partial coerente**
   - O auto-refresh deve respeitar a aba ativa.

## Fora de escopo

- Histórico multi-dia ou busca por período para agendador.
- Paginação, filtros avançados ou exportação.
- Permitir que um agendador veja casos processados por outro agendador.
- Alterar o fluxo de confirmação/recusa ou transições FSM.
- Alterar dashboard de supervisor/admin.

## Critérios de sucesso

- `/scheduler/` mostra apenas `Pendentes` e `Processados Hoje`.
- `Histórico` não aparece mais na navegação do agendador.
- Clicar em `Processados Hoje` mostra somente casos processados hoje pelo agendador logado.
- Casos confirmados e recusados aparecem na mesma lista.
- A lista usa cards com botão `Ver detalhes`.
- O detalhe read-only é acessível para caso processado pelo agendador logado.
- O detalhe de caso processado por outro agendador retorna 404.
- O polling HTMX mantém a aba ativa.
- Quality gate do AGENTS.md passa.
