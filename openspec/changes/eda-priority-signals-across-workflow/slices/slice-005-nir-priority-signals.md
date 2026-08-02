# Slice 005: Badges persistidos acompanham o caso no NIR

## Status

- [ ] Pendente

## Handoff para implementador LLM com contexto zero

Pré-condições: Slices 001–004 concluídos. O mesmo `Case.priority_signals` já aparece para médico e CHD. Este slice fecha o fluxo exibindo os badges ao NIR sem alterar resultado, confirmação de recebimento ou históricos.

O NIR usa:

- `_my_cases_context()` + `templates/intake/_my_cases_content.html` para casos operacionais compartilhados (`status != CLEANED`);
- `templates/intake/case_detail.html` para detalhe/resultado e confirmação de recebimento;
- `templates/intake/closed_case_detail.html` para histórico encerrado;
- views distintas para detalhe aberto e fechado, mas ambas recebem `case`.

Regra de dados: a migration do Slice 002 backfillou somente casos abertos. Um caso novo com sinais mantém o campo quando depois vira `CLEANED`; portanto seu detalhe encerrado deve mostrar badges. Um `CLEANED` anterior ao change continua sem badge.

Leia todos os artefatos/relatórios, intake views/templates e testes antes de editar.

## Protocolo obrigatório para implementador DeepSeek4-Flash

Este slice será implementado por um modelo rápido e com tendência a concluir cedo demais. Portanto, siga este protocolo literalmente. **Se qualquer item abaixo falhar, o slice está INCOMPLETO**: não marque `tasks.md`, não faça commit/push e responda com bloqueio + evidência.

1. **Plano antes de editar**: escreva no relatório uma mini matriz `Requisito → arquivo(s) → teste(s)`. Não implemente requisito sem teste ou justificativa explícita.
2. **Baseline de pytest antes de editar**: registre `BASE_REF=$(git rev-parse HEAD)` e rode `uv run pytest` no estado inicial limpo. Cole no relatório o exit code e a linha de resumo. Se houver `failed/error` no baseline, pare e reporte INCOMPLETE/BLOQUEADO antes de codar.
3. **RED real**: crie/ajuste testes primeiro e rode o subconjunto alvo. Pelo menos um teste novo deve falhar pelo motivo esperado. Se o teste passar antes da implementação, ele não prova o comportamento; corrija o teste.
4. **GREEN mínimo**: implemente somente o necessário para os testes do slice passarem. Não faça refactor amplo, não toque em apps fora do escopo e não antecipe slices futuros.
5. **Verificação por inspeção**: além dos testes, rode buscas `rg`/inspeções descritas neste slice para comprovar os contratos críticos do slice.
6. **Quality gate completo e comparação pytest**: execute exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` e `uv run pytest`. O `uv run pytest` final deve ter exit code 0, zero failures/errors e contagem `passed` maior ou igual ao baseline. Se `failed > 0`, `errors > 0`, exit code != 0, ou `passed_final < passed_baseline`, o slice está INCOMPLETO.
7. **Relatório com evidência, não opinião**: cole comandos executados, exit codes, linhas de resumo do pytest baseline/final, testes RED/GREEN, snippets antes/depois e respostas objetivas aos gates. Inclua também `Handoff para verificador` com: arquivos alterados, comandos exatos para rerun, riscos/limitações e checklist dos requisitos R1..Rn. Inclua uma seção final `Status: COMPLETE` somente se todos os critérios estiverem comprovados.

## Objetivo do slice

```text
caso sinalizado aparece em Meus Casos
→ NIR identifica badges no card
→ abre detalhe/resultado e mantém os mesmos badges no topo
→ após encerramento, caso novo continua sinalizado no histórico
→ caso CLEANED antigo sem backfill continua sem badge
```

## Requisitos funcionais

### R1. Lista “Meus Casos”

Em `_my_cases_context()`, adicionar `priority_signal_badges` usando exclusivamente o helper compartilhado e `case.priority_signals`.

Em `_my_cases_content.html`, incluir o partial próximo ao nome/meta/status e antes de decisão/CTA, sem alterar grid, filtros, polling, locks ou continuidade de turno.

### R2. Detalhe operacional e resultado

No contexto/render de `case_detail`, disponibilizar badges compartilhados e incluir o partial no card superior, próximo ao nome/registro/status. Eles devem permanecer visíveis independentemente do tipo de `result_info`:

- processamento;
- revisão manual;
- decisão médica;
- agendamento confirmado/negado;
- vinda imediata/fluxo operacional;
- confirmação de recebimento.

Não duplicar badges dentro de cada branch de resultado.

### R3. Detalhe encerrado

No detalhe histórico `closed_case_detail`, exibir o partial no card superior quando o caso possui sinais persistidos.

Regras:

- caso novo que foi encerrado mantém sinais;
- caso antigo `CLEANED` sem backfill mostra nenhum container;
- não executar classificação tardia ao abrir histórico;
- não reprocessar LLM.

### R4. Fonte única e segurança

- usar `build_priority_signal_badges` e partial compartilhado;
- não importar `resolve_priority_signals`;
- não ler `extracted_text` para classificar na view;
- tolerar payload malformado;
- escapar `detail` malicioso;
- preservar ordem/classes dos outros papéis.

### R5. Não regressão NIR

Preservar:

- queryset compartilhado dos casos abertos;
- busca/filtros/polling;
- status e stepper;
- confirmação de recebimento e lock;
- resultados finais;
- anexos/PDF;
- correção/reenvio;
- comunicação operacional;
- permissões intranet/NIR;
- detalhe histórico e intercorrências.

### R6. Sem automação adicional

Não criar filtros por sinal, notificações, atribuição, agenda, FSM, permissão, nova busca ou badge de contagem. Não alterar model/migration/pipeline/doctor/scheduler.

## Arquivos esperados

1. `apps/intake/views.py`
2. `templates/intake/_my_cases_content.html`
3. `templates/intake/case_detail.html`
4. `templates/intake/closed_case_detail.html`
5. testes focados em `apps/intake/tests/test_case_detail.py` e/ou arquivo de view apropriado existente
6. testes de histórico somente se necessários para R3
7. `tasks.md` somente ao concluir

Manter ideal de cinco arquivos quando possível; se dois arquivos de teste forem necessários para respeitar boundaries existentes, justificar. Não alterar partial/helper compartilhado sem blocker comprovado.

## TDD obrigatório

### RED

Criar testes antes do código para:

1. “Meus Casos” mostra múltiplos sinais em ordem;
2. detalhe aberto mostra badges no topo antes do resultado/stepper;
3. cada tipo de resultado não precisa duplicar markup e mantém top badge;
4. caso novo `CLEANED` com sinais mostra no detalhe encerrado;
5. caso `CLEANED` antigo com `[]` não mostra container;
6. payload malformado não causa 500;
7. detail malicioso é escapado;
8. permissões NIR/intranet e confirmação de recebimento não regrediram;
9. filtros/links/locks principais continuam presentes.

Rodar classes/testes RED focados e registrar a falha esperada. Depois rodar arquivos intake relevantes completos.

### GREEN

Adicionar apenas projeção de contexto/includes necessários.

### REFACTOR

- Reusar partial/helper; nenhum mapping local.
- Evitar repetir include em cada branch de resultado.
- Se o template já recebe `case`, preferir contexto explícito e testável sem lógica complexa no template.
- Não criar helper genérico novo sem necessidade.
- Não tocar em fluxo de resultado.

## Checks de inspeção obrigatórios antes de concluir

```bash
rg -n "build_priority_signal_badges|priority_signal_badges" apps/intake/views.py

rg -n "cases/_priority_signals.html" \
  templates/intake/_my_cases_content.html templates/intake/case_detail.html templates/intake/closed_case_detail.html

rg -n "resolve_priority_signals|priority_signals|extracted_text" apps/intake/views.py templates/intake

rg -n "role_required\(\"nir\"\)|can_confirm_receipt|lock_token|result_info|closed_case_detail" \
  apps/intake/views.py templates/intake/case_detail.html templates/intake/closed_case_detail.html

rg -n "my_cases_partial_url|status_filter|compute_lock_display|CaseStatus.CLEANED" apps/intake/views.py

rg -n "priority_signal_badges" apps/doctor apps/scheduler apps/intake

git diff --check
git status --short
```

Interpretar:

- todos os pontos NIR usam o mesmo partial;
- intake não chama resolvedor/detector;
- não há include duplicado em branches de resultado;
- guards, locks, filtros e histórico permanecem;
- doctor/scheduler não foram alterados neste slice.

## Critérios de sucesso binários

- [ ] Baseline full pytest e RED real registrados.
- [ ] “Meus Casos” mostra badges persistidos.
- [ ] Detalhe/resultado aberto mostra badges no topo.
- [ ] Detalhe encerrado mostra sinais de casos novos persistidos.
- [ ] `CLEANED` antigo sem sinais não mostra container.
- [ ] Nenhuma classificação tardia/reexecução LLM ocorre.
- [ ] Payload malformado é seguro e detail é escapado.
- [ ] Ordem/classes são idênticas a médico/CHD.
- [ ] Resultados, locks, confirmação, filtros, permissões e histórico preservados.
- [ ] Nenhum model/pipeline/doctor/scheduler foi alterado.
- [ ] Inspeções e full quality gate verdes; final >= baseline.
- [ ] Todos os itens DoD do change foram revistos e marcados somente com evidência.
- [ ] Relatório/task/commit/push completos.

## Gates de autoavaliação

1. Quais telas NIR exibem badges?
2. O detalhe usa um único include fora dos branches de resultado?
3. Um caso `CLEANED` antigo é classificado ao abrir? Deve ser “não”.
4. Como um caso novo mantém sinais após ficar `CLEANED`?
5. Qual teste prova payload malformado e escaping?
6. Alguma view lê texto bruto para detectar? Deve ser “não”.
7. Filtros, locks, confirmação e permissões mudaram? Deve ser “não”.
8. Os mesmos helper/partial/ordem/classes são usados pelos três papéis?
9. Algum arquivo extra foi tocado? Justifique.
10. Há requisito do change sem evidência? Se sim, status INCOMPLETE.

### Condições automáticas de INCOMPLETO

- protocolo/baseline/RED/gates sem evidência;
- lista, detalhe aberto ou detalhe encerrado aplicável sem badge;
- caso antigo `CLEANED` ser classificado dinamicamente;
- intake redetectar texto ou duplicar mapping;
- include ser duplicado em cada branch de resultado;
- payload malformado causar 500 ou detail não escapar;
- resultado, lock, confirmação, filtro, permissão, busca, histórico ou comunicação regredir;
- model/migration/pipeline/doctor/scheduler ser alterado sem blocker aprovado;
- teste/lint/mypy falhar ou final < baseline;
- qualquer item DoD ser marcado sem evidência;
- relatório/handoff ausente;
- task/commit/push prematuros.

## Relatório obrigatório

Criar:

```text
/tmp/eda-priority-signals-slice-005-report.md
```

Incluir matriz R1–R6, baseline, RED/GREEN/REFACTOR, snippets de contexts/includes, evidência HTML para lista/detalhe aberto/encerrado, inspeções, regressões de permissão/lock/resultado, full gate, comparação, checklist completo do change e handoff para terceiro LLM.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, every artifact of eda-priority-signals-across-workflow and completed Slice 001–004 reports. Inspect intake open-list, open-detail/result, closed-detail views/templates/tests. Implement ONLY Slice 005.

Follow the DeepSeek4-Flash protocol exactly: clean full pytest baseline before editing, real RED, minimal GREEN, clean DRY/YAGNI refactor, mandatory rg inspection, full quality gate and passed_final >= passed_baseline. Any missing/failing evidence means INCOMPLETE; do not update tasks.md or commit/push.

Propagate the persisted priority badges to NIR Meus Casos, open detail/result and closed detail for cases that already carry signals. Use only the shared helper/partial. Never reclassify historical CLEANED cases, redetect extracted text or rerun LLM. Preserve results, locks, receipt confirmation, filters, polling, permissions, attachments, history and communication. Do not add automation or touch model/pipeline/doctor/scheduler.

Run uv run ruff check .; uv run ruff format --check .; uv run mypy .; uv run pytest. Review the entire change DoD and mark only evidence-backed items. Create /tmp/eda-priority-signals-slice-005-report.md with RED/GREEN, snippets, inspections, exact rerun commands and Handoff para verificador. Commit/push only if COMPLETE. Reply REPORT_PATH=/tmp/eda-priority-signals-slice-005-report.md and STOP.
```
