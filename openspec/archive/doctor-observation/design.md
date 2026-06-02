# Design: Observação médica opcional no caso

## Estado atual

O modelo `apps.cases.models.Case` já possui campos relacionados à decisão médica:

```python
doctor = models.ForeignKey(...)
doctor_decision = models.CharField(max_length=10, blank=True)
doctor_support_flag = models.CharField(max_length=20, blank=True, default="none")
doctor_admission_flow = models.CharField(max_length=15, blank=True)
doctor_reason = models.TextField(blank=True)
doctor_decided_at = models.DateTimeField(null=True, blank=True)
```

A decisão é submetida em `apps/doctor/views.py::doctor_submit`, validada por `apps/doctor/forms.py::DoctorDecisionForm`, e renderizada em `templates/doctor/decision.html`.

O campo `doctor_reason` é usado como motivo de negativa e deve continuar com essa semântica.

## Decisões

### D1: Criar campo dedicado no `Case`

Adicionar campo novo:

```python
doctor_observation = models.CharField(max_length=500, blank=True)
```

Justificativa:

- preserva separação semântica entre motivo de negativa e observação opcional;
- `blank=True` mantém compatibilidade com casos existentes;
- `max_length=500` impõe limite real no banco e no form;
- 500 caracteres são suficientes para observação operacional sem degradar UI.

### D2: Não alterar FSM

A observação é metadado da decisão médica, não um novo estado. Não criar transições novas nem alterar os 17 estados.

### D3: Persistir junto com a decisão médica

Em `doctor_submit`, após `form.is_valid()` e antes da transição FSM, salvar:

```python
case.doctor_observation = form.cleaned_data.get("observation", "")
```

### D4: Auditoria mínima por evento existente

Não criar novo evento `DOCTOR_OBSERVATION_ADDED` neste change. A observação faz parte da submissão da decisão médica.

Opcional dentro do slice 001, se couber sem ampliar escopo: incluir no payload do evento `DOCTOR_ACCEPT`/`DOCTOR_DENY` apenas indicador booleano:

```python
{"decision": decision, "has_doctor_observation": bool(self.doctor_observation.strip())}
```

Não duplicar o texto completo no `CaseEvent` nesta mudança inicial. Se futuramente houver exigência legal de snapshot imutável do texto no evento, abrir change separado.

### D5: Helper opcional para evitar repetição

Pode ser útil adicionar property no `Case`:

```python
@property
def has_doctor_observation(self) -> bool:
    return bool(self.doctor_observation.strip())
```

Use apenas se simplificar views/templates e testes. Não é obrigatório.

### D6: Visibilidade downstream

#### NIR

- Listagem/cards: `templates/intake/_my_cases_content.html` deve exibir badge se houver observação.
- Detalhe: `templates/intake/case_detail.html` deve exibir bloco com o texto completo.

#### Manager/admin

A view `apps/dashboard/views.py::dashboard_case_detail` renderiza o mesmo template `templates/intake/case_detail.html`. Portanto, ao adicionar o bloco nesse template, manager/admin também passam a visualizar a observação.

#### Agendador

- Fila: `templates/scheduler/_queue_content.html` deve exibir badge nos cards `pending_cases` e `immediate_notice_cases`.
- Tela de confirmação: `templates/scheduler/confirm.html` deve exibir o texto completo, idealmente no card “Decisão Médica”.

### D7: Slices verticais enxutos

Para evitar um slice grande demais, dividir em três entregas verticais:

1. **Slice 001 — Captura e persistência médica**  
   Médico vê campo opcional, valida limite e persiste observação no `Case`.

2. **Slice 002 — Visibilidade NIR + supervisor/admin**  
   NIR vê badge na listagem e texto no detalhe; manager/admin veem texto no detalhe compartilhado.

3. **Slice 003 — Visibilidade agendador**  
   Agendador vê badge na fila e texto na tela de confirmação/ciência operacional.

## Arquivos previstos por slice

### Slice 001

- `apps/cases/models.py`
- nova migration em `apps/cases/migrations/`
- `apps/doctor/forms.py`
- `apps/doctor/views.py`
- `templates/doctor/decision.html`
- testes de model/form/view do médico

### Slice 002

- `apps/intake/views.py`
- `templates/intake/_my_cases_content.html`
- `templates/intake/case_detail.html`
- `apps/dashboard/views.py` somente se testes demonstrarem que o template compartilhado não basta
- testes de `apps/intake/tests/test_my_cases.py`, `apps/intake/tests/test_case_detail.py` e/ou `apps/dashboard/tests/test_dashboard.py`

### Slice 003

- `apps/scheduler/views.py`
- `templates/scheduler/_queue_content.html`
- `templates/scheduler/confirm.html`
- testes de `apps/scheduler/tests/`

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| UI ficar poluída | Limite de 500 caracteres, textarea de 2-3 linhas, badges discretas |
| Confundir motivo de negativa com observação | Campo novo `doctor_observation`, sem reutilizar `doctor_reason` |
| Casos antigos quebrarem | Campo opcional `blank=True`, migration sem default obrigatório |
| Slice tocar muitos arquivos | Divisão em 3 slices verticais focados |
| Testes frágeis por HTML | Assert por textos essenciais: label, badge, conteúdo da observação |

## Rollback

Se necessário:

1. Reverter templates/views/forms.
2. Reverter migration removendo o campo `doctor_observation`.
3. Como o campo é opcional e não altera FSM, rollback funcional é simples.

Em produção com dados reais, antes de remover coluna, exportar observações se houver exigência operacional.
