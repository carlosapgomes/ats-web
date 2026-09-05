# Tasks: Precedência de apresentação do card para casos híbridos

## Slice vertical

- [x] Slice 001 — Card híbrido mostra data do agendamento + docstring defasada (`slices/slice-001-hybrid-card-precedence.md`)

## Preflight

- [x] Working tree limpa em `main` @ `564ad94` (BASE_REF)
- [x] Gate global verde no fechamento do change pai (3283 passed) — sem nova baseline

## Definition of Done

- [x] Card de caso híbrido confirmado exibe data/hora do agendamento (não label do fluxo).
- [x] Casos puros (agendado/imediato) com apresentação inalterada (testes).
- [x] Docstring de `followup_list` corrigida.
- [x] Verificação focada verde (23 passed arquivo; 949 passed dashboard+cases; ruff/format/mypy exit 0).
- [x] Nota no change pai marcando os P2s fechados (Slice 002 item a; Slice 003 itens b/c).
- [x] Commit atômico; sem push sem instrução explícita.

## Registro de execução

- 1 rodada de review (reviewer contexto fresco): **OK**, nenhum finding.
