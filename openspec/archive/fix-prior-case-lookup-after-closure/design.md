# Design: Corrigir prior-case lookup após fechamento

## Estado atual

O lookup está em:

```text
apps/pipeline/prior_case.py
```

A função pública é:

```python
lookup_prior_case_context(case_id, agency_record_number, now=None) -> PriorCaseContext
```

Hoje a busca faz, conceitualmente:

```python
Case.objects.filter(agency_record_number=agency_record_number)
    .exclude(case_id=current_case_id)
    .filter(
        Q(status=CaseStatus.DOCTOR_DENIED) | Q(status=CaseStatus.APPT_DENIED),
        created_at__gte=window_start,
    )
    .order_by("-created_at")
```

E `_build_summary()` decide o tipo da negativa pelo `case.status`.

## Por que isso é problema

`Case.status` é o estado operacional atual da FSM. Ele muda conforme o fluxo avança.

Exemplos:

```text
DOCTOR_DENIED → WAIT_R1_CLEANUP_THUMBS → CLEANED
APPT_DENIED   → WAIT_R1_CLEANUP_THUMBS → CLEANED
```

A decisão negativa continua existindo nos campos persistidos, mas o status deixa de ser `DOCTOR_DENIED` ou `APPT_DENIED`. Portanto, buscar por status transitório perde casos relevantes.

## Decisões

### D1. Manter `agency_record_number` como chave de agrupamento

O prior-case lookup continuará identificando casos anteriores pelo mesmo:

```python
Case.agency_record_number
```

Motivo:

- é o identificador operacional já extraído do relatório da Secretaria;
- já é usado no contrato do pipeline e nos prompts;
- evita matching probabilístico por nome;
- minimiza escopo e risco.

### D2. Não usar nome do paciente neste change

Nome do paciente não deve ser filtro para prior case neste change.

Motivos:

- risco de homônimos;
- variações de acento, abreviação, ordem e grafia;
- origem menos confiável para matching determinístico;
- falso positivo clínico pode ser pior que falso negativo.

Nome pode continuar aparecendo em telas/resumos, mas não como critério de busca.

### D3. Não usar data externa da Secretaria neste change

Não há campo persistido autoritativo para “data de criação do caso no sistema da Secretaria”.

`Case.created_at` é data de criação dentro do ATS, não data externa. Ela não deve ser usada como janela principal para prior-case lookup.

### D4. Usar campos semânticos de decisão negativa

Negativa médica:

```python
Q(doctor_decision="deny", doctor_decided_at__gte=window_start, doctor_decided_at__lte=now)
```

Negativa de agendamento:

```python
Q(appointment_status="denied", appointment_decided_at__gte=window_start, appointment_decided_at__lte=now)
```

A implementação pode usar `< now` ou `<= now` desde que os testes sejam determinísticos e a janela inclua decisões até a referência temporal informada.

### D5. Janela baseada na data da decisão

A janela de 7 dias deve ser aplicada sobre:

- `doctor_decided_at` para negativa médica;
- `appointment_decided_at` para negativa de agendamento.

Não aplicar a janela em `created_at`.

### D6. Ordenar pelo instante real da negativa

O prior case retornado deve ser a negativa mais recente dentro da janela.

Como há dois campos de data possíveis, a implementação deve comparar eventos de negativa, não apenas casos ordenados por `created_at`.

Abordagens aceitáveis:

1. **Lista em Python, simples e explícita (preferida para slice enxuto):**
   - buscar candidatos por `agency_record_number` e condições de decisão;
   - construir uma lista interna de eventos de negativa com:
     - `case`;
     - `decision_type` (`doctor_denied` ou `appointment_denied`);
     - `decided_at`;
   - ordenar por `decided_at desc`;
   - retornar o primeiro.

2. **QuerySet com anotação:**
   - usar `Case/When` para criar `denial_decided_at` e `denial_type`;
   - ordenar por anotação.

Para manter legibilidade e baixo risco, a abordagem em Python é aceitável porque o filtro é restrito por `agency_record_number` e janela curta.

### D7. Contagem conta eventos/casos de negação dentro da janela

`prior_denial_count_7d` deve refletir o número de negativas encontradas dentro da janela.

Na prática atual, cada caso deve ter no máximo uma negativa relevante no fluxo normal:

- ou negativa médica;
- ou negativa de agendamento.

Se um caso anômalo tiver ambos os campos negativos preenchidos, a implementação deve ser determinística. Para evitar dupla contagem inesperada, preferir prioridade explícita:

1. se `appointment_status == "denied"` e `appointment_decided_at` está na janela, considerar a negativa de agendamento;
2. senão, se `doctor_decision == "deny"` e `doctor_decided_at` está na janela, considerar a negativa médica.

Motivo: negativa de agendamento ocorre depois de aceite médico e é o fato operacional mais tardio quando presente. Esse cenário anômalo não deve ampliar o escopo do change.

### D8. `_build_summary()` não deve depender de status

O summary deve ser construído a partir do tipo de decisão identificado pelo lookup.

Opção recomendada:

```python
@dataclass
class _PriorDenialCandidate:
    case: Case
    decision: str  # "doctor_denied" | "appointment_denied"
    decided_at: datetime
```

E um helper:

```python
def _build_summary(candidate: _PriorDenialCandidate) -> PriorCaseSummary:
    ...
```

Assim, `Case.status` deixa de ser fonte de verdade para o tipo da negativa.

### D9. Não alterar contrato público sem necessidade

Manter a assinatura e o DTO público:

```python
lookup_prior_case_context(...) -> PriorCaseContext
PriorCaseContext
PriorCaseSummary
```

Evitar migrations, mudanças de schema e mudanças de prompt neste change.

## Arquivos previstos

O slice deve ser enxuto. Arquivos esperados:

| Arquivo | Tipo | Mudança |
| --- | --- | --- |
| `apps/pipeline/prior_case.py` | modificado | lookup por decisão estável, summary sem status |
| `apps/pipeline/tests/test_prior_case.py` | modificado | testes RED/GREEN para status posterior e datas de decisão |
| `openspec/changes/fix-prior-case-lookup-after-closure/tasks.md` | modificado ao concluir | marcar DoD |

Não há necessidade prevista de tocar views, templates, models, migrations ou prompts.

## Dimensionamento de slices

Este change deve ter **um único slice vertical**.

Justificativa:

- a entrega de valor é indivisível: lookup correto + testes;
- dividir em slices separados por testes/código seria horizontal;
- dividir médico/agendamento em dois slices aumentaria overhead sem ganho, pois ambos usam a mesma função e o mesmo bug estrutural;
- escopo previsto toca apenas 2 arquivos de código/teste.

## Plano de implementação conceitual

1. Escrever testes falhando para casos fechados/limpos.
2. Ajustar helper de criação de casos nos testes para permitir:
   - `status` final diferente de `DOCTOR_DENIED`/`APPT_DENIED`;
   - `doctor_decided_at` separado de `created_at`;
   - `appointment_decided_at` separado de `created_at`.
3. Implementar filtragem por campos de decisão.
4. Construir candidatos de negativa sem depender de status.
5. Ordenar por `decided_at desc`.
6. Gerar summary a partir do tipo da negativa.
7. Rodar testes específicos e quality gate completo.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Contar casos errados por nome de paciente | Não usar nome como chave |
| Perder casos já `CLEANED` | Usar campos de decisão, não status |
| Ordenação errada por `created_at` | Ordenar por data da decisão |
| Mudança grande no pipeline | Manter assinatura pública e DTOs |
| Duplicar contagem em caso anômalo com duas negativas | Definir prioridade determinística, preferindo negativa de agendamento |
| Tocar arquivos demais | Limitar a `prior_case.py` e testes, salvo justificativa no relatório |

## Futuro fora deste change

- Relação formal entre caso original e caso corrigido/reenvio.
- UI para reenvio corrigido.
- Matching por identificadores mais fortes caso venham a existir, como CNS/CPF/prontuário.
- Priorização ou explicação visual de prior cases para usuários humanos.
- Ajustes de prompt LLM para expor mais nuances do histórico.
