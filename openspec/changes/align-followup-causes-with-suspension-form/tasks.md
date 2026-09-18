# Tasks: Alinhar causas do pós-procedimento à ficha de suspensão

## 0. Precondições do change

- [x] 0.1 Classificar como CRÍTICO / HIGH-ARCH, registrar `design.md`, rollback e ADR-0009 aceita com os quatro mapeamentos confirmados pelo owner.
- [x] 0.2 Preflight concluído na branch `feature/align-followup-causes-with-suspension-form`, `BASE_REF=94ab7ac`: working tree continha somente os artefatos aprovados do change; baseline global verde (`ruff check`, `ruff format --check`, `mypy`, `pytest`: 3725 passed) usando o banco de teste ativo em `POSTGRES_TEST_HOST_PORT=55433`.

## 1. Registro oficial compacto

- [ ] 1.1 Implementar o Slice 001 (`slices/slice-001-official-causes-compact-form.md`) em RED → GREEN → REFACTOR; verificar catálogo oficial, rejeição de códigos legados, migration metadata-only, select responsivo e evento persistido; obter review independente aceito.
- [ ] 1.2 Após aceite do Slice 001, confirmar `apps/dashboard/tests/test_followup_history.py` verde com fixtures legadas diretas e registrar evidência da ida/volta `0019 → 0020 → 0019 → 0020` sem alteração de dados.
- [ ] 1.3 Atualizar `tasks.md`, gerar relatório temporário com evidências/snippets, informar `REPORT_PATH`, criar commit/push rastreáveis e parar até confirmação explícita para o Slice 002.

## 2. Compatibilidade histórica e documentação

- [ ] 2.1 Implementar o Slice 002 (`slices/slice-002-legacy-projection-history.md`) em RED → GREEN → REFACTOR; verificar os quatro mapeamentos e o fallback técnico `legacy_unmapped` em tabela/cards/filtro/CSV, imutabilidade append-only, preflight fail-closed e manual atualizado; obter review independente aceito.
- [ ] 2.2 Após aceite do Slice 002, atualizar `tasks.md`, gerar relatório temporário com evidências/snippets, informar `REPORT_PATH`, criar commit/push rastreáveis e parar até confirmação explícita para o gate final.

## 3. Gate final e entrega

- [ ] 3.1 Executar uma única vez o quality gate global: `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest`.
- [ ] 3.2 Executar `openspec validate align-followup-causes-with-suspension-form --strict`, `git diff --check`, `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test`, `uv run python manage.py showmigrations cases --plan --settings=config.settings.test`, teste de migration ida/volta e inspeção final de escopo/migration.
- [ ] 3.3 Atualizar specs canônicas e `PROJECT_CONTEXT.md` no arquivamento conforme workflow, preservando a supersessão parcial ADR-0007→ADR-0009.
- [ ] 3.4 Gerar relatório final temporário com snippets antes/depois, informar `REPORT_PATH`, criar commit/push rastreáveis e parar para aprovação humana antes de deploy/arquivo.
- [ ] 3.5 Antes do deploy e sem writes concorrentes, executar o preflight de legados não mapeáveis (zero obrigatório) e ensaiar em staging `0019 → 0020 → 0019 → 0020`; qualquer divergência bloqueia rollout.
- [ ] 3.6 Após aprovação e deploy, executar smoke de uma causa oficial, **Outras causas**, rejeição legada, fallback técnico sintético e dos quatro mapeamentos no Histórico/CSV; preferir forward-fix se já houver novas gravações.

## Regra de execução

- Implementar exatamente um slice por vez e parar para confirmação explícita antes do próximo.
- Worker não altera `tasks.md`, não faz commit/push e não amplia escopo silenciosamente.
- Parent/orquestrador marca checkboxes somente após evidência e review aceito.
- Nenhuma row `ProcedureFollowUp`/`CaseFollowUp` ou `CaseEvent` histórica pode ser reescrita.
- Necessidade de remover coluna/constraint, transformar `legacy_unmapped` em causa oficial/filtrável, adicionar dependência/CSS, alterar FSM/permissão ou mudar o contrato estrutural do CSV exige escalonamento ao owner antes da edição.
