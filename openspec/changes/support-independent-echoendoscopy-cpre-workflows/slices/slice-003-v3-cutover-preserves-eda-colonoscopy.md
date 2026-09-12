# Slice 003 — Cutover 3.0 preserva EDA e Colonoscopia

## Objetivo

Fazer novos jobs EDA/Colonoscopia percorrerem integralmente os serviços/prompts/schemas 3.0 antes de liberar procedimentos especializados, preservando leitura histórica e comportamento operacional atual.

## Contexto necessário

- `design.md`: D4–D5 e Migration Plan/Cutover
- `apps/pipeline/orchestrator.py`, serviços v2, `apps/pipeline/llm.py`
- `apps/llm/management/commands/seed_prompts.py`
- testes de orchestrator, serviços e prompt cutover do change combinado

## Requisitos verificáveis

- **R1:** novos jobs usam exclusivamente LLM1/LLM2 strict 3.0.
- **R2:** quatro prompts neutros ganham versões 3.0 idempotentes; nomes não mudam.
- **R3:** EDA, Colonoscopia e EDA+Colonoscopia mantêm uma chamada por estágio, reconciliação, policy e chegada a `WAIT_DOCTOR`.
- **R4:** readers/presenters continuam aceitando 1.1/2.0.
- **R5:** flags especializadas permanecem false e nenhum novo radio é exposto.
- **R6:** artefato/eventos registram versão 3.0 sem reescrever históricos.

## Escopo e blast radius

```yaml
expected_files:
  - apps/pipeline/llm1_service_v3.py
  - apps/pipeline/llm2_service_v3.py
  - apps/pipeline/orchestrator.py
  - apps/pipeline/llm.py
  - apps/llm/management/commands/seed_prompts.py
  - apps/pipeline/tests/test_pipeline_v3_cutover.py
  - apps/pipeline/tests/test_orchestrator.py
  - apps/pipeline/tests/test_llm_client.py
allowed_incidental_files:
  - apps/llm/tests/test_seed_prompts.py
file_cap: 9
out_of_scope:
  - intake especializado
  - alteração de decisão médica
  - remoção de schemas/prompts históricos
```

Escalar se o cutover exigir manter dois caminhos graváveis em produção ou alterar FSM.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivos esperados | Teste/check |
| --- | --- | --- |
| R1/R3/R6 | services v3 + `orchestrator.py` | EDA/Colon/combinado end-to-end com cliente fake |
| R2 | `seed_prompts.py` | seed duplo não duplica; quatro versões candidatas |
| R4 | adapters/presenter tests existentes | fixtures 1.1/2.0 renderizam |
| R5 | settings/templates inalterados | inspeção do diff + teste de intake atual |

## RED

- Comando: `uv run pytest apps/pipeline/tests/test_pipeline_v3_cutover.py -q`
- Falha esperada: orchestrator ainda importa/instancia serviços 2.0 e strict schema 3.0 não chega ao cliente.

## GREEN / verificação local

- `uv run pytest apps/pipeline/tests/test_pipeline_v3_cutover.py apps/pipeline/tests/test_orchestrator.py apps/pipeline/tests/test_llm_client.py -q`
- `uv run pytest apps/pipeline/tests/test_colonoscopy_pipeline.py apps/pipeline/tests/test_slice_002_pipeline.py apps/doctor/tests/test_presenter.py -q`
- `uv run ruff check apps/pipeline apps/llm/management/commands/seed_prompts.py`
- `uv run ruff format --check` nos arquivos Python alterados.

## Critérios de aceitação

- [ ] R1–R6 provados.
- [ ] Não resta import executável de service/schema 2.0 no path de novo job.
- [ ] Nenhum prompt histórico é apagado.
- [ ] Intake especializado continua indisponível.

## Handoff

Registrar comandos, versões de prompt e `REPORT_PATH=/tmp/support-independent-echoendoscopy-cpre-slice-003-report.md`. Parar antes de expor Ecoendoscopia.
