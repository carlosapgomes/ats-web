# Design: Fluxos de aceite médico com ciência operacional do CHD

## Estado atual

### Decisão médica

O formulário médico (`templates/doctor/decision.html` + `apps/doctor/forms.py`) exibe, após `Aceitar`:

```text
Suporte Necessário:
- Nenhum
- Anestesista
- Anestesista + UTI

Fluxo de Admissão:
- Agendamento
- Vinda Imediata
```

No submit (`apps/doctor/views.py::doctor_submit`):

- `accept + scheduled` → `DOCTOR_ACCEPTED → R3_POST_REQUEST → WAIT_APPT`;
- `accept + immediate` → registra ciência operacional para CHD, posta resultado final para NIR e vai para `WAIT_R1_CLEANUP_THUMBS` sem abrir agendamento;
- `deny` → resultado final para NIR.

### CHD/agendador

A fila do CHD (`apps/scheduler/views.py::_scheduler_queue_context`) mostra:

- casos `WAIT_APPT` para agendamento;
- seção separada de `Vinda imediata autorizada — ciência operacional`, filtrada por `doctor_admission_flow="immediate"` e evento `IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE`.

O botão `Confirmar ciência` cria evento `SCHEDULER_IMMEDIATE_ACK` e remove o card da fila ativa.

### NIR/dashboard

NIR e dashboard tratam `doctor_admission_flow == "immediate"` como fluxo terminal sem agendamento. As métricas de fluxo contam apenas:

```python
scheduled
immediate
```

## Decisões

### D1. Suporte final escolhido pelo médico terá apenas dois valores novos válidos

Opções no formulário e no backend:

```text
none         → Nenhum
anesthesist  → Anestesista
```

`anesthesist_icu` deve continuar existindo apenas como valor histórico/de exibição, porque casos antigos e recomendações automáticas podem conter esse valor.

Regras:

- remover `Anestesista + UTI` do `<select>` médico;
- remover `anesthesist_icu` das choices válidas de `DoctorDecisionForm.support_flag`;
- manter `SUPPORT_FLAG_MAP["anesthesist_icu"] = "Anestesista + UTI"` nos displays downstream;
- não criar migration;
- não migrar dados históricos.

Motivo: a atribuição de reserva de UTI é do NIR, não do CHD.

### D2. Fluxo de admissão terá cinco valores estruturados

Valores internos propostos, respeitando `Case.doctor_admission_flow.max_length=15`:

```text
scheduled        → Agendamento
immediate        → Vinda Imediata
pre_icu          → Vinda prévia para UTI
ward_icu_backup  → Vinda para enfermaria (para retaguarda em UTI)
pediatric_em     → Compartilhar com EM pediátrica
```

Observação: `ward_icu_backup` tem exatamente 15 caracteres.

### D3. Só `scheduled` abre fila de agendamento

Definir helper conceitual:

```python
SCHEDULED_ADMISSION_FLOW = "scheduled"
OPERATIONAL_NOTICE_FLOWS = {
    "immediate",
    "pre_icu",
    "ward_icu_backup",
    "pediatric_em",
}
```

Roteamento no submit médico:

- se `decision == "accept" and admission_flow == "scheduled"`:
  - manter fluxo atual para `WAIT_APPT`;
- se `decision == "accept" and admission_flow in OPERATIONAL_NOTICE_FLOWS`:
  - não chamar `ready_for_scheduler()`;
  - registrar evento de ciência operacional;
  - chamar `final_reply_posted()`;
  - levar o caso para `WAIT_R1_CLEANUP_THUMBS`.

### D4. Eventos de ciência operacional devem ser genericamente nomeados daqui em diante

Criar eventos novos para os novos fluxos e para futuras vindas imediatas:

```text
ADMISSION_FLOW_OPERATIONAL_NOTICE
SCHEDULER_OPERATIONAL_NOTICE_ACK
```

Payload mínimo do notice:

```json
{
  "support_flag": "anesthesist",
  "admission_flow": "pre_icu"
}
```

Payload mínimo do ack:

```json
{
  "admission_flow": "pre_icu"
}
```

Compatibilidade:

- consultas de fila/histórico devem reconhecer também eventos legados:
  - `IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE`;
  - `SCHEDULER_IMMEDIATE_ACK`.
- labels de timeline devem ser adicionados para os novos eventos.

Motivo: evita perpetuar o termo “vinda imediata” para fluxos que não são vinda imediata.

### D5. Mensagens específicas por fluxo

Criar mapeamento de apresentação para mensagens do CHD e do NIR, idealmente perto dos maps de fluxo usados nas views.

Proposta de conteúdo:

```python
ADMISSION_FLOW_NOTICE_COPY = {
    "immediate": {
        "scheduler_title": "⚡ Vinda imediata autorizada — ciência operacional",
        "scheduler_body": "Não abrir agendamento para este caso. Comunicação apenas para ciência operacional.",
        "nir_badge": "✓ Vinda Imediata Autorizada",
        "nir_body": "Caso aceito para vinda imediata. Não abrir agendamento para este caso.",
    },
    "pre_icu": {
        "scheduler_title": "🏥 Vinda prévia para UTI — ciência operacional",
        "scheduler_body": "Não abrir agendamento para este caso. O NIR providenciará a reserva de UTI antes de qualquer ação do CHD.",
        "nir_badge": "✓ Vinda prévia para UTI",
        "nir_body": "Caso aceito para vinda prévia para UTI. Providenciar reserva de UTI antes de acionar o CHD.",
    },
    "ward_icu_backup": {
        "scheduler_title": "🏥 Enfermaria com retaguarda em UTI — ciência operacional",
        "scheduler_body": "Não abrir agendamento para este caso. O NIR providenciará leito de enfermaria e retaguarda em UTI antes de qualquer ação do CHD.",
        "nir_badge": "✓ Vinda para enfermaria com retaguarda em UTI",
        "nir_body": "Caso aceito para vinda para enfermaria com retaguarda em UTI. Providenciar leito/enfermaria e retaguarda em UTI conforme fluxo institucional.",
    },
    "pediatric_em": {
        "scheduler_title": "👶 Compartilhar com EM pediátrica — ciência operacional",
        "scheduler_body": "Não abrir agendamento para este caso. O NIR acionará o coordenador da EM Pediátrica; comunicação ao CHD é apenas para ciência operacional.",
        "nir_badge": "✓ Compartilhar com EM pediátrica",
        "nir_body": "Caso aceito para compartilhamento com EM pediátrica. Acionar o coordenador da EM Pediátrica; não há integração desta equipe no sistema.",
    },
}
```

Os textos podem ser refinados no slice, mas o comportamento deve ser esse.

### D6. Modal de confirmação médica deve refletir o fluxo selecionado

`static/js/decision.js::showFinalConfirmModal()` hoje mostra, para qualquer aceite:

```text
O caso será encaminhado automaticamente para agendamento.
```

Isso já é impreciso para `Vinda Imediata` e ficará mais errado com os novos fluxos.

Novo comportamento:

- se fluxo `scheduled`: “O caso será encaminhado automaticamente para o CHD/agendamento.”
- se fluxo não agendamento: “O CHD receberá apenas ciência operacional. O NIR dará seguimento ao fluxo escolhido.”

### D7. Fila ativa do CHD deve agrupar todos os fluxos de ciência operacional

Substituir a lógica exclusiva de `immediate_notice_qs` por consulta de notices operacionais:

- `doctor_admission_flow in OPERATIONAL_NOTICE_FLOWS`;
- evento de notice presente (`ADMISSION_FLOW_OPERATIONAL_NOTICE` ou legado imediato);
- sem ack (`SCHEDULER_OPERATIONAL_NOTICE_ACK` ou legado imediato);
- não `WAIT_APPT`.

A seção pode ter título geral:

```text
Ciência operacional — fluxos sem agendamento
```

Cada card deve mostrar seu título/mensagem específica por fluxo.

Botão permanece:

```text
Confirmar ciência
```

### D8. Histórico CHD de ciências operacionais

Como o CHD pode precisar saber quem confirmou ciência, adicionar histórico visível para o papel `scheduler`.

Design proposto para slice enxuto:

- aproveitar a tela/fila do CHD e incluir histórico na aba `Processados Hoje`, se ela existir no branch ativo;
- caso a aba ainda não esteja disponível no momento da implementação, adicionar uma seção simples “Ciências operacionais confirmadas hoje” abaixo/ao lado dos processados hoje;
- escopo do histórico: **equipe CHD no dia local atual**, não apenas o usuário logado;
- exibir:
  - paciente;
  - registro;
  - fluxo;
  - suporte;
  - médico responsável;
  - usuário CHD que confirmou ciência;
  - data/hora da ciência;
  - orientação médica, se houver.

Motivo da escolha team-wide: o requisito informado foi saber “quem da equipe deu a ciência”.

Fora do primeiro slice:

- busca multi-dia;
- paginação;
- exportação;
- detalhe histórico dedicado.

### D9. NIR deve enxergar resultado final específico por fluxo

Em `apps/intake/views.py` e templates de detalhe/encerrados:

- `immediate` mantém o texto atual;
- `pre_icu`, `ward_icu_backup`, `pediatric_em` usam badge/body específicos;
- todos esses fluxos continuam como resultado terminal sem etapa de agendamento.

Implementação sugerida:

- substituir checagens diretas `case.doctor_admission_flow == "immediate"` por helper `is_operational_notice_flow(flow)` onde a semântica for “sem agendamento”; 
- manter o nome visual do fluxo nos blocos de resultado.

### D10. Dashboard deve mostrar fluxos separados

`apps/dashboard/views.py::_compute_admission_flow()` deve retornar contagens para todos os fluxos:

```python
{
    "scheduled": ...,
    "immediate": ...,
    "pre_icu": ...,
    "ward_icu_backup": ...,
    "pediatric_em": ...,
}
```

`templates/dashboard/index.html` deve renderizar os cinco labels separados.

Também ajustar badges/status de caso para que os novos fluxos sem agendamento não apareçam como “Aguardando Agendamento”.

### D11. Recomendações automáticas podem continuar com `anesthesist_icu`

Não alterar neste change:

- schema LLM2;
- policy deterministic synthesis;
- presenter do relatório médico;
- prompts.

Racional: a recomendação automática pode apontar risco/necessidade clínica, mas o médico decide o suporte operacional final nos dois menus. A remoção é da escolha final de suporte CHD, não da análise clínica sugerida.

### D12. Compatibilidade e dados históricos

- Casos históricos com `doctor_support_flag="anesthesist_icu"` continuam exibindo “Anestesista + UTI”.
- Casos históricos com `doctor_admission_flow="immediate"` e eventos legados continuam aparecendo/funcionando até ack.
- Não haverá backfill.
- Não haverá migration.

## Slice vertical recomendado

### Slice 001 — Aceite médico + ciência operacional + resultado NIR + dashboard

Vertical end-to-end, tocando o mínimo necessário:

1. Form médico e validação.
2. Submit médico roteando novos fluxos.
3. Fila ativa CHD com notices operacionais e ack genérico.
4. Histórico simples de ciências operacionais de hoje para CHD.
5. Resultado NIR específico.
6. Dashboard com fluxos separados.
7. Testes cobrindo o fluxo completo.

## Testes esperados

### Médico

- Form não contém `anesthesist_icu` como choice válida.
- Template não renderiza `Anestesista + UTI` no select de suporte.
- Form aceita `scheduled`, `immediate`, `pre_icu`, `ward_icu_backup`, `pediatric_em`.
- POST com `support_flag=anesthesist_icu` é inválido.
- `accept + scheduled` continua em `WAIT_APPT`.
- `accept + pre_icu/ward_icu_backup/pediatric_em` vai para `WAIT_R1_CLEANUP_THUMBS`, cria notice operacional e não cria `SCHEDULER_REQUEST_POSTED`.

### CHD

- Fila ativa mostra card de ciência para cada fluxo não agendamento.
- Cada card mostra mensagem específica.
- Ack remove card ativo.
- Ack cria evento com ator.
- Histórico de ciências do dia mostra quem confirmou.
- Badge/count do CHD soma notices operacionais não confirmados.

### NIR

- Detalhe operacional mostra badge/body específico para cada fluxo não agendamento.
- Stepper remove etapa de agendamento para todos os fluxos sem agendamento.
- Casos encerrados preservam mensagem específica.

### Dashboard

- Métrica de fluxo mostra cinco contagens separadas.
- Novos fluxos sem agendamento recebem badge/status final adequado, não “Aguardando Agendamento”.

## Riscos e mitigação

### R1. Duplicação de maps de fluxo

Hoje `SUPPORT_FLAG_MAP` e `ADMISSION_FLOW_MAP` aparecem em múltiplos apps. O slice pode centralizar em um helper compartilhado se isso reduzir risco, mas deve evitar refactor amplo.

Mitigação enxuta: criar constantes/helpers em `apps/cases` apenas se a substituição local ficar menor que repetir maps.

### R2. Eventos legados de vinda imediata

Há testes e dados usando eventos antigos.

Mitigação: queries de notice/ack devem aceitar eventos novos e antigos.

### R3. Histórico CHD pode crescer

No primeiro slice, limitar histórico ao dia local atual. Histórico multi-dia fica fora de escopo.

### R4. Dashboard e resumo periódico podem divergir

O requisito confirmado é dashboard com fluxos separados. O modelo `SupervisorSummary.immediate_admission` pode permanecer como métrica legada no primeiro slice, salvo se testes evidenciarem quebra.

## Pontos assumidos

1. Histórico de ciência operacional do CHD será visível para a equipe CHD no dia local atual, não apenas para o usuário que confirmou.
2. O coordenador da EM Pediátrica é acionado pelo NIR fora do sistema.
3. Nenhum fluxo novo deve abrir `WAIT_APPT` automaticamente.
