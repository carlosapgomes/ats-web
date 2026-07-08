# Tasks: Lista estruturada de comorbidades no relatório médico

## Slice vertical

- [x] Slice 001 — Extração estruturada LLM1 + exibição de comorbidades no relatório médico (`slices/slice-001-structured-comorbidities.md`)

## Definition of Done do change

- [ ] `Llm1Response` aceita `preop_screening.comorbidities_described` como lista de comorbidades descritas.
- [ ] Campo novo é backward-compatible (`default_factory=list`) e não exige migration.
- [ ] Prompt LLM1 default e prompt renderizado final orientam extração de comorbidades explícitas.
- [ ] Prompt proíbe inferir comorbidades apenas por medicação/exame/fator de risco sem diagnóstico descrito.
- [ ] Tela médica exibe item exclusivo `Comorbidades descritas` no relatório automático.
- [ ] Comorbidades são exibidas separadas por vírgula, deduplicadas e em ordem.
- [ ] Lista vazia em caso novo mostra `sem comorbidades descritas no relatório`.
- [ ] Campo ausente em caso antigo mostra `extração de comorbidades não disponível neste caso`.
- [ ] Sem alteração de FSM, migrations, models, LLM2, policy, reconciliação, ASA/suporte ou decisão automática.
- [ ] Testes relevantes adicionados/ajustados antes da implementação passar.
- [ ] Quality gate do AGENTS.md executado:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Relatório detalhado do slice gerado em markdown temporário com snippets antes/depois.
- [ ] `REPORT_PATH=<temp-markdown-path>` informado para revisão por terceiro LLM.
- [ ] Commit e push realizados após implementação.

## Observações para implementadores

- Implementar somente o próximo slice incompleto.
- Usar slice vertical end-to-end; não separar schema/prompt de UI.
- Seguir TDD: RED → GREEN → REFACTOR.
- Aplicar clean code, DRY e YAGNI.
- Manter arquivos tocados no mínimo necessário; justificar qualquer arquivo adicional no relatório.
- Não iniciar novo change/slice sem confirmação explícita do usuário.
