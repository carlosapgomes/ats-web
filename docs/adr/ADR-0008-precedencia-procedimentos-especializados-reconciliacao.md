# ADR-0008: Precedência de procedimentos especializados na reconciliação

## Status

Accepted

**Aceita em:** 2026-09-18

**Supera parcialmente:** [ADR-0006 — Ecoendoscopia e CPRE como procedimentos independentes](ADR-0006-ecoendoscopia-e-cpre-como-procedimentos-independentes.md), na decisão que restringia a precedência a expressões locais `EDA com/e especializado` e tratava solicitações convencionais e especializadas em trechos independentes sempre como combinação incompatível.

**Change associado:** [`prioritize-specialized-procedure-requests`](../../openspec/changes/prioritize-specialized-procedure-requests/proposal.md).

## Contexto

A ADR-0006 definiu Ecoendoscopia e CPRE como procedimentos independentes e manteve EDA + Colonoscopia como a única combinação autorizável. Para evitar que duas solicitações independentes fossem colapsadas indevidamente, a precedência do procedimento especializado foi limitada a expressões textualmente ligadas, como `EDA com ecoendoscopia`.

Relatórios de regulação, porém, misturam campos administrativos, histórico de exames e condutas clínicas em seções distintas. Um caso real mostrou o padrão:

- cabeçalho administrativo `Motivo da Solicitação: EDA`;
- EDA já realizada, com data e laudo no histórico;
- complemento e condutas repetindo `Solicito Ecoendoscopia via regulação`;
- NIR declarando corretamente Ecoendoscopia.

O detector pôde produzir `{eda, echoendoscopy}` sem vínculo local `com/e`. A reconciliação classificou o conjunto como combinação especializada incompatível e devolveu o caso repetidamente ao NIR, apesar de Ecoendoscopia ser o destino clínico atual e de a avaliação médica posterior poder corrigir qualquer erro grosseiro.

A operação confirmou que combinações envolvendo Ecoendoscopia ou CPRE são exceção da exceção e não precisam de modelagem específica. O comportamento mais seguro para progressão é priorizar um único procedimento especializado solicitado, conservar toda a evidência para revisão e deixar a decisão final ao médico.

## Decisão

Como `detect_requested_procedures_v3()` une o `requested_procedures` estruturado às ocorrências textuais atuais, o conjunto `strong/any` sozinho não comprova deterministicamente a atualidade do especializado. A reconciliação seguirá estas regras:

1. Se houver **exatamente um tipo especializado detectado** (`echoendoscopy` ou `cpre`) e uma ocorrência textual do mesmo tipo qualificada como `current_request`, ele predomina sobre qualquer EDA e/ou Colonoscopia também detectadas.
2. A ocorrência atual especializada pode estar ligada por `com/e` ou em trecho distinto; vínculo local com EDA deixa de ser requisito.
3. Item especializado em `requested_procedures`, isoladamente, não autoriza suprimir convencionais. Sem ocorrência textual atual correspondente, o conjunto misto permanece incompatível e segue fail-closed ao NIR.
4. Se Ecoendoscopia e CPRE estiverem ambas presentes, o sistema não escolhe entre elas: o caso continua fail-closed em revisão NIR.
5. Tipo desconhecido e duplicata continuam fail-closed antes da precedência.
6. EDA + Colonoscopia permanece a única combinação reconciliada/autorizável e não muda quando nenhum especializado elegível à precedência existe.
7. A precedência altera apenas o conjunto detectado bruto. A declaração NIR não é sobrescrita: se não coincidir com o especializado reconciliado, o caso continua em mismatch/revisão NIR. Não há auto-upgrade convencional→especializado.
8. O artefato LLM1 original permanece imutável. Rows detectadas, policy e LLM2 usam o singleton reconciliado.
9. Quando EDA/Colonoscopia forem suprimidas, `CASE_PROCEDURES_DETECTED` e `suggested_action` registram regra, especializado selecionado e tipos convencionais suprimidos, sem texto clínico integral.
10. O relatório médico exibe aviso informativo e não bloqueante com label canônico para Ecoendoscopia ou CPRE, orientando revisar o texto original e ajustar a decisão se necessário.

A matriz final permanece:

```text
{eda}
{colonoscopy}
{eda, colonoscopy}
{echoendoscopy}
{cpre}
```

## Alternativas Consideradas

### 1. Manter precedência apenas para `EDA com/e especializado`

- **Vantagens:** máxima conservação; duas frases independentes nunca são reduzidas.
- **Desvantagens:** não representa a estrutura real dos relatórios; mantém ciclos repetidos de revisão manual quando o especializado está explicitamente solicitado.
- **Por que não escolhida:** o incidente demonstrou dano operacional sem ganho clínico proporcional.

### 2. Corrigir somente prompt/LLM para não extrair EDA do cabeçalho

- **Vantagens:** conjunto bruto já chegaria singular em muitos casos.
- **Desvantagens:** depende de comportamento probabilístico; cabeçalhos administrativos podem legitimamente ser evidência; não garante proteção determinística.
- **Por que não escolhida:** prompt pode reduzir incidência, mas não deve ser autoridade da regra de domínio.

### 3. Modelar combinações EDA+Ecoendoscopia, EDA+CPRE e outras

- **Vantagens:** preservaria literalmente todos os pedidos atuais como componentes.
- **Desvantagens:** exigiria agenda, decisão, filtros e comunicação para combinações que a operação considera excepcionais; aumentaria risco de bloqueio e complexidade.
- **Por que não escolhida:** não há demanda operacional suficiente e o médico já pode ajustar/incluir procedimentos com observação.

### 4. Priorizar exatamente um especializado e avisar o médico (escolhida)

- **Vantagens:** elimina falso combinado, permite progressão, mantém auditoria e revisão humana final; regra pequena e determinística.
- **Desvantagens:** uma EDA/Colonoscopia realmente solicitada junto pode deixar de virar componente detectado automático.
- **Por que escolhida:** combinações especializadas são excepcionalíssimas e o custo de bloquear sistematicamente é maior; aviso e artefato bruto preservado mitigam o risco.

## Consequências

### Positivas

- Casos corretamente declarados como Ecoendoscopia/CPRE deixam de retornar ao NIR apenas por menções convencionais concorrentes.
- O médico recebe o caso e pode confirmar, negar, trocar ou registrar observação pelo fluxo existente.
- Regra determinística independente de o pedido atual estar na mesma seção do convencional, desde que exista ocorrência textual especializada qualificada como atual.
- Evidência original e tipos suprimidos permanecem auditáveis.
- EDA, Colonoscopia e EDA + Colonoscopia mantêm o comportamento conhecido.

### Negativas/Trade-offs

- Uma solicitação convencional realmente simultânea a um único especializado não será projetada como segundo componente automático.
- Uma solicitação especializada atual cuja redação não seja reconhecida pelo detector de ocorrências não aciona a precedência e permanece em revisão NIR.
- Evento e `suggested_action` ganham metadado aditivo que consumidores devem ignorar quando não utilizarem.

### Riscos e Mitigações

- **Risco:** item estruturado indevido, mera menção ou histórico de especializado dominar EDA/Colonoscopia.
  **Mitigação:** precedência exige ocorrência textual correspondente com `qualification == "current_request"`; testes cobrem structured item com texto histórico/negado, além de singleton sem supressão.
- **Risco:** escolher arbitrariamente entre Ecoendoscopia e CPRE.
  **Mitigação:** exigir exatamente um tipo especializado; ambos continuam revisão NIR.
- **Risco:** esconder uma combinação excepcional real.
  **Mitigação:** preservar LLM1/texto original, registrar tipos suprimidos e exibir aviso médico não bloqueante; médico pode ajustar e observar.
- **Risco:** sobrescrever declaração do NIR.
  **Mitigação:** matriz declarado×reconciliado permanece; divergência continua mismatch.
- **Risco:** regressão do combinado convencional.
  **Mitigação:** teste explícito EDA + Colonoscopia sem especializado.

## Referências

- Change: `openspec/changes/prioritize-specialized-procedure-requests/`
- Spec: `openspec/specs/procedure-combination-policy/spec.md`
- Código alvo: `apps/pipeline/procedure_reconciliation.py`

## Histórico de Mudanças

- 2026-09-18: ADR criada e aceita após validação do processo com a equipe operacional; precedência especializada ampliada para trechos independentes.
- 2026-09-18: Após review independente, adicionado gate de ocorrência textual `current_request`; item estruturado isolado não autoriza supressão de convencionais.
