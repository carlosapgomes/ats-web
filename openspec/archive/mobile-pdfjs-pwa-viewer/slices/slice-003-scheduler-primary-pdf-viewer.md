# Slice 003: CHD/scheduler — PDF principal processado com viewer mobile interno

## Handoff para implementador LLM com contexto zero

Leia antes de codar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/mobile-pdfjs-pwa-viewer/proposal.md`
4. `openspec/changes/mobile-pdfjs-pwa-viewer/design.md`
5. `openspec/changes/mobile-pdfjs-pwa-viewer/tasks.md`
6. `openspec/changes/mobile-pdfjs-pwa-viewer/specs/mobile-pdf-viewer/spec.md`
7. Este arquivo

Assuma que os Slices 001–002 já criaram o viewer compartilhado e o padrão de `mobile_pdf_viewer_url`. Implemente **somente este slice** com TDD: RED → GREEN → REFACTOR.

## Protocolo obrigatório para implementador DeepSeek4-Flash

Este slice será implementado por um modelo rápido e com tendência a concluir cedo demais. Portanto, siga este protocolo literalmente. **Se qualquer item abaixo falhar, o slice está INCOMPLETO**: não marque `tasks.md`, não faça commit/push e responda com bloqueio + evidência.

1. **Plano antes de editar**: escreva no relatório uma mini matriz `Requisito → arquivo(s) → teste(s)`. Não implemente requisito sem teste ou justificativa explícita.
2. **RED real**: crie/ajuste testes primeiro e rode o subconjunto alvo. Pelo menos um teste novo deve falhar pelo motivo esperado. Se o teste passar antes da implementação, ele não prova o comportamento; corrija o teste.
3. **GREEN mínimo**: implemente somente o necessário para os testes do slice passarem. Não faça refactor amplo, não toque em apps fora do escopo e não antecipe slices futuros.
4. **Verificação por inspeção**: além dos testes, rode buscas `rg`/inspeções descritas neste slice para comprovar que não restaram links mobile com `target="_blank"`, que o desktop ainda tem `<embed>`, que a rota protegida correta é usada e que `Cache-Control: no-store` foi adicionado onde exigido.
5. **Quality gate completo**: execute exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` e `uv run pytest`. Se algum comando falhar, o slice não está pronto.
6. **Relatório com evidência, não opinião**: cole comandos executados, resumo das saídas, testes RED/GREEN, snippets antes/depois e respostas objetivas aos gates. Inclua também `Handoff para verificador` com: arquivos alterados, comandos exatos para rerun, riscos/limitações e checklist dos requisitos R1..Rn. Inclua uma seção final `Status: COMPLETE` somente se todos os critérios estiverem comprovados.

### Condições automáticas de INCOMPLETO

Marque como incompleto se ocorrer qualquer uma destas situações:

- teste planejado não foi escrito ou não foi executado;
- quality gate completo não foi executado;
- qualquer teste/lint/mypy falhou;
- `tasks.md` foi marcado apesar de falha ou pendência;
- `target="_blank"` permaneceu no link mobile que o slice deveria substituir;
- o `<embed>` desktop foi removido ou passou a usar a rota errada;
- viewer usa `MEDIA_URL`, caminho físico do arquivo ou URL sem autorização;
- `next` é usado sem validação/fallback canônico;
- `Cache-Control: no-store` exigido pelo slice ficou ausente;
- PDF.js/viewer foi declarado pronto sem teste/inspeção que comprove carregamento do JS/template;
- relatório temporário não foi criado no caminho exigido.


## Objetivo do slice

Entregar o viewer mobile interno para o PDF principal acessado pelo CHD/scheduler no detalhe de casos processados:

```text
CHD abre “Processados Hoje”
→ abre detalhe processado
→ no mobile toca “Visualizar PDF”
→ navega para viewer interno
→ volta ao detalhe processado
```

Desktop deve continuar usando `<embed>`.

## Contexto técnico atual

- `apps/scheduler/urls.py` já tem:
  - `processed/<uuid:case_id>/` → `scheduler:processed_detail`;
  - `processed/<uuid:case_id>/pdf/` → `scheduler:processed_pdf`.
- `apps/scheduler/views.py::scheduler_processed_detail` passa `pdf_url=reverse("scheduler:processed_pdf", ...)`.
- `apps/scheduler/views.py::scheduler_processed_pdf` tem autorização restrita a casos processados pelo scheduler logado. Essa autorização **não deve ser relaxada**.
- `templates/scheduler/context_detail.html` usa `pdf_url`:
  - mobile: link direto com `target="_blank"`;
  - desktop: `<embed src="{{ pdf_url }}">`.

## Escopo funcional

### R1. Criar rota de viewer para PDF processado

Adicionar em `apps/scheduler/urls.py`:

```text
processed/<uuid:case_id>/pdf-viewer/ → scheduler:processed_pdf_viewer
```

Criar view em `apps/scheduler/views.py`, por exemplo `scheduler_processed_pdf_viewer`:

- exige login + `role_required("scheduler")`;
- usa a **mesma regra de autorização** do `scheduler_processed_pdf` ou helper compartilhado pequeno;
- retorna 404 se não houver PDF;
- renderiza o template compartilhado do viewer;
- passa `pdf_url=reverse("scheduler:processed_pdf", args=[case.case_id])`;
- usa `next` validado ou fallback `reverse("scheduler:processed_detail", args=[case.case_id])`.

### R2. Atualizar detalhe processado/contextual

Em `templates/scheduler/context_detail.html`:

- se `pdf_url` existir, o link mobile deve usar `mobile_pdf_viewer_url`;
- não usar `target="_blank"` no link mobile;
- desktop mantém `<embed src="{{ pdf_url }}" type="application/pdf">`.

Em `apps/scheduler/views.py::scheduler_processed_detail`, passar `mobile_pdf_viewer_url` com `next` para o detalhe atual.

Atenção: se `context_detail.html` também for usado por busca histórica institucional sem `pdf_url`, não criar link quebrado. O viewer deve aparecer apenas quando a view passar `mobile_pdf_viewer_url`.

### R3. Cache-Control

Adicionar `Cache-Control: no-store` em `scheduler_processed_pdf`, preservando `Content-Type: application/pdf`.

### R4. Não criar rota histórica institucional de PDF

Não adicionar PDF para a busca histórica do scheduler se ela não tem autorização/rota própria hoje. Este slice é apenas para `processed_detail` e `processed_pdf`.

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/scheduler/urls.py`
2. `apps/scheduler/views.py`
3. `templates/scheduler/context_detail.html`
4. `apps/scheduler/tests/test_views.py`
5. `openspec/changes/mobile-pdfjs-pwa-viewer/tasks.md`

Não tocar JS/template compartilhado salvo bug real encontrado e justificado.

## TDD obrigatório

### RED

Adicionar testes falhando antes da implementação:

1. `test_scheduler_processed_detail_mobile_pdf_link_uses_internal_viewer`
   - detalhe processado contém `scheduler:processed_pdf_viewer`;
   - link mobile não usa `target="_blank"`;
   - desktop embed usa `scheduler:processed_pdf`.
2. `test_scheduler_processed_pdf_viewer_authorized_scheduler_renders`
   - usuário que processou/tem autorização acessa com 200;
   - viewer contém `scheduler:processed_pdf` como fonte;
   - contém dois “Voltar” e fallback.
3. `test_scheduler_processed_pdf_viewer_404_for_other_scheduler_case`
   - preservar autorização restrita equivalente à rota PDF.
4. `test_scheduler_processed_pdf_response_has_no_store_cache_control`.
5. Regressão: busca/contexto histórico sem `pdf_url` não ganha link de viewer quebrado, se já houver teste similar.

Registre RED no relatório.

### GREEN

Implementar o mínimo.

### REFACTOR

- Se `scheduler_processed_pdf` e viewer duplicarem autorização, extraia helper privado pequeno no próprio `apps/scheduler/views.py`.
- Não alterar semântica de processados/histórico.
- Não criar endpoint institucional amplo de PDF.

## Checks de inspeção obrigatórios antes de concluir

Além dos testes automatizados, execute e cole o resultado/resumo no relatório:

```bash
rg -n "mobile_pdf_viewer_url|target=\"_blank\"|<embed|pdf_url" templates/scheduler/context_detail.html
rg -n "processed_pdf_viewer|processed_pdf|no-store|url_has_allowed_host_and_scheme" apps/scheduler/views.py apps/scheduler/urls.py
```

Interprete os resultados no relatório: a rota de viewer deve existir apenas para `processed`, o embed desktop deve continuar apontando para `scheduler:processed_pdf`, e a busca/contexto histórico não pode ganhar link quebrado sem `pdf_url`.

## Critérios de sucesso do slice

- [ ] Detalhe processado CHD mobile usa viewer interno.
- [ ] Viewer CHD usa `scheduler:processed_pdf` como fonte protegida.
- [ ] Autorização de `scheduler_processed_pdf` não foi relaxada.
- [ ] Caso de outro scheduler continua 404/bloqueado.
- [ ] Desktop preserva `<embed>`.
- [ ] Link mobile não usa nova aba.
- [ ] `scheduler_processed_pdf` tem `Cache-Control: no-store`.
- [ ] Nenhuma rota histórica institucional de PDF foi adicionada.
- [ ] `tasks.md` atualizado ao concluir.

## Gates de autoavaliação

Responder no relatório:

1. Qual rota de viewer CHD foi criada?
2. Qual rota PDF protegida ela usa?
3. A autorização foi extraída ou duplicada? Onde está testada?
4. O teste de outro scheduler continua passando?
5. O template usado em histórico sem `pdf_url` cria link quebrado? Esperado: não.
6. O desktop ainda usa `<embed>`?
7. Algum link mobile desse fluxo ainda usa `target="_blank"`?
8. O header `Cache-Control` foi adicionado em qual rota?
9. Alguma permissão/model/FSM/pipeline foi alterada? Esperado: não.

## Relatório obrigatório

Criar:

```text
/tmp/mobile-pdfjs-pwa-viewer-slice-003-report.md
```

Incluir resumo, arquivos alterados, RED/GREEN, snippets antes/depois, evidência de autorização, cache header, quality gate e respostas aos gates.

Responder com:

```text
REPORT_PATH=/tmp/mobile-pdfjs-pwa-viewer-slice-003-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/mobile-pdfjs-pwa-viewer/{proposal.md,design.md,tasks.md,specs/mobile-pdf-viewer/spec.md,slices/slice-003-scheduler-primary-pdf-viewer.md} first. Assume previous slices are complete.
Implement ONLY Slice 003 using TDD. Follow the DeepSeek4-Flash protocol in this file: plan, RED real, GREEN mínimo, inspection checks, full quality gate and evidence report. Add a scheduler processed PDF viewer route and update templates/scheduler/context_detail.html so the mobile PDF action uses the internal viewer without target=_blank, while desktop keeps embed using scheduler:processed_pdf. If any required test/check/gate is missing or failing, report INCOMPLETE and do not update tasks.md or commit.
Preserve the existing strict authorization of scheduler_processed_pdf; do not add a broad historical scheduler PDF route. Validate next URLs or fallback to scheduler:processed_detail. Add Cache-Control: no-store to scheduler_processed_pdf.
Do not alter models, migrations, FSM, pipeline, shared JS unless a bug requires it. Run quality gate, update tasks.md, write /tmp/mobile-pdfjs-pwa-viewer-slice-003-report.md, commit and push. Reply with REPORT_PATH and stop.
```
