# Slice 001 — Detalhe gerencial sem navegação NIR e com PDF para manager/admin

## Status

Pendente.

## Objetivo

Corrigir a página de detalhe de caso aberta pelo dashboard para supervisor e
administrador, removendo elementos de navegação do NIR e permitindo visualização
do PDF por rota gerencial autorizada.

## Handoff

Leia primeiro:

- `AGENTS.md`
- `PROJECT_CONTEXT.md`
- `openspec/changes/fix-dashboard-case-detail-navigation-pdf/proposal.md`
- `openspec/changes/fix-dashboard-case-detail-navigation-pdf/design.md`
- este arquivo

Achados já confirmados:

- `templates/dashboard/index.html` linka para `dashboard:case_detail`.
- `apps/dashboard/views.py::dashboard_case_detail` renderiza
  `templates/intake/case_detail.html`.
- `templates/intake/case_detail.html` tem bloco `nav` fixo com:
  - `Novo Encaminhamento`
  - `Meus Casos`
- O mesmo template usa `{% url 'intake:serve_pdf' case.case_id %}` para embed e
  link direto do PDF.
- `apps/intake/views.py::serve_pdf` é restrita a `role_required("nir")`.

## Arquivos esperados

Manter o slice enxuto. Arquivos prováveis:

- `apps/dashboard/views.py`
- `apps/dashboard/urls.py`
- `templates/intake/case_detail.html`
- `apps/dashboard/tests/test_dashboard.py`
- `apps/intake/tests/test_case_detail.py` se necessário para regressão NIR

Se precisar tocar mais arquivos, registre justificativa no relatório.

## Implementação esperada

1. Seguir TDD:
   - adicionar testes falhando primeiro para dashboard navigation/PDF;
   - adicionar regressão NIR se o template for parametrizado.
2. Criar rota gerencial de PDF:
   - nome sugerido: `dashboard:case_pdf`;
   - path sugerido: `<uuid:case_id>/pdf/`;
   - decorators: `@login_required`, `@role_required("manager", "admin")`,
     `@xframe_options_sameorigin`;
   - retornar `FileResponse` com `application/pdf`;
   - retornar `404` quando não houver PDF.
3. Parametrizar o contexto do template:
   - NIR/intake deve usar `show_intake_nav=True`, `back_url` para `intake:my_cases`
     e `pdf_url` para `intake:serve_pdf`;
   - dashboard deve usar `show_intake_nav=False`, `back_url` para `dashboard:index`
     e `pdf_url` para `dashboard:case_pdf`.
4. Atualizar `templates/intake/case_detail.html`:
   - esconder abas NIR quando `show_intake_nav=False`;
   - trocar botão inferior de retorno para usar `back_url`/`back_label`;
   - trocar embed/link de PDF para usar `pdf_url`.
5. Preservar:
   - `can_confirm_receipt=False` no dashboard;
   - comportamento operacional do NIR;
   - bloqueio de `CLEANED` apenas na rota NIR, não na rota gerencial.

## Critérios de sucesso

- [ ] Teste prova que manager não vê `Novo Encaminhamento` nem `Meus Casos` no detalhe dashboard.
- [ ] Teste prova que admin não vê `Novo Encaminhamento` nem `Meus Casos` no detalhe dashboard.
- [ ] Teste prova que detalhe dashboard mostra retorno ao dashboard.
- [ ] Teste prova que detalhe dashboard usa `dashboard:case_pdf` e não `intake:serve_pdf` para PDF.
- [ ] Teste prova que manager/admin acessam `dashboard:case_pdf`.
- [ ] Teste prova que papel não gerencial não acessa `dashboard:case_pdf`.
- [ ] Teste prova que rota gerencial retorna `404` para caso sem PDF.
- [ ] NIR continua vendo abas NIR e rota `intake:serve_pdf` no detalhe intake.

## Gates de autoavaliação

Antes de concluir, verifique:

- A correção não usa condição baseada apenas em texto de papel dentro do template
  quando contexto explícito resolver melhor.
- Nenhum papel não gerencial consegue acessar PDF pela rota dashboard.
- `intake:serve_pdf` continua restrita ao NIR.
- Não há alteração de banco/migration.
- O slice não cria duplicação grande de template.

## Comandos de validação

Mínimo focado:

```bash
uv run pytest apps/dashboard/tests/test_dashboard.py apps/intake/tests/test_case_detail.py -q
uv run ruff check apps/dashboard apps/intake
uv run ruff format --check apps/dashboard apps/intake
uv run mypy apps/dashboard apps/intake
```

Quality gate completo, se viável:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md and PROJECT_CONTEXT.md first.
Implement ONLY openspec/changes/fix-dashboard-case-detail-navigation-pdf/slices/slice-001-dashboard-case-detail-nav-pdf.md.
Use TDD: add failing tests first, then minimal implementation, then refactor safely.
Do not create a separate dashboard detail template unless parametrizing the shared template proves unsafe.
Create a manager/admin-only dashboard PDF route and make the dashboard case detail use it.
Hide NIR navigation and NIR back links in dashboard detail while preserving NIR behavior in intake detail.
Run the focused validation commands from the slice.
Update tasks.md status when complete.
Create a detailed temporary markdown report with before/after snippets and reply with REPORT_PATH=<path>.
Commit and push the branch.
STOP after the slice and ask for explicit confirmation before any next slice.
```
