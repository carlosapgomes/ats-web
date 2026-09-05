# Manual de Uso — Fluxos Operacionais

Este manual explica, de forma prática, como usar o sistema no fluxo diário de trabalho.

O foco principal está nos três papéis operacionais:

1. **NIR** — enviar encaminhamentos, acompanhar os casos e confirmar o recebimento da resposta.
2. **Médico** — avaliar os casos e decidir se aceita ou nega a regulação.
3. **CHD/Agendador** — confirmar, negar ou ajustar o agendamento quando o caso aceito precisar ser agendado.

Além dos três papéis operacionais, o sistema também tem o papel de
**Supervisor** (perfis de gerência e administração, exibidos no sistema como
**Supervisor** e **Administrador**). O Supervisor não conduz o caso no dia a
dia, mas registra o **desfecho dos exames** depois que o dia do procedimento
passou — o chamado **follow-up de agendamento** (seção 6).

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

- quando o médico escolhe **Agendamento** ou **Compartilhar com EM pediátrica — com agendamento**, o caso vai para o **CHD** agendar;
- quando escolhe qualquer outro fluxo de admissão, o **CHD** apenas toma ciência operacional, e o **NIR** conduz a ação necessária conforme o fluxo indicado.

| Fluxo escolhido pelo médico | Ação do CHD | Ação principal do NIR |
|---|---|---|
| **Agendamento** | Agendar o exame | Aguardar resultado do CHD |
| **Compartilhar com EM pediátrica — com agendamento** | Agendar o exame | Aguardar resultado do CHD e comunicar a EM Pediátrica sobre a chegada da criança |
| **Vinda imediata** | Confirmar ciência | Comunicar e conduzir vinda imediata conforme rotina institucional |
| **Admissão prévia em leito de UTI** | Confirmar ciência | Providenciar/reservar leito de UTI |
| **Admissão em enfermaria para suporte posterior em UTI** | Confirmar ciência | Providenciar enfermaria e retaguarda em UTI |

Nesses fluxos sem agendamento, o caso segue para resultado do **NIR** após a decisão médica. O **CHD** recebe um card apenas para ciência operacional e deve clicar em **Confirmar ciência**.

> **Compatibilidade histórica:** casos antigos registrados como **Compartilhamento com a Pediatria** sem agendamento continuam operando como ciência operacional. Novas decisões usam o item **Compartilhar com EM pediátrica — com agendamento**.

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
5.  **NIR** selecionar o **tipo de exame do novo envio** (**EDA** ou
    **Colonoscopia** — escolha obrigatória). O tipo do caso anterior **não é
    herdado automaticamente**: pode ser igual ou **diferente** do original,
    caso o relatório anterior estivesse classificado incorretamente. A opção
    **Colonoscopia** fica indisponível quando a operação ainda não ativou a
    colonoscopia (mesma regra do upload novo).
6.  **NIR** selecionar o novo PDF principal correto.
7. Se houver anexos necessários, o **NIR** envia novamente os anexos corretos.
8.  **NIR** confirmar que está criando um novo envio corrigido.
9. O sistema cria um **novo caso vinculado ao caso anterior**.
10. O novo caso segue o fluxo normal de processamento e avaliação médica.
11. O médico vê que aquele caso é um **reenvio corrigido**.

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

Todos os motivos disponíveis e se exigem mensagem obrigatória:

| Motivo | Label exibido | Mensagem obrigatória? |
| --- | --- | --- |
| `death` | Paciente faleceu | Não |
| `clinical_condition` | Paciente sem condição clínica de transporte | Sim |
| `transport_unavailable` | Transporte indisponível pela unidade de origem | Sim |
| `external_regulation` | Exame realizado pela regulação estadual em outro serviço | Não |
| `reschedule_request` | Solicitação de reagendamento pela unidade de origem | Sim |
| `patient_absconded` | Paciente evadiu-se da unidade de origem | Sim |
| `accepted_elsewhere` | Paciente aceito/transferido para unidade mais próxima | Sim |
| `origin_cancelled` | Demanda cancelada pela unidade de origem | Sim |
| `other` | Outro | Sim |

Se o NIR enviar sem preencher a mensagem obrigatória, o formulário
retorna com o erro **"Mensagem é obrigatória"** e a intercorrência
não é registrada.

**Modo apenas para ciência (operacional)**:

Quando o caso foi aceito em um fluxo **sem agendamento** (`Vinda imediata`,
`Pré-UTI`, `Enfermaria + retaguarda UTI`), a intercorrência
serve apenas para o CHD tomar ciência de uma mudança operacional.

Nesse modo:

1. **NIR** acessar **Casos Encerrados** e pesquisar por registro ou nome do paciente.
2. **NIR** clicar em **Detalhes** no resultado da busca.
3. **NIR** preencher o formulário na seção **Intercorrência Pós-Aceitação**:
   escolher o motivo e escrever a mensagem (obrigatória para 7 dos 9 motivos).
4. Ao enviar, aparece a mensagem verde: **"Intercorrência registrada com
   sucesso. O agendador receberá um aviso para confirmar ciência."**
5. O badge do caso muda para **⚠️ Aguardando ciência do CHD**.
6. O caso **permanece `CLEANED`** — não volta para fila de agendamento.
7. O **CHD** recebe um card específico na fila com o título **"⚠️
   Intercorrência pós-aceitação — apenas para ciência"** e o aviso *"O CHD
   deve apenas confirmar ciência. Não abrir agendamento."*
8. **CHD** clicar em **Confirmar ciência**.
9. A pendência some da fila. O caso continua encerrado.
10. Nenhum campo de agendamento é criado ou alterado.
11. O NIR pode abrir nova intercorrência futuramente (novo ciclo).

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

1. **CHD** acessar **Buscar histórico**.
2. **CHD** pesquisar o caso por ocorrência ou nome do paciente.
3. **CHD** abrir **Detalhes**.
4. **CHD** usar **Comunicar NIR** para explicar o problema.
5. O sistema notifica o **NIR** automaticamente.
6. **NIR** abrir a notificação e ler o detalhe histórico do caso.
7. Se for necessário mudar ou cancelar o agendamento, o **NIR** registrar a
   intercorrência pós-aceitação (modo agendado).
8. O caso volta para o **CHD** responder de forma estruturada.
9. O resultado volta para o **NIR**.
10. **NIR** confirmar o recebimento do resultado.
11. **NIR** inserir resposta no SUREM.
12. O caso é concluído e sai das filas operacionais.

Importante: a mensagem do CHD para o NIR **não reabre o caso sozinha**. Quem abre a intercorrência no sistema é o **NIR**, depois de ler o contexto.

### 1.9 Fluxo combinado: EDA + Colonoscopia em um único caso

1. **NIR** enviar o PDF e declarar **EDA + Colonoscopia** na seleção.
2. O sistema processa o documento **uma vez** e gera componentes por
   procedimento.
3. O caso (único) entra na fila do **Médico** com badge **EDA + Colonoscopia**.
4. **Médico** decidir cada procedimento (aprovar/negar/incluir), com razão por
   componente quando necessário.
5. Se ambos forem aprovados com agendamento, o **CHD** confirma **um único
   agendamento casado** (data/hora/local).
6. O resultado volta para o **NIR** com **Solicitado**, **Detectado** e
   **Autorizado**.
7. **NIR** confirmar o recebimento e inserir a resposta no SUREM.

**Upgrade automático:** se o NIR declara um único procedimento e o relatório
mostra os dois com evidência forte, o sistema registra o **upgrade
automático** para **EDA + Colonoscopia** na linha do tempo e o caso segue ao
médico. Se a divergência for no sentido contrário (declarado combinado,
detectado único) ou sem evidência forte, o caso volta ao NIR para correção da
seleção declarada.

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

1. selecionar o(s) **procedimento(s)** do lote: **EDA**, **Colonoscopia** ou **EDA + Colonoscopia** (seleção obrigatória — o envio é bloqueado sem escolha);
2. clicar para selecionar os PDFs ou arraste os arquivos para a área indicada;
3. conferir a lista de arquivos selecionados;
4. clicar em **Enviar para Regulação**.

O sistema aceita arquivos PDF de encaminhamento, com até **20 MB por arquivo**. O processamento ocorre em segundo plano. Você pode sair da tela; o sistema continuará processando o caso.

**Lote com seleção única:** a seleção vale para **todos os PDFs enviados naquele lote**. Quando você escolhe **EDA + Colonoscopia**, o sistema cria **um único caso** com os dois procedimentos — não são criados dois casos nem dois envios.

**Divergência entre o que você declara e o que o relatório mostra:**

- se você declara **um procedimento** e o relatório mostra **os dois** com evidência forte, o sistema registra o **upgrade automático** para **EDA + Colonoscopia** e o caso segue para o médico — a mudança fica registrada na linha do tempo do caso;
- se você declara **EDA + Colonoscopia** e o relatório mostra **apenas um** dos procedimentos, ou a evidência não é forte, o caso volta para a **revisão manual** do NIR, que corrige a seleção declarada antes de seguir;
- trocas entre tipos únicos (declarou EDA e o relatório mostra Colonoscopia, por exemplo) também voltam para a revisão manual.

**Colonoscopia/Combinado indisponíveis:** quando a operação ainda não ativou a colonoscopia, as opções **Colonoscopia** e **EDA + Colonoscopia** ficam desabilitadas com uma explicação. Casos de colonoscopia já existentes continuam sendo processados normalmente — apenas novos uploads ficam bloqueados nessa situação.

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
3. filtrar por **tipo de exame** (Todos os tipos, EDA ou Colonoscopia) — compõe com os demais filtros;
4. abrir os detalhes do caso em **Ver detalhes**.

Na tela de detalhes, o NIR pode ver:

- tipo de exame do caso (badge **EDA** ou **Colonoscopia**);
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
- regulação aceita para fluxo sem agendamento, como vinda imediata, admissão prévia em UTI, enfermaria com retaguarda em UTI;
- negativa médica;
- agendamento negado;
- revisão manual obrigatória;
- falha de processamento;
- resultado de intercorrência pós-aceitação (modo agendado).

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
4. selecionar o **tipo de exame do novo envio** (**EDA** ou **Colonoscopia**
   — escolha obrigatória; o tipo anterior **não é herdado** e pode ser
   **diferente** do original; **Colonoscopia** só está disponível quando a
   operação a liberou para novos envios);
5. selecionar o novo PDF correto;
6. marcar a confirmação;
7. clicar em **Enviar caso corrigido**.

O caso anterior não é reaberto. O sistema cria um novo caso vinculado ao anterior.

Atenção:

- enviar novamente todos os documentos necessários;
- os anexos do caso anterior não são copiados;
- decisões anteriores não são copiadas;
- o médico verá que se trata de um reenvio corrigido.

---

## 3.8 Registrar intercorrência pós-aceitação

A intercorrência pós-aceitação permite ao NIR comunicar mudanças em casos já
aceitos e encerrados. Funciona em dois modos, conforme o fluxo de admissão.

### Modo agendado (scheduled)

Use quando o caso foi aceito com **Agendamento**:

1. acessar **Casos Encerrados**;
2. buscar pelo nome do paciente ou número de registro/ocorrência;
3. abrir **Detalhes** do caso correto;
4. preencher o formulário na seção **Intercorrência Pós-Aceitação**;
5. selecionar o motivo;
6. escrever a mensagem, quando necessário;
7. clicar em **Registrar intercorrência**.

Depois disso, o caso volta para análise do **CHD** (cancelar, reagendar,
manter ou negar). Quando o CHD responder, o resultado aparecerá para o NIR.
O NIR deve abrir o caso, conferir a resposta e clicar em
**Confirmar Recebimento**.

### Modo apenas para ciência (operational_notice)

Use quando o caso foi aceito em fluxo **sem agendamento** (Vinda imediata,
Pré-UTI, Enfermaria + retaguarda UTI):

1. acessar **Casos Encerrados**;
2. buscar pelo nome do paciente ou número de registro/ocorrência;
3. encontrar o caso na lista de resultados e clique em **Detalhes**;
4. na seção **Intercorrência Pós-Aceitação**, selecionar o motivo;
5. escrever a mensagem descrevendo a situação (obrigatória para 7 dos 9
   motivos — veja tabela na seção 1.7);
6. clicar em **Registrar intercorrência**.

Após o envio:

- aparece a mensagem verde: **"Intercorrência registrada com sucesso.
  O agendador receberá um aviso para confirmar ciência."**
- o status do caso mostra o badge amarelo **⚠️ Aguardando ciência do CHD**;
- o caso **permanece encerrado** (`CLEANED`);
- o CHD recebe um card na fila com os dados da intercorrência e um único
  botão: **Confirmar ciência**.

Quando o CHD confirmar a ciência, o badge desaparece e o caso volta ao
estado normal. Nenhum campo de agendamento é criado ou alterado em nenhum
momento.

Motivos novos que exigem mensagem obrigatória:
- **Paciente evadiu-se da unidade de origem** — informe o contexto;
- **Paciente aceito/transferido para unidade mais próxima** — informe o
  destino ou serviço para onde o paciente foi;
- **Demanda cancelada pela unidade de origem** — informe o motivo informado
  pela origem.

A pendência **não expira na virada do dia** — o CHD continua vendo o card
até confirmar a ciência, mesmo que a intercorrência tenha sido aberta há
vários dias.

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
6. se for necessário mudar, cancelar ou pedir nova avaliação do agendamento,
   usar a seção **Intercorrência Pós-Aceitação**;
7. selecionar o motivo;
8. escrever uma mensagem explicando o pedido;
9. clicar em **Registrar intercorrência**.

Depois disso, o caso volta para a fila do CHD para resposta estruturada.

Se a mensagem do CHD for apenas informativa e não exigir mudança no agendamento, não é necessário abrir intercorrência. A mensagem continuará registrada na comunicação operacional do caso.

---

## 3.10 Corrigir a seleção de procedimentos de um caso

Quando o sistema identifica divergência entre a seleção declarada no upload e
o conteúdo do relatório, o caso vai para **Revisão Manual** e o NIR pode
corrigir o conjunto de procedimentos declarado (**EDA**, **Colonoscopia** ou
**EDA + Colonoscopia**).

A correção está disponível **somente** quando o caso está exatamente nesta
situação:

- status `WAIT_R1_CLEANUP_THUMBS` (revisão manual do NIR);
- resultado `manual_review_required` com motivo `exam_type_mismatch`
  (divergência de tipo), `mixed_exam_request` (solicitação mista) ou
  `unknown_exam_type` (tipo não identificado);
- **sem** decisão médica registrada.

A correção **não** está disponível durante o processamento do worker, nem
quando o caso já está na fila médica ou já foi decidido. Fora das condições
acima, o formulário de correção não aparece.

Passo a passo:

1. abrir o caso em **Meus Casos**;
2. localizar a seção de **correção da seleção de procedimentos** (visível
   apenas quando o caso está em revisão manual, conforme as condições acima);
3. selecionar a seleção correta (**EDA**, **Colonoscopia** ou
   **EDA + Colonoscopia**);
4. confirmar a correção.

O sistema reprocessa o caso com a seleção corrigida, sem novo upload e sem
perder o PDF, os anexos, o texto extraído ou o histórico de eventos. A
correção fica registrada na linha do tempo do caso para auditoria. A seleção
declarada corrigida não altera o que foi detectado na análise nem qualquer
decisão médica (que não existe nesta etapa).

---

## 3.11 Resposta final: solicitado, detectado e autorizado

Quando o caso termina, a resposta final mostra as três dimensões do caso,
separadas por procedimento:

- **Solicitado** — o que o NIR declarou no envio (EDA, Colonoscopia ou
  EDA + Colonoscopia);
- **Detectado** — o que a análise do relatório identificou como solicitação
  atual;
- **Autorizado** — o que o médico aprovou, com as razões registradas.

Em um caso combinado, as três dimensões aparecem para cada procedimento.
Confira as três antes de inserir a resposta no SUREM. Se algo estiver
divergente, use a comunicação operacional para esclarecer com o médico ou o
CHD antes de encerrar.

---

# 4. Ações do usuário Médico

## 4.1 Abrir a fila médica

Na página inicial do médico, acesse a **Fila de Avaliação**.

A fila mostra os casos aguardando decisão médica.

Em cada card, o médico pode ver informações como:

- tipo de exame (badge **EDA** ou **Colonoscopia**);
- nome do paciente;
- registro;
- idade e sexo;
- unidade de origem;
- diagnóstico de encaminhamento;
- suporte sugerido pelo sistema;
- fluxo sugerido pelo sistema;
- tempo de espera;
- dias em tela, quando essa informação estiver disponível.

Nas abas **Pendentes** e **Decididos Hoje**, o médico pode filtrar por **tipo de exame** (Todos, EDA ou Colonoscopia). O filtro compõe com a busca por nome/ocorrência, e o termo digitado é preservado ao trocar o tipo.

Para iniciar a avaliação, clique em **Avaliar**.

Se outro médico já estiver avaliando o caso, ele pode aparecer como **Reservado**.

---

## 4.2 Avaliar um caso

Na tela de decisão médica, o médico deve revisar:

- dados do paciente;
- tipo de exame (badge **EDA** ou **Colonoscopia**);
- relatório automático da regulação;
- **alerta medicamentoso informativo** (quando o relatório descreve anticoagulante ou antiagregante, o sistema exibe um aviso apenas informativo — ele **não** altera a sugestão nem a decisão e **não** gera orientação de suspensão de medicamento);
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
   - Compartilhar com EM pediátrica — com agendamento;
4. se necessário, preencher **Orientações para agendamento/execução**;
5. clicar em **Enviar Decisão**;
6. conferir o resumo na janela de confirmação;
7. clicar em **Confirmar Decisão**.

O campo **Suporte Necessário** informa ao **CHD** se será preciso reservar anestesista. A reserva de leito de UTI ou enfermaria é conduzida pelo **NIR**, conforme o fluxo de admissão escolhido.

Regra geral do **Fluxo de Admissão**:

- escolha **Agendamento** ou **Compartilhar com EM pediátrica — com agendamento** quando o **CHD** precisa marcar data/horário;
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

## 4.7 Decidir um caso combinado (EDA + Colonoscopia)

Quando o caso tem os dois procedimentos (badge **EDA + Colonoscopia**), a
decisão é feita **por componente**: o médico avalia e decide cada
procedimento separadamente na mesma tela.

- **Aprovar** um procedimento e **negar** o outro é permitido — a negativa
exige **razão específica para aquele procedimento**.
- **Incluir** um procedimento não detectado também é permitido — a inclusão
exige razão específica e **não** reexecuta a análise automática: o
procedimento incluído entra com o contexto clínico já extraído.
- O **Suporte Necessário** e o **Fluxo de Admissão** continuam sendo
escolhidos para o caso como um todo; a sugestão global usa o requisito mais
restritivo entre os procedimentos, mas a escolha final permanece médica.
- Depois de confirmar, o conjunto **Autorizado** é o que vale para o CHD e
para a resposta final.

---

# 5. Ações do usuário CHD/Agendador

## 5.1 Abrir a fila de agendamento

Na página do CHD/agendador, acesse a **Fila de Agendamento**.

A fila pode mostrar três tipos principais de item:

1. **Ciência operacional — fluxos sem agendamento** — não devem ser agendados pelo CHD.
2. **Casos aguardando agendamento** — precisam ser confirmados ou negados.
3. **Intercorrências pós-aceitação (modo agendado)** — precisam de resposta do CHD.

Em **Pendentes**, **Processados Hoje** e no **histórico**, o CHD pode filtrar por **tipo de exame** (Todos, EDA ou Colonoscopia). No histórico, o tipo compõe com a busca por nome/ocorrência — selecionar um tipo sem termo lista os casos recentes daquele tipo.

A fila é atualizada automaticamente.

---

## 5.2 Confirmar ciência de fluxos sem agendamento

O CHD pode receber dois tipos de card de ciência na fila:

1. **Nota operacional inicial** — aviso original da decisão médica em
   fluxo sem agendamento.
2. **Intercorrência pós-aceitação operacional** — card gerado quando o NIR
   registra uma mudança em caso já aceito e encerrado (ver seção 5.5).

Em ambos os casos, o procedimento é o mesmo:

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

> **Compartilhar com EM pediátrica** é exceção: novas decisões passam pelo agendamento normal (confirmar data/hora ou negar com motivo); apenas casos históricos de **Compartilhamento com a Pediatria** permanecem como ciência operacional.

Na prática, o encaminhamento operacional desses casos é conduzido pelo **NIR** conforme a rotina institucional. O ponto principal para o CHD é: **não abrir agendamento** e registrar ciência no sistema.

---

## 5.3 Confirmar um agendamento

Para agendar um caso:

1. na fila, clicar em **Agendar**;
2. revisar os dados do caso;
3. revisar a decisão médica;
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

## 5.5 Resolver intercorrência pós-aceitação

### Quando o caso é agendado (scheduled)

Quando o NIR registra uma intercorrência após um caso já agendado, o item volta para a fila do CHD com o aviso **Intercorrência pós-aceitação**.

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

### Quando o caso é sem agendamento (operational_notice)

Quando o NIR registra uma intercorrência em fluxo **sem agendamento**
(Vinda imediata, Pré-UTI, Enfermaria + retaguarda UTI),
o card aparece na fila do CHD dentro da seção:

> ⚠️ **Intercorrência pós-aceitação — apenas para ciência**
>
> *O CHD deve apenas confirmar ciência. Não abrir agendamento.*

O card exibe:

- nome do paciente e número de registro;
- unidade de origem (hospital e unidade);
- badge amarelo **⚠️ Intercorrência pós-aceitação**;
- **Motivo** da intercorrência (ex.: "Paciente evadiu-se da unidade de origem");
- **Mensagem do NIR** com a descrição da situação;
- diagnóstico, suporte necessário e fluxo de admissão;
- médico responsável, se houver;
- quem abriu a intercorrência e quando (data/hora);
- badge **Não agendar**;
- botão **Confirmar ciência**.

Ações do CHD:

1. ler o motivo e a mensagem do NIR;
2. clicar em **Confirmar ciência** (única ação possível);
3. o card desaparece da fila;
4. o caso permanece encerrado (`CLEANED`), sem alteração de agendamento;
5. a confirmação fica registrada para auditoria (quem confirmou, quando,
   qual fluxo e ciclo).

> O card operacional **não** contém botões de agendamento (Agendar,
> Cancelar agendamento, Reagendar, Manter agendamento, Negar solicitação)
> nem campos de data/hora/local. A única ação possível é **Confirmar
> ciência**.
>
> A pendência **não expira na virada do dia**. O CHD continua vendo o
> card até confirmar a ciência, mesmo que a intercorrência tenha sido
> aberta há vários dias.

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

## 5.8 Agendamento casado (caso com EDA + Colonoscopia autorizadas)

Quando o médico autoriza **os dois procedimentos** (EDA e Colonoscopia) com
fluxo de agendamento, o card do CHD aparece como **Agendamento casado**: os
dois componentes são apresentados juntos, e o CHD confirma **uma única**
data, hora e localização para o caso — não existe agendamento separado por
procedimento.

O CHD não altera silenciosamente os componentes do conjunto autorizado. Se
precisar ajustar alguma informação do agendamento, use as orientações
médicas e a comunicação operacional com o médico/NIR.

---

# 6. Ações do usuário Supervisor

O papel de **Supervisor** corresponde aos perfis de gerência e administração
do sistema. O Supervisor não conduz o caso no dia a dia: ele acompanha o
**desfecho do dia do exame**. A aba **Follow-up**, no Dashboard, permite
registrar, para cada caso com exame no dia, o que aconteceu — se o
procedimento foi realizado, a causa quando não foi e se o paciente foi
internado.

Esse registro é apenas informativo, de acompanhamento e de métrica. Ele
**não** altera o estado do caso, **não** abre intercorrência, **não** cancela
e **não** reagenda exames.

## 6.1 Registrar follow-up de agendamento

### Quando usar

Registre o follow-up quando o dia do exame já passou e o desfecho é
conhecido:

- o exame foi **realizado** normalmente;
- o exame **não foi realizado** — registrar a causa;
- o paciente **foi internado** ou não.

Atenção: o follow-up **não substitui** os fluxos de intercorrência e
reagendamento. Se um exame não realizado precisar de nova data, use o fluxo
de reagendamento do CHD (seção 5.5); se houve mudança após o aceite, use a
intercorrência pós-aceitação do NIR (seção 3.8). O follow-up apenas registra
o desfecho.

### Como abrir a aba Follow-up

1. entrar no sistema com o perfil ativo **Supervisor** ou **Administrador**;
2. acessar o **Dashboard**;
3. clicar na aba **Follow-up** no menu do dashboard.

### O que a lista mostra

A lista abre mostrando os casos elegíveis de **hoje e ontem** (dias locais):

- casos com **agendamento confirmado** cujo dia do exame está na data
  listada;
- casos de **vinda imediata autorizada** (fluxos sem agendamento, como vinda
  imediata, pré-UTI ou enfermaria + retaguarda UTI) com decisão médica
  registrada na data listada.

Cada card mostra o nome do paciente, o número da ocorrência/registro, o
horário do agendamento (ou o fluxo e a data/hora da decisão, na vinda
imediata) e o estado do follow-up:

- badge **Follow-up registrado** — o caso já tem follow-up; a versão (v1,
  v2, ...), a data/hora e o autor aparecem logo abaixo do badge;
- badge **Follow-up pendente** — ainda não há follow-up registrado para o
  caso.

Também é possível refinar a lista:

- escolher uma **data específica** no seletor de data para ver apenas os
  casos daquele dia;
- buscar por **número da ocorrência** ou **nome do paciente** — a busca cobre
  qualquer data e devolve no máximo **50 casos**.

Atenção: caso **reagendado** aparece na lista apenas na data vigente do novo
agendamento, não na data antiga.

### Como preencher o follow-up

1. localizar o caso na lista e clicar em **Registrar follow-up** (ou
   **Atualizar follow-up**, quando o caso já tiver registro);
2. para **cada procedimento** do caso (EDA, Colonoscopia ou os dois),
   informar o desfecho:
   - **Realizado** — o exame foi realizado;
   - **Não realizado** — informar a causa:
     - **Absenteísmo** — o paciente não compareceu;
     - **Cancelamento por falta de recursos no dia** — informar o submotivo:
       urgências que ocuparam o horário, falta de tempo hábil ou equipamento
       quebrado/não disponível;
     - **Outras causas** — descrever a causa no campo de texto;
3. responder se **o paciente foi internado** — a pergunta é sempre exibida e
   é obrigatória em todos os casos;
4. clicar em **Registrar follow-up**.

Regras do formulário:

- procedimento **realizado** dispensa causa;
- procedimento **não realizado** exige a causa — sem causa, o envio é
  bloqueado;
- **Cancelamento por falta de recursos no dia** exige um dos submotivos;
- **Outras causas** exige a descrição (obrigatória).

### Versões do follow-up

Cada gravação cria uma **nova versão** do follow-up do caso:

- a primeira gravação cria a **versão 1**;
- gravar novamente (correção ou complemento) cria a **versão seguinte**;
- as versões anteriores **nunca são editadas nem apagadas** — cada versão
  fica preservada com o **autor** e a **data/hora** do registro;
- a versão de número maior é a **versão atual**, usada na lista para o badge
  **Follow-up registrado**.

Na tela do formulário, o painel **Versões do follow-up** mostra a versão
atual e o histórico completo das versões preservadas. Para corrigir um
follow-up já registrado, basta salvar novamente: o sistema cria uma versão
nova e mantém a anterior no histórico com autor e data originais.

---

# 7. Boas práticas para todos os usuários

## 7.1 Antes de concluir uma ação

Sempre confira:

- se o paciente está correto;
- se o número de registro/ocorrência está correto;
- se os documentos pertencem ao mesmo paciente;
- se a decisão escolhida corresponde ao fluxo desejado;
- se os campos obrigatórios foram preenchidos corretamente.

## 7.2 Use os botões formais para decisões formais

| Necessidade | Onde fazer |
|---|---|
| Enviar novo caso | **Novo Encaminhamento** |
| Decidir aceite/negativa médica | **Formulário de Decisão Médica** |
| Médico indicar fluxo sem agendamento | **Formulário de Decisão Médica > Fluxo de Admissão** |
| Pedir documento antes da decisão | **Comunicação operacional** |
| Confirmar ou negar agendamento | **Confirmação de Agendamento** |
| CHD tomar ciência de fluxo sem agendamento | **Fila do CHD > Confirmar ciência** |
| NIR executar ação de UTI, enfermaria ou vinda imediata | **Resultado final do caso + rotina operacional NIR** |
| CHD avisar NIR sobre alteração interna em caso histórico | **Buscar histórico > Detalhes > Comunicar NIR** |
| NIR registrar intercorrência após agendamento | **Casos Encerrados > Detalhes > Intercorrência Pós-Aceitação** |
| Responder intercorrência | **Fila do CHD/Agendador** |
| Encerrar caso após resultado | **Confirmar Recebimento** |
| Corrigir caso anterior | **Reenviar caso corrigido** |

## 7.3 Quando usar comunicação operacional

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

## 7.4 O que acontece quando o caso é concluído

Quando o NIR confirma o recebimento do resultado final, o caso sai das filas operacionais.

Ele continua registrado para auditoria e pode ser localizado em **Casos Encerrados**, quando aplicável.

---

# 8. Observações finais

## 8.1 Padronização de termos

Neste manual:

- usamos **CHD** como termo principal para o usuário de agendamento;
- usamos `@medico` e `@chd` como menções preferenciais;
- as menções devem ser digitadas sem acento.

## 8.2 Ativação da colonoscopia e do combinado é assunto da operação

A disponibilidade da **Colonoscopia** e da seleção **EDA + Colonoscopia** no
upload é controlada pela operação (flag de configuração). Esse controle não é
assunto de usuário comum: o usuário apenas vê as opções habilitadas quando o
sistema as liberar, ou desabilitadas com explicação quando não. Nenhuma ação
individual ativa ou desativa os procedimentos.
