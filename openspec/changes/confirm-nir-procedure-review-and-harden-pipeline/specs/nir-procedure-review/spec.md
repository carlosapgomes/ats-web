# nir-procedure-review Delta

## Purpose

Define a confirmação explícita do procedimento solicitado pelo NIR após revisão manual, com autoridade limitada à fonte revisada, rastreabilidade humana e continuidade da análise até a avaliação médica.

## ADDED Requirements

### Requirement: Revisão permite confirmar a mesma seleção ou outra seleção válida

O sistema SHALL permitir ao NIR confirmar a seleção vigente ou outra seleção canônica habilitada quando o caso estiver em revisão manual elegível pré-médica. SHALL exigir leitura confirmada e justificativa breve, sem exigir reescrita do relatório ou mudança artificial da seleção.

#### Scenario: Mesmo procedimento confirmado
- **GIVEN** caso em revisão por divergência automática com seleção CPRE vigente
- **WHEN** NIR confirma CPRE, leitura e justificativa
- **THEN** a ação é aceita como revisão humana
- **AND** o caso segue à análise, sem erro de seleção igual.

#### Scenario: Troca confirmada
- **GIVEN** seleção EDA e revisão de conflito com argônio
- **WHEN** NIR confirma Retossigmoidoscopia + Argônio e justifica
- **THEN** somente essa identidade fica declarada para a análise
- **AND** o relatório original não precisa ser reescrito.

#### Scenario: Consentimento ou justificativa ausentes
- **WHEN** POST não contém consentimento explícito ou justificativa não vazia válida
- **THEN** nenhum evento de confirmação, transição ou enqueue ocorre
- **AND** a interface informa o erro e preserva a escolha/justificativa tentadas sem marcar consentimento automaticamente.

### Requirement: Autoridade humana resolve somente a identificação do procedimento

Confirmação válida SHALL definir o conjunto de procedimentos analisado para a fonte revisada, mesmo sem cobertura da evidência automática ou item LLM1 correspondente. SHALL NOT dispensar policy clínica, validação de artefatos, catálogo, segurança ou decisão médica. Sem confirmação explícita, as regras automáticas SHALL permanecer inalteradas.

#### Scenario: Conflito repetido não bloqueia confirmação
- **GIVEN** NIR confirmou um singleton permitido após revisão
- **WHEN** reprocessamento repete a mesma união automática incompatível
- **THEN** essa divergência não reabre revisão de procedimento
- **AND** a análise clínica usa o singleton confirmado.

#### Scenario: Policy continua negando
- **GIVEN** CPRE foi confirmada mas imagem exigida não está comprovada
- **WHEN** a análise continua
- **THEN** a pendência e a sugestão clínica de negativa permanecem
- **AND** a confirmação não equivale a aceite médico.

#### Scenario: Declaração sem confirmação não adquire autoridade
- **GIVEN** seleção coincide com item contraditado e não há confirmação humana explícita
- **WHEN** processamento automático executa
- **THEN** a coincidência sozinha não libera o gate existente.

### Requirement: Confirmação está vinculada à revisão e à fonte

A confirmação SHALL identificar a revisão vista e a fonte principal revisada. Fonte, revisão ou declaração posteriormente alteradas SHALL invalidar seu uso. O sistema SHALL NOT reutilizar uma confirmação anterior inválida nem inferir consentimento de correções históricas.

#### Scenario: Documento mudou desde a tela
- **GIVEN** NIR abriu a revisão e a fonte principal mudou antes do POST
- **WHEN** confirma com os dados antigos da tela
- **THEN** backend recusa sem mutação/enqueue
- **AND** solicita revisar a fonte atual.

#### Scenario: Fonte mudou antes da aplicação
- **GIVEN** confirmação válida foi gravada e fonte mudou antes do job
- **WHEN** análise tenta aplicar a confirmação
- **THEN** a confirmação não é usada
- **AND** sua invalidação fica auditada e a análise retorna às regras automáticas.

#### Scenario: Correção antiga não vira confirmação
- **GIVEN** histórico contém CASE_PROCEDURE_DECLARATION_CORRECTED anterior ao novo fluxo
- **WHEN** caso é analisado
- **THEN** o evento antigo não adquire autoridade humana retroativa.

### Requirement: Confirmação e encerramento são mutuamente exclusivos

A ação SHALL exigir ator NIR, papel ativo NIR e reserva válida, revalidando elegibilidade sob serialização com confirmação de recebimento. Duplo envio ou corrida SHALL NOT produzir confirmação/análise duplicada ou atualização parcial. Casos encerrados, em análise ou já médicos SHALL NOT aceitar nova confirmação por esse fluxo.

#### Scenario: Corrida com encerramento
- **WHEN** confirmação de procedimento e confirmação de recebimento disputam o mesmo caso
- **THEN** somente a operação elegível vencedora é persistida
- **AND** a outra não modifica estado nem enfileira análise.

#### Scenario: Papel ou reserva incompatível
- **WHEN** ator sem papel ativo NIR ou com reserva expirada/trocada tenta confirmar
- **THEN** a ação falha sem efeitos parciais.

#### Scenario: Double POST
- **WHEN** o mesmo submit válido chega duas vezes
- **THEN** existe uma confirmação e um enqueue da operação vencedora
- **AND** o segundo request não reabre o fluxo.

### Requirement: Linha do Tempo identifica quem confirmou qual procedimento

Cada confirmação SHALL gerar evento humano append-only com ator, data/hora, conjunto anterior/confirmado, justificativa e referência à revisão. A Linha do Tempo SHALL mostrar nome legível do autor, label canônico da seleção confirmada e manutenção/troca, inclusive após encerramento. Aplicação/invalidação SHALL aparecer como eventos sistêmicos distintos, sem substituir a confirmação.

#### Scenario: Seleção mantida aparece explicitamente
- **WHEN** NIR confirma CPRE já vigente e abre a Linha do Tempo
- **THEN** vê “Procedimento confirmado pelo NIR: CPRE”, autor, horário, justificativa e informação de seleção mantida
- **AND** não vê apenas “Reprocessamento solicitado”.

#### Scenario: Troca e histórico posterior
- **WHEN** seleção muda para Retossigmoidoscopia + Argônio e caso posteriormente é encerrado
- **THEN** a Linha do Tempo conserva quem confirmou a nova seleção, horário e justificativa
- **AND** evidência e eventos anteriores permanecem intactos.

#### Scenario: Texto livre escapado
- **WHEN** justificativa contém markup
- **THEN** ela aparece como texto escapado, sem execução HTML/JS.

### Requirement: Evidência automática e projeção humana têm proveniência distinta

O sistema SHALL preservar artefato e união bruta da detecção automática. A projeção operacional após confirmação SHALL conter somente o conjunto confirmado permitido e SHALL ser identificada como confirmação NIR, não detecção automática ou autorização médica.

#### Scenario: Detecção de três e confirmação de um
- **GIVEN** LLM identifica EDA, Ecoendoscopia e CPRE
- **WHEN** NIR confirma CPRE
- **THEN** o evento de detecção mantém os três códigos e o artefato original
- **AND** fila, análise e projeção operacional usam CPRE com proveniência humana explícita.

### Requirement: Médico vê a confirmação antes de decidir

A avaliação médica SHALL apresentar aviso não bloqueante com procedimento confirmado, autor, justificativa e referência à divergência automática. SHALL informar que confirmação NIR não é aprovação clínica. Leitores legados sem confirmação SHALL continuar funcionando sem aviso inventado.

#### Scenario: Confirmação mantida é visível ao médico
- **WHEN** médico abre caso cuja seleção foi mantida após revisão NIR
- **THEN** vê autoria e procedimento confirmado mesmo sem precedência automática
- **AND** decisão e razões médicas continuam obrigatórias conforme o fluxo atual.

#### Scenario: Caso sem confirmação
- **WHEN** médico abre caso legado/automático sem evento de confirmação
- **THEN** nenhum aviso humano fictício é apresentado.

### Requirement: Falha de enqueue não apaga confirmação

O sistema SHALL preservar confirmação commitada quando enqueue pós-commit falhar e SHALL informar se recovery foi agendado ou não. SHALL NOT prometer análise retomada quando nenhuma recuperação existe.

#### Scenario: Recovery disponível
- **WHEN** enqueue falha e recovery é programado
- **THEN** confirmação continua na Linha do Tempo
- **AND** NIR recebe mensagem de tentativa programada, não falsa chegada à fila médica.

#### Scenario: Recovery também falha
- **WHEN** enqueue e agendamento de recovery falham
- **THEN** confirmação permanece durável
- **AND** mensagem informa necessidade de suporte, sem afirmar retomada automática.
