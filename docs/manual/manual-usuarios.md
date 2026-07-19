# Manual de Uso — Fluxos Operacionais

Este manual explica, de forma prática, como usar o sistema no fluxo diário de trabalho.

O foco principal está nos três papéis operacionais:

1. **NIR** — enviar encaminhamentos, acompanhar os casos e confirmar o recebimento da resposta.
2. **Médico** — avaliar os casos e decidir se aceita ou nega a regulação.
3. **CHD/Agendador** — confirmar, negar ou ajustar o agendamento quando o caso aceito precisar ser agendado.

Neste manual, vamos usar principalmente o termo **CHD**, porque é o nome mais usado pela equipe. Quando aparecer **Agendador**, considere que estamos falando do mesmo papel no sistema.

> Observação: se o usuário estiver habilitado para exercer mais de um papel/perfil no sistema, ele deve conferir se está usando o **perfil ativo correto** antes de iniciar o trabalho.

---

## 1. Resumo dos fluxos cobertos pelo sistema

### 1.1 Fluxo principal: encaminhamento com agendamento

1. **NIR** enviar o PDF do pedido de regulação.
2. O sistema processa o documento automaticamente e gera o resumo.
3. O caso entra na fila do **Médico**.
4. **Médico** avaliar e aceitar o caso, escolhendo o fluxo **Agendamento**.
5. O caso entra na fila do **CHD**.
6. **CHD** confirmar data/horário ou negar o agendamento.
7. O resultado volta para o **NIR**.
8. **NIR** confirmar o recebimento do resultado.
9. **NIR** inserir resposta no SUREM.
10. O caso é concluído e sai das filas operacionais.

### 1.2 Fluxos sem agendamento: ciência operacional do CHD e ação do NIR

Além do fluxo **Agendamento**, o médico pode aceitar um caso escolhendo um fluxo que **não abre agendamento para o CHD**.

Regra geral:

- quando o médico escolhe **Agendamento**, o caso vai para o **CHD** agendar;
- quando escolhe qualquer outro fluxo de admissão, o **CHD** apenas toma ciência operacional, e o **NIR** conduz a ação necessária conforme o fluxo indicado.

| Fluxo escolhido pelo médico | Ação do CHD | Ação principal do NIR |
|---|---|---|
| **Agendamento** | Agendar o exame | Aguardar resultado do CHD |
| **Vinda imediata** | Confirmar ciência | Comunicar e conduzir vinda imediata conforme rotina institucional |
| **Admissão prévia em leito de UTI** | Confirmar ciência | Providenciar/reservar leito de UTI |
| **Admissão em enfermaria para suporte posterior em UTI** | Confirmar ciência | Providenciar enfermaria e retaguarda em UTI |
| **Compartilhamento com a Pediatria** | Confirmar ciência | Acionar o coordenador da EM Pediátrica |

Nesses fluxos sem agendamento, o caso segue para resultado do **NIR** após a decisão médica. O **CHD** recebe um card apenas para ciência operacional e deve clicar em **Confirmar ciência**.

### 1.3 Fluxo de negativa médica

1. **Médico** avaliar o caso.
2. Se a regulação não for indicada, seleciona **Negar**.
3. **Médico** incluir o motivo da negativa (obrigatório).
4. O resultado volta para o **NIR**.
5. **NIR** confirmar o recebimento da resposta.
6. **NIR** inserir resposta no SUREM.
7. O caso é concluído.

### 1.4 Fluxo de negativa de agendamento

1. **Médico** aceitar o caso para **Agendamento**.
2. O caso vai para o **CHD**.
3. **CHD** selecionar **Negar Agendamento**, quando não houver vaga disponível.
4. **CHD** incluir o motivo da negativa (obrigatório).
5. O resultado volta para o **NIR**.
6. **NIR** confirmar o recebimento da resposta.
7. **NIR** inserir resposta no SUREM.
8. O caso é concluído.

### 1.5 Fluxo de complemento antes da decisão médica

Quando o **Médico** precisar de documento ou informação complementar antes de decidir:

1. Médico **deve negar o caso**.
2. Médico informar a razão no campo justificativa.
3. **NIR** confirmar o recebimento da resposta.
4. **NIR** inserir resposta no SUREM.
5. O caso é concluído.
6. Quando o relatório for atualizado no SUREM, o **NIR** reinsere o caso para avaliação.

### 1.6 Fluxo de reenvio corrigido

Use esse fluxo quando um caso anterior precisa ser corrigido e reenviado pelo **NIR**, por exemplo:

- relatório errado;
- documento incompleto;
- anexo incorreto;
- necessidade de reenviar o caso com informações corrigidas.

Nesse caso:

1. **NIR** localizar o caso anterior em **Meus Casos** ou **Casos Encerrados**.
2.  **NIR** abrir os **Detalhes** do caso.
3.  **NIR** clicar em **Reenviar caso corrigido**.
4.  **NIR** informar o motivo do reenvio.
5.  **NIR** selecionar o novo PDF principal correto.
6. Se houver anexos necessários, o **NIR** envia novamente os anexos corretos.
7.  **NIR** confirmar que está criando um novo envio corrigido.
8. O sistema cria um **novo caso vinculado ao caso anterior**.
9. O novo caso segue o fluxo normal de processamento e avaliação médica.
10. O médico vê que aquele caso é um **reenvio corrigido**.

O caso anterior **não é reaberto nem alterado**. Ele permanece registrado para auditoria.

Atenção:

- o novo caso **não herda** PDF, anexos, decisões ou mensagens do caso anterior;
- o NIR deve enviar novamente todos os documentos necessários;
- esse fluxo não deve ser usado apenas para complementar um caso ainda antes da decisão médica — nesse caso, use **Adicionar anexo complementar** ou **Comunicação operacional**.

### 1.7 Fluxo de intercorrência após agendamento aberta pelo NIR

Depois que um caso foi agendado e encerrado, pode acontecer uma intercorrência informada pela CER ao NIR, como:

- óbito;
- paciente sem condição clínica;
- transporte indisponível;
- necessidade de reagendamento;
- agendamento realizado em outra unidade;
- outro motivo operacional.

Nesse caso:

1. **NIR** localizar o caso em **Casos Encerrados**.
2.  **NIR** abrir os **Detalhes** do caso.
3.  **NIR** registrar a intercorrência dentro do detalhe.
4. O caso volta para o **CHD** avaliar.
5.  **CHD** pode cancelar, reagendar, manter o agendamento ou negar a solicitação.
6. O resultado volta para o **NIR**.
7.  **NIR** confirmar o recebimento.

### 1.8 Fluxo de alteração interna de agendamento comunicada pelo CHD

Também pode acontecer o caminho inverso: o **CHD** identifica uma mudança interna depois que o caso já foi agendado ou encerrado.

Exemplos:

- médico do dia indisponível;
- sala ou recurso indisponível;
- necessidade interna de trocar data, horário ou local;
- outro problema operacional percebido pelo setor de agendamento.

Nesse caso:

1. **CHD** acessar **Buscar histórico**.
2. **CHD** pesquisar o caso por ocorrência ou nome do paciente.
3. **CHD** abrir **Detalhes**.
4. **CHD** usar **Comunicar NIR** para explicar o problema.
5. O sistema notifica o **NIR** automaticamente.
6. **NIR** abrir a notificação e ler o detalhe histórico do caso.
7. Se for necessário mudar ou cancelar o agendamento, o **NIR** registra a intercorrência pós-agendamento.
8. O caso volta para o **CHD** responder de forma estruturada.
9. O resultado volta para o **NIR**.
10. **NIR** confirmar o recebimento do resultado.
11. **NIR** inserir resposta no SUREM.
12. O caso é concluído e sai das filas operacionais.

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

1. clicar para selecionar os PDFs ou arraste os arquivos para a área indicada;
2. conferir a lista de arquivos selecionados;
3. clicar em **Enviar para Regulação**.

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

Usar esta opção quando algum documento clínico ficou faltando no upload inicial.

Passo a passo:

1. abrir o caso em **Ver detalhes**;
2. procurar a seção **Adicionar anexo complementar**;
3. selecionar os arquivos;
4. informar a justificativa do envio tardio;
5. clicar em **Enviar anexo complementar**.

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

1. abrir os detalhes do caso;
2. Ir até **Anexos Clínicos**;
3. abrir o anexo correspondente;
4. clicar em **Suprimir anexo enviado incorretamente**;
5. informar o motivo;
6. confirmar a supressão.

A supressão é auditada. O anexo deixa de aparecer para o médico.

---

## 3.5 Enviar mensagem operacional sobre o caso

Na aba **Meus Casos** ou em **Casos Recentes**, clique em **Ver detalhes**.

Na página do caso:

1. procurar a seção **Comunicação operacional**;
2. escrever a mensagem;
3. se necessário, mencionar uma equipe ou usuário com `@`;
4. clicar em **Enviar mensagem**.

Exemplo:

> `@medico anexo complementar incluído conforme solicitado.`

---

## 3.6 Confirmar recebimento do resultado final

Quando o caso já tiver um resultado final, o NIR deve confirmar o recebimento.

O resultado pode ser, por exemplo:

- regulação aceita com agendamento confirmado;
- regulação aceita para fluxo sem agendamento, como vinda imediata, admissão prévia em UTI, enfermaria com retaguarda em UTI ou compartilhamento com Pediatria;
- negativa médica;
- agendamento negado;
- revisão manual obrigatória;
- falha de processamento;
- resultado de intercorrência pós-agendamento.

Nos fluxos sem agendamento, o resultado final indica qual ação operacional cabe ao **NIR**. O **CHD** apenas toma ciência no sistema.

Passo a passo:

1. abrir o caso em **Meus Casos**;
2. conferir o **Resultado Final**;
3. ler motivo, data, orientações ou resposta do CHD;
4. clicar em **Confirmar Recebimento**.

Depois disso, o caso é concluído e sai das filas operacionais.

---

## 3.7 Reenviar caso corrigido

Use **Reenviar caso corrigido** quando for necessário criar um novo envio a partir de um caso anterior.

Passo a passo:

1. abrir o caso anterior;
2. clicar em **Reenviar caso corrigido**;
3. informar o motivo do reenvio;
4. selecionar o novo PDF correto;
5. marcar a confirmação;
6. clicar em **Enviar caso corrigido**.

O caso anterior não é reaberto. O sistema cria um novo caso vinculado ao anterior.

Atenção:

- enviar novamente todos os documentos necessários;
- os anexos do caso anterior não são copiados;
- decisões anteriores não são copiadas;
- o médico verá que se trata de um reenvio corrigido.

---

## 3.8 Abrir intercorrência após agendamento

Use esse fluxo quando um caso já foi agendado e encerrado, mas depois surgiu uma necessidade de mudança ou cancelamento.

Passo a passo:

1. acessar **Casos Encerrados**;
2. buscar pelo nome do paciente ou número de registro/ocorrência;
3. abrir **Detalhes** do caso correto;
4. clicar em **Registrar intercorrência**;
5. selecionar o motivo;
6. escrever a mensagem, quando necessário;
7. clicar em **Registrar intercorrência**.

Depois disso, o caso volta para análise do **CHD**.

Quando o CHD responder, o resultado aparecerá para o NIR. O NIR deve abrir o caso, conferir a resposta e clicar em **Confirmar Recebimento**.

---

## 3.9 Atender aviso do CHD sobre mudança interna de agendamento

Use este fluxo quando o CHD enviar uma mensagem informando mudança interna no agendamento de um caso histórico.

Exemplos:

- trocar de data ou horário por motivo interno;
- indisponibilidade de médico, sala ou equipamento;
- necessidade de cancelar ou reagendar por organização interna do serviço.

Passo a passo para o NIR:

1. abrir **Minhas Notificações**;
2. localizar a notificação relacionada ao caso;
3. clicar em **Abrir caso**;
4. ler a mensagem do CHD na **Comunicação operacional**;
5. confirmar os dados do caso e o agendamento anterior;
6. se for necessário mudar, cancelar ou pedir nova avaliação do agendamento, use a seção **Intercorrência Pós-Agendamento**;
7. selecionar o motivo;
8. escrever uma mensagem explicando o pedido;
9. clicar em **Registrar intercorrência**.

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

1. selecionar **Aceitar**;
2. selecionar o **Suporte Necessário**:
   - Nenhum;
   - Anestesista;
3. selecionar o **Fluxo de Admissão**:
   - Agendamento;
   - Vinda imediata;
   - Admissão prévia em leito de UTI;
   - Admissão em enfermaria para suporte posterior em UTI;
   - Compartilhamento com a Pediatria;
4. se necessário, preencher **Orientações para agendamento/execução**;
5. clicar em **Enviar Decisão**;
6. conferir o resumo na janela de confirmação;
7. clicar em **Confirmar Decisão**.

O campo **Suporte Necessário** informa ao **CHD** se será preciso reservar anestesista. A reserva de leito de UTI ou enfermaria é conduzida pelo **NIR**, conforme o fluxo de admissão escolhido.

Regra geral do **Fluxo de Admissão**:

- escolha **Agendamento** quando o **CHD** precisa marcar data/horário;
- escolha os demais fluxos quando o **CHD** deve apenas tomar ciência e o **NIR** deve executar uma ação operacional antes ou fora do agendamento.

Caso importante: se o paciente já está em UTI próxima ao hospital, por exemplo na Grande Salvador, e virá de UTI móvel apenas para realizar o exame e retornar, selecione **Agendamento**. Nesse caso, use o campo **Orientações para agendamento/execução** para informar que o paciente está em UTI e provavelmente virá de UTI móvel.

Use o campo de orientações para informações como:

- priorizar por anemia;
- agendar com anestesia;
- paciente está em UTI e provavelmente virá de UTI móvel;
- paciente deve trazer exames recentes;
- cuidados para execução do procedimento.

Não use esse campo para pedir documentos ao NIR. Para isso, use a **Comunicação operacional**.

---

## 4.4 Negar um caso

Para negar:

1. selecionar **Negar**;
2. preencher o **Motivo da Negativa**;
3. clicar em **Enviar Decisão**;
4. conferir o resumo;
5. clicar em **Confirmar Decisão**.

O motivo da negativa é obrigatório.

Use negativa apenas quando estiver emitindo um desfecho médico. Não use negativa para pedir complemento de documento.

---

## 4.5 Pedir complemento antes de decidir

Se faltam documentos ou informações para decidir:

1. ir até **Comunicação operacional**;
2. escrever a mensagem explicando o que falta;
3. mencionar o NIR, por exemplo `@nir`;
4. clicar em **Enviar mensagem**;
5. clicar em **Voltar sem decidir**.

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

1. **Ciência operacional — fluxos sem agendamento** — não devem ser agendados pelo CHD.
2. **Casos aguardando agendamento** — precisam ser confirmados ou negados.
3. **Intercorrências pós-agendamento** — precisam de resposta do CHD.

A fila é atualizada automaticamente.

---

## 5.2 Confirmar ciência de fluxos sem agendamento

Quando aparecer a seção de **ciência operacional**:

1. ler os dados do caso;
2. conferir o fluxo escolhido pelo médico;
3. conferir a decisão médica e orientações, se houver;
4. não abrir agendamento para esse caso;
5. clicar em **Confirmar ciência**.

Esse botão apenas registra que o **CHD** tomou ciência do fluxo sem agendamento. A confirmação fica registrada no histórico, incluindo quem confirmou e quando.

Fluxos em que o CHD apenas confirma ciência:

- **Vinda imediata**;
- **Admissão prévia em leito de UTI**;
- **Admissão em enfermaria para suporte posterior em UTI**;
- **Compartilhamento com a Pediatria**.

Na prática, o encaminhamento operacional desses casos é conduzido pelo **NIR** conforme a rotina institucional. O ponto principal para o CHD é: **não abrir agendamento** e registrar ciência no sistema.

---

## 5.3 Confirmar um agendamento

Para agendar um caso:

1. na fila, clique em **Agendar**;
2. revisar os dados do caso;
3. revissar a decisão médica;
4. conferir suporte necessário e orientações médicas;
5. selecionar **Confirmar Agendamento**;
6. informar **Data** e **Horário**;
7. se necessário, informar **Local** e **Observações**;
8. clicar em **Enviar Confirmação**;
9. revisar a janela de confirmação;
10. clicar em **Confirmar**.

Data e horário são obrigatórios para confirmar o agendamento.

O campo **Local** pode ser preenchido pelo CHD quando essa informação estiver disponível ou fizer parte da rotina local do setor.

---

## 5.4 Negar um agendamento

Se não for possível realizar o agendamento:

1. abrir o caso em **Agendar**;
2. selecionar **Negar Agendamento**;
3. informar o **Motivo da Negativa**;
4. clicar em **Enviar Confirmação**;
5. revisar a janela de confirmação;
6. clicar em **Confirmar**.

O motivo da negativa é obrigatório.

Depois da negativa, o resultado volta para o NIR.

---

## 5.5 Resolver intercorrência pós-agendamento

Quando o NIR registra uma intercorrência após um caso já agendado, o item volta para a fila do CHD com o aviso **Intercorrência pós-agendamento**.

Passo a passo:

1. abrir o caso;
2. ler o motivo e a mensagem do NIR;
3. escolher uma das ações disponíveis;
4. preencher os campos obrigatórios;
5. clicar em **Enviar Resposta**;
6. revisar a janela de confirmação;
7. clicar em **Confirmar**.

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
2. pesquisar por número de ocorrência/registro ou nome do paciente;
3. encontrar o caso correto na lista;
4. clicar em **Detalhes**;
5. conferir os dados do paciente, decisão médica e dados do agendamento;
6. procurar a seção **Comunicar NIR**;
7. escrever a mensagem explicando a alteração ou problema;
8. clicar em **Enviar mensagem ao NIR**.

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
| Médico indicar fluxo sem agendamento | **Formulário de Decisão Médica > Fluxo de Admissão** |
| Pedir documento antes da decisão | **Comunicação operacional** |
| Confirmar ou negar agendamento | **Confirmação de Agendamento** |
| CHD tomar ciência de fluxo sem agendamento | **Fila do CHD > Confirmar ciência** |
| NIR executar ação de UTI, enfermaria, vinda imediata ou Pediatria | **Resultado final do caso + rotina operacional NIR** |
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
