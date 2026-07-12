# Slice 003b: Consolidar validação de `next` dos PDF viewers

## Handoff para implementador LLM com contexto zero

Leia antes de codar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/mobile-pdfjs-pwa-viewer/proposal.md`
4. `openspec/changes/mobile-pdfjs-pwa-viewer/design.md`
5. `openspec/changes/mobile-pdfjs-pwa-viewer/tasks.md`
6. `openspec/changes/mobile-pdfjs-pwa-viewer/specs/mobile-pdf-viewer/spec.md`
7. Este arquivo

Implemente **somente este follow-up 003b** usando TDD: RED → GREEN → REFACTOR. Este slice existe para corrigir dívida técnica apontada pelo avaliador após o Slice 003, antes de implementar anexos no Slice 004.

## Protocolo obrigatório para implementador DeepSeek4-Flash

Este slice será implementado por um modelo rápido e com tendência a concluir cedo demais. Portanto, siga este protocolo literalmente. **Se qualquer item abaixo falhar, o slice está INCOMPLETO**: não marque `tasks.md`, não faça commit/push e responda com bloqueio + evidência.

1. **Plano antes de editar**: escreva no relatório uma mini matriz `Requisito → arquivo(s) → teste(s)`. Não implemente requisito sem teste ou justificativa explícita.
2. **RED real**: crie/ajuste testes primeiro e rode o subconjunto alvo. Pelo menos um teste novo deve falhar pelo motivo esperado. Se o teste passar antes da implementação, ele não prova o comportamento; corrija o teste.
3. **GREEN mínimo**: implemente somente o necessário para os testes do slice passarem. Não faça refactor amplo, não toque em apps fora do escopo e não antecipe slices futuros.
4. **Verificação por inspeção**: além dos testes, rode buscas `rg`/inspeções descritas neste slice para comprovar os contratos críticos do slice.
5. **Quality gate completo**: execute exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` e `uv run pytest`. Se algum comando falhar, o slice não está pronto.
6. **Relatório com evidência, não opinião**: cole comandos executados, resumo das saídas, testes RED/GREEN, snippets antes/depois e respostas objetivas aos gates. Inclua também `Handoff para verificador` com: arquivos alterados, comandos exatos para rerun, riscos/limitações e checklist dos requisitos R1..Rn. Inclua uma seção final `Status: COMPLETE` somente se todos os critérios estiverem comprovados.

### Condições automáticas de INCOMPLETO

Marque como incompleto se ocorrer qualquer uma destas situações:

- teste planejado não foi escrito ou não foi executado;
- quality gate completo não foi executado;
- qualquer teste/lint/mypy falhou;
- `tasks.md` foi marcado apesar de falha ou pendência;
- ainda existirem helpers locais de validação de `next` dos PDF viewers em doctor/intake/dashboard;
- o viewer scheduler continuar validando `next` inline;
- algum PDF viewer aceitar `next` externo/malicioso;
- algum fallback canônico de viewer mudar ou quebrar;
- autorização, rotas de PDF, templates ou PDF.js forem alterados sem necessidade;
- relatório temporário não foi criado no caminho exigido.

## Objetivo do slice

Consolidar os 4 estilos atuais de validação de `next` dos PDF viewers em um único helper compartilhado, sem alterar UX, rotas, permissões ou renderização.

Dívida apontada pelo avaliador:

```text
- doctor: helper _validate_next_url (top-level)
- intake: helper _intake_validate_next_url (lazy import dentro da função)
- dashboard: helper _dashboard_validate_next_url (import no topo)
- scheduler: validação inline (sem helper)
```

Novo comportamento desejado:

```text
Todos os PDF viewers usam o mesmo helper compartilhado
→ next seguro interno é aceito
→ next externo/malicioso cai no fallback canônico da superfície
→ Slice 004 poderá reutilizar o mesmo padrão para anexos
```

## Contexto técnico atual

PDF viewers já implementados:

- `apps/doctor/views.py::pdf_viewer`
- `apps/intake/views.py::pdf_viewer`
- `apps/intake/views.py::closed_case_pdf_viewer`
- `apps/dashboard/views.py::dashboard_pdf_viewer`
- `apps/scheduler/views.py::scheduler_processed_pdf_viewer`

Todos renderizam `templates/pdf_viewer/mobile_pdf_viewer.html` e recebem `back_url` derivado de `?next=` ou fallback canônico.

Este slice **não** deve mexer em links mobile, `<embed>`, PDF.js, `Cache-Control`, permissões ou rotas, exceto se um import ficar obsoleto após o refactor.

## Escopo funcional

### R1. Criar helper compartilhado de navegação segura

Criar novo helper pequeno, preferencialmente em:

```text
apps/cases/navigation.py
```

Assinatura recomendada:

```python
from django.http import HttpRequest


def resolve_safe_next_url(request: HttpRequest, fallback_url: str, *, param_name: str = "next") -> str:
    """Return a same-host next URL from query string or the fallback URL."""
```

Regras:

- ler `request.GET.get(param_name, "")`;
- aceitar apenas URL considerada segura por `url_has_allowed_host_and_scheme`;
- usar `allowed_hosts={request.get_host()}`;
- usar `require_https=request.is_secure()`;
- retornar `fallback_url` quando `next` estiver ausente, vazio, externo, protocol-relative (`//evil`) ou inseguro;
- manter tipo de retorno sempre `str`, nunca `None`.

### R2. Substituir validações locais nos PDF viewers

Atualizar os viewers para chamar o helper compartilhado:

```python
back_url = resolve_safe_next_url(
    request,
    reverse("...:...", args=[case.case_id]),
)
```

Remover, se não usados por outro fluxo:

- `apps/doctor/views.py::_validate_next_url`;
- `apps/intake/views.py::_intake_validate_next_url`;
- `apps/dashboard/views.py::_dashboard_validate_next_url`;
- validação inline com `url_has_allowed_host_and_scheme` em `apps/scheduler/views.py::scheduler_processed_pdf_viewer`.

Não remover `apps/intake/views.py::_is_safe_redirect` neste slice se ele for usado por outros fluxos de POST/redirect fora dos PDF viewers. O escopo é consolidar validação dos **PDF viewers**.

### R3. Preservar fallbacks canônicos existentes

Fallo backs esperados:

- doctor viewer → `reverse("doctor:decision", args=[case.case_id])`;
- intake operacional viewer → `reverse("intake:case_detail", args=[case.case_id])`;
- intake histórico viewer → `reverse("intake:closed_case_detail", args=[case.case_id])`;
- dashboard viewer → `reverse("dashboard:case_detail", args=[case.case_id])`;
- scheduler processed viewer → `reverse("scheduler:processed_detail", args=[case.case_id])`.

### R4. Testar rejeição de `next` externo nos viewers

Adicionar cobertura que prove que `next=https://evil.example/...` ou `next=//evil.example/...` **não aparece** no HTML do viewer e que o fallback canônico aparece.

Cobertura mínima aceitável:

- teste unitário do helper compartilhado cobrindo safe/internal, vazio, externo e protocol-relative;
- pelo menos um teste de view por superfície já implementada ou, se optar por reduzir duplicação, testes de view para doctor + scheduler e justificativa no relatório de que intake/dashboard seguem o mesmo helper e já têm testes de fallback/safe next.

Preferência: cobrir todas as superfícies com testes explícitos porque o bug é cross-app.

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/cases/navigation.py` (novo)
2. `apps/cases/tests/test_navigation.py` (novo)
3. `apps/doctor/views.py`
4. `apps/doctor/tests/test_pdf_viewer.py`
5. `apps/intake/views.py`
6. `apps/intake/tests/test_pdf_viewer.py`
7. `apps/dashboard/views.py`
8. `apps/dashboard/tests/test_dashboard.py`
9. `apps/scheduler/views.py`
10. `apps/scheduler/tests/test_views.py`
11. `openspec/changes/mobile-pdfjs-pwa-viewer/tasks.md`

Se tocar mais arquivos, justificar no relatório. Não tocar templates/static files neste slice.

## Fora de escopo

Não implementar neste slice:

- viewer de anexos do Slice 004;
- mudanças em PDF.js;
- mudanças em templates;
- mudanças de rotas/URLs públicas;
- mudanças de autorização;
- migrations/models/FSM/pipeline;
- refactor amplo de redirects não relacionados aos PDF viewers.

## TDD obrigatório

### RED

Antes de implementar, adicione testes falhando. Sugestão objetiva:

1. `apps/cases/tests/test_navigation.py`
   - `test_resolve_safe_next_url_accepts_same_host_path`;
   - `test_resolve_safe_next_url_returns_fallback_for_empty_next`;
   - `test_resolve_safe_next_url_returns_fallback_for_external_url`;
   - `test_resolve_safe_next_url_returns_fallback_for_protocol_relative_url`.

2. Testes nos PDF viewers:
   - doctor: `next=https://evil.example/...` cai para `doctor:decision`;
   - intake operacional: `next=https://evil.example/...` cai para `intake:case_detail`;
   - intake histórico: `next=https://evil.example/...` cai para `intake:closed_case_detail`;
   - dashboard: `next=https://evil.example/...` cai para `dashboard:case_detail`;
   - scheduler processed: `next=https://evil.example/...` cai para `scheduler:processed_detail`.

Cada teste de view deve verificar:

- resposta autorizada continua 200;
- string `evil.example` não aparece no HTML;
- fallback canônico aparece no HTML.

Registre no relatório o comando RED e a falha esperada por ausência do helper ou por comportamento ainda não refatorado.

### GREEN

Implementar o helper e substituir as validações locais pelo mínimo necessário.

### REFACTOR

- Remover imports mortos de `url_has_allowed_host_and_scheme` nos apps que não usam mais diretamente.
- Manter nomes claros e função coesa.
- Não criar abstração maior que o helper único.
- Não alterar comportamento fora dos PDF viewers.

## Checks de inspeção obrigatórios antes de concluir

Além dos testes automatizados, execute e cole o resultado/resumo no relatório:

```bash
rg -n "def _validate_next_url|def _intake_validate_next_url|def _dashboard_validate_next_url" apps/doctor/views.py apps/intake/views.py apps/dashboard/views.py
rg -n "url_has_allowed_host_and_scheme|resolve_safe_next_url" apps/doctor/views.py apps/intake/views.py apps/dashboard/views.py apps/scheduler/views.py apps/cases/navigation.py
rg -n "next_url = request.GET.get|request.GET.get\(\"next\"|allowed_hosts=\{request.get_host\(\)\}" apps/doctor/views.py apps/intake/views.py apps/dashboard/views.py apps/scheduler/views.py
rg -n "resolve_safe_next_url" apps/doctor/tests/test_pdf_viewer.py apps/intake/tests/test_pdf_viewer.py apps/dashboard/tests/test_dashboard.py apps/scheduler/tests/test_views.py apps/cases/tests/test_navigation.py
```

Interpretação obrigatória no relatório:

- o primeiro comando não deve encontrar os helpers locais removidos;
- `url_has_allowed_host_and_scheme` deve aparecer no helper compartilhado, não nos PDF viewers refatorados;
- não deve haver validação inline de `request.GET.get("next")` nos PDF viewers;
- os testes devem mencionar ou cobrir o helper/resultado dele.

## Critérios de sucesso do slice

- [ ] Existe um helper compartilhado para resolver `next` seguro com fallback.
- [ ] Todos os PDF viewers implementados nos Slices 001–003 usam esse helper.
- [ ] Helpers locais de PDF viewer foram removidos.
- [ ] Validação inline do scheduler foi removida.
- [ ] `next` seguro interno continua aceito.
- [ ] `next` externo/protocol-relative é rejeitado e cai no fallback canônico.
- [ ] Fallback canônico de cada superfície foi preservado.
- [ ] Nenhuma permissão, rota, template, PDF.js, FSM, model ou migration foi alterada.
- [ ] Testes relevantes passam.
- [ ] `tasks.md` atualizado ao concluir.

## Gates de autoavaliação

Responder no relatório:

1. Onde está o helper compartilhado e qual é sua assinatura?
2. Quais PDF viewers foram alterados para usar o helper?
3. Quais helpers locais foram removidos?
4. O scheduler ainda tem validação inline de `next`? Esperado: não.
5. Quais testes provam rejeição de `next` externo?
6. Quais testes provam fallback canônico por superfície?
7. `next` seguro interno continua aceito? Onde está testado?
8. Alguma URL/rota/template/permissão mudou? Esperado: não.
9. Algum redirect não relacionado a PDF viewer foi alterado? Esperado: não.
10. Como o Slice 004 deve reutilizar esse helper?

## Relatório obrigatório

Criar:

```text
/tmp/mobile-pdfjs-pwa-viewer-slice-003b-report.md
```

O relatório deve conter:

- `Status: COMPLETE` ou `Status: INCOMPLETE`;
- matriz requisito → arquivo(s) → teste(s);
- evidência RED;
- evidência GREEN;
- snippets antes/depois de pelo menos 2 viewers, incluindo scheduler;
- resultado dos checks de inspeção obrigatórios;
- resultado do quality gate completo;
- respostas aos gates de autoavaliação;
- `Handoff para verificador` com arquivos alterados, comandos para rerun, riscos/limitações e checklist R1..R4.

Responder ao final com:

```text
REPORT_PATH=/tmp/mobile-pdfjs-pwa-viewer-slice-003b-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/mobile-pdfjs-pwa-viewer/{proposal.md,design.md,tasks.md,specs/mobile-pdf-viewer/spec.md,slices/slice-003b-consolidate-pdf-viewer-next-validation.md} first.
Implement ONLY Slice 003b. Follow the DeepSeek4-Flash protocol in this file: plan, RED real, GREEN mínimo, inspection checks, full quality gate and evidence report. If any required test/check/gate is missing or failing, report INCOMPLETE and do not update tasks.md or commit.
Consolidate PDF viewer next validation into one shared helper, preferably apps/cases/navigation.py::resolve_safe_next_url(request, fallback_url, *, param_name="next") -> str. Replace doctor/intake/dashboard local helpers and scheduler inline validation in PDF viewers only. Preserve all canonical fallbacks, permissions, routes, templates, PDF.js, Cache-Control behavior and existing UX.
Use TDD: add failing tests for helper behavior and for external next rejection/fallback in the existing PDF viewers. Do not implement Slice 004 attachments. Do not touch models, migrations, FSM, pipeline or unrelated redirects.
Run ruff check, ruff format --check, mypy and pytest. Update tasks.md only if all checks pass. Create /tmp/mobile-pdfjs-pwa-viewer-slice-003b-report.md with RED/GREEN evidence, inspection checks, snippets and handoff for verifier. Commit and push. Reply with REPORT_PATH and stop.
```
