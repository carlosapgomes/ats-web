# Slice 004 — Hardening operacional, docs e quality gate

## Objetivo

Fechar a feature com documentação operacional, testes de regressão relevantes e quality gate completo.

## Escopo

Arquivos previstos:

- `README.md` ou documentação operacional existente.
- `openspec/changes/regulation-report-intake-gate/tasks.md`.
- Testes de regressão adicionais se lacunas forem identificadas.

## Fora de Escopo

- Não mudar critérios da barreira sem nova evidência/testes.
- Não arquivar o change antes de validação manual do usuário.
- Não implementar OCR nem análise por LLM.

## Critérios de Sucesso

- README/documentação explica:
  - diferença entre barreira de relatório de regulação e scope gate EDA;
  - critérios determinísticos usados;
  - comportamento para PDFs barrados;
  - limitações para PDFs escaneados sem texto.
- `tasks.md` marca slices concluídos somente após implementação real.
- Quality gate completo passa.
- Relatório final lista comandos executados, resultados e pendências pós-MVP.

## Gates de Autoavaliação

- [ ] Documentação não recomenda query/tabela errada.
- [ ] Documentação não promete OCR.
- [ ] Critérios descritos batem com código e testes.
- [ ] `git status --short` limpo após commit/push.

## Prompt para Implementador LLM

```text
Implemente somente o Slice 004 do change openspec/changes/regulation-report-intake-gate.
Leia AGENTS.md, PROJECT_CONTEXT.md, proposal.md, design.md e slices 001-003.
Atualize documentação operacional explicando a barreira de relatório de regulação, diferenças para scope gate EDA, comportamento de manual_review_required, eventos e limitações sem OCR.
Atualize tasks.md com status real do change.
Rode quality gate completo: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest.
Gere relatório em /tmp/ats-web-slice-004-regulation-gate-hardening-quality-report.md.
Commit/push e pare. Não arquive o OpenSpec até o usuário confirmar validação manual.
```

## Validação Recomendada

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
git status --short
```
