# Proposal: Exibir médico responsável e CRM para NIR e Agendador

**Change ID**: `show-doctor-registration-downstream`
**Risco**: ESSENCIAL (exibição de dados já persistidos, sem migration)
**Dependências**: `user-professional-council` implementado; `Case.doctor` já preenchido na decisão médica.

## Objetivo

Propagar visualmente a identificação do médico que decidiu o caso para os atores downstream: NIR e agendador.

Quando um médico aceita ou nega um caso, o NIR e o agendador devem ver com clareza o nome do médico responsável e, quando cadastrado, seu conselho/número profissional, por exemplo:

```text
Médico: Dra. Maria Silva — CRM 12345
```

Se o médico não tiver conselho/número cadastrado, exibir ao menos o nome:

```text
Médico: Dra. Maria Silva
```

## Escopo

### Funcionalidades

1. Criar representação padronizada do médico responsável:
   - nome preferencial: `get_full_name()`; fallback: `username`;
   - registro profissional: `professional_council professional_council_number`, quando ambos existirem.

2. Exibir médico responsável para o NIR:
   - listagem/cards de “Meus Casos”;
   - detalhe do caso, especialmente no bloco de resultado final.

3. Exibir médico responsável para o agendador:
   - fila de agendamento para casos aceitos com fluxo `scheduled`;
   - bloco de vinda imediata para ciência operacional;
   - tela de confirmação de agendamento.

4. Cobrir com testes de views/templates relevantes.

## Fora de escopo

- Alterar persistência da decisão médica.
- Criar migration.
- Bloquear decisão médica sem CRM.
- Validar externamente CRM/COREN.
- Adicionar filtros ou busca por médico/CRM.
- Exibir médico na tela do próprio médico.

## Observações

O projeto é greenfield, mas a UI deve ter fallback para médico sem CRM cadastrado porque o campo é facultativo.