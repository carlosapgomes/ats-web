<!-- markdownlint-disable MD013 -->

# Tasks: Simplificar o card de procedimentos do dashboard

## Slice vertical

- [ ] Slice 001 — Entregar resumo compacto de procedimentos e retirar comparação avançada (`slices/slice-001-compact-procedure-summary.md`)

## Definition of Done do change

- [ ] Card renderiza `.procedure-summary-card` com exatamente quatro categorias case-level da dimensão ativa.
- [ ] Rótulos visíveis são `Solicitado (NIR)`, `Detectado (análise)` e `Autorizado (médico)` sem alterar chaves/URLs.
- [ ] Matriz de conversão, volume de componentes, tabela técnica e explicações associadas não aparecem no dashboard.
- [ ] Agendamentos combinados confirmados aparecem apenas quando o contador for maior que zero.
- [ ] Breakdown, volume, matriz e contador continuam preservados no motor analítico e cobertos por regressão.
- [ ] Filtro dimensional, busca, paginação, partial SSR e permissões continuam inalterados.
- [ ] Nenhum model, migration, FSM, CSS, JS ou app fora do dashboard foi alterado.
- [ ] Testes relevantes e quality gate completo passam.
- [ ] Relatório temporário contém RED/GREEN, snippets, inspeções e comparação baseline-final.
- [ ] Commit e push foram realizados.
