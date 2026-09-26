# procedure-neutral-analysis Delta

## Purpose

Estender a detecção determinística e a reconciliação para que pistas de
procedimentos no corpo do relatório — em particular na seção `Justificativa
da Transferência` — qualifiquem como solicitação atual, com precedência de
família absorvendo o alias guarda-chuva do `Motivo da Solicitação` e gate de
conflito para itens estruturados contraditados, mantendo o regime fail-closed.

## ADDED Requirements

### Requirement: Seção Justificativa da Transferência é contexto de solicitação atual

O detector determinístico MUST delimitar a seção `Justificativa da Transferência` (do rótulo até o primeiro terminador conhecido: cabeçalho de página ou rótulo operacional do relatório de regulação; sem terminador, até o fim do texto) e MUST qualificar como `current_request` ocorrências de identidades do catálogo que, dentro dessa seção, seriam mera menção. Ocorrências qualificadas como históricas ou negadas dentro da seção MUST permanecer inalteradas, e ocorrências dentro da seção MUST carregar o rótulo da seção para exibição. O MESMO mecanismo MUST marcar ocorrências dentro do campo `Motivo da Solicitação` com o rótulo dessa seção (proveniência usada pela precedência de família e pela exibição), e a iteração de cláusulas MUST usar offsets absolutos de modo que cláusulas idênticas repetidas entre páginas não misturem contextos.

#### Scenario: Procedimento da família Retossigmoidoscopia na Justificativa

- **GIVEN** relatório com `Motivo da Solicitação: Endoscopia Digestiva Baixa - Colonoscopia`
- **AND** seção `Justificativa da Transferência` contendo ocorrência de `retossigmoidoscopia` sem verbo de solicitação nem rótulo imediato
- **WHEN** `detect_procedure_occurrences` executa
- **THEN** a ocorrência de `rectosigmoidoscopy` é qualificada `current_request`
- **AND** carrega `section` da justificativa
- **AND** a qualificação da colonoscopia derivada do Motivo não muda.

#### Scenario: Ocorrência intermediária entre rótulo e procedimento

- **GIVEN** justificativa com oração intermediária terminada em `.` entre o rótulo da seção e o nome do procedimento
- **WHEN** o detector executa
- **THEN** a ocorrência do procedimento dentro do span da seção ainda é qualificada `current_request`.

#### Scenario: Histórico dentro da Justificativa não vira solicitação

- **GIVEN** justificativa contendo ocorrência coberta pelos padrões de histórico ou negação existentes
- **WHEN** o detector executa
- **THEN** a qualificação permanece `historical` ou `negated`
- **AND** nenhuma identidade é detectada por essa ocorrência.

#### Scenario: Fora da seção permanece menção

- **GIVEN** ocorrência de procedimento no `Resumo Clínico`/histórico sem verbo de solicitação nem rótulo imediato
- **WHEN** o detector executa
- **THEN** a ocorrência permanece `mention`
- **AND** nenhuma identidade é detectada por essa ocorrência.

#### Scenario: Cláusulas repetidas entre páginas não cruzam contextos

- **GIVEN** relatório multi-página com cláusulas idênticas repetidas (boilerplate operacional) e uma delas dentro da Justificativa
- **WHEN** o detector executa
- **THEN** cada ocorrência usa o offset da sua própria página/seção
- **AND** a ocorrência dentro da Justificativa é promovida e a repetida fora dela permanece `mention`.

#### Scenario: Ocorrência do Motivo carrega proveniência do campo

- **GIVEN** ocorrência atual dentro do campo `Motivo da Solicitação`
- **WHEN** o detector executa
- **THEN** a ocorrência carrega `section` do Motivo
- **AND** essa proveniência distingue o alias guarda-chuva do Motivo do mesmo termo citado no corpo.

### Requirement: Vínculo variação-base aceita conectores instrumentais

O vínculo local entre termo ambíguo (`dilatacao`, `argonio`) e a base da família na mesma cláusula MUST aceitar, além de `com`/`e`, os conectores `via`, `por`, `através de` e `com uso de`. Termos ambíguos sem vínculo local com a base MUST continuar qualificados como menção.

#### Scenario: Dilatação via retossigmoidoscopia

- **GIVEN** cláusula atual com `dilatação de anastomose colorretal via retossigmoidoscopia flexivel`
- **WHEN** o detector executa
- **THEN** `rectosigmoidoscopy_dilation` tem ocorrência `current_request` com `linked_base` verdadeiro
- **AND** a base `rectosigmoidoscopy` da mesma expressão também é `current_request`.

#### Scenario: Termo ambíguo solto continua menção

- **GIVEN** ocorrência de `dilatacao` sem base da família na mesma cláusula
- **WHEN** o detector executa
- **THEN** a ocorrência permanece `mention`
- **AND** nenhuma variação é detectada.

### Requirement: Precedência de família absorve o guarda-chuva do Motivo

A reconciliação MUST suprimir `colonoscopy` do conjunto detectado quando: exatamente uma identidade da família Retossigmoidoscopia tem ocorrência `current_request` (com vínculo local quando exigido), `colonoscopy` está no conjunto, e toda ocorrência atual de colonoscopia provém do alias guarda-chuva `endoscopia digestiva baixa` com proveniência do campo `Motivo da Solicitação` (nenhuma ocorrência atual do termo explícito, e nenhuma ocorrência atual do guarda-chuva citada no corpo). A supressão MUST ser registrada com regra auditada `family_umbrella_over_colonoscopy`. Os metadados de precedência de evento/payload MUST carregar, de forma aditiva (`procedure_precedence_rules`), a lista de todas as reduções aplicadas quando mais de uma regra atuar no mesmo caso, PRESERVANDO o campo único existente (`procedure_precedence`) para consumidores atuais, e o aviso ao médico MUST usar copy própria para a regra de família. A supressão MUST NOT ocorrer quando houver evidência atual explícita de `colonoscopy` ou guarda-chuva atual fora do Motivo.

#### Scenario: Corrigido para a variação da família prossegue

- **GIVEN** Motivo `EDB - Colonoscopia` (guarda-chuva) e corpo com `retossigmoidoscopia` + `dilatação` vinculados como solicitação atual
- **AND** NIR declarou `rectosigmoidoscopy_dilation`
- **WHEN** a reconciliação executa
- **THEN** o conjunto detectado é `rectosigmoidoscopy_dilation`
- **AND** a ação é `proceed`
- **AND** o evento registra a regra `family_umbrella_over_colonoscopy`.

#### Scenario: Declarado colonoscopia vira mismatch claro

- **GIVEN** o mesmo relatório
- **AND** NIR declarou `colonoscopy`
- **WHEN** a reconciliação executa
- **THEN** a ação é `nir_review` com reason `exam_type_mismatch`
- **AND** o conjunto detectado é `rectosigmoidoscopy_dilation`.

#### Scenario: Colonoscopia explícita não é absorvida

- **GIVEN** identidade da família Retossigmoidoscopia atual no corpo
- **AND** ocorrência atual de colonoscopia com excerpt explícito `colonoscopia`
- **WHEN** a reconciliação executa
- **THEN** nenhuma supressão de família ocorre
- **AND** o conjunto segue para a matriz (fail-closed).

#### Scenario: Guarda-chuva atual citado no corpo não é absorvido

- **GIVEN** identidade da família Retossigmoidoscopia atual no corpo
- **AND** ocorrência atual de `endoscopia digestiva baixa` dentro da Justificativa (fora do Motivo)
- **WHEN** a reconciliação executa
- **THEN** nenhuma supressão de família ocorre
- **AND** o conjunto segue para a matriz (fail-closed).

### Requirement: Prompt do LLM1 reconhece seções do corpo como fonte de solicitação atual

O prompt do LLM1 MUST instruir que os campos `Justificativa da Transferência` e `Complemento da Solicitação` são fontes legítimas de evidência de solicitação atual (dado que o `Motivo da Solicitação` costuma registrar apenas o exame base), MUST preservar os guardrails de histórico/negação e a exigência de `evidence_spans` com excerpt real, e MUST recomendar valores canônicos de `field_path` sem alterar o schema 4.0. A instrução MUST estar presente no conteúdo canônico semeado e no sufixo sempre anexado pelo renderizador do user prompt (garantia com template de banco desatualizado).

#### Scenario: Instrução presente no prompt canônico e no sufixo

- **GIVEN** o conteúdo canônico 4.0 e o render do user prompt com um template arbitrário
- **WHEN** o contrato de texto é verificado
- **THEN** ambos nomeiam a Justificativa como fonte legítima de solicitação atual
- **AND** os guardrails de histórico/negação permanecem
- **AND** `field_path` canônicos são recomendados sem mudança de schema.

#### Scenario: Seed cria nova versão auditável

- **GIVEN** versão ativa de prompt com conteúdo anterior
- **WHEN** `seed_prompts` é executado
- **THEN** uma nova versão ativa é criada com o conteúdo novo
- **AND** versões históricas são preservadas com exatamente uma ativa por nome.

#### Scenario: Schema inalterado

- **GIVEN** `evidence_spans` do schema 4.0
- **THEN** `field_path` permanece string livre (1-120) sem enum
- **AND** os contratos strict existentes do LLM1 continuam válidos sem edição.

### Requirement: Item estruturado contraditado por ocorrência não-atual gera revisão NIR

Quando o LLM1 reporta um procedimento estruturado cujo termo tem ocorrência não-atual (menção, histórico ou negação) no texto, a detecção MUST sinalizar conflito e a reconciliação MUST retornar `nir_review` com reason `conflicting_procedure_evidence`, incluindo o tipo conflitante no conjunto detectado. O item contraditado MUST NOT virar detecção (`strong`/`any` permanecem falsos) e o caso MUST NOT prosseguir silenciosamente quando o conjunto restante coincidir com o declarado.

#### Scenario: Declaração coincide com o Motivo e item estruturado é contraditado

- **GIVEN** NIR declarou `colonoscopy`, Motivo produz colonoscopia atual
- **AND** LLM1 reporta `rectosigmoidoscopy_dilation` com evidence span
- **AND** o corpo tem apenas menção do termo
- **WHEN** a detecção e a reconciliação executam
- **THEN** a ação é `nir_review` com reason `conflicting_procedure_evidence`
- **AND** `rectosigmoidoscopy_dilation` aparece no conjunto detectado do payload
- **AND** `strong`/`any` de `rectosigmoidoscopy_dilation` permanecem falsos.

#### Scenario: Sem item estruturado o comportamento não muda

- **GIVEN** o mesmo texto sem item estruturado do LLM1 para o tipo
- **WHEN** a detecção e a reconciliação executam
- **THEN** o desfecho é idêntico ao anterior a este requisito (menção isolada não cria identidade).
