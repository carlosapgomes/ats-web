# procedure-combination-policy Delta

## MODIFIED Requirements

### Requirement: Matriz de conjuntos SHALL ser fechada

Somente qualquer singleton canônico e o conjunto exato {eda, colonoscopy} SHALL ser válidos em declaração, projeção operacional reconciliada e autorização. Sem confirmação humana válida, precedências textuais e cobertura máxima SHALL preservar o fail-closed existente. Com confirmação NIR válida, o conjunto escolhido permitido SHALL definir a análise mesmo sem cobrir a união automática; isso SHALL NOT ampliar a matriz. Em todos os casos, auditoria SHALL preservar evidência bruta completa, distinguindo resolução humana de detecção.

#### Scenario: Única combinação permitida
- **WHEN** conjunto reconciliado ou confirmado contém exatamente EDA e Colonoscopia
- **THEN** é válido e segue combinado/agendamento casado.

#### Scenario: Um especializado atual com procedimentos convencionais
- **WHEN** união automática contém um especializado e convencionais, com ocorrência atual do especializado
- **THEN** precedência especializada existente atua antes da matriz
- **AND** conjunto automático reconciliado contém só o especializado.

#### Scenario: Base absorvida pelo pacote na exibição e na decisão
- **WHEN** evidência reúne eda e eda_dilation sem confirmação humana
- **THEN** cobertura máxima apresenta eda_dilation
- **AND** evento preserva união bruta, sem criar combinação persistida nova.

#### Scenario: União bruta válida passa inalterada pelo payload
- **WHEN** conjunto automático detectado é {eda, colonoscopy}
- **THEN** payload mantém ambos e nenhuma chave interna vaza à UI.

#### Scenario: Item estruturado sem ocorrência textual com declaração do pacote e evidência atual prossegue
- **GIVEN** item eda_dilation sem ocorrência textual, EDA atual e declaração eda_dilation
- **WHEN** reconciliação automática avalia a união
- **THEN** cobertura máxima igual à declaração com any não-vazio permite prosseguir
- **AND** união bruta permanece no evento.

#### Scenario: Combinação especializada incompatível
- **WHEN** união automática contém Ecoendoscopia e CPRE sem confirmação humana válida
- **THEN** caso vai à revisão NIR
- **AND** nenhum especializado é escolhido arbitrariamente.

#### Scenario: Variação com Colonoscopia
- **WHEN** conjunto contém variação junto de Colonoscopia sem resolução humana válida
- **THEN** declaração/autorização proibida é rejeitada ou evidência automática segue à revisão
- **AND** detector não descarta componente para fabricar validade.

#### Scenario: Duas identidades atômicas fora do combinado
- **WHEN** request tenta confirmar ou autorizar duas identidades distintas fora de EDA + Colonoscopia
- **THEN** é rejeitado como incompatível
- **AND** consentimento humano não amplia catálogo/matriz.

#### Scenario: Tipo desconhecido não é descartado
- **WHEN** declaração ou evidência automática contém tipo desconhecido junto de tipo suportado
- **THEN** request é rejeitado ou detecção segue à revisão explicitamente
- **AND** valor desconhecido não é descartado para produzir validade automática.

#### Scenario: Humano resolve evidência incompatível para singleton
- **GIVEN** revisão por EDA + Ecoendoscopia + CPRE
- **WHEN** NIR confirma CPRE da fonte revisada com consentimento e justificativa
- **THEN** CPRE define o conjunto efetivo permitido
- **AND** evento preserva os três tipos automáticos sem aparentar consenso do detector.

#### Scenario: Humano confirma mesma seleção sem cobertura automática
- **GIVEN** declaração CPRE e união automática sem cobertura válida
- **WHEN** NIR confirma novamente CPRE na revisão
- **THEN** análise usa CPRE e não repete o gate pela mesma divergência
- **AND** policy e decisão médica permanecem obrigatórias.

### Requirement: Mismatch especializado SHALL retornar ao NIR

Sem confirmação humana válida da fonte, mismatch especializado SHALL retornar ao NIR e SHALL NOT existir upgrade automático entre convencional e especializado. Precedência SHALL alterar somente o conjunto automático bruto, sem sobrescrever declaração. Upgrade automático SHALL permanecer restrito a EDA ou Colonoscopia única detectada como {eda, colonoscopy} com evidência forte. Confirmação explícita posterior SHALL resolver identificação conforme nir-procedure-review, sem se tornar upgrade automático.

#### Scenario: EDA declarada e Ecoendoscopia detectada
- **WHEN** declaração EDA e precedência automática Ecoendoscopia, sem confirmação humana
- **THEN** caso retorna ao NIR por mismatch
- **AND** nenhuma dimensão é sobrescrita silenciosamente.

#### Scenario: Tipo especializado declarado e EDA detectada
- **WHEN** declaração Ecoendoscopia ou CPRE e detecção automática somente EDA, sem confirmação humana
- **THEN** caso retorna ao NIR por mismatch.

#### Scenario: Confirmação posterior resolve mismatch
- **GIVEN** revisão de mismatch entre declaração CPRE e detecção Ecoendoscopia
- **WHEN** NIR confirma CPRE com leitura e justificativa da fonte atual
- **THEN** CPRE define a análise, sem upgrade automático
- **AND** divergência continua auditável para o médico.
