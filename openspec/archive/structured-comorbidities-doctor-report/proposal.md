# Proposal: Lista estruturada de comorbidades no relatório médico

**Change ID**: `structured-comorbidities-doctor-report`  
**Risco**: PROFISSIONAL (altera contrato LLM1 e informação clínica exibida ao médico; sem migration/FSM)  
**Fase**: melhoria de usabilidade clínica da decisão médica  
**Dependências**: `align-llm-contract-and-doctor-routing`, `doctor-queue`, `pipeline-llm`

## Problema

O relatório automático exibido ao médico na tela de decisão mostra resumo clínico, achados críticos, pendências, sugestão, suporte, ASA e motivo objetivo. Porém um médico solicitou explicitamente uma **lista de comorbidades** descritas no relatório.

Hoje o sistema já extrai sinais clínicos usados para rulebook/ASA em:

```text
preop_screening.rulebook_signals.clinical_flags
```

Exemplos:

- `diabetes_mellitus`
- `explicit_obesity`
- `cardiopathy_explicit`
- `known_cardiovascular_disease`
- `prior_respiratory_disease`
- `multiple_comorbidities`

Esses flags ajudam regra determinística, ASA e suporte, mas **não satisfazem** a solicitação do médico porque não preservam uma lista textual de comorbidades encontradas no relatório, separadas por vírgula.

## Objetivo

Adicionar extração e exibição de uma lista explícita de comorbidades descritas no relatório clínico:

```text
Comorbidades descritas: hipertensão arterial sistêmica, diabetes mellitus tipo 2, doença renal crônica
```

Quando o relatório não descrever comorbidades, exibir:

```text
Comorbidades descritas: sem comorbidades descritas no relatório
```

Para casos antigos sem o novo campo estruturado, usar fallback seguro:

```text
Comorbidades descritas: extração de comorbidades não disponível neste caso
```

## Escopo

### Dentro

- Adicionar campo estruturado no contrato LLM1 para lista de comorbidades descritas.
- Atualizar instruções do LLM1 para preencher a lista com base apenas em evidência textual explícita.
- Exibir um item exclusivo de comorbidades no relatório médico (`templates/doctor/decision.html`).
- Preservar compatibilidade com casos já processados sem o novo campo.
- Testes TDD cobrindo schema/prompt e presenter.

### Fora

- Não alterar decisão automática, policy, ASA, suporte, reconciliação, LLM2 ou FSM.
- Não criar migration nem novo campo em `Case`.
- Não reprocessar casos antigos.
- Não implementar NLP determinístico/regex para extrair todas as comorbidades do texto bruto.
- Não inferir comorbidade apenas por medicação, exame ou fator de risco sem diagnóstico/antecedente explícito.
- Não sobrescrever prompts ativos existentes no banco.
- Não adicionar autocomplete, edição manual da lista ou UI administrativa para corrigir comorbidades.

## Critérios de sucesso

- LLM1 aceita e persiste `preop_screening.comorbidities_described` como lista de objetos `{name, source_text_hint}`.
- O prompt renderizado final orienta o LLM a extrair comorbidades descritas explicitamente e a retornar lista vazia quando não houver.
- A tela médica mostra item exclusivo `Comorbidades descritas`.
- Lista é renderizada separada por vírgula.
- Lista vazia em caso novo mostra `sem comorbidades descritas no relatório`.
- Campo ausente em caso antigo mostra `extração de comorbidades não disponível neste caso`.
- Sem alteração de banco, FSM, LLM2, policy, decisão automática ou suporte.
- Testes relevantes criados antes da implementação passar.
- Quality gate do `AGENTS.md` passa.
