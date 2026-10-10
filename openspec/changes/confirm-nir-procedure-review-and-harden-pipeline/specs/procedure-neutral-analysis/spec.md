# procedure-neutral-analysis Delta

## MODIFIED Requirements

### Requirement: Detecção reconcilia declaração sem apagar proveniência

O sistema MUST preservar declaração e evidência automática separadamente. Sem confirmação humana válida, a reconciliação automática continua autoritativa. Após confirmação NIR vinculada à fonte, o conjunto efetivo MUST ser o confirmado, com proveniência explícita; artefato LLM1 e união bruta de detecção MUST permanecer auditáveis.

#### Scenario: Upgrade automático para combinado
- **GIVEN** NIR declarou EDA ou Colonoscopia e evidência forte confirma ambas, sem resolução humana
- **WHEN** reconciliação executa
- **THEN** ambos ficam detectados e caso segue ao médico sem ACK
- **AND** evento registra declaração original, detecção e base da evidência.

#### Scenario: Combinado declarado mas somente um detectado
- **GIVEN** declarado EDA + Colonoscopia e nenhuma confirmação humana válida
- **WHEN** análise detecta só um componente
- **THEN** caso retorna ao NIR
- **AND** não entra em WAIT_DOCTOR.

#### Scenario: Tipos únicos contraditórios
- **GIVEN** declarado EDA e detectado Colonoscopia, ou vice-versa, sem confirmação humana
- **WHEN** reconciliação executa
- **THEN** caso retorna ao NIR por mismatch
- **AND** nenhum swap silencioso ocorre.

#### Scenario: Confirmação define conjunto efetivo distinto
- **GIVEN** revisão automática de EDA + Eco + CPRE e confirmação humana válida de CPRE
- **WHEN** reprocessamento executa
- **THEN** policy, contexto anterior, recomendação e fila médica usam CPRE
- **AND** união automática e JSON original não são substituídos pela escolha humana.

### Requirement: Item estruturado contraditado por ocorrência não-atual gera revisão NIR

Na análise automática sem confirmação NIR válida, quando o LLM1 reporta um procedimento cujo termo tem ocorrência não-atual, a detecção MUST sinalizar conflito e retornar nir_review com conflicting_procedure_evidence se a resolução automática não se cumprir. Strong/any do contraditado MUST permanecer falsos. Payload MUST normalizar só união fora da matriz com cobertura máxima existente; evento MUST preservar união bruta. Resolução automática exige any não-vazio, declaração canônica válida e igualdade com cobertura máxima. Confirmação humana válida resolve pelo conjunto escolhido sem alterar esses fatos de detecção.

#### Scenario: Declaração coincide com o Motivo e item estruturado é contraditado
- **GIVEN** declarado colonoscopy, Motivo atual e item rectosigmoidoscopy_dilation só como menção, sem confirmação humana
- **WHEN** detecção/reconciliação executam
- **THEN** ação é nir_review por conflicting_procedure_evidence
- **AND** payload normaliza cobertura apenas quando aplicável, strong/any do contraditado são falsos e evento preserva união bruta.

#### Scenario: Coincidência sem evidência atual permanece fail-closed
- **GIVEN** termo negado/histórico, array LLM1 e declaração coincidem, sem confirmação humana
- **WHEN** reconciliação automática executa
- **THEN** revisão persiste
- **AND** igualdade sozinha não autoriza encaminhamento.

#### Scenario: Correção para a seleção mais completa com evidência atual resolve o conflito
- **GIVEN** EDA atual, dilatação não-atual estruturada e declaração canônica vigente eda_dilation
- **WHEN** reprocessamento automático executa
- **THEN** regra existente de cobertura máxima prossegue com declaração
- **AND** união bruta eda + eda_dilation permanece auditável.

#### Scenario: Sem item estruturado o comportamento não muda
- **GIVEN** mesmo texto sem item estruturado do tipo e sem confirmação humana
- **WHEN** detecção/reconciliação executam
- **THEN** menção isolada não cria identidade e comportamento automático permanece.

#### Scenario: União sem combinação válida continua fail-closed
- **GIVEN** união sem cobertura por seleção válida e sem confirmação humana
- **WHEN** reconciliação automática executa
- **THEN** ação é nir_review
- **AND** payload expõe união bruta sem descartar componentes.

#### Scenario: Confirmação resolve união sem cobertura
- **GIVEN** mesmo gate anterior e NIR confirma um singleton canônico da fonte revisada
- **WHEN** análise aplica a confirmação válida
- **THEN** análise prossegue com esse conjunto, mantendo strong/any e evidência originais
- **AND** não reabre o gate de identificação pela repetição dessa divergência.

## ADDED Requirements

### Requirement: Procedimento confirmado ausente no LLM1 usa dados comuns sem fabricação

O pipeline SHALL analisar o conjunto confirmado com dados comuns e detalhes específicos disponíveis, sem exigir item correspondente no LLM1. Dados ausentes SHALL permanecer unknown/ausentes e SHALL NOT receber evidência, subtipo ou exceção de outro componente. LLM2 SHALL receber lista fechada confirmada e sua origem humana separada do artefato original.

#### Scenario: Seleção não extraída
- **GIVEN** confirmação válida de CPRE, dados comuns presentes e nenhum item CPRE no LLM1
- **WHEN** policy e LLM2 executam
- **THEN** policy CPRE usa dados comuns/unknown e LLM2 recomenda exatamente CPRE
- **AND** nenhum evidence_span/item clínico CPRE é fabricado no JSON original
- **AND** ausência de dados específicos não reabre revisão de identificação.

#### Scenario: Combinado confirmado com um item ausente
- **GIVEN** conjunto humano EDA + Colonoscopia e só item EDA extraído
- **WHEN** análise conjunta executa
- **THEN** há policy/recomendação por ambos e pendências permanecem locais
- **AND** exceção de corpo estranho de EDA não é herdada por Colonoscopia.

#### Scenario: LLM2 diverge do conjunto confirmado
- **GIVEN** conjunto confirmado CPRE e LLM2 adiciona Ecoendoscopia
- **WHEN** contrato da resposta é validado
- **THEN** retries/erro de conjunto existentes continuam
- **AND** confirmação não dispensa validação nem vira aceite automático.

### Requirement: Artefatos LLM são verificados antes de persistir

O sistema SHALL rejeitar U+0000 em strings, chaves e valores aninhados de artefatos LLM1/LLM2 e textos derivados antes de persistir artefatos ou projetar seus efeitos. SHALL NOT remover silenciosamente conteúdo clínico, introduzir retry LLM novo ou enviar dados inválidos ao médico.

#### Scenario: Escape JSON vira caractere nulo
- **GIVEN** resposta JSON schema-válida com escape Unicode de U+0000 em string aninhada
- **WHEN** é decodificada e verificada
- **THEN** falha explícita llm_output_not_persistable identifica a etapa
- **AND** nenhum artefato/projeção baseado nesse resultado é gravado.

#### Scenario: Texto literal não é caractere nulo
- **GIVEN** string contém literalmente os seis caracteres barra-u-zero-zero-zero-zero, sem U+0000 após decode
- **WHEN** verificação executa
- **THEN** não remove nem modifica esse texto por confundi-lo com o caractere nulo.

#### Scenario: LLM2 não persistível
- **GIVEN** resultado LLM1 válido e LLM2 contém U+0000 em rationale
- **WHEN** verificação executa
- **THEN** não grava recomendação inválida nem envia caso ao médico
- **AND** resultados válidos já gravados permanecem auditáveis.

### Requirement: Falha de persistência tem desfecho auditável independente do artefato inválido

O pipeline SHALL registrar falha técnica e transição FSM apropriada usando estado persistido íntegro, sem resalvar o artefato rejeitado. Se o desfecho de erro não puder ser persistido, SHALL propagar exceção ao worker e SHALL NOT retornar sucesso falso. Erros/logs SHALL usar informação técnica limitada sem raw clínico ou SQL recusado.

#### Scenario: Save rejeitado não contamina auditoria
- **GIVEN** save de artefato falha e instância em memória contém dado inválido
- **WHEN** tratamento de falha executa
- **THEN** PIPELINE_FAILED é persistido com etapa/código seguros e caso vai a FAILED pela FSM adequada
- **AND** rejeição não impede a Linha do Tempo de informar a falha.

#### Scenario: Registro de falha também falha
- **GIVEN** handler não consegue persistir o desfecho de erro
- **WHEN** tarefa termina
- **THEN** exceção chega ao worker
- **AND** job não é marcado como sucesso por retorno normal do handler.

#### Scenario: Estado avançou por outro ator
- **GIVEN** estado persistido já avançou além da etapa falha
- **WHEN** handler recarrega o caso
- **THEN** não força regressão nem status direto
- **AND** incompatibilidade é tratada explicitamente, não escondida como sucesso.

#### Scenario: Falha não vaza conteúdo clínico
- **GIVEN** exceção DB inclui trecho JSON clínico no CONTEXT
- **WHEN** erro é tratado e apresentado
- **THEN** evento/log controlado não inclui raw, trecho clínico ou SQL recusado
- **AND** código/etapa permitem diagnóstico.
