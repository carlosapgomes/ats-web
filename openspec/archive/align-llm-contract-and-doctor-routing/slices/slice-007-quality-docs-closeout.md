# Slice 007 — Quality Gate e Closeout

## Handoff para Implementador LLM

Este é o slice final do change. Leia todos os slices anteriores e seus relatórios de implementação.

Implemente somente este slice.

## Objetivo

Executar quality gate completo, atualizar documentação de estado do projeto e garantir que o change ficou rastreável.

## Escopo Preferencial

Arquivos prováveis:

- `PROJECT_CONTEXT.md`
- `ROADMAP.md`, se aplicável
- `docs/investigations/2026-05-18-nir-to-doctor-flow-review.md`, se precisar registrar resolução dos achados
- artefatos deste change, se necessário

Não implementar comportamento novo neste slice, salvo correções mínimas para fechar gates.

## Requisitos

1. Rodar quality gate completo:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

2. Atualizar documentação para refletir:
   - prompts canônicos legados;
   - validação Pydantic LLM1/LLM2;
   - scope gate direto ao NIR;
   - presenter médico equivalente ao legado;
   - role guard médico.
3. Registrar qualquer exceção ou pendência.
4. Criar relatório final do change.

## Critérios de Sucesso

- Quality gate completo verde ou falhas justificadas com evidência.
- Documentação não contradiz comportamento implementado.
- Relatório final aponta todos os slices e reports.

## Relatório Obrigatório

Crie:

```text
/tmp/ats-web-slice-007-quality-docs-closeout-report.md
```

Inclua:

- comandos executados;
- resultado de cada comando;
- arquivos de documentação atualizados;
- pendências remanescentes;
- lista dos reports dos slices anteriores, se disponíveis.

Responda com:

```text
REPORT_PATH=/tmp/ats-web-slice-007-quality-docs-closeout-report.md
```

## Stop Rule

Após este slice, pare e aguarde avaliação do planner.
