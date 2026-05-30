# Tasks: Dados de conselho profissional no usuário

## Status

Change pequeno criado para implementação por outro LLM com contexto zero.

## Slices

- [x] Slice 001 — Campos de conselho profissional no usuário (`slices/slice-001-user-professional-council.md`)
  - Commit: `ab1f1c1` (feat(accounts): add professional council fields to users)
  - Report: `/tmp/ats-web-slice-001-user-professional-council-report.md`
  - Testes: 61 pass (50 originais + 11 novos)

## Definition of Done do Change

- [x] `User` possui campos opcionais `professional_council` e `professional_council_number`.
- [x] Choices de conselho restritas a `COREN` e `CRM`.
- [x] Validação impede preenchimento parcial dos dois campos.
- [x] Gestão de usuários permite criar/editar os campos.
- [x] Listagem de usuários exibe o registro profissional quando existir.
- [x] Django Admin expõe os campos.
- [x] Testes relevantes adicionados/atualizados.
- [x] Quality gate do `AGENTS.md` executado.
- [x] Relatório temporário do slice gerado e `REPORT_PATH` informado.
- [x] Commit e push realizados.
