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

Use esse fluxo quando um caso anterior precisa ser corrigido e reenviado pelo **NIR**, por exemplo:

- relatório errado;
- documento incompleto;
- anexo incorreto;
- necessidade de reenviar o caso com informações corrigidas.

Nesse caso:

1. O **NIR** localiza o caso anterior em **Meus Casos** ou **Casos Encerrados**.
2. O **NIR** abre os **Detalhes** do caso.
3. O **NIR** clica em **Reenviar caso corrigido**.
4. O **NIR** informa o motivo do reenvio.
5. O **NIR** seleciona o novo PDF principal correto.
6. Se houver anexos necessários, o **NIR** envia novamente os anexos corretos.
7. O **NIR** confirma que está criando um novo envio corrigido.
8. O sistema cria um **novo caso vinculado ao caso anterior**.
9. O novo caso segue o fluxo normal de processamento e avaliação médica.
10. O médico vê que aquele caso é um **reenvio corrigido**.

O caso anterior **não é reaberto nem alterado**. Ele permanece registrado para auditoria.

Atenção:

- o novo caso **não herda** PDF, anexos, decisões ou mensagens do caso anterior;
- o NIR deve enviar novamente todos os documentos necessários;
- esse fluxo não deve ser usado apenas para complementar um caso ainda antes da decisão médica — nesse caso, use **Adicionar anexo complementar** ou **Comunicação operacional**.

### 1.7 Fluxo de intercorrência após aceite médico

Depois que um caso foi aceito e encerrado (`CLEANED`), o NIR pode registrar uma
**intercorrência pós-aceitação**. Existem dois modos, dependendo do fluxo de
admissão escolhido pelo médico:

**Modo agendado (scheduled)**:

Quando o caso foi aceito com fluxo **Agendamento** e o agendamento está
confirmado, a intercorrência permite ao CHD:
- cancelar o agendamento;
- reagendar;
- manter o agendamento;
- negar a solicitação.

O caso volta para a fila do CHD (`WAIT_APPT`) e depois retorna ao NIR para
confirmação do recebimento.

Motivos disponíveis para o NIR:
- óbito;
- paciente sem condição clínica;
- transporte indisponível;
- exame realizado em outro serviço;
- solicitação de reagendamento;
- paciente evadiu-se da unidade de origem;
- paciente aceito/transferido para unidade mais próxima;
- demanda cancelada pela unidade de origem;
- outro motivo operacional.

**Modo apenas para ciência (operational_notice)**:

Quando o caso foi aceito em um fluxo **sem agendamento** (`Vinda imediata`,
`Pré-UTI`, `Enfermaria + retaguarda UTI` ou `EM pediátrica`), a intercorrência
serve apenas para o CHD tomar ciência de uma mudança operacional.

Nesse modo:
1. O **NIR** localiza o caso em **Casos Encerrados**.
2. O **NIR** abre os **Detalhes** do caso.
3. O **NIR** registra a intercorrência com o motivo e a mensagem.
4. O caso **permanece `CLEANED`** — não volta para fila de agendamento.
5. O **CHD** recebe um card específico na fila com o aviso **"Intercorrência
   pós-aceitação — apenas para ciência"**.
6. O **CHD** clica em **Confirmar ciência**.
7. A pendência some da fila. O caso continua encerrado.
8. Nenhum campo de agendamento é criado ou alterado.
9. O NIR pode abrir nova intercorrência futuramente (novo ciclo).

Motivos disponíveis são os mesmos do modo agendado, com atenção especial para:
- **paciente evadiu-se da unidade de origem** (mensagem obrigatória);
- **paciente aceito/transferido para unidade mais próxima** (mensagem
  obrigatória — informe o destino);
- **demanda cancelada pela unidade de origem** (mensagem obrigatória).

> A pendência de ciência **não expira na virada do dia**. O CHD continua
> vendo o card até confirmar a ciência, mesmo que a intercorrência tenha
> sido aberta em dias anteriores.

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
7. Se for necessário mudar ou cancelar o agendamento, o **NIR** registra a intercorrência pós-aceitação (modo agendado).
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
- intercorrência pós-aceitação (modo agendado) deve ser registrada no formulário específico;
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
- regulação aceita para fluxo sem agendamento, como vinda imediata, admissão prévia em UTI, enfermaria com retaguarda em UTI ou compartilhamento com Pediatria;
- negativa médica;
- agendamento negado;
- revisão manual obrigatória;
- falha de processamento;
- resultado de intercorrência pós-aceitação (modo agendado).

Nos fluxos sem agendamento, o resultado final indica qual ação operacional cabe ao **NIR**. O **CHD** apenas toma ciência no sistema.

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

## 3.8 Registrar intercorrência pós-aceitação

A intercorrência pós-aceitação permite ao NIR comunicar mudanças em casos já
aceitos e encerrados. Funciona em dois modos, conforme o fluxo de admissão.

### Modo agendado (scheduled)

Use quando o caso foi aceito com **Agendamento**:

1. acesse **Casos Encerrados**;
2. busque pelo nome do paciente ou número de registro/ocorrência;
3. abra **Detalhes** do caso correto;
4. na seção **Intercorrência Pós-Aceitação**, preencha o formulário;
5. selecione o motivo;
6. escreva a mensagem, quando necessário;
7. clique em **Registrar intercorrência**.

Depois disso, o caso volta para análise do **CHD** (cancelar, reagendar,
manter ou negar). Quando o CHD responder, o resultado aparecerá para o NIR.
O NIR deve abrir o caso, conferir a resposta e clicar em
**Confirmar Recebimento**.

### Modo apenas para ciência (operational_notice)

Use quando o caso foi aceito em fluxo **sem agendamento** (Vinda imediata,
Pré-UTI, Enfermaria + retaguarda UTI ou EM pediátrica):

1. acesse **Casos Encerrados**;
2. busque pelo nome do paciente ou número de registro/ocorrência;
3. abra **Detalhes** do caso correto;
4. na seção **Intercorrência Pós-Aceitação**, preencha o formulário;
5. selecione o motivo (os três novos motivos exigem mensagem);
6. escreva a mensagem descrevendo a situação;
7. clique em **Registrar intercorrência**.

O caso **permanece encerrado** (`CLEANED`). O status mostrará **"Aguardando
ciência do CHD"**. O CHD recebe um card específico apenas para confirmar
ciência, sem abrir agendamento. Nenhum campo de agendamento é criado ou
alterado.

Motivos novos (exigem mensagem):
- **Paciente evadiu-se da unidade de origem** — informe o contexto;
- **Paciente aceito/transferido para unidade mais próxima** — informe o
  destino ou serviço para onde o paciente foi;
- **Demanda cancelada pela unidade de origem** — informe o motivo informado
  pela origem.

A pendência **não expira na virada do dia** — o CHD continua vendo o card
até confirmar a ciência.

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
6. se for necessário mudar, cancelar ou pedir nova avaliação do agendamento, use a seção **Intercorrência Pós-Aceitação**;
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
3. selecione o **Fluxo de Admissão**:
   - Agendamento;
   - Vinda imediata;
   - Admissão prévia em leito de UTI;
   - Admissão em enfermaria para suporte posterior em UTI;
   - Compartilhamento com a Pediatria;
4. se necessário, preencha **Orientações para agendamento/execução**;
5. clique em **Enviar Decisão**;
6. confira o resumo na janela de confirmação;
7. clique em **Confirmar Decisão**.

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

1. **Ciência operacional — fluxos sem agendamento** — não devem ser agendados pelo CHD.
2. **Casos aguardando agendamento** — precisam ser confirmados ou negados.
3. **Intercorrências pós-aceitação (modo agendado)** — precisam de resposta do CHD.

A fila é atualizada automaticamente.

---

## 5.2 Confirmar ciência de fluxos sem agendamento

Quando aparecer a seção de **ciência operacional**:

1. leia os dados do caso;
2. confira o fluxo escolhido pelo médico;
3. confira a decisão médica e orientações, se houver;
4. não abra agendamento para esse caso;
5. clique em **Confirmar ciência**.

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

## 5.5 Resolver intercorrência pós-aceitação

### Quando o caso é agendado (scheduled)

Quando o NIR registra uma intercorrência após um caso já agendado, o item volta para a fila do CHD com o aviso **Intercorrência pós-aceitação**.

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

### Quando o caso é sem agendamento (operational_notice)

Quando o NIR registra uma intercorrência em fluxo **sem agendamento**
(Vinda imediata, Pré-UTI, Enfermaria + retaguarda UTI ou EM pediátrica),
o card aparece na seção **⚠️ Intercorrência pós-aceitação — apenas para
ciência**.

Nesse modo:

1. o card exibe motivo, mensagem do NIR, fluxo de admissão e quem abriu;
2. o CHD **apenas confirma ciência** — não há ações de agendamento;
3. clique em **Confirmar ciência**;
4. o card desaparece da fila;
5. o caso permanece encerrado (`CLEANED`), sem alteração de agendamento.

> A pendência **não expira na virada do dia**. O CHD continua vendo o card
> até confirmar a ciência.

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
- depois de receber o aviso, o NIR decide se deve abrir uma **Intercorrência Pós-Aceitação**;
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
| NIR registrar intercorrência após agendamento | **Casos Encerrados > Detalhes > Intercorrência Pós-Aceitação** |
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
