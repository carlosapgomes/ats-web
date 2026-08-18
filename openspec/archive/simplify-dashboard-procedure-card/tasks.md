<!-- markdownlint-disable MD013 -->

# Tasks: Simplificar o card de procedimentos do dashboard

## Slice vertical

- [x] Slice 001 — Entregar resumo compacto de procedimentos e retirar comparação avançada (`slices/slice-001-compact-procedure-summary.md`)

## Definition of Done do change

- [x] Card renderiza `.procedure-summary-card` com exatamente quatro categorias case-level da dimensão ativa.
- [x] Rótulos visíveis são `Solicitado (NIR)`, `Detectado (análise)` e `Autorizado (médico)` sem alterar chaves/URLs.
- [x] Matriz de conversão, volume de componentes, tabela técnica e explicações associadas não aparecem no dashboard.
- [x] Agendamentos combinados confirmados aparecem apenas quando o contador for maior que zero.
- [x] Breakdown, volume, matriz e contador continuam preservados no motor analítico e cobertos por regressão.
- [x] Filtro dimensional, busca, paginação, partial SSR e permissões continuam inalterados.
- [x] Nenhum model, migration, FSM, CSS, JS ou app fora do dashboard foi alterado.
- [x] Testes relevantes e quality gate completo passam.
- [x] Relatório temporário contém RED/GREEN, snippets, inspeções e comparação baseline-final.
- [x] Commit e push foram realizados.
