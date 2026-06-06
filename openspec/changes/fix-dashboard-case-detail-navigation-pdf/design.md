# Design: Detalhe gerencial de caso e PDF no dashboard

## Decisão

Manter um único template de detalhe por enquanto, mas torná-lo explicitamente
parametrizado por superfície de uso.

A view `apps/dashboard/views.py::dashboard_case_detail` continuará renderizando
`templates/intake/case_detail.html`, porém deve enviar contexto suficiente para o
template não assumir que está no fluxo NIR.

Essa abordagem é preferível para este bugfix porque:

- reduz escopo e duplicação de HTML;
- preserva todos os blocos já compartilhados de detalhe/timeline/resultado;
- mantém a view do dashboard como boundary de permissão gerencial;
- corrige a navegação e PDF com baixo risco.

Se, no futuro, o detalhe gerencial divergir muito do NIR, um template específico
`templates/dashboard/case_detail.html` pode ser criado como refactor planejado.

## Contexto de template proposto

Adicionar flags/URLs explícitas no contexto das views.

### Intake/NIR

Em `apps/intake/views.py::case_detail`, manter comportamento atual e passar, se
necessário:

```python
"detail_surface": "intake",
"show_intake_nav": True,
"back_url": reverse("intake:my_cases"),
"back_label": "← Voltar para lista",
"pdf_url": reverse("intake:serve_pdf", args=[case.case_id]),
```

### Dashboard manager/admin

Em `apps/dashboard/views.py::dashboard_case_detail`, passar:

```python
"detail_surface": "dashboard",
"show_intake_nav": False,
"back_url": reverse("dashboard:index"),
"back_label": "← Voltar ao dashboard",
"pdf_url": reverse("dashboard:case_pdf", args=[case.case_id]),
```

O template deve usar essas variáveis em vez de URLs fixas para navegação e PDF.

## Navegação

No bloco `nav` de `templates/intake/case_detail.html`:

- renderizar as abas NIR somente quando `show_intake_nav` for verdadeiro;
- para dashboard, não renderizar as abas NIR;
- opcionalmente renderizar um pill/link simples para `Dashboard`, se o slice
  optar por manter navegação superior gerencial.

No botão inferior de retorno:

- substituir `{% url 'intake:my_cases' %}` por `back_url`;
- substituir texto fixo por `back_label`;
- garantir que o botão continue aparecendo quando não houver lock bloqueando a
  tela.

## PDF gerencial

Criar endpoint dedicado no app dashboard, por exemplo:

```text
/dashboard/<uuid:case_id>/pdf/
```

com nome:

```text
dashboard:case_pdf
```

A view deve:

- exigir login;
- exigir papel ativo `manager` ou `admin` com `@role_required("manager", "admin")`;
- usar `@xframe_options_sameorigin` para permitir embed no mesmo site, espelhando
  a rota NIR;
- buscar o `Case` por `case_id`;
- retornar `404` quando não houver `pdf_file`;
- retornar `FileResponse(case.pdf_file.open("rb"), content_type="application/pdf")`.

Não ampliar `intake:serve_pdf` para manager/admin. A rota NIR deve continuar
operacional e restrita ao NIR.

## Casos CLEANED

O dashboard é superfície gerencial/auditoria e já permite consultar casos fora
da fila operacional. Portanto, a rota gerencial de PDF não deve bloquear
automaticamente casos `CLEANED`. Ela deve se limitar à autorização
manager/admin e à existência do arquivo.

A rota NIR deve manter seu comportamento atual, incluindo bloqueio operacional
para `CLEANED`.

## Testes esperados

Adicionar testes em `apps/dashboard/tests/test_dashboard.py` cobrindo:

1. `manager` abre detalhe do dashboard e não vê `Novo Encaminhamento` nem
   `Meus Casos`.
2. `admin` abre detalhe do dashboard e não vê `Novo Encaminhamento` nem
   `Meus Casos`.
3. detalhe do dashboard exibe retorno ao dashboard, não retorno para lista NIR.
4. detalhe do dashboard com `pdf_file` contém URL `dashboard:case_pdf`, não
   `intake:serve_pdf`.
5. `manager` consegue GET em `dashboard:case_pdf` para caso com PDF.
6. `admin` consegue GET em `dashboard:case_pdf` para caso com PDF.
7. `nir`, `doctor` e/ou `scheduler` não conseguem acessar `dashboard:case_pdf`.
8. rota `dashboard:case_pdf` retorna `404` para caso sem PDF.

Adicionar ou preservar testes em `apps/intake/tests/test_case_detail.py` para
garantir que o NIR continua vendo abas NIR e usando `intake:serve_pdf`.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Quebrar detalhe NIR ao parametrizar template | Testes de regressão no app intake |
| Expor PDF para papéis indevidos | Endpoint dedicado com `role_required("manager", "admin")` |
| Duplicar template desnecessariamente | Parametrizar template compartilhado neste slice |
| Botões de ação NIR aparecerem no dashboard | Manter `can_confirm_receipt=False` na view dashboard e testar ausência de ações NIR |

## Rollback

Rollback simples por Git revert do slice. Como não há migration nem mudança de
schema, a reversão deve voltar o comportamento anterior sem impacto no banco.
