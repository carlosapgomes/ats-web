# Tasks: Header responsivo com `navbar` do Bootstrap

## Slices

- [x] Slice 001 — Corrigir bug CSS do seletor `:has()` global (escopar a `.case-card`) (`slices/slice-001-scope-css-has.md`)
- [x] Slice 001b — Remediação: restaurar empilhamento mobile das fileiras de ação de página via `.btn-stack-mobile` (`slices/slice-001b-action-rows-stacking.md`)
- [x] Slice 002 — Refatorar `<header>` para `navbar navbar-expand-lg` (Opção C: hambúrguer híbrido) (`slices/slice-002-navbar-refactor.md`)
- [x] Slice 002b — Remediação: subnav full-width no navbar + ordem canônica do toggler (`slices/slice-002b-subnav-and-toggler-order.md`)
- [ ] Slice 003 — Ajustes complementares mobile (avatar iniciais <576px, área de toque 44px) (`slices/slice-003-mobile-complements.md`)

## Definition of Done

- [ ] Header renderiza em linha única no desktop (≥992px), sem regressão visual.
- [ ] Header no mobile: marca + notificação + avatar + hambúrguer em uma linha, sem overflow horizontal.
- [ ] Ações secundárias acessíveis via hambúrguer no mobile.
- [ ] Avatar mostra apenas iniciais em <576px; nome completo e papel no menu.
- [ ] Seletor `.d-flex.gap-2:has(> .btn)` não afeta mais o header (escopado).
- [ ] Alvos de toque (notificação, avatar) ≥ 44×44px no mobile.
- [ ] Sem alteração de FSM/models/migrations.
- [ ] Quality gate: ruff, ruff format, mypy, pytest.
- [ ] Teste de renderização do template base cobre autenticado/não autenticado.
- [ ] Relatório temporário + REPORT_PATH informado por slice.
- [ ] Commit + push por slice.
