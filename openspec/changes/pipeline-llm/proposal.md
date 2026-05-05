# Change Proposal: Pipeline LLM

> **Change ID**: `pipeline-llm`
> **Fase**: 2
> **Risco**: CRÍTICO
> **Depende de**: Fase 1 (Intake NIR) concluída

---

## Contexto

O intake NIR está funcional: upload de PDF, extração de texto, criação de caso (status `LLM_STRUCT`).
Agora precisamos processar o caso via pipeline LLM completa: LLM1 (extração estruturada) → Policy Engine determinístico → LLM2 (sugestão) → Scope Detection → FSM transitions.

## Escopo

1. **Client LLM abstraído** — adapter para OpenAI chat completions, injetável via settings
2. **LLM1 Service** — extração estruturada do texto (structured_data + summary_text)
3. **EDA Preop Policy** — engine determinístico de regras (thresholds, minimum exams, conditional gates)
4. **EDA Policy Reconciliation** — hard rules sobre saída LLM2
5. **Support Synthesis** — ASA + risco cardiovascular → recomendação de suporte
6. **Scope Detection** — detectar se exame é EDA; se não → `manual_review`
7. **LLM2 Service** — sugestão de decisão (accept/deny + support + rationale)
8. **Pipeline orchestrator** — django-q2 task que coordena toda a pipeline
9. **Job execution** — disparo automático após upload, transições FSM, persistência de artifacts

## Non-Goals

- **UI para prompts** — admin prompt management é Fase 7
- **Prior case lookup** — é Fase 9
- **Retries automáticos** — versão futura; nesta fase, falha = status FAILED + evento
- **LLM interaction log** — tabela separada de logs de interação LLM (pode ser ADR futura)

## Risco: CRÍTICO

Esta fase contém o **core clínico** do sistema. O policy engine determinístico é a peça mais sensível:
- Thresholds de HB, plaquetas, INR são regras de segurança clínica
- False negatives (deny errado) podem atrasar procedimentos
- False positives (accept errado) podem colocar paciente em risco
- **Todos os testes do policy engine devem ser preservados fielmente do legado**

## Dependências novas

```bash
uv add openai    # OpenAI Python SDK (oficial)
```

O legado usava `urllib` direto. No Django, usaremos o SDK oficial `openai` com `httpx` (já é dependência transitiva).

## Critério de Sucesso

- Pipeline completa executa após upload de PDF
- Case transita LLM_STRUCT → LLM_SUGGEST → R2_POST_WIDGET (ou FAILED)
- `structured_data`, `summary_text`, `suggested_action` persistidos no Case
- Policy engine: todos os testes do legado passam no Django
- Scope detection: caso non-EDA → manual_review sem LLM2
- Eventos auditáveis gerados para cada etapa
