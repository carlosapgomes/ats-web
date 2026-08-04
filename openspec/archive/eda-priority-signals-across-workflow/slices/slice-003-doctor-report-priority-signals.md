# Slice 003: Topo e corpo do relatório médico usam os sinais persistidos

## Status

- [ ] Pendente

## Handoff para implementador LLM com contexto zero

Pré-condições: Slices 001 e 002 concluídos. Ecoendoscopia já segue EDA padrão. `Case.priority_signals` já existe, novos casos e abertos backfillados possuem sinais, há uma projeção compartilhada de badges e a fila médica já os mostra.

Este slice completa a experiência do médico ao abrir o caso. O topo e o corpo do relatório devem usar os sinais persistidos, não redetectar texto nem depender do resumo LLM. O presenter atual ainda recebe `structured_data`, `summary_text`, `suggested_action` e `source_text`; ingestão cáustica pode ter compatibilidade residual após Slice 002.

Leia:

- `AGENTS.md`, `PROJECT_CONTEXT.md`
- todos os artefatos e relatórios concluídos deste change
- `apps/doctor/reporting.py`
- `apps/doctor/presenters.py`
- `apps/doctor/views.py`
- `templates/doctor/decision.html`
- `templates/cases/_priority_signals.html`
- testes de presenter e view

Não altere pipeline, model, migration, scheduler ou intake.

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
médico abre caso com Case.priority_signals
→ prepare_doctor_case_report passa sinais persistidos
→ presenter projeta badges e linhas clínicas determinísticas
→ mesmo partial aparece no topo
→ Resumo clínico e Achados críticos evidenciam os sinais
```

## Requisitos funcionais

### R1. Entrada explícita no presenter

`DoctorReportPresenter` deve receber a coleção persistida de sinais por argumento explícito, com default seguro para testes/casos legados. `prepare_doctor_case_report()` deve passar `case.priority_signals`.

Não fazer o presenter consultar ORM. Não chamar `resolve_priority_signals()` nesta etapa. A fonte é o valor persistido.

### R2. Badges no contexto

O relatório deve expor `priority_signal_badges` usando o helper compartilhado criado no Slice 002. Não duplicar mapping de labels/classes no app doctor.

`templates/doctor/decision.html` deve incluir `cases/_priority_signals.html` imediatamente abaixo do título do relatório automático ou antes do metadata mutado. O container não aparece se não houver sinais.

### R3. Contextos prioritários no Resumo clínico

Quando houver um ou mais dos códigos abaixo:

- `pediatric`;
- `echoendoscopy`;
- `esophageal_dilation`;
- `gastrostomy`;

Adicionar deterministicamente uma única linha legível no início de `Resumo clínico`, por exemplo:

```text
Contextos prioritários: Pediatria — 10 anos; Ecoendoscopia; Dilatação esofágica.
```

Requisitos:

- usar projeção segura, sem texto bruto;
- respeitar ordem canônica;
- não remover `summary_text`;
- não repetir item;
- manter fallback atual quando summary vazio;
- evitar crescimento ilimitado; seis sinais conhecidos no máximo.

### R4. Alertas no início de Achados críticos

Quando persistidos:

- `foreign_body` → linha documental clara sobre suspeita/retirada;
- `caustic_ingestion` → linha documental com tempo quando `detail` existir.

Ambos devem aparecer antes de Hb/Plaquetas/INR/ECG e usar tom informativo, sem afirmar urgência/negativa automática.

Não duplicar ingestão cáustica em `clinical_alert_lines` e `achados_criticos`. Escolher a representação canônica baseada em persistência e remover/compatibilizar o caminho antigo com testes de regressão.

### R5. Procedimento canônico e coexistência

Preservar nomes existentes. Quando sinais procedimentais coexistirem, a linha de procedimento deve representar a combinação sem enum combinatório, por exemplo:

```text
procedimento solicitado: EDA com ecoendoscopia e dilatação esofágica
```

Ordem de fragmentos:

```text
ecoendoscopia → dilatação esofágica → gastrostomia
```

Corpo estranho continua sendo destacado como alerta e nome procedimental quando for o subtipo principal. Não produzir frases impossíveis por simples concatenação; manter implementação pequena e coberta.

### R6. Texto/relatório de auditoria

`build_text_report()` deve conter os mesmos contextos e alertas determinísticos usados na tela. Isso facilita teste/auditoria. Não incluir HTML.

### R7. Não regressão visual e de segurança

Preservar:

- sete blocos existentes;
- escaping automático do Django;
- alertas de caso anterior/correção;
- JSON colapsável;
- texto/PDF;
- formulário, lock e permissões.

Não criar CSS/JS se Bootstrap existente resolver.

## Arquivos esperados

1. `apps/doctor/reporting.py`
2. `apps/doctor/presenters.py`
3. `apps/doctor/views.py` somente se contexto explícito adicional for realmente necessário
4. `templates/doctor/decision.html`
5. `apps/doctor/tests/test_presenter.py`
6. `apps/doctor/tests/test_views.py`
7. `tasks.md` somente ao concluir

Não tocar model/migration/pipeline/scheduler/intake/shared mapping salvo correção mínima comprovadamente necessária. Justificar extra.

## TDD obrigatório

### RED

Criar primeiro testes para:

1. presenter recebe sinais persistidos e não depende de `source_text` para classificá-los;
2. contextos prioritários aparecem uma vez e antes do resumo LLM;
3. corpo estranho/cáustico aparecem antes dos labs;
4. cáustico inclui detail de tempo;
5. sem sinal persistido, texto bruto sozinho não cria novo destaque canônico (compatibilidade precisa seguir decisão do Slice 002);
6. coexistência eco+dilatação+gastro produz ordem estável;
7. `build_text_report()` contém as mesmas linhas;
8. view HTML mostra badges no topo e corpo;
9. caso vazio não mostra container;
10. conteúdo malicioso em `detail` é escapado no template.

Rodar RED:

```bash
uv run pytest apps/doctor/tests/test_presenter.py -q
uv run pytest apps/doctor/tests/test_views.py -q
```

### GREEN

Implementar somente R1–R7 e rodar os testes focados.

### REFACTOR

- Reusar `build_priority_signal_badges`.
- Separar montagem de linha de resumo e alertas em helpers pequenos.
- Não espalhar comparação de códigos pelo template.
- Remover caminho morto/duplicado do cáustico somente com regressão protegida.
- Não criar novo “oitavo bloco”.
- Não alterar summary persistido; enriquecer apenas apresentação.

## Checks de inspeção obrigatórios antes de concluir

```bash
rg -n "priority_signals|priority_signal_badges|build_priority_signal_badges" \
  apps/doctor/reporting.py apps/doctor/presenters.py apps/doctor/views.py templates/doctor/decision.html

rg -n "cases/_priority_signals.html|Resumo Clínico|Achados Críticos" templates/doctor/decision.html

rg -n "_detect_caustic_ingestion|clinical_alert_lines|caustic_ingestion" \
  apps/doctor/presenters.py apps/cases/priority_signals.py templates/doctor/decision.html

rg -n "doctor-report-grid|report.blocks.resumo_clinico|report.blocks.achados_criticos" templates/doctor/decision.html

rg -n "priority_signals" apps/pipeline apps/scheduler apps/intake templates/scheduler templates/intake || true

git diff --check
git status --short
```

Interpretar:

- presenter recebe persistência e usa mapping compartilhado;
- partial está no topo;
- não há duplicação runtime do detector cáustico;
- sete blocos permanecem;
- pipeline/scheduler/intake não foram ampliados neste slice.

## Critérios de sucesso binários

- [ ] Baseline e RED real registrados.
- [ ] Presenter recebe sinais explicitamente, sem ORM/detecção.
- [ ] Partial compartilhado aparece no topo.
- [ ] Resumo clínico inclui linha determinística de população/procedimentos.
- [ ] Achados críticos começa com corpo estranho/cáustico quando presentes.
- [ ] Tempo cáustico aparece quando persistido.
- [ ] `summary_text` e sete blocos são preservados.
- [ ] Combinações são ordenadas e sem enum combinatório.
- [ ] Text report e HTML estão alinhados.
- [ ] Payload vazio/malformado não quebra tela nem cria container.
- [ ] Escaping está coberto.
- [ ] Nenhum downstream/pipeline/model foi antecipado.
- [ ] Inspeções e quality gate completos passaram; final >= baseline.
- [ ] Relatório/task/commit/push corretos.

## Gates de autoavaliação

1. O presenter usa valor persistido ou redetecta texto? Deve usar persistido.
2. Como o mesmo mapping de labels/classes é reutilizado?
3. Qual teste prova ordem no Resumo clínico?
4. Qual teste prova ordem em Achados críticos?
5. Como duplicidade cáustica foi evitada?
6. O `summary_text` original foi alterado no banco? Deve ser “não”.
7. Os sete blocos continuam presentes?
8. Qual teste prova escaping do detail?
9. Quais arquivos extras foram tocados e por quê?
10. Scheduler/intake permanecem para próximos slices?

### Condições automáticas de INCOMPLETO

- qualquer condição geral do protocolo sem evidência;
- presenter consultar banco ou redetectar PDF;
- mapping de badge duplicado no doctor;
- badge não aparecer no topo;
- corpo depender apenas do one-liner;
- corpo estranho/cáustico não aparecerem antes de labs;
- cáustico aparecer duplicado;
- sete blocos, formulário, lock, permissão ou escaping regredirem;
- model/migration/pipeline/scheduler/intake serem alterados sem bloqueio comprovado;
- teste/lint/mypy falhar ou final < baseline;
- relatório ausente/incompleto;
- task/commit/push antes de todos os gates.

## Relatório obrigatório

Criar:

```text
/tmp/eda-priority-signals-slice-003-report.md
```

Incluir matriz R1–R7, baseline, RED/GREEN/REFACTOR, snippets de passagem de dados/presenter/template, HTML/text report demonstrativo, inspeções, quality gate, gates e `Handoff para verificador` com rerun/checklist.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, all OpenSpec artifacts for eda-priority-signals-across-workflow, completed Slice 001/002 reports, and current doctor reporting/presenter/view/templates/tests. Implement ONLY Slice 003.

Follow the DeepSeek4-Flash protocol exactly. Record a clean full pytest baseline before editing, create a real RED, implement minimal GREEN, refactor for clean code/DRY/YAGNI, run required rg checks and the full quality gate, and prove passed_final >= passed_baseline. Any missing or failing evidence means INCOMPLETE; do not update tasks.md or commit/push.

Make the doctor decision report consume Case.priority_signals explicitly. Reuse the shared badge projection/partial at the top. Add deterministic population/procedure context to Resumo clínico and foreign-body/caustic alerts to the start of Achados críticos, preserving the seven blocks, summary text, escaping, form, lock and permissions. Avoid duplicate caustic display and support coexistence without combined enums.

Do not alter model, migration, pipeline, scheduler, intake, FSM, forms or permissions. Run uv run ruff check .; uv run ruff format --check .; uv run mypy .; uv run pytest. Mark only Slice 003 if complete. Create /tmp/eda-priority-signals-slice-003-report.md with evidence, exact rerun commands and Handoff para verificador. Commit/push only if COMPLETE. Reply REPORT_PATH=/tmp/eda-priority-signals-slice-003-report.md and STOP.
```
