<!-- markdownlint-disable MD013 -->

# Proposal: Intercorrência pós-aceitação

**Change ID**: `post-acceptance-intercurrence`

**Branch**: `change/post-acceptance-intercurrence`

**Risco**: PROFISSIONAL — amplia workflow após aceite médico, altera fila/contagem do CHD, adiciona migration compatível e preserva auditoria histórica.

**Dependências funcionais**: `post-schedule-intercurrence`, `doctor-admission-operational-flows`, `nir-result-closure`, `workflow-system-notices-in-case-communication`.

## Problema

O sistema chama hoje de **intercorrência pós-agendamento** o ciclo aberto pelo NIR depois que um caso aceito, agendado e concluído sofre uma mudança operacional. Esse nome e a elegibilidade atual cobrem apenas `doctor_admission_flow="scheduled"` com `appointment_status="confirmed"`.

Existem, porém, quatro fluxos de aceite médico em que o CHD não agenda e apenas toma ciência de uma demanda provável:

- `immediate` — vinda imediata;
- `pre_icu` — vinda prévia para UTI;
- `ward_icu_backup` — vinda para enfermaria com retaguarda em UTI;
- `pediatric_em` — compartilhamento/entrada pela emergência pediátrica.

Depois do aceite, essa demanda pode deixar de existir: paciente pode evadir-se, falecer, perder condição de transporte ou ser aceito por unidade mais próxima. O encerramento administrativo não resolve o problema: ele é uma intervenção de manager/admin para retirar caso travado, altera a semântica gerencial e não cria uma pendência de ciência para o CHD.

### Fragilidade adicional da ciência operacional atual

A consulta de notices operacionais não confirmados limita a fila aos eventos do dia local. Assim, um aviso criado ontem e ainda sem ACK pode desaparecer da fila e do badge na virada do dia. Além disso, a regra “não existe qualquer ACK histórico no caso” não pode ser reutilizada para intercorrências recorrentes, pois um ACK antigo bloquearia notices futuros.

## Objetivo

Adotar **intercorrência pós-aceitação** como conceito de domínio e oferecer dois modos explícitos:

1. **Com agendamento**: preservar cancelar/reagendar/manter/negar, retorno ao NIR e ciclo FSM existente.
2. **Somente ciência operacional**: avisar o CHD sobre mudança em caso aceito sem agenda; o CHD apenas confirma ciência, sem alterar campos de agendamento e sem reabrir `WAIT_APPT`.

Também tornar os notices operacionais iniciais duráveis até ACK, independentemente da data de criação, e identificar cada ciclo futuro de intercorrência para que ACKs históricos não ocultem novas pendências.

## Escopo incluído

- Corrigir a fila/badge de ciência operacional inicial para manter avisos antigos não confirmados.
- Renomear a linguagem funcional e visual para “intercorrência pós-aceitação”.
- Preservar os campos legados `post_schedule_issue_*` nesta entrega para compatibilidade de schema e rollout.
- Adicionar contexto explícito e identificador de ciclo para a intercorrência ativa.
- Fazer backfill seguro de eventual intercorrência legada ativa como contexto agendado.
- Manter o fluxo agendado atual, com novos nomes/eventos e payload de auditoria fortalecido.
- Permitir abertura em caso `CLEANED`, aceito, dos quatro fluxos sem agendamento.
- Criar pendência própria na fila do CHD para intercorrência apenas de ciência.
- Permitir ao CHD confirmar ciência atomicamente, sem lock de agendamento e sem alterar `appointment_*`.
- Evitar card duplicado quando uma intercorrência operacional substitui um notice inicial ainda não confirmado.
- Adicionar motivos explícitos para evasão e aceite/transferência para unidade mais próxima.
- Preservar leitura e projeção dos eventos históricos `POST_SCHEDULE_ISSUE_*`.
- Adicionar testes de regressão para locks, permissões, FSM, dashboard, histórico e métricas afetadas.

## Fora de escopo

- Permitir abertura antes de `CLEANED`, inclusive em `WAIT_R1_CLEANUP_THUMBS`.
- Criar novo estado FSM ou remover qualquer um dos 17 estados.
- Alterar decisão médica ou fluxo de admissão já registrado.
- Dar ao CHD poder de negar/cancelar uma transferência sem agenda; nesses casos ele apenas confirma ciência.
- Integrar EM Pediátrica, reserva de UTI ou transporte.
- Notificações por WhatsApp, telefone, SMS, push ou e-mail operacional.
- Renomear fisicamente todos os campos `post_schedule_issue_*` no mesmo rollout.
- Reescrever eventos históricos append-only.
- Criar workflow engine/ticketing genérico.
- Histórico CHD multi-dia completo, busca avançada ou exportação.

## Fluxos esperados

### Agendado

```text
Case CLEANED + aceite scheduled + appointment confirmed
→ NIR abre intercorrência pós-aceitação
→ WAIT_APPT, contexto scheduled, ciclo identificado
→ CHD cancela/reagenda/mantém/nega
→ WAIT_R1_CLEANUP_THUMBS
→ NIR confirma ciência
→ CLEANED e campos ativos limpos
```

### Somente ciência operacional

```text
Case CLEANED + aceite immediate/pre_icu/ward_icu_backup/pediatric_em
→ NIR abre intercorrência pós-aceitação
→ Case permanece CLEANED, contexto operational_notice, ciclo identificado
→ CHD vê pendência específica e confirma ciência
→ Case permanece CLEANED e campos ativos são limpos
```

## Decisões de produto

- “Pós-aceitação” descreve o marco de negócio; a primeira versão continua exigindo `CLEANED` para evitar concorrência com a confirmação do resultado original.
- Em caso sem agenda, o CHD não responde com ações de agendamento: apenas confirma ciência.
- A intercorrência operacional ativa substitui visualmente o notice inicial ainda pendente do mesmo caso, evitando dois cards para a mesma demanda.
- Notices iniciais permanecem na fila até ACK, mesmo após a virada do dia.
- Histórico e múltiplos ciclos são preservados por `CaseEvent` com `cycle_id`; os campos no `Case` representam somente o ciclo ativo/latest.

## Critérios globais de sucesso

- Um notice operacional inicial não confirmado continua visível no dia seguinte e entra no badge do CHD.
- ACK remove esse notice durável da fila e o histórico “confirmados hoje” continua baseado na data do ACK.
- O fluxo agendado continua funcionando sem regressão de locks, FSM ou ações do CHD.
- Toda UI nova usa “intercorrência pós-aceitação”; eventos legados continuam legíveis.
- NIR consegue abrir intercorrência nos quatro fluxos sem agendamento após `CLEANED`.
- CHD vê a intercorrência operacional até confirmar ciência, mesmo que o notice original já tenha ACK histórico.
- ACK de uma intercorrência antiga não oculta um novo ciclo.
- Intercorrência sem agenda nunca muda `Case.status` para `WAIT_APPT` e nunca altera `appointment_status`, `appointment_at`, local ou instruções.
- Não há duplicidade entre notice inicial e intercorrência operacional ativa.
- Evasão e aceite por unidade mais próxima possuem motivos estruturados próprios.
- Auditoria registra `cycle_id`, contexto, fluxo de admissão e snapshots necessários.
- Encerramento administrativo permanece excepcional e não é reutilizado para este fluxo.
- Quality gate completo passa em cada slice.
