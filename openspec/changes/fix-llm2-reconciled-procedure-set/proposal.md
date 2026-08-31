<!-- markdownlint-disable MD013 -->

# Proposal: Alinhar o contexto do LLM2 ao conjunto reconciliado de procedimentos

**Change ID**: `fix-llm2-reconciled-procedure-set`  
**Risco**: CRÍTICO (hotfix no pipeline clínico de produção e no contrato com provedor LLM; comportamento permanece fail-closed)  
**Relação arquitetural**: corrige a execução da ADR-0004 e da spec `procedure-neutral-analysis`; não introduz nova arquitetura nem exige ADR adicional  
**Incidente**: ocorrências de produção `5025447`, `5027759` e `5028231`, incluindo reapresentações do mesmo caso

## Problema

O pipeline v2 possui duas representações legítimas, porém hoje usa a representação errada como contexto do LLM2:

1. o LLM1 produz e o sistema persiste `structured_data.requested_procedures` como artefato original de extração;
2. `detect_requested_procedures_v2()` e `reconcile_detected_procedures()` qualificam histórico, negação e solicitação atual, produzindo o conjunto reconciliado que governa policy, `CaseProcedure` e validação do LLM2;
3. o orchestrator passa ao LLM2 o `structured_data` bruto do LLM1, mas passa ao validator o conjunto reconciliado.

Quando o LLM1 lista EDA e Colonoscopia, porém a reconciliação mantém somente um deles, o prompt continua mostrando os dois itens. O modelo tende a devolver duas recomendações, enquanto `_decode_and_validate()` exige corretamente somente o procedimento reconciliado. Os erros observados foram:

```text
LLM2 v2 procedure set mismatch: expected ['eda'], got ['colonoscopy', 'eda']
LLM2 v2 procedure set mismatch: expected ['colonoscopy'], got ['colonoscopy', 'eda']
```

A investigação confirmou que PDF, PostgreSQL, Docker, django-q e o provedor LLM estavam operacionais. Foram encontrados cinco mismatches; 68 dos 73 casos que chegaram a `LLM1_OK` chegaram a `LLM2_OK`. `run_pipeline()` captura a exceção e registra a falha do caso, enquanto a tarefa django-q termina sem retry automático do job.

## Objetivo

Tornar o conjunto reconciliado a autoridade explícita da chamada LLM2, sem reescrever a evidência original do LLM1:

```text
LLM1 structured_data original
→ detecção + reconciliação
→ cópia efêmera com requested_procedures filtrado
→ prompt declara o conjunto reconciliado como lista fechada
→ LLM2 responde exatamente esse conjunto
→ validator mantém igualdade exata
```

Se a primeira resposta ainda alterar o conjunto, o serviço deve realizar exatamente um retry corretivo específico para `procedure set mismatch`. Um segundo mismatch deve continuar falhando de forma controlada, sem sugestão parcial.

## Escopo incluído

- Construir no orchestrator uma cópia efêmera do `structured_data` para o LLM2.
- Filtrar somente `requested_procedures` nessa cópia pelo conjunto reconciliado, em ordem canônica, sem inventar item clínico.
- Preservar `Case.structured_data` exatamente como recebido e validado do LLM1 para auditoria.
- Acrescentar ao envelope de prompt do LLM2 uma lista JSON explícita dos procedimentos reconciliados e instrução de cardinalidade exata.
- Diferenciar `procedure set mismatch` dos demais erros de validação por tipo, sem inspecionar texto de exceção.
- Permitir um único retry corretivo para esse tipo de mismatch; persistindo a divergência, manter o fluxo fail-closed.
- Preservar o retry de idioma pt-BR já existente, com orçamento independente e finito.
- Cobrir EDA-only, Colonoscopia-only, combinado, recuperação no primeiro retry, falha no segundo mismatch e imutabilidade do artefato original.
- Atualizar por delta a spec canônica `procedure-neutral-analysis`.

## Fora de escopo

- Alterar regex, aliases ou regras de `scope_detection.py`, incluindo grafias como `colonospia` ou `colonoscópica`.
- Alterar a matriz de reconciliação, seus reason codes ou os gates de revisão NIR.
- Alterar schemas Pydantic, policy, prior-case, presenter, FSM, modelos, migrations, filas ou permissões.
- Reescrever, normalizar ou corrigir retrospectivamente `Case.structured_data` existente.
- Criar transição de recuperação para casos em `FAILED`, retry do job django-q ou reprocessamento automático.
- Alterar prompts versionados no banco, seed de prompts ou admin de prompts; o conjunto dinâmico será anexado pelo envelope do serviço em todas as variantes de template.
- Adicionar suporte a CPRE ou qualquer novo procedimento.
- Corrigir casos de produção durante o slice de código.

## Dimensionamento em slices

O change terá **um único slice vertical**.

A correção só entrega valor quando projeção, prompt, validação/retry e persistência auditável funcionam juntas no mesmo fluxo. Separar “projeção no orchestrator” de “retry no serviço” criaria um estado intermediário ainda suscetível ao incidente. O footprint funcional previsto é de quatro arquivos:

1. `apps/pipeline/orchestrator.py`
2. `apps/pipeline/llm2_service_v2.py`
3. `apps/pipeline/tests/test_slice_002_contracts.py`
4. `apps/pipeline/tests/test_slice_002_pipeline.py`

Nenhum model, migration, schema, detector ou arquivo de prompt é necessário.

## Critérios de sucesso globais

- LLM1 com ambos e reconciliação somente EDA envia ao LLM2 apenas o item EDA em `requested_procedures` e declara `['eda']` como conjunto autoritativo.
- LLM1 com ambos e reconciliação somente Colonoscopia envia ao LLM2 apenas o item Colonoscopia e declara `['colonoscopy']`.
- Reconciliação combinada continua enviando ambos e aceitando duas recomendações.
- `Case.structured_data` mantém os dois itens originais nos cenários em que a visão efêmera do LLM2 contém apenas um.
- Caminho sem mismatch continua usando uma tentativa LLM2 inicial, sem retry adicional.
- Primeiro `procedure set mismatch` pode ser corrigido por exatamente uma tentativa adicional.
- Segundo `procedure set mismatch` falha, gera o tratamento existente de `PIPELINE_FAILED`/`FAILED` e não persiste `suggested_action` parcial.
- Erros não relacionados ao conjunto não consomem o retry de conjunto.
- Retry de idioma continua limitado e funcional; nenhum loop de chamadas é possível.
- Quality gate completo do `AGENTS.md` passa.

## Rollout, recuperação operacional e rollback

Não há migration nem transformação de dados. Após aprovação, release e deploy:

1. executar smoke de EDA-only, Colonoscopia-only e combinado;
2. confirmar `WAIT_DOCTOR`, conjunto correto em `LLM2_OK` e ausência de novo mismatch;
3. reapresentar uma única vez as ocorrências `5025447`, `5027759` e `5028231`;
4. manter tentativas antigas em `FAILED` como histórico, sem editá-las nem reabri-las.

Rollback é o revert do slice e novo deploy da aplicação. O banco permanece idêntico. O rollback restaura a vulnerabilidade atual e, por isso, só deve ser usado diante de regressão mais grave comprovada.
