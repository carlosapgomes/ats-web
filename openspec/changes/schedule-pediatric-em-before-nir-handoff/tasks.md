# Tasks: Agendar entrada pela Emergência Pediátrica antes do retorno ao NIR

## Ordem obrigatória dos slices

- [x] Slice 001 — Nova decisão pediátrica percorre agendamento CHD e retorna resultado completo ao NIR (`slices/slice-001-pediatric-scheduling-to-nir.md`)
- [x] Slice 002 — Continuidade pós-encerramento, histórico, dashboard e documentação (`slices/slice-002-pediatric-scheduled-lifecycle.md`)

> Implementar um slice por vez. Não iniciar o Slice 002 sem o relatório do Slice 001 aprovado pelo planner/verificador e confirmação explícita do usuário.

## Definition of Done do change

### Fluxo principal

- [x] Novas decisões médicas usam `pediatric_appt`, não `pediatric_em`.
- [x] A opção médica deixa explícito que o compartilhamento/entrada pela EM Pediátrica terá agendamento.
- [x] `accept + pediatric_appt` segue `DOCTOR_ACCEPTED → R3_POST_REQUEST → WAIT_APPT`.
- [x] O fluxo cria `SCHEDULER_REQUEST_POSTED` e não cria `ADMISSION_FLOW_OPERATIONAL_NOTICE`.
- [x] O modal médico informa corretamente o encaminhamento para agendamento.
- [x] CHD vê e processa o caso pela fila/formulário normal de agendamento.
- [x] Confirmação do CHD persiste data/hora e retorna o caso ao NIR.
- [x] Resultado NIR ativo e histórico mostram explicitamente “Entrada pela Emergência Pediátrica” e a data/hora.
- [x] Negativa do CHD retorna ao NIR com o motivo informado.

### Compatibilidade e continuidade

- [x] `pediatric_em` histórico permanece fluxo operacional sem agendamento.
- [x] Notices/ACKs históricos de `pediatric_em` continuam visíveis e funcionais.
- [x] Nenhum caso histórico é migrado, reaberto ou recebe agenda artificial.
- [x] Novo caso pediátrico confirmado é elegível para intercorrência `scheduled`.
- [x] Caso histórico `pediatric_em` continua elegível somente para `operational_notice`.
- [x] Busca/histórico do CHD inclui `scheduled` e `pediatric_appt`, mas não promove `pediatric_em` legado a agendado.
- [x] Dashboard mostra CHD como próximo responsável por `pediatric_appt` em `WAIT_APPT`.
- [x] Métrica funcional de EM Pediátrica consolida `pediatric_em` legado + `pediatric_appt` novo sem dupla contagem.

### Restrições e evidências

- [x] Nenhum model, migration, estado FSM, permissão ou pipeline LLM foi alterado.
- [x] Specs, manual e `PROJECT_CONTEXT.md` estão alinhados ao comportamento entregue.
- [x] TDD RED → GREEN → REFACTOR foi comprovado em cada slice.
- [x] Cada slice tem relatório temporário com matriz requisito/teste, RED/GREEN, snippets antes/depois, inspeções, baseline/final e handoff para verificador.
- [x] Em cada slice, `passed_final >= passed_baseline`, com exit code 0 e zero failures/errors.
- [x] Quality gate completo executado em cada slice:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Cada slice foi commitado e enviado à branch remota somente após todos os gates passarem.
