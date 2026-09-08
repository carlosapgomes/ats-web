# Design: Causa "Preparo inadequado" no pós-procedimento

## D1 — Causa de não realização, não terceiro estado do desfecho

`ProcedureFollowUp.performed` permanece booleano: a pergunta binária é "o
exame agendado se completou como planejado?". Exame interrompido por preparo
inadequado não se completou e exige novo agendamento — operacionalmente
idêntico a "não realizado"; a causa responde "por quê". A alternativa
rejeitada (terceiro radio inicial "interrompido") foi avaliada e descartada:

- **Métrica**: "taxa de realização" é proporção booleana (`performed/total`).
  Um terceiro estado ou colapsa para binário em todo agregado (estado que só
  existe na entrada), ou conta exame parcial como realizado (infla a métrica
  de qualidade). Falha de preparo deve reduzir a taxa de realização.
- **Histórico append-only**: `CaseEvent.payload.outcomes[].performed` é
  booleano em todas as versões passadas; um terceiro estado criaria era
  inconsistente para coortes. Como causa, rows antigas são naturalmente
  consistentes (a causa não existia no vocabulário da época).
- **Blast radius**: terceiro estado exigiria reescrever `performed`, 6
  CheckConstraints, service, form, JS, filtros yes/no, CSV e agregados
  (~10+ arquivos). Como causa: 1 linha no enum + migração choices-only.
- **Filtro equivalente**: "exames interrompidos por preparo" continua
  extraível por `performed=no & reason=inadequate_prep` (o que o CHD quer
  medir). A única semântica perdida é "interrompido mas contado como
  realizado" — que não deve ser expressável.

## D2 — Rótulo e valor

`INADEQUATE_PREP = "inadequate_prep", "Preparo inadequado"`.

- Rótulo paralelo a "Absenteísmo": fraseado como **causa** — "interrompido"
  é o desfecho, não a causa. O manual explica a semântica completa ("o exame
  não foi realizado ou foi interrompido porque o preparo do paciente estava
  inadequado").
- Valor `inadequate_prep` (15 chars) cabe no `max_length=30` do campo
  `ProcedureFollowUp.non_performance_reason`.

## D3 — Posição no enum

Imediatamente após `ABSENTEEISM`: agrupa causas do lado do paciente
(absenteísmo, preparo) antes das do lado do hospital (recursos) e genérica
(other). `_FOLLOWUP_REASON_ORDER` (ordenação do gráfico de causas) deriva da
ordem de declaração do enum — a nova causa aparece entre absenteísmo e falta
de recursos nos cards do Histórico.

## D4 — Sem submotivo e sem texto livre (YAGNI)

A nova causa não exige submotivo nem texto. Se o CHD pedir depois a
distinção "não iniciado" vs "iniciado e interrompido", o padrão condicional
existente (`resource_shortage → submotivo`; grupo revelado por
`data-followup-detail` no JS) generaliza mecanicamente. Não antecipar.

## D5 — Superfícies derivadas do enum não mudam

Tudo abaixo deriva de `FollowUpNonPerformanceReason.choices/values` e herda
a causa nova sem edição: radios do form (`FollowUpForm`), validação
condicional do form e do service (genéricas: submotivo só em
`resource_shortage`, texto só em `other`), options do filtro de linha
(`_FOLLOWUP_REASON_OPTIONS`), labels do CSV (`_FOLLOWUP_REASON_LABELS`),
ordenação dos cards (`_FOLLOWUP_REASON_ORDER`), show/hide do JS (a causa não
tem grupo `data-followup-detail` — todos os grupos ficam ocultos).

Única edição residual: o comentário do branch `else` em
`_followup_history_rows` (`# absenteeism`) passa a
`# absenteeism/inadequate_prep` — verdade do comentário, sem mudança de
comportamento.

## D6 — Migração e integridade

Migração choices-only (`AlterField` em `ProcedureFollowUp.non_performance_reason`,
`0018_*`). As 6 CheckConstraints existentes permanecem válidas: a causa nova
não interage com submotivo/texto (D4). `CaseEvent` carrega a causa como
string no payload — formato inalterado. Sem migração de dados.

## D7 — Spec delta

`supervisor-appointment-follow-up` requisito 1: corpo passa a enumerar o
conjunto fechado de causas (incluindo a nova) + cenário de aceitação
"Registro com causa de preparo inadequado". Os cenários de validação
existente são genéricos ("motivo diferente de resource_shortage com
submotivo", etc.) e já cobrem a causa nova — sem alteração. A enumeração no
Purpose da spec é atualizada no archive (convenção do projeto). A spec
`supervisor-followup-history` é genérica quanto a causas ("causas de não
realização com breakdown de submotivos") — sem delta.
