# Proposal: Corrigir prior-case lookup após fechamento

**Change ID**: `fix-prior-case-lookup-after-closure`  
**Fase**: Fase 3 — débitos técnicos / hardening de pipeline  
**Risco**: PROFISSIONAL baixo/médio (altera contexto enviado ao LLM2; escopo restrito a lookup e testes)  
**Dependências**: `prior-case-lookup`, `pipeline-llm`, `case-attachments-initial-upload`

## Problema

O sistema já possui lookup de casos anteriores para enriquecer o contexto do LLM2 quando há negações recentes do mesmo paciente/caso operacional. A implementação atual em `apps/pipeline/prior_case.py` busca casos anteriores usando:

```python
agency_record_number == agency_record_number_do_caso_atual
status in [DOCTOR_DENIED, APPT_DENIED]
created_at >= now - 7 dias
```

Esse critério é frágil porque `DOCTOR_DENIED` e `APPT_DENIED` são estados transitórios da FSM. Após a negativa, o caso normalmente segue para etapas de ciência/cleanup e pode terminar como `CLEANED`. Quando isso acontece, o prior-case lookup deixa de encontrar uma negativa real e recente.

Impacto:

- reenvios/reinserções podem perder o contexto de negativa recente;
- o LLM2 pode deixar de considerar histórico relevante;
- casos corrigidos/reconsiderações futuras ficam menos rastreáveis;
- a regra depende de estado operacional atual em vez do fato semântico da decisão.

## Objetivo

Corrigir o prior-case lookup para identificar negações anteriores por campos semânticos e estáveis de decisão, não por status FSM transitório.

## Critérios de identificação de prior cases

### Chave principal

Usar o número de ocorrência/protocolo da Secretaria já persistido em:

```python
Case.agency_record_number
```

Esse campo continua sendo a chave de agrupamento deste change.

### Decisão negativa

Identificar prior cases por fatos de decisão:

```python
doctor_decision == "deny"
doctor_decided_at dentro da janela
```

ou:

```python
appointment_status == "denied"
appointment_decided_at dentro da janela
```

### Janela temporal

Usar a janela atual de 7 dias (`PRIOR_CASE_WINDOW_DAYS`), mas baseada na data da decisão negativa, não na data de criação do caso no ATS.

### Não usar neste change

- Nome do paciente como chave de matching.
- Data de criação do caso no sistema externo da Secretaria.
- `Case.created_at` como critério de janela principal.
- `status` FSM atual como indicador de negativa.

## Escopo

1. Atualizar `lookup_prior_case_context()` para:
   - filtrar por mesmo `agency_record_number`;
   - excluir o caso atual;
   - considerar negativas médicas por `doctor_decision="deny"` + `doctor_decided_at` na janela;
   - considerar negativas de agendamento por `appointment_status="denied"` + `appointment_decided_at` na janela;
   - não depender de `Case.status`;
   - ordenar/selecionar o prior case mais recente pela data da negativa, não por `created_at`.

2. Atualizar `_build_summary()` ou helper equivalente para:
   - classificar corretamente `doctor_denied` mesmo quando o status atual já é `CLEANED` ou outro estado posterior;
   - classificar corretamente `appointment_denied` mesmo quando o status atual já é `CLEANED` ou outro estado posterior;
   - preservar `reason`, `decided_at`, `decided_by` e `decided_by_role`.

3. Atualizar testes em `apps/pipeline/tests/test_prior_case.py` para cobrir:
   - negativa médica já fechada/limpa ainda encontrada;
   - negativa de agendamento já fechada/limpa ainda encontrada;
   - caso fora da janela por `doctor_decided_at`/`appointment_decided_at` não encontrado, mesmo com `created_at` recente;
   - caso dentro da janela por decisão encontrado, mesmo com `created_at` antigo;
   - caso mais recente escolhido pela data da decisão, não por `created_at`;
   - casos não negativos continuam excluídos.

## Fora de escopo

- Criar relação formal entre caso original e caso corrigido.
- Implementar fluxo de reabertura/reconsideração.
- Usar nome do paciente, CPF, CNS ou prontuário como matching.
- Alterar extração de `agency_record_number` do PDF.
- Alterar prompts LLM.
- Alterar FSM.
- Alterar UI.
- Criar migrations ou novos campos.
- Processar anexos por IA/OCR.

## Critérios de sucesso

- Prior case com negativa médica recente é encontrado mesmo que `status=CLEANED` ou outro estado posterior.
- Prior case com negativa de agendamento recente é encontrado mesmo que `status=CLEANED` ou outro estado posterior.
- Lookup não depende de `status in [DOCTOR_DENIED, APPT_DENIED]`.
- Janela de 7 dias usa `doctor_decided_at`/`appointment_decided_at`.
- `created_at` não é usado como critério de janela de decisão.
- A contagem `prior_denial_count_7d` reflete o número de negativas dentro da janela.
- O prior case retornado é a negativa mais recente pela data da decisão.
- Testes relevantes passam.
- Quality gate do AGENTS.md passa.
