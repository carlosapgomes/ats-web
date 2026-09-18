# Proposal: Priorizar solicitações de Ecoendoscopia e CPRE na reconciliação

**Change ID:** `prioritize-specialized-procedure-requests`

**Branch de implementação:** `feature/prioritize-specialized-procedure-requests`

**Risco:** CRÍTICO / HIGH-ARCH — altera o roteamento clínico entre revisão manual do NIR e avaliação médica. A classificação determinística registrou nível CRITICAL; o footprint é pequeno, mas falso positivo ou falso negativo pode mudar a fila operacional de um caso.

**ADR:** [`ADR-0008 — Precedência de procedimentos especializados na reconciliação`](../../../docs/adr/ADR-0008-precedencia-procedimentos-especializados-reconciliacao.md), que supera parcialmente a precedência restrita da ADR-0006.

## Why

O pipeline 3.0 aceita apenas cinco conjuntos reconciliados: EDA, Colonoscopia, EDA + Colonoscopia, Ecoendoscopia ou CPRE. Hoje, Ecoendoscopia/CPRE só predominam sobre EDA quando o detector comprova uma expressão local ligada por `com/e`, como `EDA com ecoendoscopia`. Se o relatório contém um cabeçalho administrativo de EDA e, em outro trecho, uma solicitação explícita e repetida de Ecoendoscopia, o conjunto bruto `{eda, echoendoscopy}` é tratado como combinação incompatível e retorna ao NIR.

Isso pode criar um ciclo de revisão manual mesmo quando:

- o NIR já declarou o procedimento especializado correto;
- EDA aparece como categoria administrativa ou exame previamente realizado;
- a conduta atual solicita explicitamente Ecoendoscopia ou CPRE;
- a única combinação operacional normal é EDA + Colonoscopia.

O caso deve avançar à avaliação médica como o procedimento especializado singleton, preservando a extração original e informando ao médico que menções convencionais foram suprimidas pela regra de precedência.

## What Changes

- Uma única Ecoendoscopia ou uma única CPRE detectada passa a predominar sobre EDA e/ou Colonoscopia, mesmo em trechos independentes, somente quando uma ocorrência textual do mesmo especializado foi qualificada deterministicamente como `current_request`.
- `requested_procedures` do LLM1 continua participando da detecção, mas, isoladamente, não autoriza suprimir procedimentos convencionais. A regra não depende mais de vínculo local `EDA com/e ...`; exige apenas a ocorrência atual do especializado em qualquer trecho.
- EDA + Colonoscopia permanece inalterada quando nenhum procedimento especializado é elegível à precedência.
- Ecoendoscopia + CPRE continua incompatível e retorna ao NIR; tipo desconhecido e duplicata continuam fail-closed.
- A declaração do NIR permanece dimensão separada: o caso só segue ao médico quando o singleton especializado reconciliado coincide com o declarado. Não haverá troca silenciosa nem auto-upgrade convencional→especializado.
- O artefato LLM1 permanece imutável. A projeção detectada e a visão efêmera do LLM2 contêm somente o especializado priorizado.
- O evento `CASE_PROCEDURES_DETECTED` e `suggested_action` registram metadados enxutos da precedência (`selected` e convencionais `suppressed`).
- O relatório médico mostra aviso informativo, não bloqueante, somente quando a precedência efetivamente suprimiu EDA/Colonoscopia.

## Capabilities

### Modified Capabilities

- `procedure-combination-policy`: amplia a precedência especializada, explicita conflitos que permanecem fail-closed e torna a aplicação da regra auditável/visível ao médico.

## Impact

- **Reconciliação:** `apps/pipeline/procedure_reconciliation.py`.
- **Orquestração/auditoria:** `apps/pipeline/orchestrator.py`.
- **Avaliação médica:** `apps/doctor/presenters.py`; o template existente já renderiza `report.notices`.
- **Testes:** regressões focadas de Ecoendoscopia e CPRE no pipeline 3.0, incluindo notice para ambos os tipos e structured item especializado sem ocorrência textual atual.
- **Sem impacto pretendido:** detector/aliases, prompts, schemas LLM, policy clínica, models, migrations, FSM, flags de intake, permissões, filas CHD/NIR, decisão médica ou combinações autorizadas.

## Critérios de sucesso globais

- NIR declara Ecoendoscopia; relatório contém cabeçalho/solicitação convencional e ocorrência textual atual de Ecoendoscopia; o caso chega a `WAIT_DOCTOR` como `{echoendoscopy}`.
- O cenário equivalente de CPRE, também comprovado por ocorrência textual `current_request`, chega a `WAIT_DOCTOR` como `{cpre}`.
- EDA e/ou Colonoscopia convencionais são suprimidas quando existe exatamente um tipo especializado detectado e uma ocorrência atual correspondente; a extração LLM1 original continua íntegra.
- Item especializado em `requested_procedures` cujo texto contém apenas histórico, negação ou menção não autoriza supressão; o conjunto misto permanece fail-closed.
- EDA + Colonoscopia continua reconciliada como combinado quando não há especializado elegível à precedência.
- Ecoendoscopia + CPRE, valores desconhecidos e duplicatas continuam em revisão NIR.
- Declaração convencional divergente continua retornando ao NIR como mismatch; não existe auto-upgrade especializado.
- Evento e sugestão registram a regra aplicada sem copiar texto clínico integral.
- Médico recebe aviso informativo apenas quando houve supressão por precedência e continua livre para ajustar a decisão.
- Testes focados, quality gate global e `openspec validate ... --strict` passam.

## Rollout e rollback

Não há migration, backfill ou mudança de contrato externo. O deploy usa a mesma imagem web/worker e respeita as flags especializadas existentes.

Após deploy:

1. executar smoke sintético de Ecoendoscopia e CPRE com cabeçalho EDA + ocorrência textual atual do especializado em trecho independente;
2. confirmar `WAIT_DOCTOR`, singleton especializado, evento com precedência e aviso médico;
3. confirmar regressões de EDA-only, Colonoscopia-only e EDA + Colonoscopia;
4. monitorar `unsupported_procedure_combination`, `exam_type_mismatch`, `PIPELINE_FAILED` e volume de casos especializados que alcançam a fila médica.

Rollback é revert da aplicação e novo deploy. Como não há transformação de banco, rows ou artefatos já gravados permanecem auditáveis; o rollback apenas restaura a regra anterior para processamentos futuros. Casos já enviados ao médico não devem ser reabertos automaticamente.
