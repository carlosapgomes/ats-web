# Proposal: Corrigir contadores do dashboard

**Change ID**: `fix-dashboard-counters`  
**Risco**: PROFISSIONAL (correção de métricas de supervisão — impacto operacional em decisões de gestão)  
**Solicitante**: investigação iniciada pelo agente

## Objetivo

Corrigir os 4 contadores principais do dashboard (`Total Hoje`, `Aceitos`, `Negados`, `Em Andamento`) para refletirem com precisão o desfecho real dos casos, usando os campos de decisão imutáveis (`doctor_decision`, `appointment_status`) em vez do estado FSM transitório (`status`).

## Problema

Os contadores do dashboard usam critérios inconsistentes para classificar casos:

| Contador | Campo usado | Natureza do campo |
|----------|-------------|-------------------|
| **Aceitos** | `doctor_decision` | Decisão — imutável após o fato |
| **Negados** | `status` (FSM) | Estado — transiciona ao longo do pipeline |
| **Em Andamento** | Subtração dos dois | Herda erros de ambos |

### Bugs concretos identificados

1. **"Negados" = 0 quando deveria ser 3**: casos negados que já transicionaram para `CLEANED` não são capturados pelo filtro `status__in=[DOCTOR_DENIED, APPT_DENIED]`. Os campos `doctor_decision="deny"` e `appointment_status="denied"` são ignorados.

2. **"Aceitos" inflado**: conta casos com `doctor_decision="accept"` mas `appointment_status="denied"` como aceitos. O desfecho final foi negativo (scheduler negou), mas o contador trata como positivo.

3. **"Em Andamento" inclui casos terminais negados**: a fórmula `total_today - accepted - denied` deixa escapar casos negados que não são capturados por nenhum dos dois contadores, fazendo-os cair em "Em Andamento".

4. **Risco latente de dupla contagem**: um caso com `doctor_decision="accept"` e `status=APPT_DENIED` seria contado simultaneamente em "Aceitos" e "Negados", subcontando "Em Andamento".

### Evidência (banco real em 31/05/2026)

| # | Status | doctor_decision | appointment_status | Desfecho real | Contador atual |
|---|--------|-----------------|-------------------|---------------|----------------|
| A | `WAIT_DOCTOR` | *(vazio)* | *(vazio)* | ⏳ Em andamento | Em Andamento ✅ |
| B | `CLEANED` | `accept` | *(vazio)* | ✅ Aceito (prov. imediato) | Aceitos ✅ |
| C | `CLEANED` | `accept` | `confirmed` | ✅ Aceito confirmado | Aceitos ✅ |
| D | `CLEANED` | `accept` | `denied` | ❌ Negado pelo scheduler | Aceitos ❌ |
| E | `CLEANED` | `accept` | `denied` | ❌ Negado pelo scheduler | Aceitos ❌ |
| F | `CLEANED` | `deny` | *(vazio)* | ❌ Negado pelo médico | Em Andamento ❌ |

**Resumo dos erros:**

| Contador | Exibido | Correto | Delta |
|----------|:-------:|:-------:|:-----:|
| Total Hoje | 6 | 6 | — |
| Aceitos | 4 | 2 | +2 |
| Negados | 0 | 3 | −3 |
| Em Andamento | 2 | 1 | +1 |

## Escopo

### Funcionalidades

1. Reescrever `_compute_summary()` em `apps/dashboard/views.py` para usar campos de decisão imutáveis.
2. Atualizar testes existentes do dashboard para refletir as novas queries.
3. Adicionar testes que cubram os cenários de bug identificados (denied → CLEANED, accepted + appointment denied, scope-gated cases).
4. Verificar que submétricas (Aguardando por Etapa, Fluxo de Admissão, Tempo Médio) não foram quebradas.

### Fora de escopo

- Alterar labels, layout ou CSS dos cards de contadores.
- Alterar submétricas (`_compute_stage_waiting`, `_compute_admission_flow`, `_compute_average_times`).
- Alterar a tabela de casos ou filtros.
- Alterar o modelo `Case`, FSM ou migrations.
- Alterar o `SupervisorSummary`.
- Criar novos endpoints ou views.

## Nova semântica proposta

```python
# Aceitos: médico aceitou E scheduler não negou (ou ainda não decidiu)
# Usa doctor_decision e appointment_status — campos imutáveis após decisão
accepted = today_cases.filter(
    doctor_decision="accept"
).exclude(
    appointment_status="denied"
).count()

# Negados: médico negou OU scheduler negou
# Independe do status FSM atual (funciona mesmo após CLEANED)
denied = today_cases.filter(
    models.Q(doctor_decision="deny") | models.Q(appointment_status="denied")
).count()

# Em Andamento: resto (total - aceitos - negados)
# Como accepted e denied agora usam critérios mutuamente exclusivos,
# a subtração é confiável
in_progress = total_today - accepted - denied
```

**Garantia de exclusão mútua:** um caso com `doctor_decision="accept"` e `appointment_status="denied"`:
- `accepted`: `doctor_decision="accept"` ✅ → mas `.exclude(appointment_status="denied")` ❌ → **não conta**
- `denied`: `appointment_status="denied"` ✅ → **conta**

Um caso com `doctor_decision="deny"` e sem appointment_status:
- `accepted`: `doctor_decision="accept"` ❌ → **não conta**
- `denied`: `doctor_decision="deny"` ✅ → **conta**

## Critérios de aceitação do change

- [ ] "Negados" captura casos com `doctor_decision="deny"` mesmo após CLEANED.
- [ ] "Negados" captura casos com `appointment_status="denied"` mesmo após CLEANED.
- [ ] "Aceitos" exclui casos com `appointment_status="denied"`.
- [ ] "Em Andamento" é igual a `total - aceitos - negados` sem dupla contagem nem gaps.
- [ ] Casos scope-gated (sem doctor_decision) permanecem em "Em Andamento" enquanto não atingirem estado terminal.
- [ ] Testes existentes do dashboard continuam passando (ajustados quando necessário).
- [ ] Novos testes cobrem os cenários de bug identificados.
- [ ] Quality gate do `AGENTS.md` executado.
- [ ] Relatório do slice gerado com `REPORT_PATH`.
