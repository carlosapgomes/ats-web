# Tasks: Ênfase de ingestão cáustica/corrosiva no relatório médico

## Slices verticais

- [x] Slice 001 — Detector documental e renderização no relatório médico (`slices/slice-001-detector-e-relatorio-medico.md`)
- [x] Slice 002 — Reforço do prompt canônico LLM1 para resumo narrativo (`slices/slice-002-prompt-llm1-caustico.md`)

## Definition of Done do change

- [x] Texto extraído com ingestão cáustica/corrosiva dispara alerta no relatório técnico médico.
- [x] Alerta mostra tempo desde ingestão quando expressão temporal próxima estiver disponível.
- [x] Alerta mostra `tempo desde a ingestão: não informado no relatório` quando evento é detectado sem tempo claro.
- [x] Casos sem ingestão cáustica/corrosiva não mostram alerta.
- [x] Negação explícita no mesmo contexto (`nega ingestão`, `sem ingestão`, `não ingeriu`) não dispara alerta.
- [x] Alerta é apenas documental e não altera decisão sugerida, suporte, policy, FSM, fila, status ou notificações.
- [x] Prompt LLM1 orienta mencionar evento e tempo no resumo narrativo quando disponível.
- [x] Não há alteração de schema LLM1/LLM2.
- [x] Não há migration nem alteração de dados persistidos.
- [x] Testes relevantes adicionados antes da implementação passar.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatório dos slices gerados em markdown temporário.
- [x] Commit e push realizados após cada slice implementado.
