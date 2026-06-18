# Slice 000: ADR + OpenSpec/design do change

## Status

- [x] Done

## Contexto zero para implementador

O projeto ATS Web proibia emails em sua documentação original porque notificações operacionais deveriam ser exclusivamente in-app. O novo requisito abre uma exceção controlada: emails transacionais de autenticação, segurança de conta e cadastro.

Este slice prepara os artefatos para que outros LLMs implementem os fluxos com contexto zero e sem ampliar escopo.

Leia antes de revisar:

- `AGENTS.md`
- `PROJECT_CONTEXT.md`
- `docs/adr/ADR-0002-emails-transacionais-autenticacao-cadastro.md`
- `openspec/changes/transactional-emails-auth-flows/proposal.md`
- `openspec/changes/transactional-emails-auth-flows/design.md`
- `openspec/changes/transactional-emails-auth-flows/tasks.md`

## Objetivo do slice

Criar os artefatos de decisão e planejamento:

```text
ADR aceita
→ OpenSpec proposal/design/tasks
→ slices verticais com handoff e prompts
→ branch dedicada criada
```

## Arquivos esperados

- `docs/adr/ADR-0002-emails-transacionais-autenticacao-cadastro.md`
- `docs/adr/README.md`
- `openspec/changes/transactional-emails-auth-flows/proposal.md`
- `openspec/changes/transactional-emails-auth-flows/design.md`
- `openspec/changes/transactional-emails-auth-flows/tasks.md`
- `openspec/changes/transactional-emails-auth-flows/slices/*.md`

## Critérios de sucesso

- [x] ADR documenta exceção para emails transacionais e mantém notificações operacionais in-app.
- [x] Proposal define problema, escopo, fora de escopo e critérios.
- [x] Design define decisões técnicas, env vars, riscos e estratégia.
- [x] Tasks lista slices verticais e DoD.
- [x] Slices possuem handoff, TDD, gates, prompt e relatório obrigatório.
- [x] Branch `feat/transactional-emails-auth-flows` criada.

## Relatório final obrigatório

Este slice é documental. O relatório deve apontar arquivos criados, decisões principais e pendências para Slice 001.

Responder com:

```text
REPORT_PATH=<path>
```
