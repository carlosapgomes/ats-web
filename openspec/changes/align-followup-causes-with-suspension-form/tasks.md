# Tasks: Alinhar causas do pós-procedimento à ficha de suspensão

## 0. Precondições do change

- [x] 0.1 Classificar como CRÍTICO / HIGH-ARCH, registrar `design.md`, rollback e ADR-0009 aceita com os quatro mapeamentos confirmados pelo owner.
- [x] 0.2 Preflight concluído na branch `feature/align-followup-causes-with-suspension-form`, `BASE_REF=94ab7ac`: working tree continha somente os artefatos aprovados do change; baseline global verde (`ruff check`, `ruff format --check`, `mypy`, `pytest`: 3725 passed) usando o banco de teste ativo em `POSTGRES_TEST_HOST_PORT=55433`.

## 1. Registro oficial compacto

- [x] 1.1 Implementar o Slice 001 (`slices/slice-001-official-causes-compact-form.md`) em RED → GREEN → REFACTOR; catálogo oficial, rejeição legada, migration metadata-only, select compacto e eventos verificados; review aceito na rodada 2 após correção P1 do POST residual de submotivo.
- [x] 1.2 `apps/dashboard/tests/test_followup_history.py` verde com fixtures legadas diretas (74 passed); teste de migration comprovou `0019 → 0020 → 0019 → 0020` sem alteração de rows/eventos.
- [x] 1.3 `tasks.md` atualizado e relatório gerado em `/tmp/align-followup-causes-slice-001-report.md`; commit atômico criado sem push, conforme instrução atual do owner. A autorização desta execução sequencial substitui a parada intermediária antes do Slice 002.

## 2. Compatibilidade histórica e documentação

- [x] 2.1 Implementar o Slice 002 (`slices/slice-002-legacy-projection-history.md`) em RED → GREEN → REFACTOR; quatro mapeamentos, fallback `legacy_unmapped`, superfícies, imutabilidade, preflight e manual verificados. Review 3 excepcional autorizado pelo owner aceitou o fix final D5/R7 sem P0/P1/P2.
- [x] 2.2 `tasks.md` atualizado e relatório gerado em `/tmp/align-followup-causes-slice-002-report.md`; commit atômico criado sem push, conforme instrução atual do owner. A autorização da execução sequencial e do único gate final substitui a parada intermediária antes desse gate.

## 3. Gate final e entrega

- [x] 3.1 Quality gate global concluído. A primeira tentativa fail-fast encontrou um erro mypy test-only (`field.max_length: int | None`); após correção mínima, a repetição completa passou: Ruff check/format, mypy (292 source files) e pytest (3835 passed).
- [x] 3.2 `openspec validate --strict`, `git diff --check`, `makemigrations --check --dry-run`, `showmigrations cases --plan`, teste de migration ida/volta (8 passed) e inspeção final de escopo/migration passaram.
- [ ] 3.3 Atualizar specs canônicas e `PROJECT_CONTEXT.md` no arquivamento conforme workflow, preservando a supersessão parcial ADR-0007→ADR-0009. **Adiado:** archive não autorizado nesta execução.
- [x] 3.4 Relatório final gerado em `/tmp/align-followup-causes-final-report.md`; commit de fechamento criado sem push e execução parada para aprovação humana antes de deploy/archive.
- [ ] 3.5 Antes do deploy e sem writes concorrentes, executar o preflight de legados não mapeáveis (zero obrigatório) e ensaiar em staging `0019 → 0020 → 0019 → 0020`; qualquer divergência bloqueia rollout.
- [ ] 3.6 Após aprovação e deploy, executar smoke de uma causa oficial, **Outras causas**, rejeição legada, fallback técnico sintético e dos quatro mapeamentos no Histórico/CSV; preferir forward-fix se já houver novas gravações.

## Regra de execução

- Implementar exatamente um slice por vez e parar para confirmação explícita antes do próximo.
- Worker não altera `tasks.md`, não faz commit/push e não amplia escopo silenciosamente.
- Parent/orquestrador marca checkboxes somente após evidência e review aceito.
- Nenhuma row `ProcedureFollowUp`/`CaseFollowUp` ou `CaseEvent` histórica pode ser reescrita.
- Necessidade de remover coluna/constraint, transformar `legacy_unmapped` em causa oficial/filtrável, adicionar dependência/CSS, alterar FSM/permissão ou mudar o contrato estrutural do CSV exige escalonamento ao owner antes da edição.
