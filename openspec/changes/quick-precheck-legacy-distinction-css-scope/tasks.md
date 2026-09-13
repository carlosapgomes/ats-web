# Tasks: Distinção fronteira-3.0 vs legado-v2 no precheck + CSS no blast radius

## Slice vertical

- [x] 1.1 Slice 001 — Precheck separa fronteira 3.0 de legado v2; runbook e AGENTS.md alinhados (`slices/slice-001-precheck-legacy-distinction.md`)

## Preflight

- [x] Evidências do rollout v0.8.0/v0.8.1 registradas (desvio Opção A aprovado pelo operador; bug do badge corrigido em `f8b33b9`/v0.8.1)
- [x] Baseline do gate: 3711 passed @ `3889460` (main)

## Definition of Done

- [x] Cenário legado-only: exit 0, `status: allowed`, `old_image_return_available: false`.
- [x] Fronteira 3.0 cruzada: exit 1, `status: blocked` (comportamento preservado).
- [x] Runbook (3d/6c/§4.3) coerente com a saída nova.
- [x] AGENTS.md §8 com o anti-padrão de CSS em fatia de UI.
- [x] Gate completo verde; commit atômico.
