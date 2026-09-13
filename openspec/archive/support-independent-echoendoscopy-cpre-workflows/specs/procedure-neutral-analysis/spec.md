## MODIFIED Requirements

### Requirement: História clínica comum é extraída uma única vez

Cada novo processamento MUST executar uma única extração LLM1 procedure-neutral 3.0 por caso e MUST representar EDA, Colonoscopia, Ecoendoscopia e CPRE como coleção tipada sujeita à matriz fechada.

#### Scenario: Solicitação especializada válida

- **GIVEN** texto contém solicitação atual sustentada de Ecoendoscopia ou CPRE
- **WHEN** LLM1 3.0 processa o caso
- **THEN** produz uma única história/pré-operatório comum
- **AND** `requested_procedures` contém exatamente o procedimento especializado
- **AND** não o representa também como EDA.

#### Scenario: Solicitação combinada válida

- **GIVEN** texto contém solicitações atuais sustentadas de EDA e Colonoscopia
- **WHEN** LLM1 3.0 processa o caso
- **THEN** produz uma única história/pré-operatório comum
- **AND** `requested_procedures` contém exatamente EDA e Colonoscopia
- **AND** não existem dois artefatos concorrentes de paciente/história.

#### Scenario: Procedimento inventado

- **GIVEN** apenas EDA possui evidência de solicitação atual
- **WHEN** resposta LLM1 inclui procedimento sem evidência válida
- **THEN** contrato/reconciliação rejeita ou encaminha para revisão
- **AND** o procedimento não se torna detectado silenciosamente.

### Requirement: Policy e recomendação são por procedimento

O sistema MUST avaliar separadamente cada procedimento reconciliado e MUST executar uma única análise LLM2 3.0 conjunta por caso. A chamada MUST receber apenas itens pertencentes ao conjunto reconciliado e uma lista fechada explícita. O artefato LLM1 persistido MUST permanecer inalterado.

A resposta LLM2 MUST conter exatamente uma recomendação para cada procedimento reconciliado, sem omissão, duplicata ou adição. Diante exclusivamente de resposta schema-válida com conjunto divergente, o serviço MAY realizar no máximo um retry corretivo específico. Um segundo mismatch MUST falhar explicitamente e MUST NOT produzir artefato parcial.

#### Scenario: Recomendação de Ecoendoscopia

- **GIVEN** somente Ecoendoscopia foi reconciliada
- **WHEN** orchestrator monta a chamada LLM2
- **THEN** prompt declara `["echoendoscopy"]` como conjunto fechado
- **AND** policy, contexto anterior e resposta usam somente Ecoendoscopia.

#### Scenario: Recomendação de CPRE

- **GIVEN** somente CPRE foi reconciliada
- **WHEN** orchestrator monta a chamada LLM2
- **THEN** prompt declara `["cpre"]` como conjunto fechado
- **AND** resposta válida contém exatamente uma recomendação CPRE.

#### Scenario: Recomendações divergentes no combinado

- **GIVEN** caso EDA + Colonoscopia possui resultados de policy diferentes
- **WHEN** LLM2 3.0 responde
- **THEN** há uma recomendação por procedimento
- **AND** suporte global sugerido é o nível mais restritivo.

#### Scenario: LLM1 contém ambos mas somente EDA é reconciliada

- **GIVEN** artefato LLM1 contém EDA e Colonoscopia
- **AND** somente EDA é reconciliada como solicitação atual
- **WHEN** orchestrator monta LLM2
- **THEN** cópia efêmera e lista fechada contêm somente EDA
- **AND** artefato persistido continua inalterado.

#### Scenario: LLM1 contém ambos mas somente Colonoscopia é reconciliada

- **GIVEN** artefato LLM1 contém EDA e Colonoscopia
- **AND** somente Colonoscopia é reconciliada como solicitação atual
- **WHEN** orchestrator monta LLM2
- **THEN** cópia efêmera e lista fechada contêm somente Colonoscopia
- **AND** artefato persistido continua inalterado.

#### Scenario: Conjunto combinado permanece completo

- **GIVEN** EDA e Colonoscopia foram reconciliadas como solicitações atuais
- **WHEN** orchestrator monta LLM2
- **THEN** cópia efêmera mantém os dois itens
- **AND** prompt declara `["eda", "colonoscopy"]` como conjunto fechado
- **AND** resposta válida contém duas recomendações.

#### Scenario: Conjunto combinado permanece convencional

- **GIVEN** EDA e Colonoscopia foram reconciliadas
- **WHEN** orchestrator monta a chamada LLM2
- **THEN** prompt declara `["eda", "colonoscopy"]` como conjunto fechado
- **AND** nenhuma opção especializada é adicionada.

#### Scenario: Primeiro mismatch é corrigido

- **GIVEN** conjunto reconciliado foi incluído explicitamente no prompt
- **AND** primeira resposta schema-válida omite ou adiciona procedimento
- **WHEN** serviço detecta mismatch
- **THEN** executa exatamente uma tentativa corretiva com o mesmo conjunto
- **AND** aceita a segunda resposta somente se todas as validações passarem.

#### Scenario: Mismatch persiste após retry

- **GIVEN** tentativa corretiva já foi consumida
- **WHEN** resposta ainda diverge
- **THEN** pipeline segue tratamento fail-closed
- **AND** nenhuma recomendação parcial chega ao médico.

#### Scenario: Erro não relacionado ao conjunto

- **GIVEN** resposta é inválida por JSON, schema, duplicata, ids ou idioma
- **WHEN** validação falha
- **THEN** retry específico de conjunto não é executado
- **AND** erro permanece explícito.

### Requirement: Artefatos legados continuam legíveis

Presenters e auditoria MUST ler schemas 1.1 e 2.0 históricos e schema 3.0 novo sem reescrever JSON antigo. O subtipo/sinal histórico de Ecoendoscopia MUST continuar apresentável, mas novos artefatos 3.0 MUST usar a identidade independente e MUST NOT duplicá-la como sinal.

#### Scenario: Caso antigo de Ecoendoscopia

- **GIVEN** caso possui schema 1.1/2.0 com subtipo ou sinal `echoendoscopy`
- **WHEN** usuário autorizado abre detalhe/histórico após cutover
- **THEN** conteúdo continua renderizável
- **AND** nenhum procedimento novo é criado automaticamente.

#### Scenario: Caso antigo aberto após cutover

- **GIVEN** caso possui `structured_data` schema 1.1 ou 2.0
- **WHEN** usuário autorizado abre detalhe/histórico
- **THEN** conteúdo continua renderizável
- **AND** nenhuma migration altera o JSON clínico.

## REMOVED Requirements

### Requirement: Dispatch LLM de produção vincula strict schema ao contrato 2.0

**Reason:** O contrato 2.0 é fechado em EDA/Colonoscopia e deixa de ser writer após o cutover 3.0.

**Migration:** Drenar jobs 2.0 antes do cutover, ativar exatamente uma versão 3.0 dos quatro prompts neutros e manter schemas/adapters 2.0 somente para leitura histórica. Depois do primeiro write 3.0, rollback não reativa writer 2.0.

## ADDED Requirements

### Requirement: Dispatch LLM de produção SHALL vincular strict schema ao contrato 3.0

O pipeline de produção, sem cliente LLM injetado, SHALL vincular novos processamentos exclusivamente aos strict schemas 3.0. Schemas 1.1/2.0 SHALL permanecer somente em adapters e leitores históricos após o cutover.

#### Scenario: LLM1 de produção recebe strict schema 3.0

- **GIVEN** o pipeline cria o cliente LLM1 sem injeção de teste após o cutover
- **WHEN** a chamada à API é montada
- **THEN** `response_format` usa `json_schema` strict
- **AND** o schema vinculado define `schema_version` fixo em `"3.0"`
- **AND** aceita quatro tipos e evidência abdominal tipada
- **AND** não contém chaves exclusivas do contrato 1.1.

#### Scenario: LLM2 de produção recebe strict schema 3.0

- **GIVEN** o pipeline cria o cliente LLM2 sem injeção de teste após o cutover
- **WHEN** a chamada à API é montada
- **THEN** `response_format` usa `json_schema` strict
- **AND** o schema vinculado define `schema_version` fixo em `"3.0"`
- **AND** `procedure_recommendations` aceita os quatro tipos.

#### Scenario: Schema 3.0 é compatível com normalização strict

- **GIVEN** o JSON Schema de `Llm1ResponseV3` ou `Llm2ResponseV3`
- **WHEN** a normalização strict é aplicada
- **THEN** todo nó objeto declara `additionalProperties: false`
- **AND** todo nó objeto lista todas as propriedades em `required`
- **AND** nenhuma construção incompatível com strict mode permanece.

### Requirement: Evidência abdominal SHALL separar modalidade, anatomia e achado

LLM1 3.0 SHALL extrair imagens do relatório principal em coleção tipada com modalidade, localização anatômica, presença de conclusão/achado, trecho-fonte e data opcional. `tracked_exams` textual e anexos MUST NOT satisfazer a hard rule.

#### Scenario: TC sem anatomia

- **GIVEN** relatório menciona resultado de TC sem indicar abdome/abdome superior
- **WHEN** evidência é normalizada
- **THEN** localização permanece não especificada
- **AND** a imagem não satisfaz Ecoendoscopia nem CPRE.

#### Scenario: Mera solicitação de imagem

- **GIVEN** relatório apenas solicita ou agenda uma imagem
- **WHEN** LLM1 extrai o documento
- **THEN** `report_finding_present` não é verdadeiro
- **AND** a imagem não satisfaz a policy.

#### Scenario: Data antiga disponível

- **GIVEN** imagem qualificante possui conclusão/achado e data antiga
- **WHEN** policy executa
- **THEN** data é preservada
- **AND** antiguidade não invalida o requisito.

### Requirement: Evidência de imagem SHALL estar ancorada no relatório principal

Antes da hard rule, o sistema MUST verificar deterministicamente que contexto e conclusão/achado extraídos correspondem a trecho real e único do relatório principal. No mesmo contexto, o sistema MUST rederivar modalidade/anatomia por aliases versionados e exigir predicado positivo de resultado ou heading estrito de conclusão/achados/laudo/resultado. Substantivo isolado não é marcador positivo; qualquer intenção/agendamento na mesma oração MUST dominar e rejeitar. Mismatch, aliases conflitantes, ocorrência duplicada, contexto amplo com imagens distintas ou classificação ambígua MUST falhar fechados. Campo declarado pelo LLM, `tracked_exams` ou conteúdo somente em anexo MUST NOT satisfazer.

#### Scenario: Excerpt inventado pelo LLM

- **GIVEN** LLM1 declara modalidade/anatomia/achado válidos, mas o excerpt não existe no texto do relatório principal
- **WHEN** evidência é verificada antes da policy
- **THEN** ela é marcada insuficiente
- **AND** a sugestão é negar por requisito de imagem não comprovado.

#### Scenario: Solicitação real rotulada como achado

- **GIVEN** relatório principal contém apenas `solicita TC de abdome`
- **AND** LLM1 declara `ct`, `abdomen` e `report_finding_present=yes`
- **WHEN** evidência é verificada antes da policy
- **THEN** marcador de intenção torna a evidência insuficiente
- **AND** a sugestão é negar.

#### Scenario: Palavra laudo não contorna intenção ou agendamento

- **GIVEN** cada contexto `solicita laudo de TC de abdome` e `laudo de TC de abdome agendado`
- **AND** LLM1 declara achado presente
- **WHEN** evidência é verificada
- **THEN** intenção/estado futuro domina a palavra isolada `laudo`
- **AND** a sugestão é negar.

#### Scenario: Mera menção ao exame

- **GIVEN** contexto menciona TC de abdome sem predicado de resultado e sem heading estrito
- **WHEN** evidência é verificada
- **THEN** a menção é insuficiente
- **AND** a sugestão é negar.

#### Scenario: Modalidade ou anatomia não corresponde ao contexto

- **GIVEN** contexto ancorado não contém aliases da modalidade e anatomia declaradas
- **WHEN** verificador rederiva esses campos
- **THEN** mismatch é rejeitado fail-closed
- **AND** trecho real não relacionado não satisfaz a hard rule.

#### Scenario: Contexto conflitante ou ambíguo

- **GIVEN** contexto contém aliases conflitantes, duas imagens distintas, mais de uma ocorrência normalizada ou não pode ser delimitado a uma entrada inequívoca
- **WHEN** evidência é verificada
- **THEN** ela é rejeitada fail-closed
- **AND** a sugestão é negar por imagem não comprovada.

#### Scenario: Evidência presente somente em tracked exams

- **GIVEN** `tracked_exams` contém texto de imagem qualificante
- **AND** relatório principal não contém contexto/achado verificável correspondente
- **WHEN** hard rule executa
- **THEN** `tracked_exams` não é promovido a evidência
- **AND** a sugestão é negar.

#### Scenario: Achado presente somente em anexo

- **GIVEN** relatório principal não contém conclusão/achado qualificante e um anexo separado contém o laudo
- **WHEN** pipeline do primeiro rollout executa
- **THEN** o texto do anexo não é usado pela verificação
- **AND** a sugestão é negar
- **AND** o relatório médico informa que anexos não participaram da automação.

#### Scenario: Excerpt real no relatório principal

- **GIVEN** contexto e excerpt correspondem ao relatório principal após normalização conservadora
- **AND** modalidade/anatomia rederivadas coincidem e há predicado positivo ou heading estrito de resultado
- **WHEN** evidência é verificada
- **THEN** ela pode seguir para a policy
- **AND** a correspondência por si só não contorna os demais requisitos.

### Requirement: Ecoendoscopia SHALL exigir imagem adicional

Ecoendoscopia MUST aplicar todos os critérios comuns da EDA, sem exceção de corpo estranho, e MUST exigir pelo menos TC ou RM de abdome/abdome superior com conclusão ou achado.

#### Scenario: Ecoendoscopia com RM qualificante

- **GIVEN** critérios comuns atendidos e RM de abdome superior possui conclusão
- **WHEN** policy executa
- **THEN** requisito adicional está atendido.

#### Scenario: Ecoendoscopia somente com USG

- **GIVEN** critérios comuns atendidos e apenas USG abdominal possui laudo
- **WHEN** policy executa
- **THEN** sugestão reconciliada é negar por ausência de TC/RM qualificante.

### Requirement: CPRE SHALL exigir imagem adicional

CPRE MUST aplicar todos os critérios comuns da EDA, sem exceção de corpo estranho, e MUST exigir pelo menos USG abdominal/abdome superior/hepatobiliar, TC/RM de abdome/abdome superior ou CPRM com conclusão ou achado.

#### Scenario: USG hepatobiliar qualificante

- **GIVEN** critérios comuns atendidos e USG hepatobiliar possui achado
- **WHEN** policy CPRE executa
- **THEN** requisito adicional está atendido.

#### Scenario: Exame sem achado

- **GIVEN** modalidade/anatomia são aceitas, mas não há conclusão/achado do laudo
- **WHEN** policy executa
- **THEN** sugestão reconciliada é negar.

### Requirement: Policy SHALL agregar todas as pendências

A avaliação SHALL retornar coleção ordenada de todos os requisitos não atendidos e SHALL preservar motivo primário compatível para consumidores históricos. Qualquer item na coleção MUST forçar sugestão final de negativa, sem impedir decisão médica divergente.

#### Scenario: Múltiplas pendências

- **GIVEN** CPRE sem plaquetas, creatinina, ECG condicional e imagem qualificante
- **WHEN** policy e reconciliação executam
- **THEN** todos os quatro requisitos aparecem na coleção
- **AND** sugestão final é negar
- **AND** motivo primário permanece determinístico.

#### Scenario: LLM2 contradiz hard rule

- **GIVEN** policy possui pelo menos uma pendência e LLM2 sugere aceitar
- **WHEN** reconciliação executa
- **THEN** sugestão é corrigida para negar
- **AND** contradição fica auditada.
