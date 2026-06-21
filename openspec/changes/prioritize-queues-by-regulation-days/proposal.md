# Proposal: Priorizar filas por “Dias em tela” do relatório de regulação

**Change ID**: `prioritize-queues-by-regulation-days`  
**Risco**: PROFISSIONAL (adiciona campo persistente em `Case`, parser determinístico de PDF e altera ordenação de filas operacionais)  
**Solicitante**: usuários médicos e agendadores

## Objetivo

Extrair o número informado no cabeçalho do relatório de regulação como `Dias em tela` e usar esse valor para priorizar as filas operacionais:

- fila médica (`WAIT_DOCTOR`);
- fila de agendamento (`WAIT_APPT`).

A ordenação deve mostrar primeiro os casos com maior `Dias em tela`, pois esse é o fator acordado com usuários como prioridade operacional mais relevante.

## Problema

Hoje as filas de médico e agendador são ordenadas por `Case.created_at`, isto é, pelo tempo de entrada no ATS. O card também mostra `Aguardando há X min`, calculado a partir de `created_at`.

Isso não representa a idade real do pedido na regulação. Um caso pode ter entrado recentemente no ATS, mas já estar há muitos dias aguardando no sistema de regulação, informação que aparece no PDF como:

```text
Dias em tela: 12
```

O sistema já reconhece a expressão `Dias em tela` apenas como sinal de validade do relatório em `apps/intake/regulation_gate.py`, mas não extrai o número nem o persiste.

## Escopo funcional

1. Extrair deterministicamente o número depois de `Dias em tela:` a partir do texto extraído do PDF.
2. Persistir esse número no `Case`.
3. Para ocorrências repetidas em cabeçalhos de múltiplas páginas:
   - coletar todos os números encontrados;
   - usar o maior valor encontrado.
4. Quando o dado não for encontrado:
   - manter `NULL` no banco;
   - ordenar esses casos por último nas filas priorizadas.
5. Ordenar a fila médica por:
   1. maior `Dias em tela` primeiro;
   2. empate: `created_at` mais antigo primeiro.
6. Ordenar a fila de agendamento `WAIT_APPT` por:
   1. maior `Dias em tela` primeiro;
   2. empate: `created_at` mais antigo primeiro.
7. Exibir o valor nos cards das filas médica e de agendamento quando disponível.
8. Manter os cards de vinda imediata do agendador no topo absoluto da fila; este change não altera a prioridade de vinda imediata.

## Fora de escopo

- Usar LLM para extrair `Dias em tela`.
- Somar dias desde upload ao número do PDF.
- Criar score de prioridade composto.
- Alterar FSM ou estados do caso.
- Alterar filas processadas/decididas/históricas.
- Ordenar cards de vinda imediata por `Dias em tela`; vinda imediata permanece no topo por regra própria.
- Criar filtros, dashboards ou relatórios gerenciais novos.
- Reprocessar PDF original quando `extracted_text` já existir.

## Decisões funcionais confirmadas

- PDF sem `Dias em tela`: vai para o final da fila priorizada.
- Múltiplos `Dias em tela` divergentes: usar o maior número.
- Deve ordenar e exibir o dado.
- No agendador, a ordenação vale apenas para `WAIT_APPT`; vinda imediata continua com prioridade absoluta e aparece no topo.
- A prioridade deve ser apenas o número impresso no PDF, sem somar tempo posterior no ATS.

## Critérios de aceitação do change

- [ ] Casos novos persistem `Dias em tela` durante extração do PDF quando o texto contém `Dias em tela: N`.
- [ ] Quando houver múltiplas ocorrências, o maior número é persistido.
- [ ] Quando não houver ocorrência, o campo fica `NULL`.
- [ ] Casos existentes com `extracted_text` são preenchidos por migration/data backfill ou mecanismo equivalente documentado.
- [ ] Fila médica ordena por maior `Dias em tela`, com `NULL` por último e `created_at` como desempate.
- [ ] Fila médica exibe `Dias em tela: N` no card quando disponível.
- [ ] Fila de agendamento `WAIT_APPT` ordena por maior `Dias em tela`, com `NULL` por último e `created_at` como desempate.
- [ ] Fila de agendamento exibe `Dias em tela: N` no card `WAIT_APPT` quando disponível.
- [ ] Cards de vinda imediata continuam aparecendo antes da lista `WAIT_APPT`.
- [ ] Testes relevantes cobrem parser, persistência e ordenação/visualização nas duas filas.
- [ ] Quality gate do `AGENTS.md` executado ou falhas justificadas.
- [ ] Cada slice gera relatório markdown temporário com snippets antes/depois e informa `REPORT_PATH`.
