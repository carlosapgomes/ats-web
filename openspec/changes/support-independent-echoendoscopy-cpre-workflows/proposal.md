# Proposal: Ecoendoscopia e CPRE como procedimentos independentes

**Change ID:** `support-independent-echoendoscopy-cpre-workflows`

**Branch de implementação:** `feature/support-independent-echoendoscopy-cpre-workflows`

**Risco:** CRÍTICO / HIGH-ARCH — altera catálogo clínico, contrato LLM strict, hard rules, decisão médica, filas, comunicação, analytics e compatibilidade operacional de rollback.

**ADR:** [`ADR-0006 — Ecoendoscopia e CPRE como procedimentos independentes`](../../../docs/adr/ADR-0006-ecoendoscopia-e-cpre-como-procedimentos-independentes.md), aceita antes do primeiro slice de código.

## Why

Ecoendoscopia ainda é representada como subtipo/sinal de EDA e CPRE não pertence ao domínio suportado, embora ambos sejam exames independentes, realizados separadamente e com fluxo próprio de seleção, análise, autorização e agendamento. Essa modelagem impede o NIR de declarar corretamente o procedimento e não preserva com clareza o que foi solicitado, detectado e autorizado.

O ATS precisa promover os dois exames a `CaseProcedure`, aplicar requisitos pré-operatórios aprovados de modo determinístico, permitir troca médica auditável sem reanálise e comunicar o conjunto autorizado a CHD/NIR, mantendo EDA + Colonoscopia como a única combinação permitida.

## What Changes

- Adicionar `echoendoscopy` e `cpre` ao catálogo autoritativo de `ProcedureType`.
- Centralizar a matriz fechada: EDA, Colonoscopia, EDA + Colonoscopia, Ecoendoscopia ou CPRE.
- Permitir seleção NIR de Ecoendoscopia/CPRE em upload, correção e reenvio, sob flags independentes.
- Evoluir novos processamentos para contrato LLM strict 3.0 com quatro tipos e evidência abdominal tipada.
- Aplicar precedência determinística: `EDA com/e Ecoendoscopia → Ecoendoscopia` e `EDA com/e CPRE → CPRE`.
- Aplicar policy comum da EDA sem bypass de corpo estranho e exigir imagem com conclusão/achado:
  - Ecoendoscopia: TC ou RM de abdome/abdome superior;
  - CPRE: USG abdominal/hepatobiliar, TC/RM de abdome/abdome superior ou CPRM.
- Agregar todas as pendências aplicáveis; qualquer falha força sugestão de negativa, sem bloquear o médico.
- Permitir que o médico substitua um procedimento e o aprove em uma única decisão, sem nova chamada LLM, recálculo de policy ou reapresentação de sugestão.
- Bloquear conjuntos finais incompatíveis; não dividir caso/agendamento no MVP.
- Destacar o autorizado em CHD/NIR e registrar transformação textual, resposta final, evento e mensagem sistêmica sem notificação global.
- Estender filtros, analytics e follow-up aos dois novos procedimentos.
- Preservar schemas 1.1/2.0 e sinais históricos sem backfill de Ecoendoscopia.
- Fazer rollout sequencial: Ecoendoscopia antes de CPRE, com rollback por flags e fix-forward.
- **BREAKING operacional:** depois do primeiro write 3.0 — mesmo de EDA/Colonoscopia — ou da primeira row especializada, imagens antigas que só possuem writer 2.0 e dois tipos não são opção segura de rollback.

## Capabilities

### New Capabilities

- `procedure-combination-policy`: catálogo, ordem canônica, matriz fechada de conjuntos, precedências, regras de mismatch e limites de substituição.

### Modified Capabilities

- `exam-type-intake-routing`: intake passa a aceitar Ecoendoscopia/CPRE sob flags próprias e a exibir as novas identidades.
- `procedure-neutral-analysis`: contrato gravável 3.0, extração tipada de imagem, policies especializadas, pendências agregadas e igualdade exata no LLM2.
- `per-procedure-medical-decision`: decisão passa a aceitar os quatro tipos, troca-aprovação sem reanálise e validação do conjunto final.
- `exam-type-work-queues`: filas/filtros/cards de médico e CHD passam a projetar Ecoendoscopia/CPRE e transformações detectado→autorizado.
- `exam-type-correction`: correção/reenvio NIR passam a aceitar tipos especializados e a preservar reprocessamento seguro.
- `exam-type-analytics`: categorias exclusivas e volumes por componente passam a contemplar os quatro tipos.

## Impact

- **Domínio:** `ProcedureType`, helpers de `CaseProcedure`, catálogo/ordem e validação de conjuntos.
- **Pipeline:** schemas/adapters 3.0, prompts neutros versionados, scope/detecção, reconciliação, policy, LLM2 e orchestrator.
- **Médico:** relatório agregado, formulário por catálogo, troca atômica e evento de transformação.
- **CHD/NIR:** badges, filtros, cards, detalhes, agendamento, resposta final e thread sistêmica.
- **Dashboard/follow-up:** categorias, contagens, filtros e desfecho por novo componente.
- **Operação:** flags `ECHOENDOSCOPY_INTAKE_ENABLED` e `CPRE_INTAKE_ENABLED`, cutover de prompts/schema, observabilidade e runbook sem downgrade destrutivo.
- **Sem impacto pretendido:** FSM, roles, locks, intranet guard, modelo de sala, segundo appointment, REST/SPA ou processamento automático de anexos.

## Critérios de sucesso

- NIR cria um único caso declarado como Ecoendoscopia ou CPRE quando a flag correspondente está ativa.
- Detecção, policy e LLM2 produzem resultado próprio para o procedimento especializado usando schema 3.0.
- Imagem só satisfaz a hard rule com contexto/achado ancorados, modalidade/anatomia rederivadas e predicado positivo ou heading estrito de resultado; intenção/agendamento dominam palavras isoladas como `laudo`, e mismatch, conflito ou ambiguidade falham fechados.
- Todas as pendências aparecem juntas e forçam sugestão de negativa; decisão médica continua livre.
- Troca médica persiste origem e destino com justificativa, não reanalisa e segue diretamente no fluxo escolhido.
- Somente EDA + Colonoscopia é tratada como combinação/agendamento casado.
- CHD e NIR veem o autorizado e a transformação em superfícies operacionais e comunicação do caso, sem `UserNotification` automática.
- Filtros, analytics e follow-up reconhecem Ecoendoscopia e CPRE sem dupla contagem de casos.
- Artefatos 1.1/2.0 e sinais históricos continuam legíveis; nenhum backfill infere novo procedimento.
- Rollout ativa Ecoendoscopia antes de CPRE e rollback suportado mantém imagem/schema novos.
