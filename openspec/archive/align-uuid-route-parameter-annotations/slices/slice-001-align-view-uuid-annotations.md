# Slice 001: Ajustar type hints de views com converters UUID

## Handoff para implementador LLM com contexto zero

Leia:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/align-uuid-route-parameter-annotations/proposal.md`
4. `openspec/changes/align-uuid-route-parameter-annotations/tasks.md`
5. Este arquivo
6. `apps/*/urls.py`
7. `apps/*/views.py`

Implemente somente este slice.

## Objetivo

Ajustar anotações de parâmetros de views que recebem converters Django
`<uuid:...>` para `uuid.UUID`.

## Escopo

- Inventariar `path("<uuid:...>", ...)` em `apps/*/urls.py`.
- Localizar views correspondentes com parâmetro anotado como `str`.
- Trocar para `uuid.UUID` e adicionar `import uuid` quando necessário.
- Preservar comportamento runtime.
- Manter como `str` valores que são payload textual, schemas LLM ou IDs externos
  que não vêm de converter UUID de URL.

## Fora de escopo

- Alterar URL patterns.
- Alterar templates.
- Alterar modelos.
- Refatorar serviços sem relação com views/rotas.

## Critérios de aceite

- [ ] Views associadas a `<uuid:...>` usam `uuid.UUID`.
- [ ] `uv run mypy .` passa.
- [ ] Testes relevantes passam.
- [ ] Não houve mudança funcional.

## Relatório obrigatório

Criar:

```text
/tmp/ats-web-align-uuid-route-annotations-slice-001-report.md
```

Responder com:

```text
REPORT_PATH=/tmp/ats-web-align-uuid-route-annotations-slice-001-report.md
```

## Prompt pronto

```text
Read AGENTS.md, PROJECT_CONTEXT.md and align-uuid-route-parameter-annotations OpenSpec through Slice 001. Implement ONLY Slice 001. Inventory Django URL patterns with <uuid:...>, update corresponding view parameter annotations from str to uuid.UUID, keep textual payload IDs unchanged, run mypy/tests/ruff, update tasks.md, create /tmp/ats-web-align-uuid-route-annotations-slice-001-report.md, commit and push, reply REPORT_PATH and stop.
```
