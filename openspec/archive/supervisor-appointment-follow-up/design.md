# Design: Follow-up de agendamentos pelo Supervisor

## Estado atual relevante

- `Case` tem `appointment_at` (aware, TZ `America/Bahia`), `appointment_status` (`confirmed`/`denied`), `doctor_admission_flow`, `doctor_decided_at`, `agency_record_number` e `structured_data["patient"]["name"]` (índice trigram `cases_case_patient_name_trgm_idx`).
- Fluxos `OPERATIONAL_NOTICE_FLOWS` (`immediate`, `pre_icu`, `ward_icu_backup`, `pediatric_em`) não passam por `WAIT_APPT`: a "data da autorização da vinda imediata" é `doctor_decided_at` (mesma convenção da fila de ciência operacional do scheduler: `doctor_decided_at or created_at`, `apps/scheduler/views.py` ~L311-322).
- Na data do exame o caso já está tipicamente `CLEANED` (ciclo `APPT_CONFIRMED → resposta final → CLEANED` via ciência do NIR). `cleanup_completed` não redige dados: `structured_data` sobrevive (busca de casos encerrados já lista por nome).
- Auditoria: `CaseEvent` append-only (`actor`, `actor_type`, `timestamp`, `event_type` livre ≤80, `payload` JSON). Services criam eventos diretamente (`CaseEvent.objects.create`) — padrão de `apps/cases/services.py::_record_event`.
- Desfecho por procedimento existe como `CaseProcedure` (`case.procedures`, `procedure_type` ∈ {`eda`,`colonoscopy`}); rows são a projeção do conjunto (nunca coluna singular no `Case`).
- Busca por ocorrência/nome: padrão existente `Q(agency_record_number__icontains) | Q(structured_data__patient__name__icontains)` limitado a 50 (`apps/intake/views.py::closed_cases_search`).
- Área do supervisor: app `dashboard`, views com `@login_required @role_required("manager", "admin")`, nav em `templates/dashboard/_nav.html`.

## Decisões

### D1. Follow-up é registro — FSM intocada

Nenhuma transição, estado ou fila nova. Os models vivem em `apps/cases` (domínio), consumidos por views do `dashboard`. Justificativa: preserva o FSM legado de 18 estados, as filas operacionais e elimina risco de regressão; o desfecho é fato complementar ao caso, não fase do fluxo. (Decisão do domínio confirmada pelo owner: follow-up ≠ intercorrência.)

### D2. Modelos versionados append-only

```text
CaseFollowUp                    (1 row por versão de follow-up do caso)
  case           FK Case, related_name="follow_ups", CASCADE
  version        PositiveIntegerField (1, 2, 3…)
  patient_admitted  BooleanField   — internação no nível do CASO (sempre informada)
  recorded_by    FK AUTH_USER_MODEL, SET_NULL, null  — quem preencheu esta versão
  recorded_at    DateTimeField(auto_now_add)
  UNIQUE (case, version)

ProcedureFollowUp               (desfecho por procedimento, dentro da versão)
  follow_up      FK CaseFollowUp, related_name="procedure_outcomes", CASCADE
  procedure      FK CaseProcedure, CASCADE
  performed      BooleanField
  non_performance_reason       CharField choices FollowUpNonPerformanceReason ("" quando performed)
  resource_shortage_detail     CharField choices FollowUpResourceShortageDetail ("")
  other_reason                 TextField ("")
  UNIQUE (follow_up, procedure)
```

- `FollowUpNonPerformanceReason`: `absenteeism` (Absenteísmo), `resource_shortage` (Cancelamento por falta de recursos no dia), `other` (Outras causas).
- `FollowUpResourceShortageDetail`: `emergency_occupied` (Urgências que ocuparam o horário), `insufficient_time` (Falta de tempo hábil), `equipment_unavailable` (Equipamento quebrado/não disponível).
- **Versão atual** = maior `version` do caso. Atualizar = gravar nova versão; nada é editado/apagado (rastreabilidade de dados anteriores + autor por construção).
- Desfecho **por procedimento** (decisão do owner): EDA realizada + colonoscopia suspensa no mesmo ato é cenário real. Internação é **por caso** e o campo aparece **sempre** (paciente pode ser internado por causa da suspensão).
- Integridade condicional (motivo exigido quando não realizado; submotivo só em `resource_shortage`; texto só em `other`; campos zerados caso contrário) validada no service com `ValueError` amigável **e** respaldada por `CheckConstraint`s. O service também valida **valores** de `resource_shortage_detail` contra as choices e **rejeita combinações incompatíveis** (ex.: `absenteeism` com submotivo) com `ValueError` — o usuário nunca vê `IntegrityError`.

### D3. Auditoria unificada em `CaseEvent`

Cada gravação cria um evento direto (padrão dos services):

- `FOLLOWUP_RECORDED` (versão 1) / `FOLLOWUP_UPDATED` (versão ≥ 2), `actor_type="human"`, `actor=recorded_by`.
- `payload` snapshot: `{"version", "patient_admitted", "outcomes": [{procedure_id, procedure_type, performed, non_performance_reason, resource_shortage_detail, other_reason}]}`.
- NÃO adicionar os tipos a `OPERATIONAL_NOTICE_EVENT_TYPES`/`SUPPORTED_SYSTEM_NOTICE_EVENT_TYPES`: follow-up não gera mensagem operacional nem notificação.

### D4. Elegibilidade e listagem — por campos atuais do agendamento, não por status FSM

População elegível da aba (lição de `scheduler-processed-today-tab` D3), sempre via **campos atuais** do `Case` — que refletem reagendamentos: um caso reagendado aparece na data para a qual está agendado agora, não na data antiga (não há snapshot histórico de data; o histórico operacional da troca fica nos eventos de intercorrência):

- **Grupo agendado**: `appointment_status="confirmed"` AND `appointment_at IS NOT NULL` AND `localdate(appointment_at) == data`.
- **Grupo vinda imediata**: `doctor_admission_flow ∈ OPERATIONAL_NOTICE_FLOWS` AND `doctor_decided_at IS NOT NULL` AND `localdate(doctor_decided_at) == data`. **Sem fallback para `created_at`** (diferente da fila de ciência do scheduler, que exibe `doctor_decided_at or created_at`): caso operacional sem timestamp de decisão não existe no fluxo atual e, se existir, fica conservadoramente fora do follow-up.
- O predicado combinado vive em **`is_followup_eligible(case)`/queryset helper em `apps/cases/followup.py`**, usado pela listagem e **revalidado no GET e no POST do formulário** (acesso direto por URL a caso inelegível → 404 com mensagem; nunca expor formulário).
- Caso elegível sem rows `CaseProcedure` (defensivo; não deve ocorrer — decisão médica cria as rows): o service rejeita a gravação (`ValueError`) e o formulário exibe aviso orientando correção do caso, sem campos.
- **Default** (sem `?date=`): hoje + ontem locais, agrupados por data; **`?date=YYYY-MM-DD`**: somente a data informada; inválida → default.
- **Ordenação**: data asc, depois nome do paciente (annotate `KeyTextTransform("name", "structured_data__patient")`), depois horário.
- **Sem paginação** na visão diária (volume diário limitado); busca limitada a 50 resultados (padrão intake).
- **`?q=`**: busca por `agency_record_number__icontains` OU nome icontains sobre a **população elegível de qualquer data**, ignorando o filtro de data quando preenchida.
- Badge por caso: "Follow-up pendente" vs. "Follow-up registrado" (existência de `CaseFollowUp` atual).

### D5. Permissões e rotas

- `@login_required @role_required("manager", "admin")` nas duas views (padrão dashboard).
- `dashboard:followup_list` → `/dashboard/follow-ups/`; `dashboard:followup_form` → `/dashboard/follow-ups/cases/<uuid:case_id>/`.
- Pill "Follow-up" em `templates/dashboard/_nav.html`.
- Supervisor (`manager`) não está no `INTRANET_RESTRICTED_ROLES`: acessível via túnel, sem mudança no middleware.

### D6. Formulário

- `forms.Form` no `apps/dashboard/forms.py` (padrão do projeto, sem ModelForm): um subbloco por `CaseProcedure` do caso (prefixos `proc_<id>`), radios Bootstrap, internação (`patient_admitted`) no nível do caso.
- Validação server-side autoritativa (condicionais de D2). `static/js/followup_form.js` apenas mostra/esconde os campos condicionais — sem lógica de negócio no cliente.
- GET exibe: identificação do caso (ocorrência, paciente, data/hora ou fluxo de admissão), versão atual com autor/timestamp, histórico compacto de versões e o formulário para **nova** versão (rótulo explícito "Atualização cria nova versão").
- POST válido → `record_case_follow_up(...)` → `messages.success` → redirect para a lista. POST inválido → re-render com erros.

### D7. Timezone

Todo filtro por dia usa `timezone.localdate()`/`timezone.localtime` (`TIME_ZONE=America/Bahia`); nada de `date.today()`.

## Riscos / não-objetivos

- Dupla contagem cancelamentos (follow-up vs. intercorrência): aceita e desejada — dimensões distintas (registro de desfecho vs. ação operacional). Documentado no manual em change futuro.
- Casos `APPT_DENIED` (CHD recusou agendar) NÃO entram na aba: nunca houve procedimento marcado.
- `appointment_at`/`appointment_status` são alteráveis por reagendamento (`apps/cases/services.py`, fluxo de intercorrência): a listagem usa o valor vigente de propósito — o follow-up acompanha a data real do procedimento.

## Registro de review (ciclo 1 — reviewer independente, verdict BLOCK)

Correções incorporadas: (1) elegibilidade revalidada no GET/POST do formulário via `is_followup_eligible` (D4, spec, slices 002/003); (2) D4 reescrito — "campos atuais", fallback `created_at` explicitamente descartado, semântica de reagendamento documentada; (3) navegação entre slices — link do card para o formulário movido do Slice 002 para o Slice 003 (a rota só existe a partir de então); (4) service valida valores de choices e combinações incompatíveis com `ValueError` (implementado) — antes, `absenteeism` com submotivo vazaria como `IntegrityError`; (5) cobertura real das 6 CheckConstraints nos testes (um teste não era coletado por falta do prefixo `test_`); (6) cenários de spec para reagendamento, vinda imediata sem timestamp, combinação inválida de causa e acesso direto a inelegível.
