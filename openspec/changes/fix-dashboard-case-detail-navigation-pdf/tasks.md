# Tasks: Corrigir detalhe de caso do dashboard e acesso a PDF

## Status

Slice 001 concluído. Testes, lint, type check e quality gate verde.

## Slices

- [x] Slice 001 — Detalhe gerencial sem navegação NIR e com PDF para manager/admin
  (`slices/slice-001-dashboard-case-detail-nav-pdf.md`)

## Definition of Done

- [ ] Supervisor/admin não veem abas `Novo Encaminhamento` e `Meus Casos` no detalhe do dashboard.
- [ ] Supervisor/admin veem retorno apropriado ao dashboard.
- [ ] Detalhe do dashboard usa URL de PDF gerencial (`dashboard:case_pdf`).
- [ ] Rota de PDF gerencial existe e é restrita a `manager`/`admin`.
- [ ] Manager/admin conseguem abrir PDF de caso com `pdf_file`.
- [ ] Papéis não gerenciais não acessam PDF via dashboard.
- [ ] NIR mantém navegação e PDF operacional atuais no detalhe intake.
- [ ] Testes de regressão adicionados.
- [ ] Quality gate relevante executado.
- [ ] Relatório temporário gerado com `REPORT_PATH`.
- [ ] Commit e push realizados.

## Validação recomendada

Rodar testes focados:

```bash
uv run pytest apps/dashboard/tests/test_dashboard.py apps/intake/tests/test_case_detail.py -q
```

Rodar lint/format/type dos apps tocados:

```bash
uv run ruff check apps/dashboard apps/intake
uv run ruff format --check apps/dashboard apps/intake
uv run mypy apps/dashboard apps/intake
```

Quality gate completo, se viável:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```
