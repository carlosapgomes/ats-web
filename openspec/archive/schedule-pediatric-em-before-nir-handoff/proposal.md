# Proposal: Agendar entrada pela Emergência Pediátrica antes do retorno ao NIR

**Change ID**: `schedule-pediatric-em-before-nir-handoff`  
**Tipo**: FEATURE  
**Risco**: PROFISSIONAL  
**Classificação**: `classify-change-risk` → PROFESSIONAL; `design.md` obrigatório.

## Problema

No fluxo médico **Compartilhar com EM pediátrica**, o valor persistido atual é `pediatric_em` e ele pertence ao conjunto de fluxos sem agendamento.

Depois do aceite médico, o sistema atualmente:

1. registra `ADMISSION_FLOW_OPERATIONAL_NOTICE` para o CHD;
2. não entra em `WAIT_APPT`;
3. publica imediatamente o resultado para o NIR;
4. orienta o NIR a acionar a Emergência Pediátrica;
5. permite ao CHD somente confirmar ciência, sem informar data/hora.

Esse comportamento não atende à operação validada com os usuários. O NIR precisa receber, no mesmo resultado final:

1. a informação explícita de que a criança deverá entrar pela **Emergência Pediátrica**;
2. a **data/hora já agendada** pelo CHD.

## Relação com o change anterior

Este change **altera prospectivamente** a decisão registrada em `openspec/changes/doctor-admission-operational-flows/`: o valor histórico `pediatric_em` continua obedecendo ao contrato antigo, enquanto novas decisões usarão uma variante interna agendada. Os artefatos anteriores não devem ser reescritos, pois documentam a origem e o comportamento dos registros históricos.

## Objetivo

Fazer com que novas decisões médicas desse item passem pelo fluxo normal de agendamento antes do retorno final ao NIR:

```text
Médico aceita “Compartilhar com EM pediátrica”
→ caso entra em WAIT_APPT
→ CHD confirma data/hora ou nega com motivo
→ resultado retorna ao NIR
→ NIR vê via de entrada + data/hora, ou motivo da negativa
→ NIR confirma recebimento
```

## Escopo incluído

- Preservar o nome funcional da escolha médica, deixando explícito que haverá agendamento.
- Usar um código interno novo e compatível com `Case.doctor_admission_flow.max_length=15` para distinguir novas decisões agendadas dos casos históricos operacionais.
- Encaminhar novas decisões pediátricas ao `WAIT_APPT` usando as transições FSM existentes.
- Fazer o CHD processar esses casos pela fila e formulário normais de agendamento.
- Em confirmação, retornar ao NIR a data/hora e a informação explícita de entrada pela Emergência Pediátrica.
- Em negativa do CHD, retornar ao NIR o motivo, como no fluxo normal de agendamento.
- Preservar casos históricos `pediatric_em` como ciência operacional, sem backfill ou reabertura.
- Alinhar histórico do CHD, intercorrência pós-aceitação, próximo passo do dashboard e métricas ao novo comportamento.
- Atualizar documentação operacional e contexto do projeto.
- Adicionar cobertura TDD end-to-end e de regressão histórica.

## Fora de escopo

- Integrar a equipe da Emergência Pediátrica ao sistema.
- Criar papel de usuário para a Emergência Pediátrica.
- Enviar SMS, push ou email operacional.
- Alterar os fluxos `immediate`, `pre_icu` ou `ward_icu_backup`.
- Criar novo estado FSM.
- Alterar o modelo `Case` ou criar migration.
- Migrar ou reabrir casos históricos `pediatric_em`.
- Criar feature flag, tabela de domínio ou abstração genérica de workflow.
- Alterar regras clínicas, pipeline LLM ou sinalização pediátrica.

## Critérios de sucesso

- [ ] Nova escolha médica de compartilhamento/entrada pela EM Pediátrica persiste o código interno agendado definido no design.
- [ ] Após o aceite médico, o caso fica em `WAIT_APPT` e cria `SCHEDULER_REQUEST_POSTED`.
- [ ] A nova decisão não cria `ADMISSION_FLOW_OPERATIONAL_NOTICE`.
- [ ] O CHD vê o caso na fila de agendamento e entende que a entrada será pela Emergência Pediátrica.
- [ ] O CHD consegue confirmar data/hora pelo formulário normal.
- [ ] Após confirmação, o NIR vê simultaneamente data/hora e via de entrada pela Emergência Pediátrica.
- [ ] Após negativa, o NIR vê “Agendamento Negado” e o motivo informado pelo CHD.
- [ ] O resultado só fica disponível para confirmação final do NIR após confirmação ou negativa do CHD.
- [ ] Casos históricos com código `pediatric_em` continuam no comportamento de ciência operacional e sem agendamento.
- [ ] Intercorrência posterior de novo caso pediátrico confirmado usa o contexto `scheduled`; caso histórico continua usando `operational_notice`.
- [ ] Histórico/busca do CHD inclui novos casos pediátricos agendados.
- [ ] Dashboard atribui `WAIT_APPT` pediátrico ao CHD e consolida métricas históricas/novas na mesma categoria funcional.
- [ ] Manual e `PROJECT_CONTEXT.md` refletem o novo comportamento.
- [ ] Quality gate completo do `AGENTS.md` passa em cada slice.

## Dimensionamento

O change terá **2 slices verticais**:

1. **Slice 001 — decisão médica → CHD → resultado NIR**: entrega o caminho operacional principal completo, incluindo confirmação e negativa, com compatibilidade histórica imediata.
2. **Slice 002 — ciclo pós-encerramento e projeções operacionais**: entrega a continuidade end-to-end após o encerramento (intercorrência agendada), histórico CHD, próximo passo/métrica e documentação.

Um único slice concentraria roteamento, UI de três papéis, lifecycle pós-aceitação, dashboard e documentação em escopo excessivo para DeepSeek4-Flash. Três slices criariam uma fatia horizontal apenas para documentação/métricas. Dois slices equilibram verticalidade e número mínimo de arquivos.
