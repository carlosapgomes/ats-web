# Slice 007: Filtros NIR e tipo no reenvio corrigido

## Handoff contexto zero

Leia AGENTS/PROJECT_CONTEXT, todos artefatos, specs `exam-type-analytics` e `exam-type-correction`, este slice, `apps/intake/views.py` (`_my_cases_context`, closed search/detail, corrected_resubmission), `apps/intake/services.py::create_corrected_resubmission`, templates NIR e testes de correção/closed search. Slice 006 trata reprocessamento do mesmo caso; este slice trata localização e **novo caso corrigido**.

Objetivo:

```text
NIR filtra operacionais e encerrados por Todos/EDA/Colonoscopia
→ filtros compõem e polling preserva query
→ reenvio corrigido exige tipo explícito e pode diferir do original
→ novo Case segue regras existentes de não herança
```

## Protocolo DeepSeek4-Flash

**Qualquer falha = INCOMPLETO; não marque task/commit/push.**

1. Confirme branch `feature/colonoscopy-exam-workflow`, árvore limpa e registre `BASE_REF=$(git rev-parse HEAD)`.
2. Registre matriz `Requisito → arquivo(s) → teste(s)` e rode `uv run pytest` baseline antes de editar; pare com failure/error.
3. Escreva testes primeiro e prove RED real.
4. Faça GREEN mínimo sem antecipar slices.
5. Faça REFACTOR estreito com clean code, DRY, YAGNI e sem código morto.
6. Execute/interprete todos os checks `rg`/diff.
7. Rode exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`, `uv run pytest`; final exit 0, zero failures/errors e `passed_final >= passed_baseline`.
8. Relatório deve conter comandos/exit codes, snippets, comparação e seção **Handoff para verificador**.
9. Só então marque Slice 007, commit/push, responda REPORT_PATH e PARE.

## Requisitos

### R1. Meus Casos

Adicionar GET `exam_type=all|eda|colonoscopy`, fallback all, compondo com status e ocorrência. Todos default. Polling partial preserva tipo/status/q. Controle acessível e botão limpar restaura todos filtros conforme comportamento atual.

### R2. Encerrados

Busca/lista de encerrados recebe o mesmo filtro e compõe com nome/ocorrência/regras atuais. Tipo específico sem termo deve listar recentes do tipo se a tela já suporta listagem; se contrato atual exige termo, implementar comportamento definido no design de forma explícita e testar. Cards mostram badge persistido.

### R3. Reenvio corrigido exige tipo

Formulário sem opção prechecked; backend exige tipo válido e respeita flag para nova colonoscopia. `create_corrected_resubmission(..., exam_type=...)` persiste escolha no novo caso.

### R4. Tipo pode divergir

Original EDA → novo colonoscopia é válido com flag ativa. Original permanece EDA. Não exigir alerta adicional. Eventos de correção incluem tipo do novo caso quando útil, sem mudar semântica.

### R5. Não herança e pipeline preservados

Reenvio continua sem copiar PDF/anexos/artefatos/decisões; usa novo PDF/anexos e enfileira extração normal. Não reutilizar mecanismo same-case do Slice 006.

## Arquivos esperados/proibidos

Máximo 7 produto/teste + tasks:

1. `apps/intake/views.py`
2. `apps/intake/services.py`
3. `templates/intake/my_cases.html`
4. `templates/intake/closed_cases_search.html`
5. `templates/intake/corrected_resubmission.html`
6. até dois arquivos teste focados

Partial `_my_cases_content.html` pode substituir um template listado; qualquer oitavo exige revisão. Proibido models/migrations/FSM/pipeline/doctor/scheduler/dashboard/JS framework/novo endpoint salvo rota já existente.

## TDD

RED mínimo:

1. active all/eda/colon + composição status/q;
2. partial URL preserva parâmetros;
3. closed all/eda/colon + composição;
4. badges;
5. reenvio sem tipo/inválido rejeita;
6. colon com flag false rejeita;
7. EDA original → colon novo válido, original intacto;
8. não herança continua;
9. extração normal enfileirada;
10. role NIR preservada.

## Inspeções

```bash
rg -n "exam_type|Todos|EDA|Colonoscopia" apps/intake/views.py apps/intake/services.py templates/intake
rg -n "my_cases_partial_url|QUERY_STRING|status|q" apps/intake/views.py templates/intake/my_cases.html
rg -n "create_corrected_resubmission|exam_type|corrects_case" apps/intake/services.py apps/intake/views.py
rg -n "pdf_file|attachments|structured_data|suggested_action|enqueue_pdf_extraction" apps/intake/services.py

git diff --name-only "$BASE_REF"
git diff -- apps/cases apps/pipeline apps/doctor apps/scheduler apps/dashboard config
```

## Critérios/gates

- [ ] R1–R5; filtros compõem/polling; badges; tipo obrigatório sem default; diferença original/novo; flag; não herança; ≤7; baseline/gate/report.

## Gates de autoavaliação

Responder no relatório: query composition; polling; closed sem termo; teste tipo divergente; flag backend; same-case vs new-case não misturados; prova não herança; extras/pytest.

### Condições automáticas de INCOMPLETO

Baseline/RED/gate/report ausentes; filtros usam OR indevido/perdem polling; default não Todos; radio prechecked; tipo só validado client; flag burlada; original alterado; dados/documentos herdados; mecanismo same-case usado; model/pipeline alterado; role relaxada; >7; requisito sem prova; final falha/passed menor; commit prematuro.

## Relatório obrigatório

`/tmp/introduce-colonoscopy-exam-workflow-slice-007-report.md` com matriz, baseline, RED/GREEN/REFACTOR, snippets filtros/reenvio, inspeções, gate, baseline-final, gates, diff, rerun e Handoff R1–R5.

## Prompt pronto

```text
Read the full handoff in slice-007-nir-type-filters-resubmission.md. Implement ONLY Slice 007 on feature/colonoscopy-exam-workflow under the mandatory DeepSeek protocol: clean BASE_REF, full pytest baseline, real RED, minimal GREEN, narrow clean/DRY/YAGNI refactor, all inspections, exact gate and passed comparison. Failure means INCOMPLETE; no tasks/commit/push.

Add server-side Todos/EDA/Colonoscopia filters to NIR operational and closed cases, preserving composition and polling. Require an explicit type in corrected resubmission, allow a new colonoscopy case from an EDA original when intake flag is active, preserve the original and all existing non-inheritance/new-PDF pipeline rules. Do not touch model/FSM/pipeline/other roles or reuse same-case correction.

Create /tmp/introduce-colonoscopy-exam-workflow-slice-007-report.md with evidence and verifier handoff. If complete mark only Slice 007, commit, push, reply REPORT_PATH=... and STOP.
```
