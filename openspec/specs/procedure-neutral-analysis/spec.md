# procedure-neutral-analysis Specification

## Purpose
TBD - created by archiving change support-combined-eda-colonoscopy-workflow. Update Purpose after archive.

## Requirements

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

### Requirement: Detecção reconcilia declaração sem apagar proveniência

O sistema MUST preservar a declaração do NIR e persistir detecção separadamente.

#### Scenario: Upgrade automático para combinado

- **GIVEN** NIR declarou somente EDA ou somente Colonoscopia
- **AND** evidência forte confirma duas solicitações atuais
- **WHEN** reconciliação executa
- **THEN** ambos os procedimentos ficam detectados
- **AND** caso segue ao médico sem ACK prévio do NIR
- **AND** evento registra declaração original, seleção detectada e base codificada da evidência.

#### Scenario: Combinado declarado mas somente um detectado

- **GIVEN** NIR declarou EDA + Colonoscopia
- **WHEN** apenas um procedimento é detectado
- **THEN** caso retorna à revisão do NIR
- **AND** não entra em `WAIT_DOCTOR`.

#### Scenario: Tipos únicos contraditórios

- **GIVEN** NIR declarou EDA e somente Colonoscopia é detectada, ou vice-versa
- **WHEN** reconciliação executa
- **THEN** caso retorna ao NIR como mismatch
- **AND** nenhum upgrade/swap silencioso ocorre.

### Requirement: Referências históricas e negações não criam combinação

Detecção MUST qualificar cada ocorrência por solicitação atual, histórico e negação.

#### Scenario: EDA histórica e Colonoscopia atual

- **GIVEN** texto informa EDA realizada no passado e solicita Colonoscopia agora
- **WHEN** detector executa
- **THEN** somente Colonoscopia fica detectada.

#### Scenario: Outro procedimento negado

- **GIVEN** texto solicita EDA e nega indicação de Colonoscopia
- **WHEN** detector executa
- **THEN** somente EDA fica detectada.

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

### Requirement: Exceções permanecem locais ao procedimento

A avaliação combinada MUST compartilhar dados comuns sem vazar exceções específicas.

#### Scenario: Corpo estranho em caso combinado

- **GIVEN** componente EDA é corpo estranho e componente Colonoscopia também existe
- **WHEN** policies executam
- **THEN** exceção pode afetar somente EDA
- **AND** Colonoscopia mantém seus critérios normais.

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

### Requirement: Schema enviado à API SHALL converter uniões oneOf para anyOf

O normalizador de strict schema SHALL reescrever todo nó `oneOf` como `anyOf`
e SHALL remover a chave `discriminator` do schema enviado à API, preservando
as variantes originais da união. Os modelos Pydantic e a validação local
SHALL permanecer inalterados.

#### Scenario: União discriminada do LLM1 é aceita pela API

- **GIVEN** o schema de `Llm1ResponseV2` serializado por `model_json_schema()`
- **WHEN** a normalização strict é aplicada
- **THEN** nenhuma chave `oneOf` permanece em qualquer nível
- **AND** nenhuma chave `discriminator` permanece em qualquer nível
- **AND** a união de `requested_procedures.items` continua presente como `anyOf` com as mesmas variantes

#### Scenario: Schema sintético com oneOf e discriminator é convertido

- **GIVEN** um schema contendo um nó com `oneOf` e `discriminator`
- **WHEN** a normalização strict é aplicada
- **THEN** o nó passa a conter `anyOf` com a mesma lista de variantes
- **AND** `oneOf` e `discriminator` são removidos
- **AND** o schema original não é mutado

### Requirement: Evidência abdominal SHALL separar modalidade, anatomia e achado

LLM1 4.0 SHALL preservar a extração 3.0 de imagens do relatório principal em coleção tipada com modalidade, localização anatômica, presença de conclusão/achado, trecho-fonte e data opcional. `tracked_exams` textual e anexos MUST NOT satisfazer a hard rule de Ecoendoscopia/CPRE.

#### Scenario: TC sem anatomia

- **GIVEN** o relatório menciona resultado de TC sem indicar abdome/abdome superior
- **WHEN** evidência é normalizada
- **THEN** localização permanece não especificada
- **AND** a imagem não satisfaz Ecoendoscopia nem CPRE.

#### Scenario: Mera solicitação de imagem

- **GIVEN** o relatório apenas solicita ou agenda uma imagem
- **WHEN** LLM1 extrai o documento
- **THEN** `report_finding_present` não é verdadeiro
- **AND** a imagem não satisfaz a policy.

#### Scenario: Data antiga disponível

- **GIVEN** imagem qualificante possui conclusão/achado e data antiga
- **WHEN** a policy executa
- **THEN** a data é preservada
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

### Requirement: Detalhe de EDA + Dilatação SHALL ser anatômico e informativo

Para `eda_dilation`, LLM1 4.0 SHALL extrair exatamente um local entre `esophagus`, `pylorus`, `duodenum`, `anastomosis`, `jejunum`, `other` e `unknown`, acompanhado de trecho-fonte quando documentado. O local SHALL NOT criar identidade nova, modificar profile/policy, sugestão ou disposição e SHALL permanecer `unknown` quando o texto não sustentar uma opção.

#### Scenario: Local explícito

- **GIVEN** a solicitação atual de EDA + Dilatação informa dilatação de piloro
- **WHEN** LLM1 4.0 é validado e apresentado
- **THEN** o local é `pylorus`
- **AND** o procedimento continua `eda_dilation`.

#### Scenario: Local ausente

- **GIVEN** a solicitação pede EDA + Dilatação sem informar local
- **WHEN** LLM1 4.0 é validado
- **THEN** o local é `unknown`
- **AND** nenhuma pendência clínica é criada.

#### Scenario: Local não ancorado

- **GIVEN** a resposta declara um local cujo trecho não existe no relatório principal
- **WHEN** a evidência é verificada
- **THEN** o local apresentado cai para `unknown`
- **AND** a policy permanece inalterada.

### Requirement: Writers 3.0 SHALL encerrar antes do primeiro write 4.0

O cutover SHALL drenar jobs de análise, ativar web, workers e prompts 4.0 de forma coordenada e MUST NOT permitir writers 3.0 e 4.0 concorrentes. Nenhuma nova flag de produto SHALL mediar o rollout das identidades deste change.

#### Scenario: Job 3.0 em voo

- **GIVEN** existe job 3.0 ainda executando
- **WHEN** a operação tenta iniciar o writer 4.0
- **THEN** o cutover é interrompido até a drenagem
- **AND** nenhum write 4.0 é iniciado.

#### Scenario: Primeiro write 4.0 concluído

- **GIVEN** ao menos um artefato 4.0 foi persistido
- **WHEN** ocorre incidente após o cutover
- **THEN** rollback para writer 3.0 não é suportado
- **AND** a recuperação preserva dados e corrige para frente.

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
