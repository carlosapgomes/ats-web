# Proposal: Clarificar UX de escrita na decisão médica

**Change ID**: `clarify-doctor-writing-ux`  
**Fase**: ajuste de UX/semântica operacional pós-comunicação operacional  
**Risco**: PROFISSIONAL (altera comportamento/semântica de campo existente na decisão médica e textos downstream; sem migration prevista)  
**Dependências**: `doctor-observation`, `case-operational-communication-mvp`, `case-communication-mentions-notifications`, `workflow-system-notices-in-case-communication`

## Problema

A tela de decisão médica hoje oferece múltiplos lugares para o médico escrever:

1. **Motivo da negativa** — campo estruturado para decisão `deny`.
2. **Observação Médica** — campo opcional genérico criado antes da comunicação operacional.
3. **Comunicação operacional** — thread por caso para mensagens entre NIR/médico/agendador, com menções e notificações.

Após a criação da comunicação operacional, o campo genérico **Observação Médica** ficou ambíguo:

- se o médico quer **recusar**, já existe motivo obrigatório da negativa;
- se o médico quer **pedir complemento documental/dados**, o fluxo esperado é usar comunicação operacional e não emitir parecer ainda;
- se o médico **aceita** e quer deixar orientação para agendamento/execução, o campo ainda é útil, mas isso não está explícito na UI.

A ambiguidade pode levar a uso incorreto:

- recusar caso apenas para pedir documento;
- escrever mensagens operacionais em campo estruturado da decisão;
- escrever orientação de agendamento na thread, onde pode se perder como parte do parecer;
- duplicar informação entre motivo de negativa, observação e comunicação.

## Objetivo

Reorganizar a UX e a semântica do campo existente `doctor_observation` para deixar claro que ele não é um canal genérico de conversa.

Nova semântica proposta:

> `doctor_observation` representa **orientações médicas vinculadas ao aceite**, principalmente para agendamento/execução do exame. Para negativa, usar apenas o motivo da negativa. Para pedidos, avisos e coordenação entre equipes, usar comunicação operacional.

## Escopo

### Funcionalidades

1. **Decisão médica**
   - Renomear o campo visual de `Observação Médica` para algo explícito, como `Orientações para agendamento/execução`.
   - Exibir/posicionar esse campo como parte do fluxo de **aceite**, não como campo genérico para qualquer decisão.
   - Atualizar help text para diferenciar:
     - aceite + orientação estruturada;
     - negativa + motivo da negativa;
     - pendência/complementação + comunicação operacional.
   - Renomear o botão `Cancelar` na decisão médica para `Voltar sem decidir`, reduzindo a percepção de cancelamento do caso.
   - Em submissão de negativa, não persistir nova orientação médica enviada por POST. A negativa deve usar `doctor_reason`.

2. **Comunicação operacional**
   - Reforçar na UI da decisão médica que pedidos de documentos, avisos e coordenação devem ser feitos pela comunicação operacional.
   - Não alterar o serviço/endpoint de comunicação operacional neste change.

3. **Visibilidade downstream**
   - Renomear labels/badges downstream que hoje dizem `Observação Médica`/`Obs. médica` para refletir a nova semântica (`Orientação médica`, `Orientações médicas`, ou equivalente).
   - Não alterar banco, FSM, auditoria ou notificações.

## Fora de escopo

- Remover o campo `Case.doctor_observation` do modelo.
- Criar migration ou renomear coluna.
- Criar novo sistema de templates de orientação médica.
- Criar autocomplete ou novos recursos na comunicação operacional.
- Bloquear tecnicamente que usuários escrevam mensagens operacionais em texto livre além da validação descrita.
- Reabrir casos negados/encerrados.
- Alterar fluxo de reenvio corrigido.
- Alterar métricas do dashboard.

## Decisão de produto

### Fluxos válidos

| Situação | Fluxo correto |
|---|---|
| Médico precisa de complemento antes de decidir | Comunicação operacional com menção ao NIR; voltar sem decidir |
| Médico nega o caso | Decisão `Negar` + motivo da negativa obrigatório |
| Médico aceita e quer orientar agendamento/execução | Decisão `Aceitar` + orientações médicas opcionais |
| Caso já negado/encerrado precisa ser corrigido | Novo caso corrigido vinculado ao anterior |

### Regra de semântica

- `doctor_reason`: motivo oficial da negativa.
- `doctor_observation`: orientação médica opcional apenas quando a decisão é aceitar.
- `CaseCommunicationMessage`: conversa operacional entre equipes; não substitui parecer, motivo de negativa, agendamento ou reenvio corrigido.

## Dimensionamento dos slices

O change deve ser feito em **2 slices verticais e enxutos**:

1. **Slice 001 — Decisão médica sem ambiguidade**  
   Entrega valor diretamente ao médico na tela de parecer: campos e textos corretos, orientação apenas no aceite, negativa sem observação, botão `Voltar sem decidir`, testes TDD.

2. **Slice 002 — Labels downstream alinhados**  
   Entrega consistência para NIR, agendador, supervisor/admin: badges/cards deixam de falar `Observação Médica` e passam a falar `Orientação médica`, sem mudar storage.

A divisão evita um slice grande que toque médico + NIR + scheduler + dashboard ao mesmo tempo. Cada slice deve manter valor end-to-end e tocar o mínimo de arquivos possível.

## Critérios de sucesso do change

- Médico entende pela UI onde escrever em cada situação.
- Campo de orientação aparece/é apresentado como parte do aceite, não como observação genérica.
- Negativa usa apenas motivo da negativa; orientação enviada junto com negativa não é persistida.
- Pedido de documento/complementação é orientado para comunicação operacional.
- Botão de saída da decisão médica diz `Voltar sem decidir`.
- Downstream usa nomenclatura consistente (`Orientação médica`) para o conteúdo salvo em `doctor_observation`.
- Nenhuma migration é criada sem necessidade.
- FSM, eventos estruturados e comunicação operacional permanecem inalterados.
- Testes relevantes passam.
- Quality gate do `AGENTS.md` é executado.
- Cada slice gera relatório markdown temporário com snippets antes/depois e informa `REPORT_PATH`.
