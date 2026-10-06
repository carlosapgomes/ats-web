# Requisitos de produto — base independente de stack

> **Status:** documento de extração para revisão pelo responsável pelo produto; não é autorização de implementação, migração ou substituição da produção.
> **Base examinada:** repositório `ats-web`, branch `main`, commit `a6fb4879752b88876284efca3a99dbcb4a90ed75` (`v0.10.0-rc.10`).
> **Finalidade:** preservar o conhecimento do sistema atual e acrescentar requisitos simples de minimização de PII. As abstrações e os requisitos do produto final serão acrescentados posteriormente pelo responsável.

## 1. Como ler este documento

- **[E] Existente:** comportamento identificado no código e/ou nas especificações vigentes da base examinada. Não significa validação ao vivo em produção nem garantia de ausência de bugs.
- **[P] Proposto:** proteção ou requisito adicional para a reescrita, ainda não implementado no sistema atual.
- **[D] Decisão pendente:** ponto que necessita de definição humana; não deve ser resolvido implicitamente pelo implementador.
- Os identificadores permitem referenciar requisitos sem vincular sua implementação a linguagem, framework, biblioteca, banco, interface ou serviço específicos.
- Valores operacionais e regras clínicas atuais são uma **base de compatibilidade**, não uma recomendação clínica nova. Alterá-los requer decisão explícita do responsável clínico.
- As fontes da seção 15 explicam a origem dos requisitos. Havendo conflito, este documento explicita a divergência em vez de combinar versões incompatíveis.

**Não se prescrevem:** classes, tabelas, ORM, número de processos, topologia de serviços, fornecedor de IA, mecanismo de fila, protocolos de API ou tecnologia de interface. Auditoria append-only não implica adotar event sourcing; processamento assíncrono não implica microserviços.

## 2. Objetivo e limites

O sistema apoia a regulação de encaminhamentos: recebe relatórios, organiza informações clínicas, aplica critérios determinísticos, oferece apoio à avaliação médica, conduz agendamento ou ciência operacional e devolve uma resposta rastreável ao NIR.

A decisão clínica final é humana. O sistema não substitui o médico, não realiza o procedimento e não comprova sozinho a disponibilidade de leito, sala, profissional ou transporte.

### Escopo desta base

1. Fluxos atuais de procedimentos endoscópicos e seus modos de admissão.
2. Cadastro e acesso dos profissionais, filas, documentos, comunicação e notificações.
3. Extração e análise assistidas por IA, critérios clínicos, decisão, agendamento e encerramento.
4. Intercorrências posteriores ao aceite, desfechos e acompanhamento gerencial.
5. Proteção de PII por melhor esforço, identificada como proposta.

### Não definido nesta extração

- A modelagem futura de capacidades hospitalares, internações autônomas e cirurgias. A intenção de reuni-las na jornada de regulação é contexto futuro, **não funcionalidade existente**.
- Regras de vagas, inventário de leitos, salas, equipes, duração de procedimentos ou otimização de agenda.
- Integração automática com SUREM, prontuário ou sistemas externos: a transcrição no SUREM é uma atividade humana na rotina atual.
- OCR, análise automática de anexos ou envio de PDFs/imagens diretamente a modelos multimodais.
- Pacotes de anonimização, reconhecimento universal de entidades pessoais ou prova formal de anonimização.
- Plano de migração, cronograma de reescrita e compromisso de paridade em uma ou duas semanas.

## 3. Vocabulário de negócio

| Conceito | Significado |
|---|---|
| Caso | Um encaminhamento recebido, com identidade própria, documentos, processamento e histórico. |
| Ocorrência | Número do registro de regulação extraído do documento; não equivale a um cadastro mestre de paciente. |
| Procedimento | Uma identidade do catálogo atual que pode ser solicitada, detectada e autorizada. |
| Pacote atômico | Procedimento com variação indivisível, como EDA + GTT: recebe uma única decisão. |
| Combinado | Exclusivamente EDA + Colonoscopia, com dois componentes e um agendamento conjunto. |
| Solicitado | O que o NIR declarou no envio ou em correção posterior auditada. |
| Detectado | O conjunto resultante da análise e reconciliação da evidência do relatório. |
| Autorizado | O conjunto aprovado pelo médico; pode diferir do solicitado e do detectado. |
| Sugestão | Apoio automatizado, distinto da decisão médica efetiva. |
| Ciência operacional | Confirmação de que o CHD recebeu a informação; não é agendamento nem reserva de recurso. |
| Encerramento | Saída do fluxo operacional principal, preservando documentos e histórico. Não é eliminação de dados. |
| Pós-procedimento | Registro posterior do que efetivamente aconteceu; não substitui a decisão nem reabre o fluxo. |
| PII | Identificadores pessoais; neste escopo de proteção, principalmente nome, nome social e CNS do paciente. |

## 4. Papéis, contas e acesso

| ID | Origem | Requisito |
|---|---|---|
| AC-01 | [E] | Exigir autenticação para os fluxos de trabalho e oferecer login, logout, troca de senha e recuperação de acesso. |
| AC-02 | [E] | Permitir atribuição de múltiplos papéis a um profissional, com apenas um papel ativo por vez. O usuário deve identificar e trocar seu papel ativo; não pode selecionar papel não atribuído. |
| AC-03 | [E] | Reservar ao NIR o envio de encaminhamentos, correções elegíveis, confirmação de recebimento e abertura de intercorrências; ao médico, a avaliação e decisão; ao CHD/agendador, o agendamento e a ciência operacional. |
| AC-04 | [E] | Oferecer ao Supervisor consulta gerencial, métricas e acompanhamento. Gestão de contas e prompts pertence à Administração. Possuir vários papéis não autoriza executar uma ação usando o papel ativo errado. |
| AC-05 | [E] | Restringir registro, histórico e exportação de pós-procedimento ao Supervisor com vínculo CHD e papel ativo Supervisor, ou ao Administrador ativo, dispensado do vínculo CHD. CHD ativo sozinho não concede essa permissão. |
| AC-06 | [E] | Aplicar restrição de intranet ao NIR e CHD conforme a política atual: contas com somente papéis restritos são bloqueadas fora das redes configuradas; contas multipapel com algum papel não restrito têm exceção de rede. Sem configuração de rede válida, negar o acesso restrito. A exceção não dispensa autorização funcional. |
| AC-07 | [E] | Manter cadastro de identificação profissional e, quando informado, conselho e número de registro juntos. Permitir administração de papéis e situação da conta. |
| AC-08 | [E] | Oferecer convite e recuperação de senha por email transacional, sem enviar informações de casos. Diferenciar endereço de acesso interno/externo conforme os papéis; aplicar expiração de tokens, limitação de tentativas e respostas que não revelem a existência de uma conta no fluxo de recuperação. |
| AC-09 | [E] | Proteger a consulta e o download de documentos pela autorização do fluxo, inclusive no histórico; conhecer o endereço ou identificador de um arquivo não deve ser suficiente para acessá-lo. |

**[D] AC-D1:** confirmar se a reescrita deve manter a exceção de intranet para contas multipapel. A regra efetiva do código é mais permissiva que a descrição resumida de “NIR e CHD apenas na intranet”.

## 5. Recebimento, documentos e correções

| ID | Origem | Requisito |
|---|---|---|
| EN-01 | [E] | Receber um ou vários relatórios principais em PDF, com seleção obrigatória de procedimento aplicada ao lote. Cada PDF aceito deve criar exatamente um caso, mesmo no combinado. |
| EN-02 | [E] | Validar quantidade, tamanho por arquivo e tamanho total do lote, com mensagens compreensíveis. Rejeitar seleção desconhecida, combinação inválida e envio de procedimento desabilitado antes de criar componentes parciais. |
| EN-03 | [E] | Informar os casos criados e os erros por arquivo. O processamento de um lote pode resultar em sucessos e falhas; não deve apresentar sucesso total quando houve erro parcial. |
| EN-04 | [E] | Aceitar anexos clínicos PDF, JPEG e PNG quando há um único relatório principal, com limites próprios de quantidade e tamanho. Não distribuir implicitamente anexos entre vários relatórios de um lote. |
| EN-05 | [E] | Preservar documento original e metadados dos anexos: autor, momento, nome, tipo, tamanho, integridade e fase do envio. Permitir visualização dos documentos aos usuários autorizados, inclusive em dispositivos móveis. |
| EN-06 | [E] | Permitir anexo complementar antes da decisão médica, em etapa elegível, com justificativa. Bloquear complemento após decisão/encerramento e quando uma avaliação médica está reservada por outro profissional. |
| EN-07 | [E] | Permitir ao NIR suprimir anexo incorreto com motivo obrigatório, autor e momento. Suprimir significa retirá-lo da apresentação ativa, não apagar sua existência auditável. |
| EN-08 | [E] | Tratar anexos como apoio à leitura humana. O pipeline atual usa o relatório principal; anexo isolado não satisfaz automaticamente evidência clínica exigida nesse relatório. |
| EN-09 | [E] | Permitir reenvio corrigido criando um novo caso vinculado ao anterior, com motivo e novos documentos obrigatórios. Não herdar automaticamente relatório, anexos, análise, decisões ou mensagens; não reabrir o original. |
| EN-10 | [E] | Permitir correção da seleção declarada pelo NIR no mesmo caso apenas antes de decisão médica e quando a revisão é elegível. Preservar identificador, documentos, texto e histórico, invalidando/reprocessando a análise afetada sem novo upload. |
| EN-11 | [E] | Tornar a correção auditável, mostrando declaração anterior/nova, responsável e motivo. Validar seleção e reserva de trabalho antes de efetuar a alteração. |
| EN-12 | [E] | Distinguir correção da declaração, complemento documental e reenvio de um relatório corrigido. Uma mensagem livre não deve executar qualquer dessas operações implicitamente. |

**Limites atuais de referência:** 30 relatórios por lote; 20 MiB por relatório; 600 MiB por lote; 10 anexos ativos por caso; 20 MiB por anexo; 200 MiB de anexos por caso. A interface atual usa o rótulo MB. Preservar a possibilidade de configuração, sem transformar esses valores em limites universais do produto.

**Limitação existente:** operações de complemento em lote não têm garantia geral de atomicidade do lote inteiro. Não transportar essa limitação como requisito desejável nem afirmar que já existe uma garantia de tudo-ou-nada.

## 6. Catálogo, detecção e proveniência

### 6.1 Catálogo atual [E]

| Identidade de referência | Nome operacional | Família de critérios |
|---|---|---|
| `eda` | EDA | EDA |
| `eda_gastrostomy` | EDA + Gastrostomia (GTT) | EDA |
| `eda_capsule` | EDA + Cápsula | EDA |
| `eda_dilation` | EDA + Dilatação | EDA |
| `colonoscopy` | Colonoscopia | Colonoscopia |
| `rectosigmoidoscopy` | Retossigmoidoscopia | Colonoscopia |
| `rectosigmoidoscopy_dilation` | Retossigmoidoscopia + Dilatação | Colonoscopia |
| `rectosigmoidoscopy_argon` | Retossigmoidoscopia + Argônio | Colonoscopia |
| `echoendoscopy` | Ecoendoscopia | Ecoendoscopia |
| `cpre` | CPRE | CPRE |

Esses códigos são referências de compatibilidade, não uma prescrição de estrutura de armazenamento. Compartilhar critérios de uma família não torna suas identidades equivalentes para busca, decisão, histórico ou contagem.

| ID | Origem | Requisito |
|---|---|---|
| PR-01 | [E] | Usar nomes e identidades consistentes em seletores, análise, filas, resposta, auditoria e relatórios. Permitir localizar procedimentos por nome e aliases, sem aceitar valor fora do catálogo. |
| PR-02 | [E] | Aplicar matriz fechada: qualquer procedimento isolado do catálogo, ou exatamente EDA + Colonoscopia. Pacotes são indivisíveis; o símbolo “+” no nome não os transforma em combinado. |
| PR-03 | [E] | Preservar separadamente solicitado, detectado e autorizado. Mudança de uma dimensão não deve reescrever a outra nem apagar sua proveniência. |
| PR-04 | [E] | Reconhecer solicitação atual, menção, histórico e negação como contextos distintos. Exame realizado no passado ou indicação negada não deve virar solicitação atual. |
| PR-05 | [E] | Considerar evidência do Motivo da Solicitação, Justificativa da Transferência e corpo do relatório, sem depender exclusivamente de um cabeçalho administrativo. Preservar o contexto de cada ocorrência, inclusive em páginas repetidas. |
| PR-06 | [E] | Exigir vínculo contextual dos termos ambíguos, como dilatação e argônio, com a base do procedimento. Termo solto não deve criar identidade. |
| PR-07 | [E] | Aplicar precedência de pacote/especializado somente conforme regras de evidência atuais, registrando a redução. Um especializado atual pode prevalecer sobre termos convencionais; Ecoendoscopia + CPRE não autoriza escolher um dos dois arbitrariamente. |
| PR-08 | [E] | Absorver o termo administrativo guarda-chuva de endoscopia baixa pela identidade da família Retossigmoidoscopia somente nas condições específicas de contexto e ausência de solicitação explícita independente de Colonoscopia. |
| PR-09 | [E] | Normalizar base + pacote para a seleção válida mais completa na apresentação/reconciliação, preservando a união bruta na auditoria. Se não houver cobertura válida, encaminhar à revisão sem descartar componentes para fabricar validade. |
| PR-10 | [E] | Permitir ampliação automática de EDA ou Colonoscopia isolada para o combinado quando há evidência forte de ambas as solicitações atuais, sem exigir confirmação prévia do NIR; preservar declaração original e registrar a ampliação. |
| PR-11 | [E] | Retornar ao NIR divergência entre tipos, redução de combinado para isolado, combinação incompatível, procedimento desconhecido ou evidência conflitante não resolvida. Não enviar esses casos à fila médica como se a seleção estivesse confirmada. |
| PR-12 | [E] | Admitir resolução apoiada na declaração válida mais completa somente quando existe evidência textual atual e se cumprem as condições de reconciliação. Coincidência entre declaração e item da IA, sem evidência atual, permanece insuficiente. |
| PR-13 | [E] | Permitir desabilitar novas entradas de procedimentos controlados sem apagar dados ou interromper casos existentes. Essa habilitação não deve impedir inclusão/substituição médica justificada. |

## 7. Extração e análise assistidas

### Jornada de referência

```text
NIR envia relatório e declara procedimento(s)
  → extração do texto e validação documental
  → [P] separação da identidade e preparação do texto minimizado
  → extração clínica estruturada
  → detecção/reconciliação da solicitação
  → critérios determinísticos e sugestão por procedimento
  → médico decide
     ├─ negativa integral → resposta ao NIR
     ├─ aceite agendado → CHD confirma/nega → resposta ao NIR
     └─ aceite sem agenda → resposta ao NIR + ciência do CHD
  → NIR confirma recebimento e transcreve resposta no SUREM
  → encerramento do fluxo principal
```

| ID | Origem | Requisito |
|---|---|---|
| IA-01 | [E] | Extrair texto de todas as páginas do relatório principal, limpar ruído de marca-d’água e obter número de ocorrência e “Dias em tela” de forma programática. Número interno de contingência não deve ser apresentado como ocorrência documental comprovada. |
| IA-02 | [E] | Verificar se o texto corresponde a relatório de regulação antes de acionar a análise clínica por IA. Documento insuficiente ou não reconhecido deve produzir revisão operacional explícita, sem chamada à IA nem entrada indevida na fila médica. |
| IA-03 | [E] | Extrair uma única história clínica comum por caso, mesmo com dois procedimentos. Separar dados comuns dos detalhes específicos, sem duplicar histórias concorrentes do paciente. |
| IA-04 | [E] | Estruturar idade, sexo, contexto de origem, história/comorbidades, indicação e urgência, exames e resultados, medicamentos, transfusão, avaliações de risco e qualidade/incompletude da extração quando documentados. Informação desconhecida deve continuar desconhecida, sem preenchimento inventado. |
| IA-05 | [E] | Validar estrutura, valores permitidos, cardinalidade e ausência de procedimentos duplicados. Não transformar JSON válido em garantia de verdade clínica; evidências que exigem ancoragem precisam corresponder ao documento. |
| IA-06 | [E] | Calcular critérios e recomendação separadamente para cada procedimento reconciliado, com uma análise conjunta por caso. O conjunto de recomendações deve corresponder exatamente ao reconciliado, sem omissão, duplicata ou adição. |
| IA-07 | [E] | Enviar à etapa de sugestão apenas os procedimentos reconciliados, sem modificar o artefato original da extração. Reconciliar a sugestão com regras determinísticas e registrar contradições/ajustes. |
| IA-08 | [E] | Exibir narrativas em português brasileiro, tolerando apenas tentativas corretivas limitadas. A etapa de extração permite uma correção de idioma; a sugestão permite uma correção de conjunto e uma de idioma, com teto atual de três chamadas físicas nessa etapa. Falha persistente não deve produzir recomendação parcial aceita silenciosamente. |
| IA-09 | [E] | Associar resultados ao caso da chamada, não confiar na IA para decidir a qual caso gravar. Na implementação atual, eco divergente de identificadores na sugestão gera aviso e é substituído pelo identificador esperado; isso não dispensa validação do conteúdo. |
| IA-10 | [E] | Manter versões de prompts e artefatos identificáveis, com uma versão ativa por tipo de prompt. Preservar leitura dos contratos históricos sem reescrever análises antigas. |
| IA-11 | [E] | Apresentar ao médico resumo clínico, achados relevantes, pendências, decisão sugerida, suporte recomendado, avaliação de ASA quando disponível e motivo objetivo, distinguindo fato extraído, critério determinístico e inferência. |
| IA-12 | [E] | Recuperar contexto de decisões anteriores pela mesma ocorrência e identidade exata de procedimento nos últimos sete dias, excluindo o caso atual. Exibir decisão, motivo, autor e momento; contar negativas médicas/de agenda, não aprovações. Encerramento do caso anterior não deve apagar esse contexto. |
| IA-13 | [E] | Mostrar vínculo explícito de reenvio corrigido e evitar card duplicado quando ele aponta para o mesmo caso encontrado pelo contexto anterior. Não herdar automaticamente documentos pelo vínculo. |
| IA-14 | [E] | Processar documentos e análise fora da interação de envio, com etapas e falhas observáveis. Repetição de tarefa já concluída não deve duplicar decisões nem desfazer progresso; falha de encaminhamento entre etapas deve ser distinguida de falha da extração. |

**Validação documental atual:** pelo menos 500 caracteres de texto, título de relatório de ocorrências, pelo menos um sinal institucional e pelo menos três seções operacionais reconhecidas. Esses valores são configuráveis; essa verificação classifica o formato, não comprova autenticidade ou veracidade do documento.

## 8. Critérios clínicos atuais

> Extraídos das funções de política clínica e dos perfis da base examinada. Não constituem protocolo atualizado ou validado externamente. Antes de reutilização clínica, o responsável deve conferir valores, unidades, evidências aceitas e exceções.

| ID | Origem | Requisito |
|---|---|---|
| CL-01 | [E] | Aplicar critérios comuns às famílias atuais, preservando diferenças reais por procedimento. Não herdar exceções de outra família nem converter procedimento desconhecido silenciosamente em EDA em novas análises. |
| CL-02 | [E] | Avaliar completude documental de Hb/Ht, plaquetas, TP/INR/RNI, TTPa, ureia e creatinina. Falta, evidência insuficiente e valor fora do limiar devem ter motivos distinguíveis. |
| CL-03 | [E] | Aplicar os limiares de Hb, plaquetas e INR/RNI da tabela abaixo conforme hepatopatia/cardiopatia explicitamente documentadas. Usar comparadores estritos: Hb e plaquetas abaixo do mínimo; INR/RNI acima do máximo. |
| CL-04 | [E] | Exigir ECG, radiografia de tórax e ecocardiograma nas condições abaixo, com achado/laudo mínimo, não apenas menção de que o exame foi solicitado. |
| CL-05 | [E] | Manter a exceção de retirada de corpo estranho local ao perfil EDA, sem dispensar critérios de Colonoscopia, Ecoendoscopia ou CPRE em outro componente. |
| CL-06 | [E] | Exigir imagem abdominal qualificante adicional para Ecoendoscopia e CPRE conforme a tabela abaixo. Verificar modalidade, localização e conclusão/achado no relatório principal; solicitação/agendamento de imagem ou anexo isolado não bastam. |
| CL-07 | [E] | Expor todas as pendências em ordem estável: exames mínimos, limiares, condicionais e imagem. Preservar um motivo principal, sem esconder as demais falhas. |
| CL-08 | [E] | Sinalizar pediatria conforme idade documentada inferior a 16 anos, sem transformar idade ausente em adulto confirmado. |
| CL-09 | [E] | Extrair somente medicamentos explicitamente descritos, preservando estado de uso e evidência. Destacar anticoagulantes/antiagregantes para revisão, sem negar automaticamente ou sugerir suspensão, dose ou janela farmacológica. |
| CL-10 | [E] | Para EDA + Dilatação, apresentar local anatômico documentado e seu trecho; ausência/ambiguidade permanece desconhecida. O detalhe não cria identidade nova nem altera automaticamente a política. |
| CL-11 | [E] | Para EDA + GTT, oferecer painel consultivo de infecção com evidências ancoradas das categorias previstas. Mostrar resultados normais/negativos e valores sem interpretação; não inventar unidades, faixas de referência ou diagnóstico. |
| CL-12 | [E] | Destacar no painel de GTT preocupação explicitamente documentada, cuidado infectológico atual ou antibiótico atual, respeitando temporalidade. O painel não deve alterar critérios, recomendação, suporte, decisão, fila ou agendamento. |
| CL-13 | [E] | Tratar suporte por componente como recomendação consultiva da IA no contrato atual, consolidando o nível mais restritivo para o caso. Distinguir nenhum, anestesista e anestesista + UTI; a estimativa de ASA insuficiente deve ser exibida como não estimável, e a decisão final de suporte permanece médica. Não transportar automaticamente a antiga regra determinística de suporte como regra vigente. |
| CL-14 | [E] | Apresentar sinalizações clínicas prioritárias com evidência/contexto e escopo do procedimento pertinente. Histórico, negação ou mera menção não devem criar sinal de solicitação atual; badges informativos não substituem decisão clínica nem autorizam mudança de procedimento. |

### 8.1 Limiares de compatibilidade

| Perfil explícito | Hb mínima (g/dL) | Plaquetas mínimas (/mm³) | INR/RNI máximo |
|---|---:|---:|---:|
| Geral | 7 | 100.000 | 1,5 |
| Hepatopatia | 7 | 50.000 | 1,5 |
| Cardiopatia | 8 | 100.000 | 1,5 |
| Hepatopatia e cardiopatia | 8 | 50.000 | 1,5 |

Valor exatamente igual ao limiar não falha por esse comparador. Ausência de valor não deve ser tratada como valor normal: a completude documental tem verificação própria.

**Ponto clínico a conferir:** o rótulo de completude é Hb/Ht, mas a política atual verifica presença numérica de Hb. A interpretação de Ht isolado e de expressões como “coagulograma normal”/“função renal preservada” depende das regras de extração e precisa ser confirmada antes de reprodução literal.

### 8.2 Exames condicionais

- **ECG:** quando explicitamente exigido; idade superior a 40 anos; doença cardiovascular/cardiopatia; dor torácica, dispneia, palpitações ou síncope recentes; múltiplas comorbidades; medicamentos que prolongam QT; diabetes; ou obesidade explicitamente documentada.
- **Radiografia de tórax:** quando explicitamente exigida; sintomas respiratórios ativos; ou doença respiratória prévia documentada.
- **Ecocardiograma:** quando explicitamente exigido; dispneia inexplicada; sinais de insuficiência cardíaca; sopro novo/não avaliado; valvulopatia moderada/grave sem exame recente; piora de cardiomiopatia; hipertensão pulmonar; infarto prévio; revascularização cirúrgica prévia; ou angioplastia coronariana prévia.

### 8.3 Imagem especializada

| Procedimento | Modalidade e localização aceitas, com conclusão/achado |
|---|---|
| Ecoendoscopia | TC ou RM de abdome/abdome superior. |
| CPRE | USG de abdome/abdome superior/hepatobiliar; TC ou RM de abdome/abdome superior; ou CPRM hepatobiliar. |

### 8.4 Painel consultivo de infecção em EDA + GTT

Categorias atuais: leucócitos, PCR, procalcitonina, lactato, culturas, temperatura/febre, avaliação de infectologia e uso/início/escalonamento de antibióticos. Valor sem qualificação explícita permanece não classificado. Evidência exclusivamente histórica ou resultado normal/negativo isolado não deve produzir alerta de possível infecção.

## 9. Avaliação médica e execução operacional

| ID | Origem | Requisito |
|---|---|---|
| DE-01 | [E] | Permitir ao médico consultar relatório original, anexos ativos, análise, evidências, contexto anterior e comunicação antes de decidir. |
| DE-02 | [E] | Exigir decisão para cada componente detectado. Negativa exige motivo por componente. Pacote recebe uma decisão única; combinado admite aprovação integral, parcial ou negativa integral. |
| DE-03 | [E] | Derivar aceite global quando há pelo menos um componente autorizado e negativa global quando nenhum é autorizado. Não confundir negativa parcial com negativa integral. |
| DE-04 | [E] | Permitir inclusão/substituição por procedimento do catálogo, com justificativa quando não foi detectado e conjunto final válido. Efetuar a decisão atomicamente, sem rerun da IA nem recálculo da política do destino; sinalizar quando o destino não possui análise automatizada própria. |
| DE-05 | [E] | Quando há aceite, exigir escolha explícita de suporte e fluxo de admissão. Novas decisões oferecem nenhum suporte ou anestesista; recomendações/artefatos históricos podem conter anestesista + UTI, sem torná-lo uma opção nova automaticamente. |
| DE-06 | [E] | Permitir orientação médica operacional opcional, limitada atualmente a 500 caracteres, visível ao CHD/NIR. Não usar essa orientação como operação implícita de solicitar documento ou mudar estado. |
| DE-07 | [E] | Preservar autor, momento, motivos, procedimentos autorizados, suporte e fluxo escolhido. Sugestão automatizada não deve sobrescrever a decisão humana. |
| DE-08 | [E] | Para aceite agendado, encaminhar ao CHD; exigir data e horário para confirmar, ou motivo para negar. Permitir local e instruções. Negativa de agenda é distinta de negativa clínica. |
| DE-09 | [E] | Quando EDA e Colonoscopia foram ambas autorizadas, manter um único agendamento para o conjunto. Na aprovação parcial, agendar apenas o componente autorizado; não criar agenda para negados. |
| DE-10 | [E] | Para aceite sem agenda, disponibilizar resposta ao NIR e aviso durável ao CHD até ciência explícita. Ler o card ou uma mensagem não substitui confirmar ciência. |
| DE-11 | [E] | Apresentar resposta final com solicitado, detectado e autorizado, motivos, fluxo de admissão e agenda/instruções quando aplicáveis. Permitir ao NIR confirmar formalmente o recebimento e registrar a resposta no SUREM pela rotina humana. |
| DE-12 | [E] | Encerrar o fluxo após confirmação, retirando o caso das filas principais sem apagar histórico, documentos ou decisões. Pendências posteriores elegíveis continuam acessíveis por suas superfícies próprias. |

### Modos de admissão atuais

| Modo | CHD | Ação humana do NIR |
|---|---|---|
| Agendamento | Confirmar data/hora ou negar com motivo. | Aguardar resposta e comunicar à origem. |
| Entrada pela Emergência Pediátrica, com agendamento | Agendar antes do retorno final. | Comunicar chegada à EM Pediátrica conforme rotina institucional. |
| Vinda imediata | Confirmar ciência; não abrir agenda. | Conduzir vinda imediata conforme rotina institucional. |
| Admissão prévia em UTI | Confirmar ciência; não abrir agenda. | Providenciar reserva/leito de UTI. |
| Enfermaria com retaguarda UTI | Confirmar ciência; não abrir agenda. | Providenciar enfermaria e retaguarda. |

Compartilhamento pediátrico antigo sem agenda permanece legível e operacional apenas como compatibilidade histórica. O sistema atual não integra automaticamente a equipe da EM Pediátrica nem reserva leitos.

**Complementação antes da decisão:** a rotina descrita para relatório principal insuficiente é negar com justificativa e receber novo relatório atualizado. Paralelamente, há anexos complementares e comunicação antes da decisão. Não foi identificado um ciclo formal separado de “aguardando complemento” que pause a avaliação e retome o mesmo relatório automaticamente. **[D] DE-D1:** definir posteriormente se esse ciclo será introduzido.

## 10. Filas, concorrência e comunicação

| ID | Origem | Requisito |
|---|---|---|
| OP-01 | [E] | Oferecer filas por responsável e etapa, com próximo passo, estado, procedimento pertinente e indicação de reserva de trabalho. |
| OP-02 | [E] | Ordenar filas médica/agendamento por maior “Dias em tela”, ausentes por último e envio mais antigo como desempate. Usar o valor documental, sem somar automaticamente dias decorridos desde upload. Avisos de vinda imediata têm destaque prioritário próprio. |
| OP-03 | [E] | Filtrar NIR pela seleção declarada, médico pela detectada/autorizada pertinente e CHD pela autorizada. Pacotes devem usar identidade exata, não filtro ampliado pela família. |
| OP-04 | [E] | Oferecer consulta a decisões médicas e casos processados pelo CHD no dia, além de busca de histórico e casos encerrados. Manter os filtros ao navegar. |
| OP-05 | [E] | Reservar uma ação sensível para um profissional por vez, com contexto, titular, validade e credencial da reserva. Recusar envio com reserva vencida, ausente ou pertencente a outro profissional. |
| OP-06 | [E] | Permitir renovação válida e liberação da reserva. Duração atual: uma hora para decisão médica; cinco minutos para recebimento NIR e confirmação CHD. Override explícito prevalece sobre configuração por contexto, que prevalece sobre configuração global. |
| OP-07 | [E] | Liberar reserva após conclusão bem-sucedida da ação, sem race que a remova durante o envio do formulário. Não renovar reserva já expirada como se ainda fosse válida. |
| OP-08 | [E] | Manter comunicação operacional por caso, com autor, papel e momento, histórico sem edição destrutiva, mensagem não vazia e limite atual de 2.000 caracteres. Não substituir decisões, agendamento, supressão ou intercorrência estruturada por chat. |
| OP-09 | [E] | Bloquear comunicação genérica em casos encerrados, salvo canais históricos explicitamente elegíveis. Permitir ao CHD comunicar problema interno ao NIR no histórico agendado, notificando-o; essa mensagem não reabre o caso nem altera a agenda por si só. |
| OP-10 | [E] | Criar notificações in-app por menção explícita a usuário/equipe, com aliases de negócio como @medico, @chd e @supervisor. Deduplicar destinatários, excluir autor e contas inativas/bloqueadas. |
| OP-11 | [E] | Oferecer caixa pessoal, indicador de não lidas, abertura no contexto permitido e marcação de leitura individual/em lote. Manter não lidas independentemente da idade e ocultar lidas após a janela atual de 48 horas, sem deletá-las. |
| OP-12 | [E] | Projetar avisos sistêmicos relevantes na comunicação sem duplicá-los. Aviso sistêmico é contexto, não mensagem manual: não aciona menções nem substitui confirmação formal. |
| OP-13 | [E] | Manter notificações operacionais dentro do aplicativo. Não usar email operacional, SMS ou push; emails são restritos aos fluxos de conta/autenticação. |

## 11. Intercorrências e encerramento excepcional

| ID | Origem | Requisito |
|---|---|---|
| IN-01 | [E] | Permitir ao NIR abrir intercorrência após aceite e encerramento, distinguindo caso agendado confirmado de caso sem agenda. Impedir dois ciclos ativos simultâneos no mesmo caso. |
| IN-02 | [E] | Identificar cada ciclo e registrar motivo, mensagem, responsável, contexto e agenda anterior. Motivos atuais: óbito, ausência de condição de transporte, transporte indisponível, exame realizado por regulação externa, pedido de reagendamento, evasão, aceite/transferência para outro serviço, cancelamento pela origem e outro. |
| IN-03 | [E] | Exigir mensagem para todos os motivos exceto óbito e exame realizado por regulação externa. |
| IN-04 | [E] | No contexto agendado, devolver o caso ao CHD para cancelar, reagendar, manter ou negar a solicitação. Cancelar/negar exige mensagem; reagendar exige nova data/hora. Manter/negar a solicitação preserva agenda confirmada. |
| IN-05 | [E] | Registrar agenda antes/depois e resposta do CHD, devolver resultado ao NIR para confirmação e concluir o ciclo, preservando-o no histórico. |
| IN-06 | [E] | No contexto sem agenda, manter o caso encerrado e oferecer ao CHD apenas confirmação de ciência. Não criar/modificar agenda nem introduzir ações de agendamento. |
| IN-07 | [E] | Deduplicar aviso inicial e intercorrência operacional ativa, sem fazer o aviso inicial reaparecer após ciência do ciclo. |
| IN-08 | [E] | Permitir encerramento administrativo excepcional por Supervisor/Administrador, com código de motivo e descrição obrigatória. Preservar estado anterior e pendências, liberar reserva e distinguir esse encerramento de sucesso clínico/agendamento. |

Motivos administrativos atuais: erro de processamento, falha da IA, bug do sistema, reserva travada, duplicado/reapresentação manual e outro. Encerramento administrativo não deve ser contado como procedimento realizado ou agenda confirmada.

## 12. Desfechos, histórico e gestão

| ID | Origem | Requisito |
|---|---|---|
| GE-01 | [E] | Registrar realização/não realização de todos e somente os procedimentos autorizados em casos com agenda confirmada ou aceite operacional elegível, além de ocorrência de internação no nível do caso. Caso sem autorizados não deve aceitar gravação. |
| GE-02 | [E] | Exigir causa estruturada de não realização. “Outras causas” exige descrição; as demais não aceitam texto livre/submotivo. Usar a taxonomia da seção 12.1. |
| GE-03 | [E] | Cada alteração de desfecho deve gerar nova versão, com autor/momento, preservando anteriores e evento de auditoria. Versão corrente é a mais recente. Registro não muda estado nem dispara reagendamento/intercorrência. |
| GE-04 | [E] | Na lista de registro, oferecer hoje/ontem como referência inicial, seleção de data e busca de elegíveis por ocorrência/nome. Usar data da agenda vigente ou decisão operacional; não substituir timestamp ausente pela data de envio. |
| GE-05 | [E] | Oferecer histórico de desfechos pela versão corrente, com busca, período, causas, realização e internação, e exportação CSV fiel à população filtrada, independentemente da página visualizada. |
| GE-06 | [E] | Na consulta histórica, usar janela inicial de sete dias e máxima atual de 31 dias. Calcular resumos sobre período + busca; filtros de realização/causa/internação afetam linhas e CSV, não esses resumos. |
| GE-07 | [E] | Ler causas legadas por equivalências confirmadas sem reescrever versões ou auditoria. Causa não mapeada deve aparecer explicitamente, sem equivalência inventada; códigos legados não podem ser escolhidos em novos registros. |
| GE-08 | [E] | Oferecer visão gerencial dos recebidos, aceitos, negados, encerrados administrativamente, ainda não classificados por desfecho e aguardando por etapa. Separar população por período de estoque atual de pendências. |
| GE-09 | [E] | Usar fatos de decisão, não apenas estado transitório, para contabilizar aceite/negativa após encerramento. Negativa de agenda compõe negativa, não aceite; encerramento administrativo tem categoria própria. Aceite não comprova realização. |
| GE-10 | [E] | Distinguir volume de casos de volume de componentes. Um combinado conta um caso e dois procedimentos; um pacote conta um caso e um procedimento. Não agregar identidade especializada à base por compartilhar família. |
| GE-11 | [E] | Oferecer breakdown independente por solicitado/detectado/autorizado, com categorias exclusivas, nenhum quando aplicável e inconsistência explícita. A soma não deve omitir casos inválidos silenciosamente. |
| GE-12 | [E] | Medir tempos entre envio, decisão médica, agenda e encerramento, com período e eixo temporal explicados. Apresentar ausência de dados como ausência, não zero. Oferecer resumos periódicos sem duplicar a mesma janela. |
| GE-13 | [E] | Listar inicialmente casos recebidos hoje em todos os estados, com atalhos separados para backlog ativo e atenção necessária sem restrição implícita ao dia atual. Permitir acesso explícito ao histórico completo. |
| GE-14 | [E] | Compor busca por nome/ocorrência, dimensão de procedimento, estado, datas, atenção e paginação. Preservar escolhas na navegação e limitar a quantidade de resultados apresentada por página. |
| GE-15 | [E] | Sinalizar falha de processamento, reserva vencida, processamento parado e espera humana prolongada. Referência atual: 30 minutos de processamento e 48 horas aguardando ação; não apresentá-los como classificação de urgência clínica. |

**Exportação atual de pós-procedimento:** CSV com cabeçalhos/valores em português, separador `;`, UTF-8 com BOM e escape correto de delimitadores/quebras de linha. Exportar ou consultar não altera os fatos históricos. Acesso é restrito; a exportação contém dados identificáveis e continua sujeita à proteção de dados.

### 12.1 Taxonomia atual de não realização [E]

Na ordem da ficha de suspensão:

1. Ausência do preenchimento do TCLE para realização de exame.
2. Ausência do preenchimento do TCLE anestésico.
3. Condições clínicas desfavoráveis.
4. Erro na programação do procedimento.
5. Falta de médico gastroenterologista.
6. Falta de anestesiologista.
7. Falta de equipamentos.
8. Falta de exames.
9. Falta de hemoderivados.
10. Falta de jejum.
11. Falta de material/OPME.
12. Falta de vaga na UTI.
13. Preparo inadequado.
14. Intubação difícil.
15. Mudança de conduta médica.
16. Não comparecimento do paciente.
17. Paciente foi a óbito.
18. Prioridade para urgência.
19. Tempo excedido.
20. Transferência para outro hospital.
21. Atraso do paciente.
22. Relatório divergente.
23. Recusa do paciente.
24. Outras causas — exige descrição.

Equivalências históricas confirmadas: absenteísmo → não comparecimento; três detalhes antigos de falta de recursos → prioridade para urgência, tempo excedido ou falta de equipamentos. Fora dessas equivalências, preservar código original e sinalizar “causa legada não mapeada”.

## 13. PII: proteção simples por melhor esforço [P]

### 13.1 Situação atual e objetivo

**Situação identificada [E]:** a primeira etapa de IA recebe o texto extraído do relatório; seu contrato admite nome e documento do paciente. A etapa de sugestão recebe dados estruturados e contextos anteriores que também podem conter identidade em texto livre. Exibição e busca atuais usam o nome contido na extração da IA. Não foi identificada minimização efetiva de identidade nesse caminho.

A configuração examinada aponta para provedor externo, mas isso não é captura de requisição real de produção. Não houve inspeção de logs privados do provedor.

**Objetivo [P]:** reduzir exposição desnecessária de identificadores conhecidos, preservando o conteúdo clínico e a identidade necessária ao trabalho local. Isso é **minimização por melhor esforço**, não garantia de anonimização irreversível: relato clínico, origem, datas e combinações de fatos ainda podem permitir reidentificação.

**Escopo confirmado dos relatórios:** paciente, idade, sexo, nome social opcional e CNS. Não acrescentar CPF, endereço, telefone, data de nascimento ou nome da mãe como campos comprovadamente presentes nesses relatórios. Outros formatos e identificadores requerem avaliação posterior.

### 13.2 Requisitos propostos

| ID | Requisito |
|---|---|
| PI-01 | Extrair nome, nome social e CNS programaticamente do cabeçalho padronizado após limpeza do texto, sem depender da IA para estabelecer a identidade. Persistir a identidade separadamente da análise clínica. Não é necessário criar cadastro mestre de pacientes ou mecanismo de deduplicação global. |
| PI-02 | Preservar relatório original e texto-fonte para consulta autorizada. Criar uma cópia minimizada para análise, sem substituir destrutivamente o documento original. Exibição/busca operacional da identidade deve usar a fonte local, não a resposta do modelo. |
| PI-03 | Substituir os identificadores encontrados por `[NOME_REMOVIDO]`, `[NOME_SOCIAL_REMOVIDO]` e `[CNS_REMOVIDO]`. Preservar idade e sexo quando necessários aos critérios clínicos. Nome social vazio e CNS vazio/“não cadastrado” devem ser tratados como ausência legítima, não como identidade inventada. |
| PI-04 | Cobrir cabeçalhos repetidos e variações conhecidas da extração: valor após o rótulo ou nome antes de `Paciente:`, alterações de espaços/quebras de linha, caixa e acentuação. Não consumir campos clínicos vizinhos para completar um nome ambíguo. |
| PI-05 | Aplicar substituição das identidades conhecidas também nas repetições em narrativa e textos livres que serão enviados ao modelo. Usar fronteiras de valor completo, evitando que um nome curto remova parte de outra palavra ou um CNS remova prefixo de outro número. Não exigir descoberta universal de nomes não reconhecidos no cabeçalho. |
| PI-06 | Aplicar a mesma minimização a todas as entradas de análise: extração, sugestão, motivos de casos anteriores, resumos, notas, trechos de evidência e tentativas corretivas. Retirar apenas o campo estruturado de nome não protege as demais rotas. |
| PI-07 | Nas análises novas, não solicitar à IA extração da identidade do paciente. O contrato clínico deve omitir esses campos ou fixá-los como ausentes quando compatibilidade exigir sua presença. Saída do modelo não deve substituir a identidade local nem reintroduzir identificadores conhecidos sem tratamento. |
| PI-08 | Preservar a autoria profissional em campos próprios do contexto anterior, inclusive quem decidiu. Não aplicar um removedor indiscriminado de nomes profissionais. Coincidência de nome completo dentro de texto clínico pode ser minimizada por conservadorismo, sem apagar o campo estruturado de autoria. |
| PI-09 | Não enviar PDF, imagem ou arquivo original ao modelo como atalho quando a preparação do texto falhar. Falha técnica da proteção, cabeçalho com identidade ambígua ou identificador conhecido ainda presente deve impedir envio externo e produzir encaminhamento humano claro; não fazer fallback silencioso para texto original. Ausência legítima de um campo não exige bloqueio. |
| PI-10 | Registrar resultado/motivo da preparação com metadados mínimos, sem guardar identidade removida em logs ou em mensagem de erro. Não chamar o resultado de “anonimização garantida” nem exigir um mecanismo formal de prova de ausência de toda PII. |
| PI-11 | Verificar trechos produzidos pela IA contra a cópia de texto efetivamente enviada àquela análise. Manter rastreabilidade ao original para leitura humana, sem invalidar evidência somente porque o nome foi substituído. |
| PI-12 | Não expor conteúdo integral de prompts, relatórios, respostas ou valores inválidos em logs técnicos, telemetria ou exceções. Diagnóstico técnico deve privilegiar identificador interno, etapa, código de erro e metadados sem conteúdo identificável. |
| PI-13 | Manter exemplos e testes sintéticos. Não versionar PDFs reais nem reproduzir identidade de pacientes em relatórios, capturas ou evidências de teste. |
| PI-14 | Preservar leitura/auditoria dos dados históricos sem reescrita destrutiva automática. Se um histórico antigo for usado como entrada de nova análise, minimizar a projeção enviada mesmo que seu armazenamento original ainda contenha PII. |
| PI-15 | Permitir inferência local sem depender de fornecedor externo específico. Manter minimização e controle de acesso mesmo localmente; mudar para serviço externo não deve ser fallback implícito. Hospedagem local não prova conformidade nem elimina obrigações de proteção de dados. |

### 13.3 Limite deliberado de complexidade

Uma solução pequena, com extração de campos conhecidos, normalização de variantes observadas e substituição antes das chamadas, atende ao objetivo deste documento. **Não exigir Presidio, outro pacote/serviço de anonimização, outro LLM para remover PII, catálogo genérico de entidades ou infraestrutura adicional de privacidade.** Bibliotecas usuais de leitura de PDF não são proibidas por essa restrição.

A recusa de envio externo por falha identificável da proteção é uma salvaguarda simples. Ela não equivale a certificar que nenhum identificador desconhecido permaneceu. Variações futuras devem ampliar exemplos e regras conforme observação real, sem prometer cobertura universal.

### 13.4 Aceitação mínima da proteção

Usar documentos/textos sintéticos para verificar:

1. Nome antes/depois de `Paciente:`, nome social presente/ausente e cabeçalho repetido.
2. CNS numérico, vazio e “não cadastrado”; substituição sem consumir prefixos de números diferentes.
3. Identidade repetida no resumo, justificativa e motivo de caso anterior, com variantes de caixa, espaços e acentos.
4. Nome curto não remove parte de outro nome/palavra; nome completo conhecido não permanece nos exemplos suportados enviados à IA.
5. Idade, sexo, resultados de exames e evidência clínica permanecem utilizáveis; autoria profissional estruturada é preservada.
6. Falha técnica/ambiguidade conhecida não envia o original ao provedor externo; ausência legítima não vira erro fictício.
7. Nenhuma etapa posterior, retry, contexto histórico ou log reintroduz os identificadores conhecidos dos exemplos.
8. Busca e apresentação identificam o paciente pela fonte local, mesmo quando a IA não retorna identidade.

**[D] PI-D1:** decidir se o número de ocorrência enviado ao modelo deve ser substituído por referência interna opaca. É um correlacionador operacional; o baseline o envia, e sua exclusão não é apresentada aqui como comportamento existente ou decisão já aprovada.

**[D] PI-D2:** estabelecer retenção/eliminação de originais, análises, exportações e backups, além das condições institucionais de uso externo. Não foram extraídas políticas definitivas disso do código. Este documento não registra aceite formal do risco atual nem conclusão jurídica sobre contratos com provedores.

## 14. Rastreabilidade, qualidade e pontos de decisão

| ID | Origem | Requisito |
|---|---|---|
| RT-01 | [E] | Manter histórico de ações relevantes sem sobrescrita destrutiva: ator humano/sistema, papel pertinente, instante, tipo e dados suficientes para explicar a mudança. |
| RT-02 | [E] | Registrar envio, processamento/falha, declaração/detecção, ajustes de critérios, decisão, agenda, recebimento, encerramento, correção, anexos, intercorrências e versões de desfecho. Mensagens e dashboards são apresentações; não substituem os fatos auditáveis. |
| RT-03 | [E] | Preservar significado das decisões e documentos históricos quando catálogo/contratos evoluírem. Não inferir novos procedimentos retroativamente apenas por nome, sinal ou subtipo antigo. |
| RT-04 | [E] | Validar permissões, estados elegíveis e conjuntos no servidor, independentemente da interface. Erro de formulário deve ser visível e não provocar gravação parcial de decisão. |
| RT-05 | [E] | Oferecer interface em português, utilizável em computador/celular, com ações claras, informação de erro e seleção pesquisável acessível. Fluxos essenciais devem continuar utilizáveis sem aprimoramentos opcionais de JavaScript. |
| RT-06 | [P] | Na reescrita, comprovar persistência do trabalho e recuperação após reinício/falha, sem perder caso nem duplicar efeito clínico/operacional. Reutilizar o resultado válido da etapa quando seguro e aplicar limite explícito de tentativas. Não presumir que o baseline garante todas as situações de crash. |
| RT-07 | [P] | Substituir o sistema gradualmente, preservando operação dos usuários, casos em andamento e consulta histórica; definir migração, verificação e retorno seguro antes do corte de produção. Este documento não executa nem detalha esse plano. |
| RT-08 | [P] | Medir necessidades reais de tempo de resposta, concorrência, volume e armazenamento antes de fixar metas ou infraestrutura. Os aproximadamente 25 usuários atuais são contexto de continuidade, não medida de concorrência simultânea ou capacidade máxima. |

### Divergências que não devem ser copiadas silenciosamente

| Tema | Constatação e tratamento nesta base |
|---|---|
| Catálogo | Manual/contexto contêm passagens com dois/quatro tipos. Adotado catálogo atual de dez identidades e matriz fechada do código/ADRs recentes. |
| Versão de análise | Algumas specs ainda mencionam 3.0; writer atual é 4.0 e mantém leitura de artefatos anteriores. Versão numérica é compatibilidade histórica, não obrigação tecnológica para o produto novo. |
| Quantidade de estados | Documentação/comentários dizem 17; o enum atual declara 18 valores. Preservar fatos/etapas relevantes, não a contagem incorreta nem nomes de integração legada. |
| Encerramento | “Só aparece na auditoria” é incompleto: há consulta histórica, pós-procedimento e intercorrências de casos encerrados. Encerramento não é exclusão. |
| Restrição de rede | Existe bypass multipapel efetivo no middleware. Reavaliar conscientemente; não afirmar restrição absoluta pelo papel ativo no baseline. |
| Complemento | Negativa + reapresentação do relatório coexistem com anexos e comunicação antes da decisão. Não inventar estado formal de complemento. |
| Hb/Ht | Rótulo e verificação numérica de Hb não são equivalentes; revisar com responsável clínico. |
| Privacidade arquivada | O plano de minimização arquivado não foi implementado/aprovado como contrato executável. Suas afirmações sobre aceite de risco e dispensa jurídica não são adotadas. |

### Decisões reservadas ao responsável pelo produto

- Acrescentar abstrações de capacidades hospitalares e especificar regras próprias de exames, internações e cirurgias.
- Classificar quais funções desta base são essenciais à primeira entrega e quais podem ser simplificadas/retiradas.
- Confirmar critérios clínicos, evidências aceitas e modos de admissão antes de produção.
- Decidir exceção multipapel de rede, ciclo formal de complemento, correlação enviada à IA e retenção de dados.
- Definir metas de desempenho/disponibilidade e estratégia de migração dos casos em andamento.

## 15. Fontes e rastreabilidade

Todos os caminhos abaixo são relativos à raiz do repositório. A referência de base é o commit indicado no início, não o estado de uma implantação remota.

| Seções/IDs | Fontes principais |
|---|---|
| AC | `apps/accounts/models.py`, `apps/accounts/views.py`, `apps/accounts/decorators.py`, `apps/accounts/middleware.py`, `apps/accounts/services.py`, `apps/accounts/password_reset_views.py`, `docs/adr/ADR-0002-emails-transacionais-autenticacao-cadastro.md` |
| EN | `apps/intake/services.py`, `apps/intake/views.py`, `apps/cases/services.py`, `apps/cases/models.py`, `openspec/specs/exam-type-correction/spec.md`, `openspec/specs/exam-type-intake-routing/spec.md` |
| PR | `apps/cases/procedures.py`, `apps/cases/exam_profiles.py`, `apps/pipeline/scope_detection.py`, `openspec/specs/procedure-combination-policy/spec.md`, `openspec/specs/procedure-neutral-analysis/spec.md`, `openspec/specs/searchable-procedure-selection/spec.md`, ADR-0010 e ADR-0011 em `docs/adr/` |
| IA | `apps/intake/pdf_utils.py`, `apps/intake/regulation_gate.py`, `apps/intake/tasks.py`, `apps/pipeline/orchestrator.py`, `apps/pipeline/llm1_service_v4.py`, `apps/pipeline/llm2_service_v4.py`, `apps/pipeline/prior_case.py`, `apps/pipeline/schemas/` |
| CL | `apps/pipeline/policy/eda_preop_policy.py`, `apps/pipeline/policy/eda_policy.py`, `apps/pipeline/orchestrator.py`, `apps/cases/exam_profiles.py`, `apps/cases/priority_signals.py`, `apps/pipeline/imaging_evidence.py`, `openspec/specs/medication-safety/spec.md`, `openspec/specs/gastrostomy-infection-review/spec.md` |
| DE/OP | `apps/doctor/forms.py`, `apps/doctor/views.py`, `apps/scheduler/forms.py`, `apps/scheduler/views.py`, `apps/cases/admission.py`, `apps/cases/services.py`, `apps/accounts/services.py`, `openspec/specs/per-procedure-medical-decision/spec.md`, `openspec/specs/case-work-lock/spec.md`, `openspec/specs/exam-type-work-queues/spec.md`, `openspec/specs/user-notifications/spec.md` |
| IN | `apps/cases/services.py`, `apps/cases/models.py`, `apps/scheduler/forms.py`, `docs/manual/manual-usuarios.md` (intercorrências e comunicação histórica) |
| GE | `apps/cases/followup.py`, `apps/cases/models.py`, `apps/dashboard/views.py`, `apps/dashboard/procedure_analytics.py`, `apps/pipeline/summary.py`, `apps/pipeline/tasks.py`, `openspec/specs/supervisor-appointment-follow-up/spec.md`, `openspec/specs/supervisor-followup-history/spec.md`, `openspec/specs/exam-type-analytics/spec.md`, `openspec/specs/dashboard-case-list/spec.md` |
| PI — situação atual | `apps/pipeline/orchestrator.py`, `apps/pipeline/llm1_service_v4.py`, `apps/pipeline/llm2_service_v4.py`, `apps/pipeline/schemas/llm1.py`, `apps/cases/models.py` |
| PI — proposta | Pedido do responsável e investigação anterior, preservada em `.pi/shelved-changes/llm-pii-minimization/`; usada somente como contexto, não como aprovação nem plano de implementação. Os requisitos desta seção têm limite explícito de melhor esforço. |
| RT/contexto | `AGENTS.md`, `PROJECT_CONTEXT.md`, `docs/manual/manual-usuarios.md`, código e specs listados acima. `docs/DOMAIN_ANALYSIS.md` é referência de origem, não fonte exclusiva do comportamento mais recente. |

**Limite da extração:** revisão estática dirigida às jornadas e regras acima. Não substitui teste de aceitação com os usuários, revisão integral de segurança, validação clínica ou medição da produção. Não altera o aplicativo nem reativa changes arquivados.
