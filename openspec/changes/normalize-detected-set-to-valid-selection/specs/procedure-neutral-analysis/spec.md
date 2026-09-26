# procedure-neutral-analysis Delta

## Purpose

Fechar a fresta normativa do gate de conflito: o conjunto detectado usado na
decisão e na exibição passa a ser a seleção válida mais completa que cobre a
evidência (ADR-0011), a evidência bruta permanece na auditoria e a resolução
declarada exige evidência atual não-vazia (discriminador anti-coincidência).

## MODIFIED Requirements

### Requirement: Item estruturado contraditado por ocorrência não-atual gera revisão NIR

Quando o LLM1 reporta um procedimento estruturado cujo termo tem ocorrência não-atual (menção, histórico ou negação) no texto, a detecção MUST sinalizar conflito e a reconciliação MUST retornar `nir_review` com reason `conflicting_procedure_evidence` quando as condições de resolução abaixo não se cumprirem. O item contraditado MUST NOT virar detecção (`strong`/`any` permanecem falsos) e o caso MUST NOT prosseguir silenciosamente quando a única evidência é o próprio item contraditado e a declaração coincide com ele. O conjunto detectado exposto no payload de revisão MUST ser a seleção válida mais completa que cobre a união da evidência atual com o item conflitante quando essa cobertura existe e a união não é ela própria um conjunto válido da matriz (união válida passa inalterada; união sem cobertura passa bruta); o evento de auditoria append-only MUST preservar a união bruta completa em todos os desfechos. Condições de resolução (todas obrigatórias): existe ao menos uma ocorrência textual atual (`any` não-vazio), a declaração vigente é seleção canônica válida não-vazia e é exatamente a seleção válida mais completa que cobre a união — nesse caso a reconciliação MUST prosseguir com a declaração, gravando a evidência bruta no evento, sem novo `nir_review` pelo mesmo conflito.

#### Scenario: Declaração coincide com o Motivo e item estruturado é contraditado

- **GIVEN** NIR declarou `colonoscopy`, Motivo produz colonoscopia atual
- **AND** LLM1 reporta `rectosigmoidoscopy_dilation` com evidence span
- **AND** o corpo tem apenas menção do termo
- **WHEN** a detecção e a reconciliação executam
- **THEN** a ação é `nir_review` com reason `conflicting_procedure_evidence`
- **AND** o conjunto detectado do payload carrega a seleção válida mais completa que cobre a união (quando existe e a união não é válida na matriz)
- **AND** `strong`/`any` de `rectosigmoidoscopy_dilation` permanecem falsos
- **AND** o evento de auditoria da detecção preserva a união bruta.

#### Scenario: Coincidência sem evidência atual permanece fail-closed

- **GIVEN** o texto nega ou apenas historiza o termo (nenhuma ocorrência atual)
- **AND** LLM1 reporta o item estruturado do mesmo tipo
- **AND** a declaração vigente é exatamente esse tipo (a união coincide com a declaração)
- **WHEN** a reconciliação executa
- **THEN** a ação permanece `nir_review` com reason `conflicting_procedure_evidence`
- **AND** o caso não prossegue somente com base na coincidência entre item contraditado e declaração.

#### Scenario: Correção para a seleção mais completa com evidência atual resolve o conflito

- **GIVEN** NIR declarou `eda`, Motivo produz EDA atual e o corpo traz dilatação apenas não-atual
- **AND** LLM1 reporta `eda_dilation` estruturado, gerando `nir_review` por `conflicting_procedure_evidence`
- **AND** o NIR corrige a declaração do mesmo caso para `eda_dilation`
- **WHEN** o reprocessamento executa sobre o texto preservado
- **THEN** existe ocorrência atual (`any` não-vazio) e a declaração é a cobertura máxima da união
- **AND** a reconciliação prossegue com a declaração `eda_dilation`
- **AND** não é emitido novo `nir_review` pelo mesmo conflito
- **AND** o evento de auditoria da detecção preserva a união bruta `{eda, eda_dilation}`.

#### Scenario: Sem item estruturado o comportamento não muda

- **GIVEN** o mesmo texto sem item estruturado do LLM1 para o tipo
- **WHEN** a detecção e a reconciliação executam
- **THEN** o desfecho é idêntico ao anterior a este requisito (menção isolada não cria identidade).

#### Scenario: União sem combinação válida continua fail-closed

- **GIVEN** a união da evidência atual com o item conflitante não é coberta por nenhuma seleção válida (ex.: duas variações de EDA)
- **WHEN** a reconciliação executa
- **THEN** a ação permanece `nir_review` com reason `conflicting_procedure_evidence`
- **AND** o payload expõe a união bruta (não há combinação válida a exibir)
- **AND** nenhum componente é descartado para fabricar validade.
