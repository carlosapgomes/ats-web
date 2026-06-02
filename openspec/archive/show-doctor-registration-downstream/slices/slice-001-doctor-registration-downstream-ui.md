# Slice 001: Exibir médico responsável/CRM para NIR e Agendador

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`, um monolito Django 5.2 SSR com templates Bootstrap e sem API REST/SPA.

Antes de codar, leia obrigatoriamente:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/show-doctor-registration-downstream/proposal.md`
4. `openspec/changes/show-doctor-registration-downstream/design.md`
5. Este arquivo de slice

Implemente **somente este slice**. Não inicie outro slice. Use TDD: RED → GREEN → REFACTOR.

## Contexto de domínio

Quando o médico decide um caso, a decisão pode seguir três caminhos principais:

1. **Recusa médica**: médico nega o caso; NIR recebe resultado final.
2. **Aceite com vinda imediata**: médico aceita e define fluxo `immediate`; agendador recebe aviso apenas para ciência operacional; NIR recebe resultado final.
3. **Aceite com agendamento**: médico aceita e define fluxo `scheduled`; agendador confirma ou nega agendamento; NIR acompanha o resultado.

Em todos esses fluxos, NIR e agendador devem ver claramente **qual médico tomou a decisão**, com nome e CRM quando cadastrado.

Exemplos esperados:

```text
Médico: Dra. Maria Silva — CRM 12345
Médico: Dr. João Souza
```

O CRM é facultativo. Se o médico não tiver CRM/conselho cadastrado, exibir o nome mesmo assim.

## Estado técnico atual

O modelo `Case` já possui `doctor`:

```python
doctor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="cases_decided", ...)
```

A view `apps/doctor/views.py::doctor_submit` já preenche:

```python
case.doctor = request.user
case.doctor_decided_at = timezone.now()
```

O usuário já possui campos opcionais:

```python
professional_council
professional_council_number
```

com choices `COREN` e `CRM`.

Portanto, **não crie migration** e **não altere persistência da decisão médica**, salvo se encontrar bug real.

## Objetivo do slice

Exibir o médico responsável e seu CRM/conselho nos pontos downstream:

### NIR

1. Cards/listagem de “Meus Casos”.
2. Detalhe do caso, no bloco de resultado final.

### Agendador

3. Fila de agendamento para casos aceitos com fluxo `scheduled`.
4. Cards de vinda imediata para ciência operacional.
5. Tela de confirmação de agendamento.

## Arquivos prováveis

Mantenha o slice enxuto. Arquivos previstos:

1. `apps/accounts/models.py`
2. `apps/accounts/tests/test_models.py`
3. `apps/cases/models.py`
4. `apps/cases/tests/test_models.py` ou outro arquivo de teste de models existente
5. `apps/intake/views.py`
6. `templates/intake/_my_cases_content.html`
7. `templates/intake/case_detail.html`
8. `apps/intake/tests/test_my_cases.py`
9. `apps/intake/tests/test_case_detail.py`
10. `apps/scheduler/views.py`
11. `templates/scheduler/_queue_content.html`
12. `templates/scheduler/confirm.html`
13. `apps/scheduler/tests/test_views.py`
14. `openspec/changes/show-doctor-registration-downstream/tasks.md`

Se tocar mais arquivos, justifique no relatório.

## Plano TDD sugerido

### RED — testes primeiro

Adicione testes que falhem antes da implementação.

#### 1. Helpers de display

Em `apps/accounts/tests/test_models.py`:

- `User.display_name` usa `get_full_name()` quando first/last name existem;
- `User.display_name` cai para `username` quando nome completo está vazio;
- `User.professional_registration_display` retorna `CRM 12345` quando conselho e número existem;
- `User.professional_registration_display` retorna `""` quando não há conselho/número.

Em teste de `Case` model, por exemplo `apps/cases/tests/test_models.py` se existir, ou crie um teste coeso no app cases:

- `case.doctor_display` retorna `Nome — CRM 12345` quando médico tem registro;
- `case.doctor_display` retorna `Nome` quando médico não tem registro;
- `case.doctor_display` retorna `""` quando `case.doctor is None`.

#### 2. NIR — cards/listagem

Em `apps/intake/tests/test_my_cases.py`:

- criar caso do NIR com `doctor` preenchido, `doctor_decision="accept"`, médico com `first_name`, `last_name`, `professional_council="CRM"`, `professional_council_number="12345"`;
- acessar `intake:my_cases` como NIR;
- assert que aparecem nome do médico e `CRM 12345` no card.

Também testar fallback sem CRM, se possível:

- médico sem registro profissional;
- assert que aparece o nome do médico.

#### 3. NIR — detalhe do caso

Em `apps/intake/tests/test_case_detail.py`:

Cobrir pelo menos dois caminhos:

- recusa médica (`doctor_decision="deny"`, status final/compatível com detalhe) mostra médico e CRM no resultado final;
- aceite com vinda imediata ou agendamento confirmado mostra médico e CRM no resultado final.

Se os fixtures existentes já têm helpers de FSM, use-os. Caso contrário, crie dados mínimos respeitando estados usados pela view.

#### 4. Agendador — fila e confirmação

Em `apps/scheduler/tests/test_views.py`:

- fila `WAIT_APPT`: card de agendamento mostra médico e CRM;
- vinda imediata: card de ciência operacional mostra médico e CRM;
- tela `scheduler:confirm`: card “Decisão Médica” mostra médico e CRM.

### GREEN — implementação mínima

#### 1. `apps/accounts/models.py`

Adicionar properties no `User`:

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

#### 2. `apps/cases/models.py`

Adicionar property no `Case`:

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

Use `# type: ignore[attr-defined]` apenas se mypy exigir por causa de `AUTH_USER_MODEL`; prefira solução limpa se possível.

#### 3. `apps/intake/views.py`

- Em `_my_cases_context`, otimizar query:

```python
.select_related("doctor", "created_by")
```

- Incluir no dict de cada card:

```python
"doctor_display": c.doctor_display,
```

- Em `case_detail`, carregar médico:

```python
Case.objects.select_related("created_by", "doctor")
```

- Para `result_info`, incluir quando aplicável:

```python
"doctor_display": case.doctor_display,
```

Inclua nos tipos:

- `doctor_denied`
- `accepted_immediate`
- `accepted_scheduled`
- `appt_denied` (mostrar o médico que aceitou originalmente, se existir)

#### 4. `templates/intake/_my_cases_content.html`

Abaixo da decisão médica, exibir:

```django
{% if item.doctor_display %}
<div class="case-meta small text-muted">
  Médico: {{ item.doctor_display }}
</div>
{% endif %}
```

#### 5. `templates/intake/case_detail.html`

No card “Resultado Final”, em cada ramo relevante, adicionar bloco:

```django
{% if result_info.doctor_display %}
<div class="mb-3">
  <p class="mb-1 text-muted small">Médico responsável</p>
  <p class="mb-0 fw-medium">{{ result_info.doctor_display }}</p>
</div>
{% endif %}
```

Aplicar aos ramos:

- `accepted_immediate`
- `accepted_scheduled`
- `doctor_denied`
- `appt_denied`

Não precisa aplicar a `manual_review_required` nem `failed`, pois não há decisão médica humana.

#### 6. `apps/scheduler/views.py`

- Em `_build_case_card`, incluir:

```python
"doctor_display": case.doctor_display,
```

- Nas queries de `_scheduler_queue_context`, usar `select_related("doctor")` para `pending_cases`, `immediate_notice_qs` e, se aplicável, `confirmed_qs`.

- Em `_build_confirm_context`, incluir:

```python
"doctor_display": case.doctor_display,
```

- Em `scheduler_confirm`/`scheduler_submit`, se necessário, buscar o caso com `select_related("doctor")`.

#### 7. `templates/scheduler/_queue_content.html`

Nos cards de `immediate_notice_cases`, dentro do `summary-box`, adicionar campo `Médico`.

Nos cards de `pending_cases`, dentro do `summary-box`, adicionar campo `Médico`.

Sugestão de layout se ficar apertado:

```django
{% if c.doctor_display %}
<div class="col-sm-4 mb-2">
  <div class="summary-label">Médico</div>
  <div class="summary-value">{{ c.doctor_display }}</div>
</div>
{% endif %}
```

Ajuste colunas Bootstrap com bom senso, mantendo legibilidade.

#### 8. `templates/scheduler/confirm.html`

No card “Decisão Médica”, adicionar após “Decisão”:

```django
{% if doctor_display %}
<div class="summary-box mb-3">
  <div class="summary-label">Médico responsável</div>
  <div class="summary-value">{{ doctor_display }}</div>
</div>
{% endif %}
```

### REFACTOR

- Evite lógica de concatenação de nome/CRM nos templates.
- Use helpers/properties para centralizar display.
- Não implemente filtros ou busca por médico/CRM.
- Não crie migration.
- Mantenha templates SSR/Bootstrap, sem JS novo.

## Critérios de sucesso

- [ ] `User.display_name` implementado com fallback para username.
- [ ] `User.professional_registration_display` implementado com fallback vazio.
- [ ] `Case.doctor_display` implementado com fallback vazio quando não há médico.
- [ ] Cards do NIR mostram médico responsável após decisão médica.
- [ ] Detalhe do NIR mostra médico responsável no resultado final de recusa médica.
- [ ] Detalhe do NIR mostra médico responsável no resultado final de vinda imediata.
- [ ] Detalhe do NIR mostra médico responsável no resultado final de agendamento confirmado.
- [ ] Detalhe do NIR mostra médico responsável em agendamento negado, se houve médico anterior.
- [ ] Fila do agendador mostra médico responsável em casos `WAIT_APPT`.
- [ ] Fila do agendador mostra médico responsável em vinda imediata.
- [ ] Tela de confirmação do agendador mostra médico responsável.
- [ ] Quando há CRM, display contém `CRM 12345`.
- [ ] Quando não há CRM, display contém ao menos o nome do médico.
- [ ] Não há migration nova.
- [ ] Testes relevantes passam.
- [ ] `openspec/changes/show-doctor-registration-downstream/tasks.md` atualizado.

## Gates de autoavaliação

Antes de finalizar, responda no relatório:

1. A implementação reaproveita `Case.doctor` em vez de duplicar dados?
2. Existe fallback visual para médico sem CRM?
3. Os templates não fazem concatenação manual de nome + CRM?
4. As queries evitam N+1 com `select_related("doctor")` onde necessário?
5. O slice não criou migration nem mudou a persistência da decisão médica?
6. NIR e agendador enxergam o médico nos três fluxos: recusa, vinda imediata e agendamento?

## Comandos de validação obrigatórios

Execute os comandos do `AGENTS.md`:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy .
uv run pytest
```

Também verifique:

```bash
git status --short
```

## Relatório, commit e push

Ao concluir:

1. Gere relatório detalhado em markdown temporário, por exemplo:

```text
/tmp/ats-web-slice-001-doctor-registration-downstream-ui-report.md
```

2. O relatório deve conter:
   - resumo;
   - arquivos alterados;
   - snippets antes/depois;
   - testes adicionados/alterados;
   - resultado dos comandos de validação;
   - respostas aos gates de autoavaliação.

3. Atualize `openspec/changes/show-doctor-registration-downstream/tasks.md` marcando o slice como concluído e incluindo commit/report.

4. Faça commit com mensagem rastreável, sugestão:

```bash
git add apps/accounts apps/cases apps/intake apps/scheduler templates/intake templates/scheduler openspec/changes/show-doctor-registration-downstream
git commit -m "feat(cases): show deciding doctor downstream"
git push
```

5. Responda ao usuário/planner com resumo curto e:

```text
REPORT_PATH=/tmp/ats-web-slice-001-doctor-registration-downstream-ui-report.md
```

6. **Pare** e peça confirmação explícita antes de qualquer próximo slice.

## Prompt pronto para o implementador LLM

```text
Read AGENTS.md and PROJECT_CONTEXT.md first.
Implement ONLY openspec/changes/show-doctor-registration-downstream/slices/slice-001-doctor-registration-downstream-ui.md.
Use TDD RED→GREEN→REFACTOR.
Goal: show the doctor who decided a case to downstream actors (NIR and scheduler), including name and CRM/COREN registration when available.
Do not create migrations. Do not alter doctor decision persistence. Reuse Case.doctor.
Add User display helpers for display_name and professional_registration_display. Add Case.doctor_display.
Show doctor_display in NIR my cases cards, NIR case detail final result for doctor denial, immediate admission, scheduled confirmed and appointment denied. Show doctor_display in scheduler WAIT_APPT cards, immediate admission notice cards, and scheduler confirm screen.
Use select_related("doctor") where needed to avoid N+1. Keep SSR Bootstrap templates only; no new JS framework.
Add/adjust tests in accounts/cases/intake/scheduler. Run ruff check, ruff format --check, mypy, pytest, and git status.
Update openspec/changes/show-doctor-registration-downstream/tasks.md, create a temporary markdown implementation report with snippets, commit, push, then reply with REPORT_PATH and stop.
```
