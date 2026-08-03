# Design: Agendar entrada pela Emergência Pediátrica antes do retorno ao NIR

## 1. Estado atual confirmado

A implementação atual classifica `pediatric_em` em `OPERATIONAL_NOTICE_FLOWS` (`apps/cases/admission.py`). Em `apps/doctor/views.py::doctor_submit`, todo aceite pertencente a esse conjunto:

1. registra `ADMISSION_FLOW_OPERATIONAL_NOTICE`;
2. chama `final_reply_posted()` diretamente a partir de `DOCTOR_ACCEPTED`;
3. termina em `WAIT_R1_CLEANUP_THUMBS`;
4. não chama `ready_for_scheduler()` nem `scheduler_request_posted()`.

O CHD recebe card separado de ciência operacional e o NIR recebe texto para acionar a EM Pediátrica, sem data/hora. A cobertura atual em `apps/doctor/tests/test_operational_admission_flows.py` confirma esse contrato.

## 2. Fluxo alvo

```text
WAIT_DOCTOR
  └─ médico aceita “Compartilhar com EM pediátrica — com agendamento”
      └─ DOCTOR_ACCEPTED
          └─ R3_POST_REQUEST
              └─ WAIT_APPT
                  ├─ CHD confirma
                  │   └─ APPT_CONFIRMED
                  │       └─ WAIT_R1_CLEANUP_THUMBS
                  │           └─ NIR vê via de entrada + data/hora
                  └─ CHD nega com motivo
                      └─ APPT_DENIED
                          └─ WAIT_R1_CLEANUP_THUMBS
                              └─ NIR vê motivo da negativa
```

Não haverá evento de ciência operacional para novas decisões. A presença na fila `WAIT_APPT` é a ação estruturada do CHD.

## 3. Decisões

### D1. Versionar o comportamento por novo código interno

Usar:

```text
pediatric_appt → nova decisão; exige agendamento
pediatric_em   → valor histórico; permanece ciência operacional
```

`pediatric_appt` possui 14 caracteres e cabe em `Case.doctor_admission_flow.max_length=15`.

Motivos para não reutilizar `pediatric_em` com nova semântica:

- casos históricos possuem o mesmo valor e eventos operacionais;
- simples remoção de `pediatric_em` de `OPERATIONAL_NOTICE_FLOWS` esconderia notices antigos sem ACK;
- resultados históricos poderiam aparecer como “Agendamento Confirmado” sem data;
- intercorrências históricas mudariam indevidamente de `operational_notice` para `scheduled`.

Não haverá migration nem backfill. O novo código começa a ser persistido somente por decisões realizadas após o deploy.

### D2. Separar choices novas de compatibilidade de display

A lista de choices do formulário médico deve expor `pediatric_appt`, não `pediatric_em`.

Representação conceitual:

```python
ADMISSION_FLOW_CHOICES = (
    ("", "---"),
    ("scheduled", "Agendamento"),
    ("immediate", "Vinda Imediata"),
    ("pre_icu", "Vinda prévia para UTI"),
    ("ward_icu_backup", "Vinda para enfermaria (para retaguarda em UTI)"),
    ("pediatric_appt", "Compartilhar com EM pediátrica — com agendamento"),
)

ADMISSION_FLOW_MAP = {
    # valores novos/atuais
    ...,
    "pediatric_appt": "Entrada pela Emergência Pediátrica",
    # compatibilidade histórica; não é choice nova
    "pediatric_em": "Compartilhar com EM pediátrica",
}
```

A implementação pode escolher nomes internos diferentes para maps auxiliares, mas deve preservar:

- `pediatric_em` legível em telas históricas;
- `pediatric_em` rejeitado como nova opção do `DoctorDecisionForm`;
- `pediatric_appt` apresentado de forma explícita como agendado/entrada pela EM Pediátrica.

### D3. Definir conjuntos semânticos compartilhados

Em `apps/cases/admission.py`, centralizar conceitos pequenos:

```python
SCHEDULED_ADMISSION_FLOWS = ("scheduled", "pediatric_appt")
OPERATIONAL_NOTICE_FLOWS = (
    "immediate",
    "pre_icu",
    "ward_icu_backup",
    "pediatric_em",  # compatibilidade histórica
)
```

E helper:

```python
def is_scheduled_admission_flow(flow: str | None) -> bool:
    return bool(flow) and flow in SCHEDULED_ADMISSION_FLOWS
```

`is_operational_notice_flow()` continua reconhecendo `pediatric_em` histórico e não reconhece `pediatric_appt`.

YAGNI: não criar classe, enum de banco, strategy pattern, tabela ou registry genérico para seis valores simples.

### D4. Roteamento médico usa semântica explícita

`doctor_submit` deve manter dois branches explícitos:

- aceite + `is_operational_notice_flow()` → notice + resultado direto ao NIR;
- aceite + `is_scheduled_admission_flow()` → `ready_for_scheduler()` + `scheduler_request_posted()`;
- negativa médica → resultado direto ao NIR.

Embora o formulário restrinja choices, o código não deve transformar silenciosamente valor desconhecido em agendamento. Valor inválido deve ser rejeitado pelo form, não cair em um `elif decision == "accept"` genérico.

Eventos esperados para `pediatric_appt`:

- `DOCTOR_ACCEPT`;
- `CASE_READY_FOR_SCHEDULER`;
- `SCHEDULER_REQUEST_POSTED`.

Evento proibido para nova decisão:

- `ADMISSION_FLOW_OPERATIONAL_NOTICE`.

### D5. Reutilizar integralmente o agendamento existente do CHD

A fila do CHD já seleciona todos os casos em `WAIT_APPT`; o formulário normal já exige data/hora para confirmação e motivo para negativa. Não criar endpoint, form ou transição nova.

A UI já exibe `admission_flow_display` na fila e na confirmação. O novo label deve deixar clara a entrada pela EM Pediátrica. Nenhum segundo card de ciência/ACK deve ser criado para `pediatric_appt`, evitando duplicidade de responsabilidade.

Confirmação preserva:

- lock `scheduler_confirm`;
- `appointment_status="confirmed"`;
- `appointment_at`;
- `APPT_CONFIRMED`;
- `FINAL_REPLY_POSTED`.

Negativa preserva:

- motivo obrigatório;
- `appointment_status="denied"`;
- `appointment_reason`;
- `APPT_DENIED`;
- `FINAL_REPLY_POSTED`.

### D6. Resultado NIR deve tornar as duas informações inequívocas

No resultado confirmado, não basta depender do texto “Compartilhar”. Para `case.doctor_admission_flow == "pediatric_appt"`, detalhe ativo e histórico devem apresentar:

- badge normal `Agendamento Confirmado`;
- `Data/Hora`;
- linha explícita `Via de entrada: Emergência Pediátrica` ou texto semanticamente equivalente;
- orientação de que o NIR comunicará a Emergência Pediátrica sobre a chegada da criança.

O detalhe ativo já apresenta `result_info.flow`; o histórico precisa manter essa informação e a orientação explícita. Preferir condição simples baseada no código no template em vez de criar framework genérico de copy.

Na negativa, reutilizar o branch normal `appt_denied`, exibindo `appointment_reason`. A via de entrada planejada não deve esconder o desfecho de negativa.

### D7. Modal médico deve reconhecer ambos os fluxos agendados

`static/js/decision.js` hoje considera somente `flowValue === "scheduled"` como agendado. Deve reconhecer `pediatric_appt` e informar encaminhamento ao CHD/agendamento.

Evitar duplicar lista JS desconectada se uma solução simples por atributo HTML existente for menor; contudo, não ampliar o slice para criar framework de configuração. Teste/inspeção deve impedir que `pediatric_appt` receba a mensagem “apenas ciência operacional”.

### D8. Lifecycle pós-aceitação usa conjunto agendado

Em `apps/cases/services.py`:

- elegibilidade `scheduled` deve aceitar `doctor_admission_flow in SCHEDULED_ADMISSION_FLOWS` com `appointment_status="confirmed"`;
- elegibilidade `operational_notice` continua baseada em `OPERATIONAL_NOTICE_FLOWS`;
- mensagens de inelegibilidade devem usar a mesma regra.

Consequência:

- `pediatric_appt` confirmado e `CLEANED` pode abrir intercorrência agendada, reentrando em `WAIT_APPT`;
- `pediatric_em` histórico permanece intercorrência operacional, sem mutar `appointment_*`.

`apps/intake/views.py` deve usar o helper compartilhado ao escolher/explicar contexto, sem igualdade dispersa com `"scheduled"`.

### D9. Histórico CHD reconhece todos os fluxos agendados

`apps/scheduler/views.py::_is_scheduler_historical_case()` e `_scheduler_historical_queryset()` devem aceitar `SCHEDULED_ADMISSION_FLOWS`, mantendo os demais critérios de `doctor_decision` e `appointment_status`.

Isso inclui `pediatric_appt` confirmado/negado/cancelado e continua excluindo `pediatric_em` histórico operacional.

Não alterar permissões, decorators, rotas nem política de acesso por notificação.

### D10. Dashboard consolida categoria e próximo responsável

- `_compute_next_step()` deve considerar `pediatric_appt` em `WAIT_APPT` como `Pendente: agendador`.
- `_compute_admission_flow()` deve manter a chave visual existente `pediatric_em`, somando casos cujo valor seja `pediatric_em` ou `pediatric_appt`.
- A soma deve ser por queryset com `__in`, sem somar queries sobrepostas e sem dupla contagem.
- O template do dashboard pode permanecer inalterado se a chave/label pública for preservada.

### D11. Compatibilidade histórica é requisito testado

Casos `pediatric_em` existentes devem continuar:

- aparecendo em `unacknowledged_operational_notice_qs()` quando houver notice sem ACK;
- aceitando ACK operacional existente;
- recebendo resultado NIR operacional sem data obrigatória;
- usando `operational_notice` em intercorrência pós-aceitação;
- fora do histórico de agendamentos do CHD.

Não alterar eventos históricos nem inferir que ausência de data é erro.

### D12. Auditoria, FSM, schema e permissões permanecem

Não alterar:

- `apps/cases/models.py`;
- migrations;
- estados/transições FSM;
- formulários do scheduler;
- decorators de papel;
- lock services;
- pipeline LLM;
- eventos append-only existentes.

O change muda a rota escolhida entre transições já existentes.

## 4. Arquivos previstos por slice

### Slice 001 — fluxo principal completo

Idealmente 7 arquivos:

1. `apps/cases/admission.py`
2. `apps/doctor/views.py`
3. `templates/doctor/decision.html` (o select atual possui options explícitas)
4. `static/js/decision.js`
5. `templates/intake/case_detail.html`
6. `templates/intake/closed_case_detail.html`
7. `apps/doctor/tests/test_pediatric_em_scheduling.py` (novo teste integrado e focado)

Não é esperado alterar scheduler: fila, form, submit e FSM atuais já suportam qualquer caso em `WAIT_APPT`.

### Slice 002 — lifecycle e projeções

Máximo esperado de 7 arquivos, justificado pela continuidade cross-app e documentação final:

1. `apps/cases/services.py`
2. `apps/intake/views.py`
3. `apps/scheduler/views.py`
4. `apps/dashboard/views.py`
5. `apps/cases/tests/test_pediatric_em_scheduled_downstream.py` (novo)
6. `docs/manual/manual-usuarios.md`
7. `PROJECT_CONTEXT.md`

Não criar um terceiro slice horizontal apenas para documentação.

## 5. Estratégia TDD

### Slice 001

Teste integrado deve provar, no mínimo:

1. choice nova usa `pediatric_appt` e POST manual de `pediatric_em` é inválido;
2. médico aceita → `WAIT_APPT`, eventos de scheduler presentes, notice operacional ausente;
3. fila CHD mostra fluxo pediátrico agendado;
4. CHD confirma → data/hora persistida → NIR vê data/hora + entrada EM Pediátrica;
5. detalhe histórico NIR preserva ambas as informações;
6. CHD nega → NIR vê motivo;
7. caso histórico `pediatric_em` continua operacional.

### Slice 002

Teste focado deve provar:

1. novo caso confirmado é elegível para contexto `scheduled` e reabre `WAIT_APPT`;
2. legado `pediatric_em` continua elegível para `operational_notice` e imutável em `appointment_*`;
3. histórico CHD inclui `pediatric_appt` e exclui legado operacional;
4. dashboard aponta agendador para `pediatric_appt` em `WAIT_APPT`;
5. métrica consolida valores antigo/novo sem dupla contagem.

## 6. Deploy e rollback

### Deploy

- Deploy único de código; sem migration.
- Novos valores `pediatric_appt` passam a existir somente após novas decisões médicas.
- Monitorar fila `WAIT_APPT`, eventos `SCHEDULER_REQUEST_POSTED`, confirmações/negativas e resultados NIR pediátricos.

### Rollback

- Antes da primeira decisão `pediatric_appt`, rollback de código é direto.
- Depois de persistir `pediatric_appt`, não fazer rollback cego para versão que desconheça o código.
- Em rollback pós-uso, manter patch de compatibilidade de leitura/roteamento para `pediatric_appt` até os casos em andamento serem concluídos, ou concluir operacionalmente os casos antes da reversão.
- Não converter `pediatric_appt` de volta para `pediatric_em`, pois isso apagaria a distinção auditável entre agendado e operacional.

## 7. Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Quebrar notices pediátricos históricos | Manter `pediatric_em` em `OPERATIONAL_NOTICE_FLOWS` e testar ACK legado |
| Novo caso receber ciência e agendamento duplicados | `pediatric_appt` fora de fluxos operacionais; assert de ausência do evento |
| NIR receber data sem saber a via de entrada | Copy explícita no detalhe ativo e histórico |
| NIR receber resultado antes do CHD | Teste de estado `WAIT_APPT` e ausência de confirmação final |
| Intercorrência nova cair como operacional | Helper compartilhado de fluxos agendados em services/intake |
| Dashboard atribuir WAIT_APPT ao NIR | `_compute_next_step()` usa conjunto agendado |
| Métricas dividirem uma categoria funcional | Consolidar antigo/novo sob a chave pública existente |
| Refactor amplo por generalização precoce | Helpers/tuplas pequenos; DRY e YAGNI; proibir registry/framework |
