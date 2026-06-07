# Proposal: Endurecer exibição e extração de exames rastreados

**Change ID**: `harden-tracked-exam-reporting`  
**Fase**: ajuste de segurança/clareza pós-exibição de datas de exames  
**Risco**: PROFISSIONAL (altera apresentação clínica e instrução LLM1, sem mudar decisão/FSM/schema)  
**Dependências**: `show-recent-exam-dates-in-doctor-report`, `pipeline-llm`, `doctor-queue`

## Problema

Após passar a mostrar a data dos exames recentes, foi identificado um caso em que o relatório técnico exibiu:

```text
ECG: Sem exame (mais recente em 06/06/2026 07:00)
Ecocárdio: Sem exame (mais recente em 06/06/2026 07:00)
RX: Sem exame (mais recente em 06/06/2026 07:00)
```

O texto extraído continha uma seção datada com:

```text
ECG: Sem Exame
Ecocardio: Sem Exame
RX: Sem Exame
```

O LLM1 interpretou essas linhas como itens de `tracked_exams`. Tecnicamente havia menção datada, mas clinicamente a apresentação é confusa: pode sugerir que houve ECG/ECO/RX recentes, quando na verdade o laudo afirma ausência desses exames.

Também foi observado que exames laboratoriais externos com data podem aparecer sem data na apresentação se não estiverem marcados como `is_most_recent=true`. O ideal é mostrar a data de todos os exames rastreados quando disponível, destacando apenas o mais recente.

## Objetivo

Ajustar a apresentação e o prompt LLM1 para:

1. não apresentar entradas de ausência de exame como exame recente;
2. exibir data em todos os exames rastreados que tenham `exam_datetime_iso`, não apenas no mais recente;
3. destacar o exame mais recente sem esconder a data dos demais;
4. orientar o LLM1 a não incluir em `tracked_exams` menções como “Sem Exame”, “não realizado”, “não consta” ou equivalentes.

## Escopo

### Funcionalidades

1. Presenter médico (`apps/doctor/presenters.py`):
   - filtrar ou não renderizar como exame rastreado itens cujo `result_value` indique ausência de exame;
   - mostrar `exam_datetime_iso` formatado para qualquer item válido com data;
   - adicionar marcador de “mais recente” apenas quando `is_most_recent=true`;
   - preservar robustez para data ausente/inválida.

2. Prompt LLM1 (`apps/pipeline/llm1_service.py`):
   - instruir explicitamente que `tracked_exams` deve conter apenas exames efetivamente realizados/resultados disponíveis;
   - não incluir “Sem Exame”, “não realizado”, “não consta”, “ausente” como exame rastreado;
   - usar essas menções apenas como evidência de ausência, quando relevante para campos de pré-check;
   - preencher `exam_datetime_iso` para todo exame rastreado quando houver data associada, não apenas para o mais recente.

## Fora de escopo

- Alterar schema LLM1/LLM2.
- Alterar lógica determinística de decisão, política EDA ou FSM.
- Criar novo campo no banco ou migração.
- Criar nova UI ou componente separado para exames ausentes.
- Reprocessar casos já processados.
- Alterar templates salvo se estritamente necessário.
- Alterar LLM2.

## Critérios de sucesso

- O relatório médico não mostra `ECG: Sem exame (mais recente em ...)` nem equivalentes para ECO/RX/USG/TC/RNM.
- Exames laboratoriais válidos com `exam_datetime_iso` mostram data mesmo quando não são o mais recente.
- Exame válido marcado como `is_most_recent=true` mostra data e destaque de mais recente.
- Exame válido não recente com data mostra data sem destaque de mais recente.
- Data inválida ou ausente não quebra o relatório.
- Prompt LLM1 orienta explicitamente a não colocar ausência de exame em `tracked_exams`.
- Prompt LLM1 orienta a preencher data para todos os exames rastreados quando disponível.
- Testes cobrem os casos acima.
- Quality gate do AGENTS.md passa.
