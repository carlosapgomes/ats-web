# Slice 001: Prior-case lookup por campos estáveis de decisão

## Contexto zero para implementador

O ATS é um monolito Django SSR para triagem automatizada de EDA. O pipeline LLM usa `apps/pipeline/prior_case.py` para buscar negações recentes do mesmo `agency_record_number` e enriquecer o contexto do LLM2.

A função pública atual é:

```python
lookup_prior_case_context(
    case_id: uuid.UUID | str,
    agency_record_number: str,
    now: datetime | None = None,
) -> PriorCaseContext
```

O bug: a implementação atual busca prior cases por `Case.status in [DOCTOR_DENIED, APPT_DENIED]` e `created_at >= janela`. Esses status são transitórios. Depois da negativa, o caso pode avançar para `WAIT_R1_CLEANUP_THUMBS` e depois `CLEANED`. Assim, uma negativa real e recente deixa de ser encontrada.

Este slice corrige o lookup para usar campos semânticos de decisão:

```python
doctor_decision == "deny"
doctor_decided_at dentro da janela
```

ou:

```python
appointment_status == "denied"
appointment_decided_at dentro da janela
```

A chave de agrupamento continua sendo:

```python
Case.agency_record_number
```

Não usar nome do paciente. Não usar data externa da Secretaria. Não alterar FSM.

## Objetivo do slice

Entregar verticalmente:

```text
Caso atual entra no pipeline
→ prior-case lookup busca mesmo agency_record_number
→ encontra negativas médicas/agendamento recentes mesmo se caso anterior já estiver CLEANED
→ retorna o resumo mais recente por data da decisão
→ mantém contagem correta para o LLM2
```

## Dimensionamento

Este change deve ter apenas este slice.

Motivo:

- a entrega de valor é uma única correção coesa;
- separar testes/código seria horizontal;
- separar negativa médica e negativa de agendamento duplicaria overhead;
- implementação prevista toca apenas 2 arquivos de código/teste.

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/pipeline/prior_case.py`
2. `apps/pipeline/tests/test_prior_case.py`
3. `openspec/changes/fix-prior-case-lookup-after-closure/tasks.md` ao finalizar

Se precisar tocar outros arquivos, justificar antes/depois no relatório do slice, explicando por que o escopo foi ampliado.

## Requisitos funcionais

### R1. Matching por agency_record_number

Manter comportamento atual:

- se `agency_record_number` vazio ou só espaços, retornar `PriorCaseContext()` vazio;
- filtrar por mesmo `agency_record_number`;
- excluir o caso atual por `case_id`.

Não adicionar matching por nome do paciente.

### R2. Negativa médica por campos de decisão

Um caso anterior deve contar como negativa médica se:

```python
case.doctor_decision == "deny"
case.doctor_decided_at is not None
window_start <= case.doctor_decided_at <= now  # ou < now, de forma determinística
```

O `Case.status` atual não deve importar.

Exemplo que deve passar:

```text
status atual: CLEANED
doctor_decision: deny
doctor_decided_at: há 2 dias
agency_record_number igual ao caso atual
→ deve ser encontrado
```

### R3. Negativa de agendamento por campos de decisão

Um caso anterior deve contar como negativa de agendamento se:

```python
case.appointment_status == "denied"
case.appointment_decided_at is not None
window_start <= case.appointment_decided_at <= now  # ou < now, de forma determinística
```

O `Case.status` atual não deve importar.

Exemplo que deve passar:

```text
status atual: CLEANED
appointment_status: denied
appointment_decided_at: há 1 dia
agency_record_number igual ao caso atual
→ deve ser encontrado
```

### R4. Janela temporal por data da decisão

A janela de 7 dias deve usar:

- `doctor_decided_at` para negativa médica;
- `appointment_decided_at` para negativa de agendamento.

Não usar `created_at` como filtro de janela.

Casos esperados:

```text
created_at: hoje
doctor_decided_at: há 10 dias
→ não conta
```

```text
created_at: há 30 dias
doctor_decided_at: há 2 dias
→ conta
```

### R5. Prior case mais recente por decided_at

Se houver múltiplas negativas, retornar a mais recente pela data da decisão, não por `created_at`.

Exemplo:

```text
Caso A: created_at hoje, doctor_decided_at há 5 dias
Caso B: created_at há 20 dias, appointment_decided_at há 1 dia
→ prior_case deve ser Caso B
```

### R6. Summary sem depender de status

`PriorCaseSummary` deve continuar preenchendo:

```python
prior_case_id
decided_at
decision  # "doctor_denied" | "appointment_denied"
reason
decided_by
decided_by_role  # "doctor" | "scheduler"
```

Mas a decisão deve vir do tipo de negativa identificado, não de `case.status`.

### R7. Caso anômalo com duas negativas

Não ampliar escopo para modelar caso anômalo complexo. Se um mesmo `Case` tiver tanto negativa médica quanto negativa de agendamento preenchidas e ambas dentro da janela, usar comportamento determinístico.

Preferência:

1. considerar negativa de agendamento se `appointment_status == "denied"` e `appointment_decided_at` está na janela;
2. senão considerar negativa médica se `doctor_decision == "deny"` e `doctor_decided_at` está na janela.

## TDD obrigatório

Antes de alterar a implementação, adicionar testes falhando em:

```text
apps/pipeline/tests/test_prior_case.py
```

### Testes mínimos novos/ajustados

1. `test_doctor_denial_cleaned_status_still_found`
   - criar caso atual com `agency_record_number="AR100"`;
   - criar caso anterior com mesmo ARN, `doctor_decision="deny"`, `doctor_decided_at` dentro da janela, mas `status=CaseStatus.CLEANED`;
   - lookup deve retornar esse caso como `doctor_denied`.

2. `test_appointment_denial_cleaned_status_still_found`
   - criar caso anterior com mesmo ARN, `appointment_status="denied"`, `appointment_decided_at` dentro da janela, mas `status=CaseStatus.CLEANED`;
   - lookup deve retornar esse caso como `appointment_denied`.

3. `test_doctor_denial_uses_decided_at_not_created_at_for_window`
   - caso anterior com `created_at` recente, mas `doctor_decided_at` fora da janela;
   - não deve contar.

4. `test_doctor_denial_old_created_at_but_recent_decision_is_found`
   - caso anterior com `created_at` antigo, mas `doctor_decided_at` dentro da janela;
   - deve contar.

5. `test_appointment_denial_uses_decided_at_not_created_at_for_window`
   - caso anterior com `created_at` recente, mas `appointment_decided_at` fora da janela;
   - não deve contar.

6. `test_most_recent_prior_case_uses_decision_timestamp_not_created_at`
   - dois casos com mesmo ARN;
   - um tem `created_at` mais recente, mas decisão mais antiga;
   - outro tem `created_at` mais antigo, mas decisão mais recente;
   - lookup deve retornar o de decisão mais recente.

7. Ajustar testes existentes que assumem `created_at` como data da decisão.
   - O helper `_make_case` provavelmente precisará aceitar `doctor_decided_at`, `appointment_decided_at` e `status` explicitamente.

### Como provar o RED

No relatório temporário, registrar:

- nomes dos testes adicionados;
- comando rodado antes da implementação;
- resumo da falha esperada, por exemplo:

```text
expected prior_case, got None because implementation still filters status=DOCTOR_DENIED/APPT_DENIED
```

Se por alguma razão o RED não puder ser demonstrado literalmente, justificar no relatório.

## Orientações de implementação

### Clean code

- Preferir helpers pequenos e nomeados.
- Evitar lógica complexa inline dentro de `lookup_prior_case_context()`.
- Manter DTOs públicos estáveis.
- Usar nomes explícitos como `_PriorDenialCandidate`, `_is_within_window`, `_build_denial_candidates` se ajudarem clareza.

### DRY

- Evitar duplicar normalização de reason.
- Evitar duplicar montagem de `PriorCaseSummary` para médico e agendador se um helper com `decision` resolver.

### YAGNI

Não implementar neste slice:

- matching por nome de paciente;
- matching por CNS/CPF/prontuário;
- relação entre caso original e corrigido;
- UI;
- migrations;
- novo modelo;
- mudanças em prompt LLM;
- OCR/IA de anexos;
- busca multi-janelas configurável.

### Performance

O filtro por `agency_record_number` e janela curta deve manter a busca pequena. Uma lista em Python de candidatos é aceitável para este slice se o código ficar mais claro.

## Critérios de sucesso

- [ ] Testes novos falham no RED contra a implementação antiga.
- [ ] Lookup encontra negativa médica recente mesmo com `status=CLEANED`.
- [ ] Lookup encontra negativa de agendamento recente mesmo com `status=CLEANED`.
- [ ] Lookup não usa `status` para decidir se um caso é prior denial.
- [ ] Janela de 7 dias usa `doctor_decided_at`/`appointment_decided_at`.
- [ ] `created_at` não determina inclusão/exclusão na janela.
- [ ] Prior case retornado é o de maior `decided_at`.
- [ ] `prior_denial_count_7d` permanece correto.
- [ ] DTO público e assinatura de `lookup_prior_case_context()` preservados.
- [ ] Nenhuma migration criada.
- [ ] Nenhum template/view alterado.
- [ ] Quality gate completo passa.

## Gates de autoavaliação

Antes de finalizar, responder no relatório:

1. O lookup ainda filtra por `Case.status` para encontrar negativas? Se sim, está errado.
2. Qual teste prova que caso `CLEANED` com `doctor_decision="deny"` é encontrado?
3. Qual teste prova que caso `CLEANED` com `appointment_status="denied"` é encontrado?
4. Qual teste prova que `created_at` não controla a janela?
5. Qual teste prova que a ordenação usa `decided_at`?
6. A assinatura pública de `lookup_prior_case_context()` mudou? Se sim, justificar; idealmente não deve mudar.
7. Algum arquivo fora de `prior_case.py` e `test_prior_case.py` foi tocado? Se sim, justificar.

## Relatório obrigatório

Criar um relatório markdown temporário, por exemplo:

```text
/tmp/fix-prior-case-lookup-after-closure-slice-001-report.md
```

O relatório deve conter:

- resumo do problema;
- lista de arquivos alterados;
- evidência do RED;
- evidência do GREEN;
- snippets antes/depois das partes principais;
- respostas aos gates de autoavaliação;
- comandos de validação executados e resultados;
- eventuais desvios de escopo, se houver.

Responder ao final da implementação com:

```text
REPORT_PATH=/tmp/fix-prior-case-lookup-after-closure-slice-001-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/fix-prior-case-lookup-after-closure/proposal.md, design.md, tasks.md and slices/slice-001-prior-case-lookup-decision-fields.md.
Implement ONLY Slice 001.
Use TDD: first add failing tests in apps/pipeline/tests/test_prior_case.py for prior cases already CLEANED and for decision timestamps vs created_at, then implement minimal code.
Keep the slice lean: ideally touch only apps/pipeline/prior_case.py and apps/pipeline/tests/test_prior_case.py, plus tasks.md when complete.
Do not use patient name as matching. Do not use Case.status to identify negative prior cases. Do not change FSM. Do not create migrations. Do not alter UI/templates/views.
The lookup must keep agency_record_number as the grouping key, exclude the current case_id, identify doctor denials by doctor_decision="deny" + doctor_decided_at within 7 days, identify appointment denials by appointment_status="denied" + appointment_decided_at within 7 days, and return the most recent denial by decision timestamp.
Apply clean code, DRY and YAGNI. Keep public DTOs/signature stable unless there is a very strong reason.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/fix-prior-case-lookup-after-closure/tasks.md when complete.
Create /tmp/fix-prior-case-lookup-after-closure-slice-001-report.md with RED/GREEN evidence, before/after snippets, quality gate results and answers to self-evaluation gates.
Commit and push.
Return REPORT_PATH=<path> and stop.
```
