# Proposal: Mostrar datas dos exames recentes no relatório médico

**Change ID**: `show-recent-exam-dates-in-doctor-report`  
**Fase**: ajuste de segurança/clareza do relatório técnico da triagem  
**Risco**: PROFISSIONAL (altera apresentação clínica para médico e prompt canônico LLM1, sem mudar FSM nem decisão determinística)  
**Dependências**: `pipeline-llm`, `align-llm-contract-and-doctor-routing`, `doctor-queue`

## Problema

O LLM1 já extrai exames rastreados em `structured_data.tracked_exams[]`, incluindo `exam_datetime_iso` e `is_most_recent`. Porém, o relatório técnico apresentado ao médico atualmente mostra apenas que um exame é “mais recente”, sem imprimir a data quando ela existe.

Exemplo atual:

```text
Hb: 10.0 g/dL (mais recente)
```

Isso é insuficiente para revisão médica, pois “mais recente” sem data não informa a antiguidade real do exame. A data do exame deve aparecer sempre que estiver disponível.

Além disso, o prompt do LLM1 orienta extração de `exam_datetime_iso`, mas não explicita que o resumo narrativo (`summary.one_liner` e `summary.bullet_points`) deve mencionar a data dos exames quando comentar exames recentes.

## Objetivo

Garantir, em duas camadas, que datas de exames recentes sejam visíveis:

1. **Correção determinística no presenter médico**: o relatório final exibido ao médico deve mostrar a data/hora de exames marcados como mais recentes quando `exam_datetime_iso` estiver disponível.
2. **Reforço no prompt LLM1**: o prompt canônico/default deve instruir explicitamente que, ao mencionar exames no resumo narrativo, a data deve ser incluída quando disponível, evitando frases vagas como “exames mais recentes” sem data. Como o deploy previsto parte de banco zerado, `seed_prompts` criará o prompt ativo inicial já com esse default atualizado.

## Escopo

### Funcionalidades

1. Presenter médico (`apps/doctor/presenters.py`):
   - Para cada item em `structured_data.tracked_exams[]` com `is_most_recent=true`:
     - se `exam_datetime_iso` existir e for parseável, exibir data em formato pt-BR;
     - se houver hora relevante, exibir data e hora;
     - se não houver data, manter indicação clara de recência indeterminada/sem data no laudo.
   - Não alterar regra de escolha do exame mais recente; apenas apresentação.

2. Prompt LLM1 (`apps/pipeline/llm1_service.py`):
   - Reforçar `LLM1_DEFAULT_USER_PROMPT` e/ou instruções renderizadas em `_render_user_prompt` para exigir data dos exames nos campos narrativos quando disponível.
   - Manter schema version `1.1` e não adicionar campos novos.

3. Seeds (`apps/llm/management/commands/seed_prompts.py`):
   - Permanecer alinhado à fonte canônica dos prompts LLM1 já importada de `apps.pipeline.llm1_service`.
   - Em banco zerado, criar `llm1_user` com o default atualizado.
   - Não criar migração nem sobrescrever prompts já existentes no banco.

## Fora de escopo

- Mudar schema Pydantic do LLM1.
- Alterar lógica de recência ou seleção de `is_most_recent`.
- Alterar LLM2, política EDA, reconciliação ou decisão sugerida.
- Criar nova tela, novo componente visual ou novo armazenamento de exames.
- Fazer migração de dados históricos.
- Re-seedar prompts ativos existentes no banco automaticamente.
- Alterar o JSON completo exibido em collapse, exceto por consequência natural de prompts futuros.

## Critérios de sucesso

- Relatório técnico da triagem mostra a data de exames recentes quando `exam_datetime_iso` existe.
- Data é exibida em formato legível para médico, preferencialmente `DD/MM/AAAA` ou `DD/MM/AAAA HH:MM`.
- Quando `is_most_recent=true` mas não há data, o relatório continua deixando claro que a recência é indeterminada/sem data no laudo.
- Prompt LLM1 passa a instruir explicitamente que resumo narrativo deve incluir data dos exames quando disponível.
- Testes cobrem presenter com data, presenter sem data e presença da instrução no prompt renderizado/default.
- Nenhum campo novo é exigido do LLM.
- Quality gate do AGENTS.md passa.
