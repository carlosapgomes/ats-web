# Tasks: UX mobile da decisão médica

## Slices

- [x] Slice 001 — Clareza imediata da decisão: feedback visual, pendências em modal, botão `Confirmar decisão`, ocultar UUID (`slices/slice-001-decision-feedback-and-pending-modal.md`)
- [ ] Slice 002 — Fluxo de leitura clínica: mover formulário para o final e adicionar atalho `Ir para decisão` (`slices/slice-002-reading-order-and-decision-anchor.md`)

## Dimensionamento

Foram definidos **2 slices** para equilibrar verticalidade e baixo risco:

- Slice 001 resolve o problema vivido no mobile sem rearranjo grande de template: o médico passa a saber quando selecionou uma decisão e recebe feedback global se tentar confirmar incompleto.
- Slice 002 altera a hierarquia/ordem de leitura, depois que a interação do formulário já estiver mais robusta.

Evitar quebrar em slices horizontais por camada. Cada slice deve entregar uma melhoria perceptível end-to-end para o médico.

## Definition of Done do change

- [ ] `Aceitar`/`Negar` têm estado selecionado inequívoco, coerente com a paleta hospitalar.
- [ ] Campos condicionais continuam aparecendo apenas após decisão inicial.
- [ ] Clique em `Confirmar decisão` com pendências abre feedback global com lista do que falta.
- [ ] Clique em `Confirmar decisão` completo abre modal final de confirmação.
- [ ] UUID técnico não aparece como campo visível ao médico.
- [ ] Formulário de decisão fica depois do conteúdo clínico/operacional principal.
- [ ] Existe atalho não bloqueante `Ir para decisão`.
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
