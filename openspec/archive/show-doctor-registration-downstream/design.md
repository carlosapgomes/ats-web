# Design: Exibir médico responsável e CRM downstream

## Estado atual

O modelo `Case` já possui:

```python
doctor = models.ForeignKey(settings.AUTH_USER_MODEL, ... related_name="cases_decided")
doctor_decision = models.CharField(max_length=10, blank=True)
doctor_admission_flow = models.CharField(max_length=15, blank=True)
doctor_reason = models.TextField(blank=True)
doctor_decided_at = models.DateTimeField(null=True, blank=True)
```

A view `apps/doctor/views.py::doctor_submit` já faz:

```python
case.doctor = request.user
case.doctor_decided_at = timezone.now()
```

Portanto, este change é majoritariamente de apresentação e helpers, sem migration.

## Decisões

### D1: Não duplicar dados no `Case`

Não criar campos como `doctor_name_snapshot` ou `doctor_crm_snapshot` neste momento. Usar `Case.doctor` e os campos atuais do usuário.

Justificativa:

- requisito é UI downstream em projeto greenfield;
- `Case.doctor` já é a fonte canônica de quem decidiu;
- evita redundância e migration.

### D2: Padronizar display em properties

Adicionar helpers/properties para evitar lógica duplicada em templates.

Opção recomendada:

Em `apps/accounts/models.py`:

```python
@property
def display_name(self) -> str:
    return self.get_full_name() or self.username

@property
def professional_registration_display(self) -> str:
    if self.professional_council and self.professional_council_number:
        return f"{self.professional_council} {self.professional_council_number}"
    return ""
```

Em `apps/cases/models.py`:

```python
@property
def doctor_display(self) -> str:
    if not self.doctor:
        return ""
    registration = self.doctor.professional_registration_display
    if registration:
        return f"{self.doctor.display_name} — {registration}"
    return self.doctor.display_name
```

### D3: Fallback sem CRM

Mesmo se o médico não tiver `professional_council` e `professional_council_number`, exibir o nome.

Exemplos:

```text
Dra. Maria Silva — CRM 12345
Dr. João Souza
```

### D4: Templates alvo

#### NIR

- `templates/intake/_my_cases_content.html`
  - no card, próximo da decisão médica.

- `templates/intake/case_detail.html`
  - no bloco “Resultado Final” para:
    - `accepted_immediate`;
    - `accepted_scheduled`;
    - `doctor_denied`;
    - `appt_denied` também deve mostrar o médico que autorizou originalmente, se existir.

#### Agendador

- `templates/scheduler/_queue_content.html`
  - cards de `pending_cases`;
  - cards de `immediate_notice_cases`.

- `templates/scheduler/confirm.html`
  - card “Decisão Médica”.

### D5: Query performance

Usar `select_related("doctor")` nas queries de intake/scheduler quando o template/contexto acessar o médico.

Locais prováveis:

- `apps/intake/views.py::_my_cases_context`
- `apps/intake/views.py::case_detail`
- `apps/scheduler/views.py::_scheduler_queue_context`
- `apps/scheduler/views.py::scheduler_confirm` / `_build_confirm_context` via objeto já carregado, se adequado.

## Arquivos previstos

| Arquivo | Tipo | Alteração |
|---|---|---|
| `apps/accounts/models.py` | modificado | helpers de display do usuário |
| `apps/cases/models.py` | modificado | `Case.doctor_display` |
| `apps/accounts/tests/test_models.py` | modificado | testes dos helpers do usuário |
| `apps/cases/tests/test_models.py` ou equivalente | modificado/novo | teste do display no Case |
| `apps/intake/views.py` | modificado | passar/usar médico no contexto e otimizar query |
| `templates/intake/_my_cases_content.html` | modificado | exibir médico no card |
| `templates/intake/case_detail.html` | modificado | exibir médico no resultado final |
| `apps/intake/tests/test_my_cases.py` | modificado | assert no card |
| `apps/intake/tests/test_case_detail.py` | modificado | assert no detalhe |
| `apps/scheduler/views.py` | modificado | incluir médico em cards/contexto e otimizar query |
| `templates/scheduler/_queue_content.html` | modificado | exibir médico na fila e vinda imediata |
| `templates/scheduler/confirm.html` | modificado | exibir médico na decisão médica |
| `apps/scheduler/tests/test_views.py` | modificado | asserts downstream |

## Riscos

- Templates ficarem carregados visualmente: mitigar com label compacto `Médico` em `case-meta` ou `summary-box`.
- N+1 queries: mitigar com `select_related("doctor")`.
- Testes frágeis por caractere `—`: nos testes, preferir assert de nome e `CRM 12345` separadamente, exceto quando validar display completo.