# Proposal: Corrigir semântica de encerramento administrativo no dashboard

**Change ID**: `fix-administrative-closure-dashboard-semantics`  
**Risco**: PROFISSIONAL (corrige métricas e leitura operacional do dashboard supervisor/admin)  
**Motivação**: casos encerrados administrativamente estão aparecendo como “Agendamento Confirmado” no detalhe e continuam compondo “Em Andamento” nos cards do dashboard.

## Problema

Quando supervisor/admin encerra um caso administrativamente, o serviço registra o evento `CASE_ADMINISTRATIVELY_CLOSED` e move o caso para `CLEANED`.

Hoje, duas leituras ficam ambíguas/incorretas:

1. **Detalhe do caso — card “Resultado Final”**  
   A view do dashboard trata `CLEANED` como caso terminal com resultado normal. Se o caso não cair antes em negativa médica/agendamento negado/vinda imediata, ele é renderizado como `accepted_scheduled`, e o template mostra:

   > ✓ Agendamento Confirmado

   Isso é incorreto para encerramento administrativo, pois a ação não representa sucesso clínico nem confirmação de agendamento.

2. **Cards de totalização do dashboard**  
   Casos encerrados administrativamente, especialmente sem decisão médica/agendamento, continuam caindo em `Em Andamento` pela fórmula residual. Exemplo real informado:

   | Card | Valor atual |
   |------|------------:|
   | Total Hoje | 11 |
   | Aceitos | 1 |
   | Negados | 0 |
   | Em Andamento | 10 |

   Desses 10 em andamento, 4 já foram encerrados administrativamente. A leitura operacional correta deveria separar esses 4, por exemplo:

   | Card | Valor esperado |
   |------|---------------:|
   | Total Hoje | 11 |
   | Aceitos | 1 |
   | Negados | 0 |
   | Encerrados admin. | 4 |
   | Em Andamento | 6 |

## Objetivo

Dar precedência explícita ao encerramento administrativo na UI e nas métricas do dashboard:

- No detalhe do dashboard, mostrar **Encerrado administrativamente**, não “Agendamento Confirmado”.
- Na listagem do dashboard, o badge de resultado também deve mostrar **Encerrado administrativamente**.
- Nos cards de totalização, adicionar/separar a contagem de **Encerrados admin.** e remover esses casos de **Em Andamento**, evitando que casos já baixados pareçam pendentes.

## Escopo

### Funcionalidades

1. Detectar encerramento administrativo por evento `CASE_ADMINISTRATIVELY_CLOSED`.
2. Dar prioridade a essa detecção em:
   - card “Resultado Final” no detalhe do dashboard;
   - badge/resultado dos cards/listagem do dashboard;
   - cards de totalização do dashboard.
3. Exibir termo padronizado:
   - Badge: **Encerrado administrativamente**;
   - Texto de apoio: “Caso removido das filas operacionais por intervenção administrativa. Este encerramento não representa confirmação de agendamento.”
4. Exibir, quando disponível, payload auditável no card:
   - motivo/justificativa (`reason_text`);
   - status anterior (`previous_status`).
5. Adicionar card de totalização **Encerrados admin.** e ajustar `Em Andamento` para não contar esses casos.

### Fora de escopo

- Criar novo estado FSM.
- Alterar `administratively_close_case()` ou o payload do evento, exceto se necessário para leitura defensiva.
- Alterar filas operacionais de NIR/médico/agendador.
- Alterar `SupervisorSummary` periódico.
- Alterar semântica histórica de “Total Hoje”: continuará baseada nos casos criados no dia local, como já ocorre em `_compute_summary()`.
- Criar migrations.

## Critérios de sucesso

- [ ] Caso com evento `CASE_ADMINISTRATIVELY_CLOSED` mostra “Encerrado administrativamente” no card “Resultado Final”.
- [ ] O mesmo caso não mostra “Agendamento Confirmado” no resultado final por inferência genérica de `CLEANED`.
- [ ] Badge de resultado na listagem do dashboard mostra “Encerrado administrativamente”.
- [ ] Cards de totalização exibem quantidade de encerrados administrativos do dia.
- [ ] `Em Andamento` subtrai os encerrados administrativos.
- [ ] `Aceitos`, `Negados`, `Encerrados admin.` e `Em Andamento` são categorias mutuamente exclusivas para a totalização diária.
- [ ] Testes de regressão cobrem caso administrativamente encerrado a partir de estado sem decisão e a partir de caso que poderia parecer agendamento confirmado.
- [ ] Quality gate do `AGENTS.md` executado na implementação.
