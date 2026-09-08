# Proposal: Causa "Preparo inadequado" para procedimento não realizado no pós-procedimento

## Problema

A equipe do Centro de Hemorragia Digestiva Alta (CHD) solicitou registrar,
no pós-procedimento, o caso do **exame interrompido por preparo inadequado**
(paciente compareceu, mas o preparo — tipicamente de colonoscopia — não
permitiu completar/iniciar o exame). A superfície atual oferece dois desfechos
por procedimento (realizado / não realizado) e, para não realizado, uma causa
estruturada fechada: absenteísmo, cancelamento por falta de recursos no dia
(com submotivo) e outras causas (texto livre). A falha de preparo hoje só
caberia em "Outras causas" — sem métrica própria, que é justamente o que o
CHD quer acompanhar.

## Decisão do dono (2026-09-08)

**Nova causa de não realização**, não um terceiro desfecho inicial
("realizado / não realizado / interrompido"). Motivação (design D1):

- o eixo binário do follow-up é "o exame agendado se completou como
  planejado?" — exame interrompido por preparo **não se completou** e,
  operacionalmente, exige novo agendamento (igual a qualquer não realizado);
- preserva a "taxa de realização" como proporção booleana limpa: um terceiro
  estado teria que colapsar para binário em todo agregado, ou inflaria a
  taxa com exames parciais;
- preparo inadequado é causa do lado do paciente — irmã natural do
  absenteísmo no eixo "por que não aconteceu";
- grava o número que o CHD quer (contagem + % sobre não realizados) direto
  no gráfico existente de "Causas de não realização";
- mantém o histórico append-only coerente (`performed` booleano no
  `CaseEvent`; eras anteriores naturalmente consistentes).

## Escopo

- `FollowUpNonPerformanceReason` ganha
  `INADEQUATE_PREP = "inadequate_prep", "Preparo inadequado"`,
  imediatamente após `ABSENTEEISM` (agrupamento de causas do paciente;
  a ordenação do gráfico de causas segue a ordem do enum).
- Migração choices-only em `apps/cases` (nenhuma mudança de constraint).
- Sem submotivo e sem texto livre para a nova causa (design D4 — YAGNI).
- Superfícies derivadas do enum NÃO mudam (form, filtro, CSV, gráfico, JS —
  design D5); apenas o comentário defasado do branch `else` em
  `_followup_history_rows` é atualizado.
- Manual do usuário §6 documenta a causa (lista de causas e regras).
- Delta de spec em `supervisor-appointment-follow-up` (enumeração de causas
  no corpo do requisito 1 + cenário novo de aceitação).

## Não-goals

- Terceiro estado de desfecho no nível de `performed` (rejeitado — D1).
- Submotivos da nova causa (ex.: "não iniciado" vs "iniciado e interrompido")
  ou distinção de exame parcial — futuro, se solicitado (D4).
- Mudar guarda de acesso, FSM, `CaseEvent` (formato do payload), URLs,
  nome do CSV ou qualquer identificador.
- Migração de dados: rows históricas permanecem como estão.

## Sucesso

- Supervisor do CHD registra procedimento não realizado com a causa
  "Preparo inadequado" (sem submotivo/texto) e a gravação persiste com
  espelho em `CaseEvent`.
- Combinações inválidas (causa nova + submotivo, ou + texto) seguem
  rejeitadas pelas validações genéricas existentes (service + form).
- Histórico: cards "Causas de não realização", filtro de causa e CSV
  exibem "Preparo inadequado" com submotivo/texto vazios — sem nenhuma
  mudança de código nessas superfícies (derivação do enum).
- Manual §6 documenta a causa; teste de artefatos de manual cobre.
- Gate final verde (ruff/format/mypy/pytest) e `openspec validate` OK.
