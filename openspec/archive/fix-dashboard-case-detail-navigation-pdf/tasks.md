# Tasks: Corrigir detalhe de caso do dashboard e acesso a PDF

## Status

Concluída. Slice 001 implementado, validado e merged em main (`fa6d9ae`).

## Slices

- [x] Slice 001 — Detalhe gerencial sem navegação NIR e com PDF para manager/admin
  (`slices/slice-001-dashboard-case-detail-nav-pdf.md`)

## Definition of Done

- [x] Supervisor/admin não veem abas `Novo Encaminhamento` e `Meus Casos` no detalhe do dashboard.
- [x] Supervisor/admin veem retorno apropriado ao dashboard.
- [x] Detalhe do dashboard usa URL de PDF gerencial (`dashboard:case_pdf`).
- [x] Rota de PDF gerencial existe e é restrita a `manager`/`admin`.
- [x] Manager/admin conseguem abrir PDF de caso com `pdf_file`.
- [x] Papéis não gerenciais não acessam PDF via dashboard.
- [x] NIR mantém navegação e PDF operacional atuais no detalhe intake.
- [x] Testes de regressão adicionados.
- [x] Quality gate relevante executado.
- [x] Relatório temporário gerado com `REPORT_PATH`.
- [x] Commit e push realizados.

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
