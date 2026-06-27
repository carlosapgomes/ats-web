# Manual de Uso — Fluxos Operacionais

Este manual explica, de forma prática, como usar o sistema no fluxo diário de trabalho.

O foco principal está nos três papéis operacionais:

1. **NIR** — envia encaminhamentos, acompanha os casos e confirma o recebimento do resultado.
2. **Médico** — avalia os casos e decide se aceita ou nega a regulação.
3. **CHD/Agendador** — confirma, nega ou ajusta o agendamento quando o caso aceito precisa ser agendado.

Neste manual, vamos usar principalmente o termo **CHD**, porque é o nome mais usado pela equipe. Quando aparecer **Agendador**, considere que estamos falando do mesmo papel no sistema.

> Observação: se o usuário tiver mais de um papel no sistema, ele deve conferir se está usando o **papel ativo correto** antes de iniciar o trabalho.

---

## 1. Resumo dos fluxos cobertos pelo sistema

### 1.1 Fluxo principal: encaminhamento com agendamento

1. O **NIR** envia o PDF do encaminhamento.
2. O sistema processa o documento automaticamente.
3. O caso entra na fila do **Médico**.
4. O **Médico** avalia e aceita o caso, escolhendo o fluxo **Agendamento**.
5. O caso entra na fila do **CHD**.
6. O **CHD** confirma data/horário ou nega o agendamento.
7. O resultado volta para o **NIR**.
8. O **NIR** confirma o recebimento do resultado.
9. O caso é concluído e sai das filas operacionais.

### 1.2 Fluxo principal: encaminhamento com vinda imediata

1. O **NIR** envia o PDF do encaminhamento.
2. O sistema processa o documento automaticamente.
3. O **Médico** avalia e aceita o caso, escolhendo o fluxo **Vinda Imediata**.
4. O caso não deve ser agendado.
5. O **CHD** recebe apenas um aviso para ciência operacional e clica em **Confirmar ciência**.
6. O resultado fica disponível para o **NIR**.
7. O **NIR** confirma o recebimento do resultado.
8. O caso é concluído.

### 1.3 Fluxo de negativa médica

1. O **Médico** avalia o caso.
2. Se a regulação não for indicada, seleciona **Negar**.
3. O motivo da negativa é obrigatório.
4. O resultado volta para o **NIR**.
5. O **NIR** confirma o recebimento.
6. O caso é concluído.

### 1.4 Fluxo de negativa de agendamento

1. O **Médico** aceita o caso para **Agendamento**.
2. O caso vai para o **CHD**.
3. Se não for possível agendar, o **CHD** seleciona **Negar Agendamento**.
4. O motivo da negativa é obrigatório.
5. O resultado volta para o **NIR**.
6. O **NIR** confirma o recebimento.
7. O caso é concluído.

### 1.5 Fluxo de complemento antes da decisão médica

Quando o **Médico** precisa de documento ou informação complementar antes de decidir:

1. O médico **não deve negar o caso apenas para pedir complemento**.
2. O médico envia uma mensagem na **Comunicação operacional**, marcando o NIR com `@nir`.
3. O médico clica em **Voltar sem decidir**.
4. O **NIR** responde pela comunicação operacional ou adiciona o anexo complementar, quando aplicável.
5. O médico volta ao caso depois e emite a decisão formal.

### 1.6 Fluxo de reenvio corrigido

Quando um caso anterior precisa ser corrigido, o **NIR** pode criar um novo caso vinculado ao anterior.

Use esse fluxo quando houver, por exemplo:

- relatório errado;
- documento incompleto;
- anexo incorreto;
- necessidade de reenviar o caso com informações corrigidas.

O novo caso **não herda** PDF, anexos, decisões ou mensagens do caso anterior. O NIR deve enviar novamente os documentos corretos.

### 1.7 Fluxo de intercorrência após agendamento aberta pelo NIR

Depois que um caso foi agendado e encerrado, pode acontecer uma intercorrência identificada pelo NIR, como:

- óbito;
- paciente sem condição clínica;
- transporte indisponível;
- necessidade de reagendamento;
- agendamento realizado em outra unidade;
- outro motivo operacional.

Nesse caso:

1. O **NIR** localiza o caso em **Casos Encerrados**.
2. O **NIR** abre os **Detalhes** do caso.
3. O **NIR** registra a intercorrência dentro do detalhe.
4. O caso volta para o **CHD** avaliar.
5. O **CHD** pode cancelar, reagendar, manter o agendamento ou negar a solicitação.
6. O resultado volta para o **NIR**.
7. O **NIR** confirma o recebimento.

### 1.8 Fluxo de alteração interna de agendamento comunicada pelo CHD

Também pode acontecer o caminho inverso: o **CHD** identifica uma mudança interna depois que o caso já foi agendado ou encerrado.

Exemplos:

- médico do dia indisponível;
- sala ou recurso indisponível;
- necessidade interna de trocar data, horário ou local;
- outro problema operacional percebido pelo setor de agendamento.

Nesse caso:

1. O **CHD** acessa **Buscar histórico**.
2. O **CHD** pesquisa o caso por ocorrência ou nome do paciente.
3. O **CHD** abre **Detalhes**.
4. O **CHD** usa **Comunicar NIR** para explicar o problema.
5. O sistema notifica o **NIR** automaticamente.
6. O **NIR** abre a notificação e lê o detalhe histórico do caso.
7. Se for necessário mudar ou cancelar o agendamento, o **NIR** registra a intercorrência pós-agendamento.
8. O caso volta para o **CHD** responder de forma estruturada.

Importante: a mensagem do CHD para o NIR **não reabre o caso sozinha**. Quem abre a intercorrência no sistema é o **NIR**, depois de ler o contexto.

---

## 2. Comunicação operacional e notificações

A **Comunicação operacional** aparece dentro da página de detalhes do caso.

Ela deve ser usada para:

- pedir esclarecimentos;
- avisar sobre complemento documental;
- orientar outra equipe;
- registrar mensagens operacionais relacionadas ao caso.

Ela **não substitui** os botões formais do sistema. Por exemplo:

- decisão médica deve ser feita no formulário de decisão médica;
- confirmação ou negativa de agendamento deve ser feita no formulário do CHD/agendador;
- confirmação de recebimento deve ser feita no botão próprio do NIR;
- intercorrência pós-agendamento deve ser registrada no formulário específico;
- aviso do CHD sobre alteração interna deve ser enviado pelo fluxo **Buscar histórico > Detalhes > Comunicar NIR**.

### 2.1 Como mencionar usuários ou equipes

Dentro de uma mensagem, é possível usar `@` para notificar pessoas ou equipes.

Exemplos:

- `@nir` — notifica usuários do NIR;
- `@medico` — notifica médicos;
- `@doctor` — também funciona, mas prefira `@medico` no uso diário;
- `@chd` — notifica usuários do CHD/agendamento;
- `@scheduler` — também funciona, mas prefira `@chd` no uso diário;
- `@supervisor` ou `@manager` — notifica supervisores/gestores;
- `@admin` — notifica administradores;
- `@nome.de.usuario` — notifica um usuário específico pelo seu nome de login (ex.: `@maria`, `@joao.silva`). O nome de login é o mesmo usado para entrar no sistema; você pode conferi-lo na página **Perfil**.

Exemplo de mensagem:

> `@nir favor anexar o relatório complementar antes da decisão médica.`

Use as menções sem acento: escreva `@medico`, não `@médico`.

### 2.2 Minhas notificações

Quando alguém menciona você ou seu grupo, o sistema cria uma notificação interna.

Na página **Minhas Notificações**, é possível:

- abrir o caso relacionado;
- marcar uma notificação como lida;
- marcar todas como lidas.

---

# 3. Ações do usuário NIR

## 3.1 Enviar novo encaminhamento

Acesse a aba **Novo Encaminhamento**.

Na área de upload:

1. clique para selecionar os PDFs ou arraste os arquivos para a área indicada;
2. confira a lista de arquivos selecionados;
3. clique em **Enviar para Regulação**.

O sistema aceita arquivos PDF de encaminhamento, com até **20 MB por arquivo**. O processamento ocorre em segundo plano. Você pode sair da tela; o sistema continuará processando o caso.

### Envio de um único relatório com anexos

Quando selecionar **apenas um relatório principal**, o sistema permite anexar documentos clínicos complementares antes do envio.

Use essa opção quando os anexos já estiverem disponíveis no momento do encaminhamento.

Os anexos podem ser:

- PDF;
- JPEG/JPG;
- PNG.

Limites dos anexos:

- até **10 arquivos**;
- até **20 MB por arquivo**;
- até **200 MB no total**.

Antes de enviar, marque a confirmação de que revisou os anexos e que eles pertencem ao mesmo paciente/caso.

> Importante: anexos clínicos são mostrados ao médico, mas **não são analisados automaticamente pelo sistema**.

### Envio de múltiplos relatórios

Quando selecionar **vários relatórios principais ao mesmo tempo**, o sistema não permite anexar documentos complementares nessa etapa.

Nesse caso, envie primeiro os relatórios. Depois, se necessário, abra os detalhes do caso e use a seção **Adicionar anexo complementar**.

### Recomendação importante sobre anexos

Se o relatório já tem anexos que precisam ser avaliados pelo médico, prefira enviar o relatório **individualmente**, com os anexos no upload inicial.

Adicionar anexo depois do upload é permitido, mas deve ser usado como exceção, porque o caso pode já estar em avaliação médica.

---

## 3.2 Acompanhar casos enviados

Use as abas:

- **Novo Encaminhamento** — mostra casos recentes;
- **Meus Casos** — mostra todos os encaminhamentos em andamento;
- **Casos Encerrados** — permite buscar casos já concluídos.

Na aba **Meus Casos**, é possível:

1. buscar por número de registro;
2. filtrar por status;
3. abrir os detalhes do caso em **Ver detalhes**.

Na tela de detalhes, o NIR pode ver:

- status atual;
- progresso do caso;
- resultado final, quando disponível;
- decisão médica;
- agendamento, quando houver;
- orientações médicas;
- PDF original;
- anexos;
- comunicação operacional;
- linha do tempo do caso.

---

## 3.3 Adicionar anexo complementar

Use esta opção quando algum documento clínico ficou faltando no upload inicial.

Passo a passo:

1. abra o caso em **Ver detalhes**;
2. procure a seção **Adicionar anexo complementar**;
3. selecione os arquivos;
4. informe a justificativa do envio tardio;
5. clique em **Enviar anexo complementar**.

Exemplos de justificativa:

- `solicitação médica`;
- `dado complementar`;
- `documento recebido após o envio inicial`.

Atenção:

- o anexo complementar só pode ser enviado antes da decisão médica;
- se o caso estiver reservado por outro usuário, pode ser necessário aguardar a liberação;
- o sistema não interrompe automaticamente a avaliação médica quando um anexo é adicionado depois.

---

## 3.4 Suprimir anexo enviado incorretamente

Se um anexo foi enviado por engano, por exemplo se pertence a outro paciente, ele pode ser suprimido.

Passo a passo:

1. abra os detalhes do caso;
2. vá até **Anexos Clínicos**;
3. abra o anexo correspondente;
4. clique em **Suprimir anexo enviado incorretamente**;
5. informe o motivo;
6. confirme a supressão.

A supressão é auditada. O anexo deixa de aparecer para o médico.

---

## 3.5 Enviar mensagem operacional sobre o caso

Na aba **Meus Casos** ou em **Casos Recentes**, clique em **Ver detalhes**.

Na página do caso:

1. procure a seção **Comunicação operacional**;
2. escreva a mensagem;
3. se necessário, mencione uma equipe ou usuário com `@`;
4. clique em **Enviar mensagem**.

Exemplo:

> `@medico anexo complementar incluído conforme solicitado.`

---

## 3.6 Confirmar recebimento do resultado final

Quando o caso já tiver um resultado final, o NIR deve confirmar o recebimento.

O resultado pode ser, por exemplo:

- regulação aceita com agendamento confirmado;
- regulação aceita para vinda imediata;
- negativa médica;
- agendamento negado;
- revisão manual obrigatória;
- falha de processamento;
- resultado de intercorrência pós-agendamento.

Passo a passo:

1. abra o caso em **Meus Casos**;
2. confira o **Resultado Final**;
3. leia motivo, data, orientações ou resposta do CHD;
4. clique em **Confirmar Recebimento**.

Depois disso, o caso é concluído e sai das filas operacionais.

---

## 3.7 Reenviar caso corrigido

Use **Reenviar caso corrigido** quando for necessário criar um novo envio a partir de um caso anterior.

Passo a passo:

1. abra o caso anterior;
2. clique em **Reenviar caso corrigido**;
3. informe o motivo do reenvio;
4. selecione o novo PDF correto;
5. marque a confirmação;
6. clique em **Enviar caso corrigido**.

O caso anterior não é reaberto. O sistema cria um novo caso vinculado ao anterior.

Atenção:

- envie novamente todos os documentos necessários;
- anexos do caso anterior não são copiados;
- decisões anteriores não são copiadas;
- o médico verá que se trata de um reenvio corrigido.

---

## 3.8 Abrir intercorrência após agendamento

Use esse fluxo quando um caso já foi agendado e encerrado, mas depois surgiu uma necessidade de mudança ou cancelamento.

Passo a passo:

1. acesse **Casos Encerrados**;
2. busque pelo nome do paciente ou número de registro/ocorrência;
3. abra **Detalhes** do caso correto;
4. clique em **Registrar intercorrência**;
5. selecione o motivo;
6. escreva a mensagem, quando necessário;
7. clique em **Registrar intercorrência**.

Depois disso, o caso volta para análise do **CHD**.

Quando o CHD responder, o resultado aparecerá para o NIR. O NIR deve abrir o caso, conferir a resposta e clicar em **Confirmar Recebimento**.

---

## 3.9 Atender aviso do CHD sobre mudança interna de agendamento

Use este fluxo quando o CHD enviar uma mensagem informando mudança interna no agendamento de um caso histórico.

Exemplos:

- troca de data ou horário por motivo interno;
- indisponibilidade de médico, sala ou equipamento;
- necessidade de cancelar ou reagendar por organização interna do serviço.

Passo a passo para o NIR:

1. abra **Minhas Notificações**;
2. localize a notificação relacionada ao caso;
3. clique em **Abrir caso**;
4. leia a mensagem do CHD na **Comunicação operacional**;
5. confira os dados do caso e o agendamento anterior;
6. se for necessário mudar, cancelar ou pedir nova avaliação do agendamento, use a seção **Intercorrência Pós-Agendamento**;
7. selecione o motivo;
8. escreva uma mensagem explicando o pedido;
9. clique em **Registrar intercorrência**.

Depois disso, o caso volta para a fila do CHD para resposta estruturada.

Se a mensagem do CHD for apenas informativa e não exigir mudança no agendamento, não é necessário abrir intercorrência. A mensagem continuará registrada na comunicação operacional do caso.

---

# 4. Ações do usuário Médico

## 4.1 Abrir a fila médica

Na página inicial do médico, acesse a **Fila de Avaliação**.

A fila mostra os casos aguardando decisão médica.

Em cada card, o médico pode ver informações como:

- nome do paciente;
- registro;
- idade e sexo;
- unidade de origem;
- diagnóstico de encaminhamento;
- suporte sugerido pelo sistema;
- fluxo sugerido pelo sistema;
- tempo de espera;
- dias em tela, quando essa informação estiver disponível.

Para iniciar a avaliação, clique em **Avaliar**.

Se outro médico já estiver avaliando o caso, ele pode aparecer como **Reservado**.

---

## 4.2 Avaliar um caso

Na tela de decisão médica, o médico deve revisar:

- dados do paciente;
- relatório automático da regulação;
- texto extraído do PDF;
- PDF original;
- anexos clínicos, se houver;
- mensagens da comunicação operacional;
- alerta de reenvio corrigido, quando existir;
- histórico de negativa recente, quando existir.

O relatório automático do sistema é apenas apoio. O médico não é obrigado a seguir a recomendação automática.

---

## 4.3 Aceitar um caso

Para aceitar:

1. selecione **Aceitar**;
2. selecione o **Suporte Necessário**:
   - Nenhum;
   - Anestesista;
   - Anestesista + UTI;
3. selecione o **Fluxo de Admissão**:
   - Agendamento;
   - Vinda Imediata;
4. se necessário, preencha **Orientações para agendamento/execução**;
5. clique em **Enviar Decisão**;
6. confira o resumo na janela de confirmação;
7. clique em **Confirmar Decisão**.

Use o campo de orientações para informações como:

- priorizar por anemia;
- agendar com anestesia;
- paciente deve trazer exames recentes;
- cuidados para execução do procedimento.

Não use esse campo para pedir documentos ao NIR. Para isso, use a **Comunicação operacional**.

---

## 4.4 Negar um caso

Para negar:

1. selecione **Negar**;
2. preencha o **Motivo da Negativa**;
3. clique em **Enviar Decisão**;
4. confira o resumo;
5. clique em **Confirmar Decisão**.

O motivo da negativa é obrigatório.

Use negativa apenas quando estiver emitindo um desfecho médico. Não use negativa para pedir complemento de documento.

---

## 4.5 Pedir complemento antes de decidir

Se faltam documentos ou informações para decidir:

1. vá até **Comunicação operacional**;
2. escreva a mensagem explicando o que falta;
3. mencione o NIR, por exemplo `@nir`;
4. clique em **Enviar mensagem**;
5. clique em **Voltar sem decidir**.

Exemplo:

> `@nir favor anexar hemograma recente antes da decisão.`

Depois que o NIR responder ou anexar o documento, o médico poderá abrir o caso novamente e decidir.

| Situação | Fluxo correto |
|---|---|
| Precisa de complemento antes de decidir | Comunicação operacional com `@nir` + **Voltar sem decidir** |
| Caso deve ser negado | **Negar** + motivo obrigatório |
| Caso deve ser aceito | **Aceitar** + suporte + fluxo |
| Caso aceito precisa de orientação | Usar **Orientações para agendamento/execução** |
| Caso anterior precisa ser corrigido | NIR cria **reenvio corrigido** |

---

## 4.6 Ver casos decididos no dia

A fila médica também pode mostrar casos já decididos no dia.

Use essa área para consultar rapidamente uma decisão recente e abrir os detalhes quando necessário.

---

# 5. Ações do usuário CHD/Agendador

## 5.1 Abrir a fila de agendamento

Na página do CHD/agendador, acesse a **Fila de Agendamento**.

A fila pode mostrar três tipos principais de item:

1. **Vinda imediata autorizada** — apenas para ciência operacional. Não deve ser agendada.
2. **Casos aguardando agendamento** — precisam ser confirmados ou negados.
3. **Intercorrências pós-agendamento** — precisam de resposta do CHD.

A fila é atualizada automaticamente.

---

## 5.2 Confirmar ciência de vinda imediata

Quando aparecer a seção **Vinda imediata autorizada — ciência operacional**:

1. leia os dados do caso;
2. confira a decisão médica e orientações, se houver;
3. não abra agendamento para esse caso;
4. clique em **Confirmar ciência**.

Esse botão apenas registra que o CHD tomou ciência da vinda imediata.

Na prática, o paciente geralmente chega pela emergência, mas isso pode variar conforme decisão interna do NIR. O ponto principal para o CHD é: **não abrir agendamento** e registrar ciência no sistema.

---

## 5.3 Confirmar um agendamento

Para agendar um caso:

1. na fila, clique em **Agendar**;
2. revise os dados do caso;
3. revise a decisão médica;
4. confira suporte necessário e orientações médicas;
5. selecione **Confirmar Agendamento**;
6. informe **Data** e **Horário**;
7. se necessário, informe **Local** e **Observações**;
8. clique em **Enviar Confirmação**;
9. revise a janela de confirmação;
10. clique em **Confirmar**.

Data e horário são obrigatórios para confirmar o agendamento.

O campo **Local** pode ser preenchido pelo CHD quando essa informação estiver disponível ou fizer parte da rotina local do setor.

---

## 5.4 Negar um agendamento

Se não for possível realizar o agendamento:

1. abra o caso em **Agendar**;
2. selecione **Negar Agendamento**;
3. informe o **Motivo da Negativa**;
4. clique em **Enviar Confirmação**;
5. revise a janela de confirmação;
6. clique em **Confirmar**.

O motivo da negativa é obrigatório.

Depois da negativa, o resultado volta para o NIR.

---

## 5.5 Resolver intercorrência pós-agendamento

Quando o NIR registra uma intercorrência após um caso já agendado, o item volta para a fila do CHD com o aviso **Intercorrência pós-agendamento**.

Passo a passo:

1. abra o caso;
2. leia o motivo e a mensagem do NIR;
3. escolha uma das ações disponíveis;
4. preencha os campos obrigatórios;
5. clique em **Enviar Resposta**;
6. revise a janela de confirmação;
7. clique em **Confirmar**.

### Ações disponíveis

| Ação | Quando usar | Campos importantes |
|---|---|---|
| **Cancelar agendamento** | O agendamento não deve mais ocorrer | Mensagem/motivo obrigatório |
| **Reagendar** | O procedimento deve ocorrer em nova data/horário | Nova data e novo horário obrigatórios; local e instruções opcionais |
| **Manter agendamento** | O agendamento atual continua válido | Mensagem opcional |
| **Negar solicitação** | O pedido de alteração/cancelamento do NIR não será atendido | Mensagem/motivo obrigatório |

Depois da resposta, o resultado volta para o NIR, que deve confirmar o recebimento.

---

## 5.6 Comunicar o NIR sobre alteração interna em caso histórico

Use este fluxo quando o CHD precisa avisar o NIR sobre uma mudança interna relacionada a um caso já processado/agendado.

Exemplos:

- médico do dia indisponível;
- sala, equipamento ou recurso indisponível;
- necessidade interna de trocar data, horário ou local;
- outro problema operacional identificado pelo setor de agendamento.

Passo a passo para o CHD:

1. na tela da fila do CHD, clique em **Buscar histórico**;
2. pesquise por número de ocorrência/registro ou nome do paciente;
3. encontre o caso correto na lista;
4. clique em **Detalhes**;
5. confira os dados do paciente, decisão médica e dados do agendamento;
6. procure a seção **Comunicar NIR**;
7. escreva a mensagem explicando a alteração ou problema;
8. clique em **Enviar mensagem ao NIR**.

O sistema adiciona automaticamente a menção `@nir`, para que a equipe NIR receba notificação interna.

A mensagem fica registrada na **Comunicação operacional** do caso.

Atenção:

- essa mensagem **não reabre o caso automaticamente**;
- o CHD não deve tentar resolver esse tipo de mudança apenas por mensagem;
- depois de receber o aviso, o NIR decide se deve abrir uma **Intercorrência Pós-Agendamento**;
- se o NIR abrir a intercorrência, o caso voltará para a fila do CHD para resposta estruturada.

Se precisar mencionar outra pessoa além do NIR, o CHD pode incluir a menção na própria mensagem, por exemplo:

> `Médico do dia indisponível. Necessário reagendar. @medico para ciência.`

Mesmo nesse caso, o sistema garante a notificação do NIR.

---

## 5.7 Enviar mensagem operacional

O CHD também pode usar a **Comunicação operacional** dentro do caso.

Use esse espaço para mensagens complementares, por exemplo:

> `@nir agendamento confirmado para 15/05 às 14h. Favor orientar paciente.`

Lembre-se: a comunicação operacional não substitui a confirmação, negativa, resolução de intercorrência ou comunicação histórica ao NIR nos formulários próprios.

---

# 6. Boas práticas para todos os usuários

## 6.1 Antes de concluir uma ação

Sempre confira:

- se o paciente está correto;
- se o número de registro/ocorrência está correto;
- se os documentos pertencem ao mesmo paciente;
- se a decisão escolhida corresponde ao fluxo desejado;
- se os campos obrigatórios foram preenchidos corretamente.

## 6.2 Use os botões formais para decisões formais

| Necessidade | Onde fazer |
|---|---|
| Enviar novo caso | **Novo Encaminhamento** |
| Decidir aceite/negativa médica | **Formulário de Decisão Médica** |
| Pedir documento antes da decisão | **Comunicação operacional** |
| Confirmar ou negar agendamento | **Confirmação de Agendamento** |
| CHD avisar NIR sobre alteração interna em caso histórico | **Buscar histórico > Detalhes > Comunicar NIR** |
| NIR registrar intercorrência após agendamento | **Casos Encerrados > Detalhes > Intercorrência Pós-Agendamento** |
| Responder intercorrência | **Fila do CHD/Agendador** |
| Encerrar caso após resultado | **Confirmar Recebimento** |
| Corrigir caso anterior | **Reenviar caso corrigido** |

## 6.3 Quando usar comunicação operacional

Use comunicação operacional para mensagens entre equipes.

Não use comunicação operacional para substituir:

- decisão médica;
- motivo de negativa;
- confirmação de agendamento;
- negativa de agendamento;
- confirmação de recebimento;
- registro de intercorrência;
- reenvio corrigido;
- comunicação histórica do CHD ao NIR quando houver formulário próprio.

## 6.4 O que acontece quando o caso é concluído

Quando o NIR confirma o recebimento do resultado final, o caso sai das filas operacionais.

Ele continua registrado para auditoria e pode ser localizado em **Casos Encerrados**, quando aplicável.

---

# 7. Observações finais

## 7.1 Padronização de termos

Neste manual:

- usamos **CHD** como termo principal para o usuário de agendamento;
- usamos `@medico` e `@chd` como menções preferenciais;
- as menções devem ser digitadas sem acento.
