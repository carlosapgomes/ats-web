# Tasks: UX mobile da decisão médica

## Slices

- [x] Slice 001 — Clareza imediata da decisão: feedback visual, pendências em modal, botão `Confirmar decisão`, ocultar UUID (`slices/slice-001-decision-feedback-and-pending-modal.md`)
- [x] Slice 002 — Fluxo de leitura clínica: mover formulário para o final e adicionar atalho `Ir para decisão` (`slices/slice-002-reading-order-and-decision-anchor.md`)
- [x] Slice 003 — Refinos finais de UX mobile: ajuda contextual compacta, ocultar radio visual e reforçar estado selecionado dos cards de decisão (`slices/slice-003-compact-help-texts.md`)
- [x] Slice 004 — Follow-up enxuto: compactar texto de ajuda do campo `Orientações para agendamento/execução` (`slices/slice-004-compact-orientation-help-text.md`)

## Dimensionamento

O change começou com 2 slices e recebeu follow-ups após validação de uso no mobile:

- Slice 001 resolve o problema vivido no mobile sem rearranjo grande de template: o médico passa a saber quando selecionou uma decisão e recebe feedback global se tentar confirmar incompleto.
- Slice 002 altera a hierarquia/ordem de leitura, depois que a interação do formulário já estiver mais robusta.
- Slice 003 reduz ruído vertical remanescente em textos de ajuda, mantém orientações disponíveis por click/tap e reforça o feedback visual dos cards de decisão sem mostrar o radio button como protagonista.
- Slice 004 compacta o texto de ajuda remanescente do campo de orientações do aceite, mantendo exemplos sob `Detalhes`.

Evitar quebrar em slices horizontais por camada. Cada slice deve entregar uma melhoria perceptível end-to-end para o médico.

## Definition of Done do change

- [ ] `Aceitar`/`Negar` têm estado selecionado inequívoco, coerente com a paleta hospitalar.
- [ ] Campos condicionais continuam aparecendo apenas após decisão inicial.
- [ ] Clique em `Confirmar decisão` com pendências abre feedback global com lista do que falta.
- [ ] Clique em `Confirmar decisão` completo abre modal final de confirmação.
- [ ] UUID técnico não aparece como campo visível ao médico.
- [ ] Formulário de decisão fica depois do conteúdo clínico/operacional principal.
- [ ] Existe atalho não bloqueante `Ir para decisão`.
- [ ] Ajuda da comunicação operacional está disponível de forma compacta/colapsável, sem alerta permanente pesado.
- [ ] Orientação “Faltam informações?” fica abaixo dos botões do formulário, com detalhes sob click/tap.
- [ ] Radio buttons de `Aceitar`/`Negar` continuam no HTML, mas não aparecem visualmente como elemento protagonista.
- [ ] Cards `Aceitar`/`Negar` selecionados têm feedback forte: borda mais grossa, fundo sutil, título colorido e badge/ícone `Selecionado`.
- [ ] Texto de ajuda do campo `Orientações para agendamento/execução` é curto por padrão, com exemplos em `Detalhes` por click/tap.
- [ ] CSS customizado mínimo e escopado; Bootstrap continua sendo a base.
- [ ] Sem models/migrations/FSM.
- [ ] Testes relevantes adicionados/atualizados.
- [ ] Quality gate completo passa: `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest`.
- [ ] Cada slice gera relatório temporário em markdown com snippets antes/depois, evidências e `REPORT_PATH`.
- [ ] Cada slice tem commit e push rastreáveis.

## Branch de implementação

Recomendação: implementar este change em um branch separado antes de iniciar o Slice 001, por exemplo:

```bash
git checkout -b change/doctor-decision-mobile-ux
```

Se o branch já existir remotamente, usar o branch dedicado equivalente e manter commits/pushes dos slices nele.

## Stop rule

Após concluir cada slice:

1. atualizar este `tasks.md` marcando apenas o slice concluído;
2. salvar relatório detalhado em `tmp/` ou `.reports/`;
3. responder com `REPORT_PATH=<caminho-do-relatorio>`;
4. parar e pedir confirmação explícita antes de iniciar o próximo slice.
