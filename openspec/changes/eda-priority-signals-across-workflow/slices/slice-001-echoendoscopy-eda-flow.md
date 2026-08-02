# Slice 001: Ecoendoscopia percorre contrato, scope, policy padrão e relatório médico

## Status

- [ ] Pendente

## Handoff para implementador LLM com contexto zero

O ATS Web é um monolito Django SSR de triagem de Endoscopia Digestiva Alta. O NIR envia PDF, LLM1 extrai JSON validado, o scope gate decide se o caso pertence ao fluxo EDA, a policy determinística avalia requisitos e o médico vê o relatório.

Hoje `echoendoscopy` não é subtipo suportado. Solicitações de ecoendoscopia podem terminar como `unknown`/`non_eda` e ir diretamente para revisão manual, sem chegar ao médico. Já existem `gastrostomy`, `esophageal_dilation` e `foreign_body`.

Leia completamente antes de editar:

- `AGENTS.md`
- `PROJECT_CONTEXT.md`
- `openspec/changes/eda-priority-signals-across-workflow/proposal.md`
- `openspec/changes/eda-priority-signals-across-workflow/design.md`
- `openspec/changes/eda-priority-signals-across-workflow/specs/eda-priority-signals/spec.md`
- `openspec/changes/eda-priority-signals-across-workflow/tasks.md`
- este slice
- `apps/pipeline/schemas/llm1.py`
- `apps/pipeline/llm1_service.py`
- `apps/pipeline/scope_detection.py`
- `apps/pipeline/policy/eda_preop_policy.py`
- `apps/doctor/presenters.py`
- testes correspondentes antes de propor alterações

Objetivo estrito: ecoendoscopia explícita deve seguir o fluxo EDA padrão e aparecer como `EDA com ecoendoscopia` no relatório médico atual. Não implemente ainda campo persistido `priority_signals`, badges compartilhados, migration/backfill, CHD ou NIR; pertencem aos slices seguintes.

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

Entregar a fatia vertical:

```text
relatório solicita ecoendoscopia
→ LLM1 aceita subtype echoendoscopy
→ scope gate confirma EDA
→ policy aplica requisitos padrão
→ caso chega ao médico
→ relatório mostra “EDA com ecoendoscopia”
```

Também consolidar a regra de precedência aprovada: se a solicitação atual contém EDA suportada ou ecoendoscopia, segue o fluxo EDA mesmo quando o texto também menciona CPRE/colonoscopia. Solicitação exclusivamente fora de EDA continua em revisão manual.

## Contexto técnico atual

- `EdaRequestedProcedureSubtype` e vários sets literais não incluem `echoendoscopy`.
- `_render_user_prompt()` contém instruções anexadas independentemente do prompt ativo no banco; deve ser atualizado junto do default/schema textual.
- `scope_detection.py` normaliza acentos/case/whitespace e usa texto, nome do procedimento, resumo, bullets e evidências.
- O `Motivo da Solicitação` tem tratamento especial para exame fora de escopo; a precedência precisa ser alterada com teste explícito, sem transformar qualquer menção histórica a EDA em solicitação atual.
- `evaluate_eda_preop_policy()` tem branch especial somente para `foreign_body`; ecoendoscopia deve entrar no caminho padrão.
- `DoctorReportPresenter._resolve_canonical_procedure_name()` exibe nome por subtipo.

## Requisitos funcionais

### R1. Enum e consistência LLM1

Adicionar `echoendoscopy` a todos os enums/conjuntos de subtipo suportado do contrato LLM1, incluindo:

- `EdaRequestedProcedureSubtype`;
- instruções de schema obrigatório;
- validação de alinhamento já existente entre `requested_procedure.subtype` e `rulebook_signals.eda_subtype`.

Manter `schema_version == "1.1"`. Payloads existentes continuam válidos. Subtipos divergentes conhecidos continuam falhando.

### R2. Prompt canônico e prompt renderizado

Atualizar `LLM1_DEFAULT_SYSTEM_PROMPT`, `LLM1_DEFAULT_USER_PROMPT`, `LLM1_REQUIRED_SCHEMA_INSTRUCTIONS` e/ou `_render_user_prompt()` somente onde necessário para que o prompt final:

- liste `echoendoscopy` como subtipo permitido;
- classifique como EDA: ecoendoscopia, eco-endoscopia, ultrassonografia endoscópica, ultrassom endoscópico e `EUS` em contexto procedimental;
- trate punção/PAAF/biópsia/FNA/FNB como modificadores da ecoendoscopia, sem subtipo novo;
- instrua menção de ecoendoscopia no `summary.one_liner` ou bullets;
- preserve instruções de pediatria, cáustico, exames rastreados e escopo existentes.

### R3. Detecção determinística conservadora

Adicionar ecoendoscopia ao scope detector.

Obrigatório:

- nomes completos normalizados são positivos em contexto de solicitação;
- `EUS` usa word boundary e exige contexto de solicitação/exame/procedimento;
- ocorrência `EUS` sem contexto não basta;
- nome do procedimento/subtipo estruturado positivo basta;
- modificadores de punção não mudam o subtipo;
- evitar falso positivo óbvio por menção apenas histórica quando `Motivo da Solicitação` ou procedimento estruturado indicarem outro exame.

### R4. Precedência de EDA suportada

Quando a solicitação atual contiver EDA suportada ou ecoendoscopia, o resultado efetivo deve ser EDA mesmo com menção simultânea a CPRE/colonoscopia.

Preservar:

- somente colonoscopia → `manual_review_required/non_eda`;
- somente CPRE classificada pelo LLM como `non_eda` e sem EDA/eco atual → revisão manual;
- `unknown` real sem sinal suportado → revisão manual.

Não implementar colonoscopia como suportada.

### R5. Policy padrão

Adicionar `echoendoscopy` aos conjuntos de subtipo suportado da policy, mas não criar bypass.

Testar ao menos:

- ecoendoscopia com exames mínimos ausentes recebe a mesma decisão/reason code da EDA padrão;
- ecoendoscopia com critérios atendidos recebe `criteria_met`;
- `foreign_body` preserva `foreign_body_exception`.

Não alterar thresholds nem requisitos.

### R6. Nome canônico no relatório médico

`DoctorReportPresenter` deve resolver:

```text
EDA com ecoendoscopia
```

O contexto atual `report.context.procedure` deve continuar exibindo esse texto no topo do relatório. Não criar badges compartilhados ainda.

### R7. Testes de integração do pipeline/scope

Além dos testes unitários, cobrir que um caso ecoendoscopia não recebe payload `manual_review_required` do scope. Se um teste de orchestrator focado puder provar o caminho sem ampliar excessivamente arquivos, adicioná-lo; caso contrário, justificar por que contrato + scope + policy cobrem a fatia e registrar a limitação.

## Arquivos esperados

Esperado tocar somente o necessário entre:

1. `apps/pipeline/schemas/llm1.py`
2. `apps/pipeline/llm1_service.py`
3. `apps/pipeline/scope_detection.py`
4. `apps/pipeline/policy/eda_preop_policy.py`
5. `apps/doctor/presenters.py`
6. `apps/pipeline/tests/test_llm1_service.py`
7. `apps/pipeline/tests/test_scope_detection.py`
8. `apps/pipeline/tests/test_eda_preop_policy.py`
9. `apps/doctor/tests/test_presenter.py`
10. `openspec/changes/eda-priority-signals-across-workflow/tasks.md` somente ao concluir

O número excede o ideal de cinco porque a entrega vertical atravessa contrato, scope, policy e saída médica. Não tocar `models.py`, migrations, scheduler/intake, FSM, permissões ou templates de badges. Qualquer arquivo extra exige justificativa objetiva no relatório.

## TDD obrigatório

### RED

Antes do código de produção, criar testes que falhem pelo motivo esperado:

1. schema aceita `echoendoscopy` alinhado;
2. schema rejeita `requested=echoendoscopy` versus rulebook conhecido divergente;
3. prompt final contém enum, sinônimos, modificadores e instrução de resumo;
4. cada nome completo de ecoendoscopia retorna EDA;
5. `EUS` contextual retorna EDA e `EUS` isolado não;
6. eco + CPRE e EDA + colonoscopia seguem EDA;
7. somente colonoscopia/CPRE preserva revisão manual;
8. eco segue policy padrão com sucesso e com exame ausente;
9. presenter mostra `EDA com ecoendoscopia`.

Rodar e registrar subconjuntos RED, por exemplo:

```bash
uv run pytest apps/pipeline/tests/test_llm1_service.py -q
uv run pytest apps/pipeline/tests/test_scope_detection.py -q
uv run pytest apps/pipeline/tests/test_eda_preop_policy.py -q
uv run pytest apps/doctor/tests/test_presenter.py -q
```

Pelo menos um teste novo deve falhar antes da implementação. Cole nomes, assertion/error e motivo.

### GREEN

Implementar somente os requisitos R1–R7. Rodar os mesmos subconjuntos até passarem.

### REFACTOR

- Centralizar termos de ecoendoscopia em constante pequena e nomeada.
- Não duplicar lógica de normalização.
- Evitar branches especiais na policy quando o comportamento é padrão.
- Preservar funções coesas e tipos explícitos.
- Não antecipar resolvedor persistido ou partial dos próximos slices.
- Remover código morto e comentários que contradigam a nova lista suportada.

## Checks de inspeção obrigatórios antes de concluir

Execute e interprete no relatório:

```bash
rg -n "echoendoscopy|ecoendoscopia|eco-endoscopia|ultrassonografia endosc|ultrassom endosc|\\bEUS\\b" \
  apps/pipeline/schemas/llm1.py apps/pipeline/llm1_service.py \
  apps/pipeline/scope_detection.py apps/pipeline/policy/eda_preop_policy.py \
  apps/doctor/presenters.py

rg -n "foreign_body_exception|if subtype == \"foreign_body\"" apps/pipeline/policy/eda_preop_policy.py

rg -n "manual_review_required|non_eda_request|unknown_exam_type" apps/pipeline/scope_detection.py

rg -n "priority_signals|_priority_signals" apps templates || true

git diff --check
git status --short
```

Interpretação obrigatória:

- `echoendoscopy` deve aparecer em contrato, prompt, scope, policy suportada e presenter.
- O único bypass deve continuar associado a `foreign_body`.
- Scope manual continua existindo para casos sem EDA suportada.
- `priority_signals` não deve ser criado neste slice.

## Critérios de sucesso binários

- [ ] Baseline full pytest registrado antes das edições, verde.
- [ ] RED real registrado com pelo menos um teste novo falhando pelo motivo esperado.
- [ ] `echoendoscopy` é enum válido e valida alinhamento.
- [ ] Prompt final contém sinônimos/modificadores e pede menção no resumo.
- [ ] Ecoendoscopia explícita segue EDA.
- [ ] `EUS` isolado não gera falso positivo.
- [ ] Solicitação mista com EDA/eco segue EDA.
- [ ] Solicitação exclusivamente fora de EDA preserva revisão manual.
- [ ] Ecoendoscopia usa policy padrão e não bypass.
- [ ] Corpo estranho preserva exceção.
- [ ] Relatório resolve `EDA com ecoendoscopia`.
- [ ] Nenhum model/migration/badge downstream foi implementado.
- [ ] Checks de inspeção foram executados e interpretados.
- [ ] Quality gate completo passou e `passed_final >= passed_baseline`.
- [ ] `tasks.md` foi marcado somente após todos os itens anteriores.
- [ ] Relatório temporário contém evidência e handoff completos.
- [ ] Commit e push foram realizados somente com status COMPLETE.

## Gates de autoavaliação

Responder objetivamente no relatório:

1. Quais fontes fazem ecoendoscopia ser reconhecida: enum, procedimento estruturado e texto?
2. Como `EUS` isolado é impedido de virar falso positivo?
3. Qual teste prova eco + exame fora de escopo seguindo EDA?
4. Qual teste prova que exame exclusivamente fora de escopo não regrediu?
5. Onde está provado que eco usa exames mínimos padrão?
6. Foi criado algum bypass específico para eco? A resposta deve ser “não”.
7. A exceção `foreign_body_exception` continua intacta?
8. O prompt renderizado final funciona mesmo com template ativo customizado?
9. Algum arquivo fora da lista foi tocado? Justifique.
10. O que ficou explicitamente para os próximos slices?

### Condições automáticas de INCOMPLETO

Marque como incompleto se ocorrer qualquer uma destas situações:

- teste planejado não foi escrito ou não foi executado;
- baseline de pytest antes de editar não foi executado ou não foi registrado com exit code e resumo;
- quality gate completo não foi executado;
- qualquer teste/lint/mypy falhou;
- pytest final teve exit code diferente de 0, `failed > 0` ou `errors > 0`;
- contagem final de `passed` ficou menor que a contagem baseline;
- relatório cita apenas número de `passed` sem registrar explicitamente zero failures/errors e exit code 0;
- `tasks.md` foi marcado apesar de falha ou pendência;
- contrato crítico do slice não foi verificado por teste ou inspeção;
- ecoendoscopia ainda puder cair em `unknown/non_eda` quando explicitamente solicitada;
- ecoendoscopia ganhar bypass de exames mínimos;
- caso exclusivamente fora de EDA passar a ser aceito;
- `EUS` isolado sem contexto for aceito;
- comportamento antigo de corpo estranho for removido sem regressão;
- model, migration, CHD/NIR ou badges persistidos forem antecipados;
- permissão, FSM, lock ou formulário for alterado;
- relatório temporário não for criado no caminho exigido.

## Relatório obrigatório

Criar exatamente:

```text
/tmp/eda-priority-signals-slice-001-report.md
```

Estrutura mínima:

```markdown
# Relatório Slice 001

## Status

Status: COMPLETE | INCOMPLETE

## Matriz requisito → arquivo(s) → teste(s)

## Baseline antes de editar

## RED

## GREEN

## REFACTOR

## Snippets antes/depois

## Checks de inspeção e interpretação

## Pytest baseline vs final

## Quality gate completo

## Gates de autoavaliação

## Riscos/limitações

## Handoff para verificador

- Arquivos alterados
- Comandos exatos para rerun
- Checklist R1..R7
- Riscos/limitações
```

Incluir `BASE_REF`, comandos, exit codes, resumo com `passed/failed/errors`, diff/snippets relevantes e hash/push somente se COMPLETE.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and every artifact under openspec/changes/eda-priority-signals-across-workflow relevant to Slice 001, including proposal.md, design.md, tasks.md, specs/eda-priority-signals/spec.md and slices/slice-001-echoendoscopy-eda-flow.md. Then inspect the current schema, LLM1 prompt/service, scope detector, preop policy, doctor presenter and their tests.

Implement ONLY Slice 001. Follow the DeepSeek4-Flash protocol literally: plan, full pytest baseline before editing, real RED, minimal GREEN, safe REFACTOR, inspection checks, full quality gate and baseline-vs-final comparison. If any required test/check/gate is missing or failing, if pytest final has any failure/error, or if passed_final < passed_baseline, report INCOMPLETE and do not update tasks.md or commit.

Deliver the vertical flow: echoendoscopy becomes a valid LLM1 subtype, explicit echoendoscopy is EDA even without the literal word EDA, supported EDA/echo wins in mixed requests, echo uses the standard preop policy, and the existing doctor report resolves “EDA com ecoendoscopia”. Preserve manual review for requests exclusively outside EDA and preserve the foreign-body exception.

Use TDD RED→GREEN→REFACTOR and enforce clean code, DRY, YAGNI, cohesive functions, clear names, low coupling and no dead code. Do not create priority_signals persistence, migrations, shared badges, CHD/NIR UI, routing automation, schedule rules, permissions or FSM changes. Do not implement colonoscopy.

Run exactly: uv run ruff check .; uv run ruff format --check .; uv run mypy .; uv run pytest. Update only the Slice 001 checkbox in tasks.md after every criterion passes. Create /tmp/eda-priority-signals-slice-001-report.md with RED/GREEN evidence, before/after snippets, inspections, quality gate, rerun commands and Handoff para verificador. Commit and push only if COMPLETE. Reply with REPORT_PATH=/tmp/eda-priority-signals-slice-001-report.md and STOP for planner review.
```
