# Proposal — Confirmação NIR autoritativa e falhas de pipeline auditáveis

## Why

A revisão manual NIR hoje pode repetir indefinidamente a divergência automática e proíbe manter a seleção já informada. Além disso, um artefato LLM com U+0000 pode falhar no PostgreSQL e também impedir o registro da própria falha, deixando um caso em processamento com tarefa falsamente bem-sucedida.

O operador aprovou em 09/10/2026: a confirmação humana deve definir o procedimento após revisão, sem exigir reescrita do relatório, e a Linha do Tempo deve explicitar **quem confirmou qual procedimento**. Motivação reproduzível e sem dados clínicos identificáveis em `evidence.md`.

## What Changes

- Substituir o CTA de correção por **Revisar e confirmar procedimento**: mesma seleção ou outra seleção permitida, confirmação explícita de leitura e justificativa breve obrigatória.
- A confirmação de uma revisão elegível passa a definir o conjunto operacional analisado no mesmo UUID, mesmo quando diverge do detector, não cobre a união bruta ou não aparece no array do LLM1.
- Manter a evidência automática original e registrar confirmação humana append-only. Linha do Tempo apresenta autoria, horário, seleção confirmada, manutenção/troca e justificativa; médico recebe aviso não bloqueante.
- Reprocessar uma vez, sem reextrair PDF/anexos; não reabrir a mesma divergência de procedimento para a mesma fonte confirmada. Validações clínicas, schema, persistibilidade e decisão médica continuam obrigatórias.
- Rejeitar U+0000 antes de persistir artefatos LLM1/LLM2/projeções; registrar falha usando estado limpo e mensagem segura. Se esse registro falhar, propagar ao worker em vez de retornar sucesso falso.
- **BREAKING (semântica do POST interno):** confirmar revisão substitui “seleção precisa ser diferente”. POST antigo sem consentimento/justificativa não adquire autoridade humana implicitamente.

## Capabilities

### New Capabilities

- `nir-procedure-review`: confirmação humana de procedimento após revisão, autoridade limitada à fonte revisada, auditoria explícita e visibilidade ao médico.

### Modified Capabilities

- `exam-type-correction`: mesma seleção permitida; confirmação resolve divergência, com reserva/concorrência, reprocessamento e compatibilidade histórica.
- `procedure-neutral-analysis`: separação entre evidência automática e conjunto confirmado; dados ausentes não são inventados; artefatos persistíveis e falha auditável.
- `procedure-combination-policy`: matriz continua fechada; escolha humana válida pode resolver evidência automática incompatível sem alterar o detector ou permitir novas combinações.

## Impact

- NIR SSR (serviço, POST e card), pipeline 4.0, projeção `CaseProcedure`, eventos e Linha do Tempo, aviso médico e testes. Sem DRF/SPA, dependências novas, migration, novos estados FSM ou mudança do schema externo LLM.
- `CaseEvent` permanece fonte de verdade; novas confirmações não são inferidas de correções históricas. Legados sem confirmação explícita conservam comportamento automático.
- Não modificar o detector de argônio/CPRE nem o catálogo; não exigir PDF reescrito; não criar bypass de policy, aprovação médica ou recuperação automática de CLEANED/FAILED.
- Fora desta change: reabrir/reenviar/reenfileirar casos reais, mascaramento geral de PII, rotação de credenciais, watchdog global, release/deploy. Operações em produção dependem de autorização separada.

## Risco e decisão

**CRÍTICO / HIGH-ARCH**: altera autoridade humana sobre roteamento clínico, persistência auditável, contrato POST e várias superfícies. `design.md` obrigatório; ADR-0012 documenta a mudança em relação à resolução restrita da ADR-0011. O aceite de produto foi dado pelo operador; os detalhes técnicos são o contrato de planejamento desta change, não implementação já entregue.
