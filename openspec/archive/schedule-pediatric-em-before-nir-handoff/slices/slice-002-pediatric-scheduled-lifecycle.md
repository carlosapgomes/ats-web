# Slice 002: Lifecycle pediátrico agendado, histórico, dashboard e documentação

## Handoff para implementador LLM com contexto zero

### Pré-condição obrigatória

Este slice só pode começar depois que:

- Slice 001 estiver marcado como concluído em `tasks.md`;
- o relatório `/tmp/schedule-pediatric-em-before-nir-handoff-slice-001-report.md` tiver sido aprovado por planner/verificador;
- o usuário tiver confirmado explicitamente o próximo slice;
- a branch contiver `pediatric_appt`, `SCHEDULED_ADMISSION_FLOWS` e o fluxo principal passando.

Se qualquer pré-condição faltar, responda `INCOMPLETE/BLOQUEADO` e não edite.

Leia integralmente, nesta ordem:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/schedule-pediatric-em-before-nir-handoff/proposal.md`
4. `openspec/changes/schedule-pediatric-em-before-nir-handoff/design.md`
5. `openspec/changes/schedule-pediatric-em-before-nir-handoff/specs/pediatric-em-scheduled-admission/spec.md`
6. `openspec/changes/schedule-pediatric-em-before-nir-handoff/tasks.md`
7. este arquivo
8. relatório aprovado do Slice 001
9. implementação atual:
   - `apps/cases/admission.py`
   - `apps/cases/services.py::is_post_acceptance_issue_eligible`
   - `apps/cases/services.py::get_post_acceptance_issue_ineligibility_reason`
   - `apps/cases/services.py::open_post_acceptance_issue`
   - `apps/intake/views.py::closed_case_detail`
   - `apps/scheduler/views.py::_is_scheduler_historical_case`
   - `apps/scheduler/views.py::_scheduler_historical_queryset`
   - `apps/dashboard/views.py::_compute_admission_flow`
   - `apps/dashboard/views.py::_compute_next_step`
   - testes atuais de post-acceptance, histórico scheduler e dashboard
   - todas as ocorrências de EM Pediátrica em `docs/manual/manual-usuarios.md` e `PROJECT_CONTEXT.md`

### Estado esperado após Slice 001

- Novas decisões persistem `pediatric_appt` e passam pelo agendamento normal.
- `pediatric_em` continua operacional histórico.
- Resultado NIR principal já mostra via de entrada + data/hora ou negativa.
- Ainda há igualdades diretas com `"scheduled"` em serviços downstream, histórico e dashboard que não reconhecem `pediatric_appt`.

### Objetivo exato

Entregar a continuidade observável depois que o NIR encerra um novo caso pediátrico agendado:

```text
pediatric_appt confirmado e CLEANED
→ NIR abre intercorrência scheduled
→ caso volta a WAIT_APPT
→ CHD responde como agenda
```

Ao mesmo tempo, alinhar histórico CHD, próximo responsável, métrica funcional e documentação, preservando integralmente `pediatric_em` histórico como `operational_notice`.

## Protocolo obrigatório para implementador DeepSeek4-Flash

Este slice será implementado por modelo rápido. **Qualquer falha torna o slice INCOMPLETO**: não marque tasks, não faça commit/push e reporte evidência.

1. **Plano antes de editar**: registre matriz `Requisito → arquivo(s) → teste(s)/inspeção`.
2. **Baseline antes de editar**: registre `BASE_REF=$(git rev-parse HEAD)`, `git status --short` limpo e execute `uv run pytest`. Se houver qualquer failure/error, pare antes de editar.
3. **RED real**: escreva primeiro `apps/cases/tests/test_pediatric_em_scheduled_downstream.py`; rode-o e registre falha funcional esperada, como inelegibilidade scheduled, ausência no histórico ou “Pendente: NIR”.
4. **GREEN mínimo**: substitua igualdades dispersas apenas onde necessário por constantes/helpers já entregues no Slice 001.
5. **REFACTOR seguro**: clean code, DRY e YAGNI; não criar serviço genérico novo nem mover grandes blocos entre apps.
6. **Inspeções**: execute todos os `rg`/diff abaixo e interprete contratos antigo/novo.
7. **Quality gate completo**: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`, `uv run pytest`; final com exit 0, zero failures/errors e `passed_final >= passed_baseline`.
8. **Documentação factual**: atualize manual e contexto somente para comportamento efetivamente testado; preserve nota histórica quando necessário.
9. **Conclusão controlada**: só depois de todos os gates marque Slice 002/DoD aplicável, gere relatório, commit, push e pare.

## Requisitos funcionais testáveis

### R1. Intercorrência de novo caso usa contexto agendado

Para `pediatric_appt`, `doctor_decision="accept"`, `appointment_status="confirmed"`, status `CLEANED` e sem issue ativa:

- `is_post_acceptance_issue_eligible(..., context="scheduled")` retorna `True`;
- contexto `operational_notice` retorna `False`;
- abertura cria `POST_ACCEPTANCE_ISSUE_OPENED` com `context="scheduled"` e `admission_flow="pediatric_appt"`;
- caso transiciona `CLEANED → WAIT_APPT`;
- snapshot de agenda e locks/eventos existentes permanecem conforme serviço atual.

`get_post_acceptance_issue_ineligibility_reason()` deve usar a mesma definição compartilhada de fluxo agendado.

### R2. Legado continua intercorrência operacional

Para `pediatric_em` histórico `CLEANED`:

- contexto `scheduled` é inelegível;
- contexto `operational_notice` permanece elegível;
- abertura operacional mantém o caso `CLEANED`;
- ACK do CHD não altera nenhum `appointment_*`;
- notice/issue operacional continua usando os serviços existentes.

Não converter legado nem inferir contexto por presença/ausência de data.

### R3. Intake usa semântica compartilhada

`apps/intake/views.py::closed_case_detail` deve selecionar/explicar o contexto com helper/conjunto compartilhado, evitando igualdade exclusiva `doctor_admission_flow == "scheduled"` para a semântica de “agendado”.

- Novo pediátrico confirmado mostra formulário de intercorrência que envia ao agendador.
- Legado pediátrico mantém texto de aviso apenas para ciência.
- Sem mudança de permissão, rota, formulário ou redirect seguro.

### R4. Histórico CHD inclui novo agendado e exclui legado operacional

- `_is_scheduler_historical_case()` aceita `scheduled` e `pediatric_appt` quando appointment status permitido.
- `_scheduler_historical_queryset()` aplica `doctor_admission_flow__in=SCHEDULED_ADMISSION_FLOWS`.
- Pesquisa histórica encontra novo caso pediátrico confirmado/negado/cancelado.
- `pediatric_em` sem agenda não é promovido ao histórico agendado.
- Decorators, autorização por notificação e escopo dos demais fluxos permanecem.

### R5. Dashboard aponta responsável e consolida métrica

- `pediatric_appt` em `WAIT_APPT` retorna `Pendente: agendador`.
- `pediatric_em` histórico operacional não é redefinido como agenda.
- `_compute_admission_flow()` mantém a chave pública `pediatric_em` e conta `doctor_admission_flow__in=("pediatric_em", "pediatric_appt")`.
- Um caso de cada valor produz contagem 2, sem dupla contagem.
- Demais quatro categorias mantêm suas contagens atuais.

### R6. Documentação operacional alinhada

Atualizar todas as afirmações atuais de que EM Pediátrica é fluxo sem agendamento:

- o médico escolhe compartilhamento/entrada pela EM Pediátrica com agendamento;
- o CHD agenda ou nega com motivo;
- o NIR recebe via de entrada + data/hora e comunica a equipe;
- fluxos realmente sem agendamento continuam `immediate`, `pre_icu`, `ward_icu_backup`;
- intercorrência de novo caso pediátrico agendado segue o modo scheduled;
- compatibilidade `pediatric_em` é detalhe histórico interno, não instrução para novas decisões.

Atualizar `PROJECT_CONTEXT.md` sem inflar o documento e sem declarar testes/contagens não executados.

## Arquivos esperados

Máximo previsto e autorizado: 7 arquivos.

1. `apps/cases/services.py`
2. `apps/intake/views.py`
3. `apps/scheduler/views.py`
4. `apps/dashboard/views.py`
5. `apps/cases/tests/test_pediatric_em_scheduled_downstream.py` — novo
6. `docs/manual/manual-usuarios.md`
7. `PROJECT_CONTEXT.md`
8. `openspec/changes/schedule-pediatric-em-before-nir-handoff/tasks.md` — artefato de status, somente ao concluir

A exceção ao ideal de 5 arquivos está registrada no design: o mesmo conceito downstream é projetado por quatro apps e duas fontes documentais. Dividi-lo em slices horizontais criaria estados intermediários inconsistentes. Se qualquer oitavo arquivo de produto/teste/doc for necessário, pare e peça revisão do planner antes de ampliar.

## Arquivos proibidos / fora de escopo

- `apps/cases/models.py`
- `apps/cases/migrations/**`
- `apps/doctor/**` e `static/js/decision.js` — já concluídos no Slice 001
- templates NIR/CHD — não são necessários para os contextos previstos
- `apps/pipeline/**`
- `apps/accounts/**`
- rotas, decorators, forms e lock services
- alteração do código interno definido no Slice 001

## TDD obrigatório

### RED

Criar teste focado com cobertura mínima:

1. `pediatric_appt` confirmado/CLEANED é eligible scheduled e abre issue para `WAIT_APPT`;
2. `pediatric_em` legado é inelegível scheduled, elegível operational e preserva `appointment_*` no ciclo/ACK relevante;
3. histórico/query CHD aceita novo e exclui legado operacional;
4. dashboard retorna `Pendente: agendador` para novo `WAIT_APPT`;
5. métrica consolida um antigo + um novo em 2 e preserva categorias não relacionadas;
6. GET/POST NIR de intercorrência usa mensagem/contexto scheduled para novo código.

Comando RED sugerido:

```bash
uv run pytest apps/cases/tests/test_pediatric_em_scheduled_downstream.py -q
```

Se importar helpers privados de views tornar o teste frágil, prefira cliente Django e comportamento renderizado; imports diretos são aceitáveis para funções puras já testadas assim no projeto. Não copie centenas de linhas de fixtures.

### GREEN

- Importe `SCHEDULED_ADMISSION_FLOWS`/helper em services/intake/scheduler/dashboard.
- Substitua somente igualdades que representam “fluxo agendado”.
- Preserve igualdade literal quando ela representar especificamente a categoria comum `scheduled`, não semântica ampla.
- Consolide métrica com `__in`.
- Atualize docs após testes verdes do comportamento.

### REFACTOR

- Elimine listas duplicadas introduzidas pelo slice.
- Não crie novo módulo utilitário: `apps/cases/admission.py` já é a boundary correta.
- Confirme que nomes e mensagens distinguem `scheduled` (contexto) de código `scheduled` (valor comum).
- Remova imports não usados e mantenha mypy/ruff limpos.

## Checks de inspeção obrigatórios antes de concluir

Execute e registre saída + interpretação:

```bash
rg -n 'doctor_admission_flow == "scheduled"|doctor_admission_flow != "scheduled"|doctor_admission_flow="scheduled"' \
  apps/cases/services.py apps/intake/views.py apps/scheduler/views.py apps/dashboard/views.py

rg -n "SCHEDULED_ADMISSION_FLOWS|is_scheduled_admission_flow|pediatric_appt|pediatric_em|OPERATIONAL_NOTICE_FLOWS" \
  apps/cases/services.py apps/intake/views.py apps/scheduler/views.py apps/dashboard/views.py

rg -n "_is_scheduler_historical_case|_scheduler_historical_queryset|doctor_admission_flow__in" \
  apps/scheduler/views.py

rg -n "_compute_admission_flow|_compute_next_step|Pendente: agendador|Pendente: NIR" \
  apps/dashboard/views.py

rg -n -C 3 "EM pediátrica|Emergência Pediátrica|Compartilhamento com a Pediatria" \
  docs/manual/manual-usuarios.md PROJECT_CONTEXT.md

rg -n "pediatric_appt|pediatric_em|scheduled|operational_notice|appointment_" \
  apps/cases/tests/test_pediatric_em_scheduled_downstream.py

git diff --name-only "$BASE_REF"
git diff -- apps/cases/models.py apps/cases/migrations apps/doctor apps/pipeline apps/accounts templates
```

Interpretação obrigatória:

- toda igualdade restante com `"scheduled"` nos quatro módulos deve ser classificada como correta/específica ou dívida fora de escopo; se representar semântica ampla, corrigir;
- confirmar novo código somente no conjunto agendado;
- confirmar legado somente no conjunto operacional;
- confirmar histórico usa `__in` e dashboard não atribui novo WAIT_APPT ao NIR;
- confirmar que nenhuma instrução do manual manda CHD apenas confirmar ciência para novas decisões pediátricas;
- confirmar diff vazio nos arquivos proibidos.

## Critérios de sucesso binários

- [ ] R1 prova lifecycle scheduled completo até `WAIT_APPT`.
- [ ] R2 prova preservação operacional e imutabilidade da agenda legada.
- [ ] R3 prova contexto/mensagem corretos no NIR.
- [ ] R4 prova inclusão/exclusão no histórico CHD sem relaxar autorização.
- [ ] R5 prova próximo responsável e métrica consolidada.
- [ ] R6 passa inspeção documental de todas as ocorrências relevantes.
- [ ] Nenhum model/migration/FSM/rota/form/permissão/template foi alterado.
- [ ] Nenhuma categoria não relacionada mudou de comportamento ou contagem.
- [ ] Baseline e quality gate completo passam com `passed_final >= passed_baseline`.
- [ ] Tasks e DoD só foram marcados após evidência completa.
- [ ] Relatório temporário contém handoff reproduzível para terceiro LLM.

## Gates de autoavaliação

Responder no relatório:

1. Por que `pediatric_appt` é eligible no contexto `scheduled` apesar de seu valor não ser a string `scheduled`?
2. Que teste prova `CLEANED → WAIT_APPT` para a intercorrência nova?
3. Que teste prova que `pediatric_em` legado fica `CLEANED` e não muda `appointment_*`?
4. Histórico CHD inclui quais códigos e exclui qual código histórico? Mostre query/teste.
5. Para `pediatric_appt` em `WAIT_APPT`, qual é o próximo responsável e qual teste prova?
6. Como a métrica evita dividir ou contar duas vezes a categoria EM Pediátrica?
7. Quais ocorrências documentais antigas foram corrigidas?
8. Há igualdade restante `== "scheduled"` representando erroneamente todos os fluxos agendados?
9. Algum arquivo fora da lista foi tocado? Justifique.
10. `passed_final >= passed_baseline`, exit 0, zero failures/errors?

### Condições automáticas de INCOMPLETO

Marque incompleto se:

- pré-condição do Slice 001/aprovação/confirmação não foi atendida;
- baseline não foi executado antes de editar ou contém falhas;
- RED real não foi registrado;
- `pediatric_appt` continua inelegível no contexto scheduled;
- `pediatric_em` legado passa a reabrir `WAIT_APPT` como scheduled;
- ACK operacional legado altera qualquer `appointment_*`;
- histórico CHD continua excluindo novo pediátrico ou inclui legado sem agenda;
- dashboard mostra `Pendente: NIR` para novo caso em `WAIT_APPT`;
- métrica não consolida antigo/novo ou duplica caso;
- manual ainda orienta “não abrir agendamento” para novas decisões de EM Pediátrica;
- autorização, rota, form, template, model, migration, FSM, pipeline ou lock foi alterado;
- mais de 7 arquivos previstos foram tocados sem aprovação prévia;
- teste planejado/check de inspeção faltou;
- quality gate não foi completo ou qualquer comando falhou;
- pytest final tem exit != 0, failure/error ou `passed_final < passed_baseline`;
- relatório não contém evidência factual e handoff;
- tasks foram marcadas ou commit/push feito com pendência;
- relatório não foi criado no caminho exato.

## Relatório markdown temporário obrigatório

Criar exatamente:

```text
/tmp/schedule-pediatric-em-before-nir-handoff-slice-002-report.md
```

Conteúdo mínimo:

```markdown
# Relatório — Slice 002

## Status
Status: COMPLETE | INCOMPLETE

## Pré-condições e BASE_REF

## Matriz requisito → arquivo(s) → teste(s)

## Baseline pytest
- comando, exit code, passed/failed/errors

## RED
- teste, comando, falha esperada

## GREEN
- implementação mínima e resultados

## REFACTOR
- clean code/DRY/YAGNI

## Snippets antes/depois
- eligibility/reason service
- seleção de contexto NIR
- histórico CHD
- dashboard next step/métrica
- documentação operacional

## Checks de inspeção
- comandos, saída relevante e interpretação

## Pytest baseline vs final

## Quality gate completo

## Gates de autoavaliação 1–10

## Escopo e justificativas

## Handoff para verificador
- arquivos alterados
- checklist R1–R6
- comandos exatos para rerun
- riscos/limitações
- confirmação de compatibilidade histórica
- commit/branch
```

O handoff deve permitir que terceiro LLM valide novo e legado sem consultar a conversa original.

## Prompt pronto para implementador LLM

```text
First verify that Slice 001 of schedule-pediatric-em-before-nir-handoff is completed, approved, present on the branch, and that the user explicitly authorized Slice 002. If not, report INCOMPLETE/BLOCKED and do not edit.

Read AGENTS.md, PROJECT_CONTEXT.md, all change artifacts, this slice, and the approved Slice 001 report. Implement ONLY slice-002-pediatric-scheduled-lifecycle.md. Follow the DeepSeek4-Flash protocol literally: clean baseline and full pytest before editing, real RED first, minimal GREEN, narrow REFACTOR with clean code/DRY/YAGNI, every required rg/diff inspection, exact full quality gate, and baseline-vs-final evidence. Any missing/failing gate, any pytest failure/error/exit != 0, or passed_final < passed_baseline means INCOMPLETE; do not update tasks.md or commit/push.

Treat pediatric_appt as scheduled across post-acceptance eligibility, NIR issue context, scheduler history, dashboard next owner and consolidated metrics. Preserve pediatric_em as historical operational_notice with immutable appointment fields. Update the user manual and PROJECT_CONTEXT.md to describe the delivered behavior. Do not touch models, migrations, FSM, routes, forms, permissions, templates, doctor flow, pipeline or accounts.

Create /tmp/schedule-pediatric-em-before-nir-handoff-slice-002-report.md with RED/GREEN, before/after snippets, inspection evidence, full quality gate, baseline comparison, objective gates and Handoff para verificador. Only after every criterion passes, mark Slice 002 and applicable DoD items, commit, push, reply REPORT_PATH=/tmp/schedule-pediatric-em-before-nir-handoff-slice-002-report.md, and STOP.
```
