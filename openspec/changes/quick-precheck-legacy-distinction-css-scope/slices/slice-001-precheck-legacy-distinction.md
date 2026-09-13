# Slice 001 — Precheck separa fronteira 3.0 de legado v2

## Objetivo

O gate de cutover do runbook volta a ser binário e satisfazível: `status`/exit
code do `check_specialized_procedure_downgrade` refletem apenas a fronteira do
primeiro write 3.0; dado legado v2 (sinal de Eco da era 2.0) vira indicação
informativa da exceção §4.3, nunca bloqueio de cutover. Runbook e AGENTS.md
alinhados.

## Requisitos verificáveis

- **R1:** `status`/exit 0 exigem e somente exigem zero nas classes de
  fronteira (`v3_artifact_write`, `specialized_case_procedure`,
  `pipeline_job_in_flight`).
- **R2:** classes legadas (`legacy_echo_artifact`, `specialized_case_event`
  derivadas do sinal v2) NÃO alteram `status`/exit; aparecem no campo novo
  `old_image_return_available: false` (true somente quando também zero
  legado).
- **R3:** mensagem de `CommandError` distingue "fronteira cruzada" (bloqueia)
  de "exceção de imagem antiga indisponível por dado legado" (não bloqueia;
  presente apenas no JSON quando aplicável).
- **R4:** runbook Passos 3d/6c e §4.3 descrevem a saída nova (incluindo o
  `old_image_return_available`) sem renumerar passos.
- **R5:** AGENTS.md §8 ganha o anti-padrão: fatia de UI que introduz
  vocabulário de classe CSS deve incluir o CSS no blast radius e/ou teste de
  guarda.

## Escopo e blast radius

```yaml
expected_files:
  - apps/cases/management/commands/check_specialized_procedure_downgrade.py
  - apps/cases/tests/test_specialized_procedure_downgrade_check.py
  - docs/deploy/support-independent-echoendoscopy-cpre-workflows.md
  - AGENTS.md
allowed_incidental_files: []
file_cap: 4
out_of_scope:
  - migrações, flags, UI/estilos, backfill
  - mudar códigos estáveis das classes existentes
```

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo | Teste/check |
| --- | --- | --- |
| R1–R3 | command + testes | legado-only exit 0 + campo; fronteira exit 1 |
| R4 | runbook | leitura coerente com o comando |
| R5 | AGENTS.md | bullet presente na §8 |

## RED

1. Novo teste: fixture com sinal legado v2 (zero write 3.0) espera exit 0,
   `old_image_return_available: false`; hoje falha (exit 1, status blocked).
2. `uv run pytest apps/cases/tests/test_specialized_procedure_downgrade_check.py -q`
3. RED válido: asserções do novo cenário falham; collection vazia não vale.

## GREEN / verificação local

- Módulo completo exit 0; `uv run ruff check/format` nos Python alterados;
  `uv run mypy` nos arquivos alterados.

## Critérios de aceitação

- [ ] R1–R5 provados.
- [ ] Nenhum teste existente enfraquecido (só ajuste de premissa da semântica
      nova, justificado in-line).
- [ ] Runbook continua descrevendo o desvio aprovado de 2026-09-13 como caso
      histórico (nota), não como comportamento esperado.

## Handoff

Gerar `REPORT_PATH=/tmp/quick-precheck-legacy-distinction-slice-001-report.md`.
Parar. Worker não altera `tasks.md`, não commita/pusha.
