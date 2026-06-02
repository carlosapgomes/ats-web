# Proposal: Observação médica opcional no caso

**Change ID**: `doctor-observation`  
**Risco**: PROFISSIONAL (inclui migration simples em `Case` + propagação de UI downstream)  
**Solicitante**: equipe do centro de hemorragia digestiva

## Objetivo

Permitir que o médico registre uma **observação livre opcional** durante a decisão do caso, com limite de caracteres para não prejudicar a interface, e tornar essa observação visível para os atores downstream que acompanham ou operacionalizam o caso.

A observação deve estar disponível para:

- NIR, na listagem e no detalhe do caso;
- agendador, na fila e na tela de confirmação/ciência operacional;
- supervisor/manager e admin, no detalhe do caso via dashboard.

## Problema

Hoje o médico possui apenas os campos estruturados da decisão:

- aceitar/negar;
- suporte necessário;
- fluxo de admissão;
- motivo obrigatório quando nega.

O campo `doctor_reason` já existe, mas representa **motivo de negativa**. Reutilizá-lo para observações gerais misturaria conceitos diferentes e poderia gerar ambiguidade em casos aceitos.

## Escopo

### Funcionalidades

1. Adicionar campo opcional de observação médica no `Case`.
2. Exibir textarea opcional no formulário de decisão médica.
3. Persistir a observação junto com a decisão médica.
4. Limitar a observação a um tamanho objetivo, recomendado: **500 caracteres**.
5. Sinalizar com badge nos cards/listagens quando o caso possui observação médica.
6. Exibir o texto completo da observação nos detalhes do caso e nas telas operacionais downstream.
7. Cobrir com testes TDD por slice.

### Fora de escopo

- Criar sistema de comentários múltiplos/thread.
- Editar observação após envio da decisão médica.
- Observações de NIR, agendador, supervisor ou admin.
- Notificações push/e-mail/SMS.
- Filtros ou busca por presença/conteúdo da observação.
- Histórico versionado de alterações da observação, pois ela será enviada uma única vez na decisão médica.

## UX esperada

### Médico

Na tela de decisão médica, abaixo das seções de aceitar/negar ou antes do envio, mostrar:

```text
Observação médica opcional
[textarea]
Visível para NIR, agendamento, supervisão e administração. Máx. 500 caracteres.
```

### Cards downstream

Quando houver observação:

```text
📝 Obs. médica
```

A badge deve ser discreta e não ocupar muito espaço.

### Detalhes downstream

Quando houver observação, mostrar um bloco/card dedicado:

```text
📝 Observação Médica
<texto informado pelo médico>
```

## Critérios de aceitação do change

- [ ] Médico consegue submeter decisão sem preencher observação.
- [ ] Médico consegue submeter decisão com observação de até 500 caracteres.
- [ ] Observação acima do limite é rejeitada pelo formulário.
- [ ] Observação é persistida no `Case`.
- [ ] NIR vê badge na listagem quando há observação.
- [ ] NIR vê texto completo no detalhe do caso.
- [ ] Manager/admin veem texto completo no detalhe do caso pelo dashboard.
- [ ] Agendador vê badge na fila quando há observação.
- [ ] Agendador vê texto completo na tela de confirmação ou ciência operacional.
- [ ] Casos sem observação não exibem badge nem card vazio.
- [ ] Testes relevantes passam.
- [ ] Quality gate do `AGENTS.md` executado.
- [ ] Cada slice gera relatório temporário com snippets antes/depois e informa `REPORT_PATH`.
