# Proposal: Alinhar Contrato LLM e Roteamento NIR → Médico ao Legado

## Contexto

A investigação em `docs/investigations/2026-05-18-nir-to-doctor-flow-review.md` identificou divergências críticas entre a reimplementação Django e o sistema legado `augmented-triage-system` no fluxo NIR → médico.

O problema central é que a pipeline atual não usa integralmente o contrato LLM, prompts, validações e formato de relatório otimizados no legado com feedback médico real. Além disso, casos `non_eda`/`unknown` estão entrando na fila médica, embora o legado envie esses casos diretamente ao NIR como revisão manual.

## Objetivos

1. Restaurar os nomes canônicos de prompts do legado:
   - `llm1_system`
   - `llm1_user`
   - `llm2_system`
   - `llm2_user`
2. Portar os defaults e a renderização final dos prompts do legado quase literalmente.
3. Portar a validação Pydantic v2 dos schemas LLM1/LLM2 do legado.
4. Registrar auditoria via `CaseEvent`, incluindo versões de prompts e erros relevantes, sem criar tabela nova de interações LLM neste change.
5. Corrigir `non_eda`/`unknown` para ir direto ao resultado NIR (`WAIT_R1_CLEANUP_THUMBS`) com revisão manual obrigatória, sem entrar na fila médica.
6. Apresentar ao médico um relatório equivalente ao formato legado de 7 blocos.
7. Garantir que views médicas exijam papel ativo `doctor`.

## Não Objetivos

- Não reintroduzir Matrix, Rooms ou `case_messages` no Django.
- Não criar tabela equivalente a `case_llm_interactions` neste change.
- Não redesenhar o rulebook clínico.
- Não alterar o fluxo scheduler/immediate, exceto se necessário para manter o fluxo NIR → médico consistente.
- Não implementar novas funcionalidades administrativas além do alinhamento dos nomes de prompt existentes.

## Decisões Confirmadas

- Um único change deve cobrir este alinhamento.
- Os nomes legados de prompts são canônicos.
- Prompts defaults legados devem existir como fallback de código e seed inicial.
- Pydantic deve ser usado literalmente para validação dos DTOs, adicionando dependência explícita se necessário.
- Para `non_eda`/`unknown`, o Django deve ir direto para `WAIT_R1_CLEANUP_THUMBS` com resultado de revisão manual.
- O relatório médico pode ser implementado via presenter Django, desde que o resultado final seja equivalente ao legado.

## Riscos

- Testes atuais codificam comportamentos divergentes e precisarão ser atualizados.
- A validação Pydantic rígida pode transformar respostas LLM antes aceitas em falhas explícitas de pipeline; isso é desejável, mas precisa gerar auditoria clara.
- Portar muito código do legado em um único slice aumenta risco. Por isso o change será dividido em slices enxutos.

## Referências

- Investigação: `docs/investigations/2026-05-18-nir-to-doctor-flow-review.md`
- Legado LLM1 DTO: `/home/carlos/projects/augmented-triage-system/src/triage_automation/application/dto/llm1_models.py`
- Legado LLM2 DTO: `/home/carlos/projects/augmented-triage-system/src/triage_automation/application/dto/llm2_models.py`
- Legado LLM1 service: `/home/carlos/projects/augmented-triage-system/src/triage_automation/application/services/llm1_service.py`
- Legado LLM2 service: `/home/carlos/projects/augmented-triage-system/src/triage_automation/application/services/llm2_service.py`
- Legado Room-2 templates: `/home/carlos/projects/augmented-triage-system/src/triage_automation/infrastructure/matrix/message_templates.py`
