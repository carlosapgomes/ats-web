# Slice 001: Decisão pediátrica → agendamento CHD → resultado NIR

## Handoff para implementador LLM com contexto zero

Leia integralmente, nesta ordem, antes de editar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/schedule-pediatric-em-before-nir-handoff/proposal.md`
4. `openspec/changes/schedule-pediatric-em-before-nir-handoff/design.md`
5. `openspec/changes/schedule-pediatric-em-before-nir-handoff/specs/pediatric-em-scheduled-admission/spec.md`
6. `openspec/changes/schedule-pediatric-em-before-nir-handoff/tasks.md`
7. este arquivo
8. implementação atual:
   - `apps/cases/admission.py`
   - `apps/doctor/forms.py`
   - `apps/doctor/views.py::doctor_submit`
   - `apps/scheduler/views.py::_scheduler_queue_context`
   - `apps/scheduler/views.py::scheduler_submit`
   - `apps/intake/views.py::case_detail`
   - `apps/intake/views.py::_build_historical_result_info`
   - `templates/intake/case_detail.html`
   - `templates/intake/closed_case_detail.html`
   - `static/js/decision.js`
   - `apps/doctor/tests/test_operational_admission_flows.py`

### Estado atual resumido

- `pediatric_em` é uma choice médica e pertence a `OPERATIONAL_NOTICE_FLOWS`.
- Aceite médico com esse valor registra notice operacional, pula `WAIT_APPT` e retorna imediatamente ao NIR.
- CHD apenas confirma ciência.
- O novo comportamento deve valer somente para decisões futuras.
- Casos históricos `pediatric_em` não podem mudar de semântica.

### Objetivo exato

Entregar o fluxo observável completo para uma nova decisão:

```text
médico aceita pediatric_appt
→ WAIT_APPT
→ CHD confirma data/hora OU nega com motivo
→ WAIT_R1_CLEANUP_THUMBS
→ NIR vê entrada pela EM Pediátrica + data/hora OU motivo da negativa
```

### Limites deste slice

Não implementar ainda:

- intercorrência pós-aceitação para `pediatric_appt`;
- busca histórica ampla do CHD;
- ajuste de próximo passo/métrica do dashboard;
- atualização do manual/`PROJECT_CONTEXT.md`.

Esses itens pertencem ao Slice 002. Não alterar model, migration, FSM, permissões, scheduler form, lock service ou pipeline LLM.

## Protocolo obrigatório para implementador DeepSeek4-Flash

Este slice será implementado por um modelo rápido e com tendência a concluir cedo demais. Siga este protocolo literalmente. **Se qualquer item falhar, o slice está INCOMPLETO**: não marque `tasks.md`, não faça commit/push e responda com bloqueio + evidência.

1. **Plano antes de editar**: registre no relatório uma matriz `Requisito → arquivo(s) → teste(s)`. Nenhum requisito pode ficar sem teste ou justificativa explícita.
2. **Baseline antes de editar**: registre `BASE_REF=$(git rev-parse HEAD)`, confirme `git status --short` limpo e rode `uv run pytest`. Registre comando, exit code e linha de resumo. Se houver `failed/error`, pare e reporte `INCOMPLETE/BLOQUEADO` antes de codar.
3. **RED real**: crie primeiro `apps/doctor/tests/test_pediatric_em_scheduling.py` e rode o subconjunto alvo. Pelo menos um teste novo deve falhar pelo motivo funcional esperado. Se passar antes da implementação, fortaleça o teste.
4. **GREEN mínimo**: implemente apenas o necessário para os requisitos deste slice. Não antecipe o Slice 002.
5. **REFACTOR seguro**: aplique clean code, DRY e YAGNI somente no trecho tocado; nomes claros, funções coesas, baixo acoplamento e nenhum código morto. Não crie registry, classe de estratégia ou abstração genérica.
6. **Inspeção obrigatória**: execute todos os comandos `rg` e inspeções definidos abaixo e interprete os resultados no relatório.
7. **Quality gate e comparação**: execute exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` e `uv run pytest`. O pytest final deve ter exit code 0, zero failures/errors e `passed_final >= passed_baseline`.
8. **Relatório factual**: inclua comandos, exit codes, resumos, RED/GREEN, snippets antes/depois, diff de arquivos, respostas aos gates e `Handoff para verificador`. Só escreva `Status: COMPLETE` se tudo estiver comprovado.
9. **Git e parada**: somente após aprovação de todos os gates, marque apenas o Slice 001 em `tasks.md`, faça commit, push, responda `REPORT_PATH=...` e PARE. Não inicie o Slice 002.

## Requisitos funcionais testáveis

### R1. Código novo para decisões futuras

- A choice médica funcional deve persistir `pediatric_appt`.
- Label deve deixar explícito que haverá agendamento, sem perder a referência à EM Pediátrica.
- `DoctorDecisionForm` deve aceitar `pediatric_appt`.
- POST manual de nova decisão com `pediatric_em` deve ser inválido; esse valor fica somente para leitura/compatibilidade histórica.
- `pediatric_appt` deve estar em um conjunto/helper compartilhado de fluxos agendados.
- `pediatric_em` deve continuar em `OPERATIONAL_NOTICE_FLOWS`; `pediatric_appt` não pode entrar nesse conjunto.

### R2. Aceite médico abre a agenda

Para `accept + pediatric_appt`:

- persistir decisão e médico normalmente;
- transicionar `WAIT_DOCTOR → DOCTOR_ACCEPTED → R3_POST_REQUEST → WAIT_APPT`;
- criar `CASE_READY_FOR_SCHEDULER` e `SCHEDULER_REQUEST_POSTED`;
- não criar `ADMISSION_FLOW_OPERATIONAL_NOTICE`;
- não criar `FINAL_REPLY_POSTED` na etapa médica;
- liberar lock médico como no sucesso atual.

Valor desconhecido não deve cair silenciosamente em agendamento; usar helpers semânticos explícitos conforme D4.

### R3. CHD processa pelo fluxo normal

Sem criar rota/form novo:

- caso `pediatric_appt` em `WAIT_APPT` aparece na fila CHD;
- card/confirm mostra label inequívoco de entrada pela EM Pediátrica com agendamento;
- confirmação exige data/hora e persiste `appointment_at`;
- confirmação registra `APPT_CONFIRMED` + `FINAL_REPLY_POSTED` e retorna ao NIR;
- nenhum card/ACK de “ciência operacional” é criado para o novo código.

### R4. NIR recebe ambas as informações após confirmação

No detalhe operacional em `WAIT_R1_CLEANUP_THUMBS` e no detalhe histórico após `CLEANED`, o NIR deve ver:

- `Agendamento Confirmado`;
- data/hora formatada;
- texto explícito `Entrada pela Emergência Pediátrica`;
- orientação de que o NIR comunicará a Emergência Pediátrica sobre a chegada da criança.

Antes da decisão do CHD, em `WAIT_APPT`, não deve existir resultado final pronto nem botão de confirmação de recebimento.

### R5. Negativa CHD retorna motivo ao NIR

Para caso `pediatric_appt` em `WAIT_APPT`:

- negativa exige motivo pelas regras existentes;
- persiste `appointment_status="denied"` e `appointment_reason`;
- registra `APPT_DENIED` + `FINAL_REPLY_POSTED`;
- retorna a `WAIT_R1_CLEANUP_THUMBS`;
- NIR vê `Agendamento Negado` e o motivo exato.

Não criar tratamento pediátrico paralelo para negativa.

### R6. Modal médico não promete ciência operacional

Ao aceitar `pediatric_appt`, `static/js/decision.js` deve mostrar mensagem de encaminhamento ao CHD/agendamento. Não pode mostrar “O CHD receberá apenas ciência operacional”.

### R7. Compatibilidade histórica mínima no mesmo deploy

Um caso já persistido com `pediatric_em` deve continuar:

- classificado como operacional;
- sem ser movido para `WAIT_APPT`;
- com notice/ACK operacional funcionando;
- com resultado NIR operacional e sem “Agendamento Confirmado” artificial.

Não migrar dados e não alterar eventos históricos.

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/cases/admission.py`
2. `apps/doctor/views.py`
3. `templates/doctor/decision.html` — o select atual possui options explícitas
4. `static/js/decision.js`
5. `templates/intake/case_detail.html`
6. `templates/intake/closed_case_detail.html`
7. `apps/doctor/tests/test_pediatric_em_scheduling.py` — novo
8. `openspec/changes/schedule-pediatric-em-before-nir-handoff/tasks.md` — apenas ao concluir

`apps/doctor/forms.py` não deve precisar mudar se continuar consumindo `ADMISSION_FLOW_CHOICES` compartilhado. `apps/scheduler/*` não deve precisar mudar neste slice: a fila/submit atuais já operam por `WAIT_APPT`.

Se tocar qualquer outro arquivo, explique no relatório por que o requisito não podia ser entregue com os arquivos acima. Mais de 7 arquivos de produto/teste (desconsiderando `tasks.md` e relatório temporário) torna o slice automaticamente INCOMPLETO até revisão do planner.

## Arquivos proibidos / fora de escopo

- `apps/cases/models.py`
- `apps/cases/migrations/**`
- `apps/pipeline/**`
- `apps/accounts/**`
- `apps/dashboard/**`
- `apps/cases/services.py` neste slice
- `apps/intake/views.py` neste slice, salvo bloqueio comprovado — os dados necessários já existem no contexto/case
- novos endpoints, roles ou permissões

## TDD obrigatório

### RED

Crie testes integrados focados no novo arquivo, reutilizando helpers existentes sem copiar fixtures extensas. Cobertura mínima:

1. form aceita `pediatric_appt` e rejeita novo POST `pediatric_em`;
2. médico aceita → `WAIT_APPT`, eventos corretos, notice/final reply ausentes;
3. fila CHD contém o caso e label pediátrico agendado;
4. CHD confirma → data/hora persistida → resultado NIR contém data + entrada EM Pediátrica;
5. resultado histórico `CLEANED` preserva data + entrada;
6. CHD nega → NIR contém motivo;
7. legado `pediatric_em` continua operacional.

Comando RED mínimo sugerido:

```bash
uv run pytest apps/doctor/tests/test_pediatric_em_scheduling.py -q
```

Registre pelo menos uma falha causada por comportamento atual, por exemplo: status atual `WAIT_R1_CLEANUP_THUMBS` em vez de `WAIT_APPT` ou ausência da choice `pediatric_appt`.

### GREEN

- Adicione constantes/helpers mínimos em `apps/cases/admission.py`.
- Troque a choice nova sem remover display/semântica histórica.
- Faça `doctor_submit` rotear apenas fluxos reconhecidos.
- Ajuste modal e cópia NIR mínima.
- Reutilize scheduler, FSM e resultado de negativa existentes.

### REFACTOR

- Remova igualdade/lista duplicada criada pelo próprio slice quando o helper compartilhado resolver.
- Preserve nomes de domínio claros (`pediatric_appt`, `SCHEDULED_ADMISSION_FLOWS`, `is_scheduled_admission_flow`).
- Não refatore maps não relacionados.
- Não introduza código para requisitos do Slice 002.

## Checks de inspeção obrigatórios antes de concluir

Execute e cole saída + interpretação no relatório:

```bash
rg -n "pediatric_appt|pediatric_em|SCHEDULED_ADMISSION_FLOWS|OPERATIONAL_NOTICE_FLOWS|is_scheduled_admission_flow" \
  apps/cases/admission.py apps/doctor/views.py apps/doctor/forms.py templates/doctor/decision.html

rg -n "ADMISSION_FLOW_OPERATIONAL_NOTICE|SCHEDULER_REQUEST_POSTED|FINAL_REPLY_POSTED" \
  apps/doctor/views.py apps/doctor/tests/test_pediatric_em_scheduling.py

rg -n "pediatric_appt|ciência operacional|CHD/agendamento" static/js/decision.js

rg -n "Entrada pela Emergência Pediátrica|Data/Hora|comunic" \
  templates/intake/case_detail.html templates/intake/closed_case_detail.html

rg -n "pediatric_appt|pediatric_em|Agendamento Negado|appointment_reason" \
  apps/doctor/tests/test_pediatric_em_scheduling.py

git diff --name-only "$BASE_REF"
git diff -- apps/cases/models.py apps/cases/migrations apps/pipeline apps/accounts apps/dashboard apps/cases/services.py apps/intake/views.py
```

Interpretação obrigatória:

- confirmar que `pediatric_em` permanece operacional histórico;
- confirmar que `pediatric_appt` é agendado e nunca aparece no map/caminho de notice operacional;
- confirmar que modal possui branch agendado para o código novo;
- confirmar copy NIR ativa e histórica;
- confirmar diff vazio nos arquivos proibidos.

## Critérios de sucesso binários

- [ ] R1 provado por teste de form/choice e inspeção das tuplas.
- [ ] R2 provado por status e eventos positivos/negativos.
- [ ] R3 provado por GET fila CHD e POST real de confirmação.
- [ ] R4 provado nos detalhes operacional e histórico.
- [ ] R5 provado por POST real de negativa e render do motivo no NIR.
- [ ] R6 provado por teste apropriado ou inspeção inequívoca do JS registrada.
- [ ] R7 provado por regressão de caso/evento `pediatric_em`.
- [ ] Nenhum model/migration/FSM/permissão/pipeline foi alterado.
- [ ] Nenhum requisito do Slice 002 foi antecipado.
- [ ] Baseline e quality gate completos passam com comparação registrada.
- [ ] Relatório existe no caminho exigido e contém handoff verificável.

## Gates de autoavaliação

Responda objetivamente no relatório:

1. Qual valor o formulário novo persiste e por que não reutiliza `pediatric_em`?
2. Quais eventos provam que o aceite entrou em agendamento? Qual evento proibido foi testado como ausente?
3. O NIR consegue confirmar recebimento enquanto o caso ainda está em `WAIT_APPT`? Mostre a evidência.
4. Onde estão visíveis, ao mesmo tempo, data/hora e entrada pela EM Pediátrica?
5. A negativa usa exatamente o fluxo normal e preserva o motivo? Qual teste prova isso?
6. O modal médico trata `pediatric_appt` como agendado?
7. Um notice histórico `pediatric_em` sem ACK ainda aparece para o CHD?
8. Algum arquivo fora da lista esperada foi tocado? Justifique individualmente.
9. `passed_final >= passed_baseline` com zero failures/errors e exit code 0?

### Condições automáticas de INCOMPLETO

Marque o slice como incompleto se ocorrer qualquer situação:

- baseline completo não executado/registrado antes de editar;
- baseline com falha e implementação iniciada mesmo assim;
- nenhum teste RED falhou pelo motivo esperado;
- qualquer requisito R1–R7 ficou sem teste ou inspeção justificável;
- `pediatric_em` foi removido de `OPERATIONAL_NOTICE_FLOWS`;
- `pediatric_appt` foi adicionado a `OPERATIONAL_NOTICE_FLOWS`;
- nova decisão cria notice operacional ou pula `WAIT_APPT`;
- resultado NIR confirmado omite data/hora ou via de entrada;
- negativa CHD omite o motivo no retorno ao NIR;
- caso histórico passa a parecer agendado sem data;
- model, migration, FSM, permissão, pipeline ou endpoint foi alterado;
- mais de 7 arquivos de produto/teste foram tocados sem aprovação do planner;
- quality gate completo não foi executado;
- qualquer lint, format, mypy ou pytest falhou;
- pytest final tem exit code != 0, `failed > 0`, `errors > 0` ou menos testes passados que o baseline;
- relatório informa apenas “passou” sem comandos, exit codes e resumos;
- `tasks.md` foi marcado antes de todos os gates;
- relatório temporário não existe no caminho exigido;
- commit/push foi feito apesar de pendência.

## Relatório markdown temporário obrigatório

Criar exatamente:

```text
/tmp/schedule-pediatric-em-before-nir-handoff-slice-001-report.md
```

Conteúdo mínimo:

```markdown
# Relatório — Slice 001

## Status
Status: COMPLETE | INCOMPLETE

## BASE_REF e working tree inicial

## Matriz requisito → arquivo(s) → teste(s)
| Requisito | Arquivos | Testes/inspeções |

## Baseline pytest
- comando
- exit code
- passed/failed/errors
- linha de resumo

## RED
- testes escritos primeiro
- comando e exit code
- falha esperada e por que prova o requisito

## GREEN
- comandos e resultados

## REFACTOR
- decisões de clean code/DRY/YAGNI

## Snippets antes/depois
- routing médico
- classificação admission flow
- resultado NIR ativo/histórico
- modal JS

## Checks de inspeção
- comandos rg/diff
- saída relevante
- interpretação

## Pytest baseline vs final
- passed_baseline
- passed_final
- failed/errors/exit code
- confirmação passed_final >= passed_baseline

## Quality gate completo
- ruff check
- ruff format --check
- mypy
- pytest

## Gates de autoavaliação
- respostas 1–9

## Escopo
- git diff --name-only
- justificativa para extras

## Handoff para verificador
- arquivos alterados
- requisitos R1–R7 com evidência
- comandos exatos para rerun
- riscos/limitações
- commit e branch
```

Incluir snippets reais e curtos, não apenas descrição. O verificador deve conseguir reproduzir a conclusão sem confiar na opinião do implementador.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and every artifact under openspec/changes/schedule-pediatric-em-before-nir-handoff listed in the Slice 001 handoff. Then implement ONLY slice-001-pediatric-scheduling-to-nir.md.

Follow the DeepSeek4-Flash protocol literally: record BASE_REF and clean status, run the full pytest baseline before editing, write a real failing RED test first, implement GREEN minimally, REFACTOR only the touched code with clean code/DRY/YAGNI, run all required rg/diff inspections, then run the exact full quality gate and compare baseline vs final. If any required test/check/gate is missing or failing, if pytest final has any failure/error or exit code != 0, or if passed_final < passed_baseline, report INCOMPLETE and do not update tasks.md or commit/push.

Deliver the complete new-decision path: pediatric_appt from doctor acceptance to WAIT_APPT, CHD confirmation or denial through the existing scheduler workflow, and NIR result with both scheduled date/time and explicit entry through the Pediatric Emergency Department, or denial reason. Preserve pediatric_em as historical operational-notice behavior. Do not touch models, migrations, FSM, permissions, pipeline, dashboard, post-acceptance services or unrelated apps. Do not implement Slice 002.

Create /tmp/schedule-pediatric-em-before-nir-handoff-slice-001-report.md with RED/GREEN evidence, before/after snippets, inspection outputs, full quality gate, baseline-vs-final comparison, objective gates and Handoff para verificador. Only after every criterion passes, mark only Slice 001 in tasks.md, commit with a traceable message, push the current branch, reply REPORT_PATH=/tmp/schedule-pediatric-em-before-nir-handoff-slice-001-report.md, and STOP for planner review.
```
