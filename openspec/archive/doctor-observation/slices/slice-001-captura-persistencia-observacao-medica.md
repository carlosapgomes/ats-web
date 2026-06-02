# Slice 001: Captura e persistência da observação médica

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`, um monolito Django 5.2 SSR com templates Bootstrap, sem API REST e sem SPA.

Antes de codar, leia obrigatoriamente:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/doctor-observation/proposal.md`
4. `openspec/changes/doctor-observation/design.md`
5. Este arquivo de slice

Implemente **somente este slice**. Não implemente visibilidade para NIR/agendador neste slice, exceto se um teste existente exigir ajuste mínimo. Use TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Permitir que o médico informe uma observação livre opcional no formulário de decisão médica e persistir essa observação no `Case`.

Este slice entrega o fluxo vertical mínimo:

```text
Médico abre decisão -> preenche observação opcional -> envia decisão -> Case.doctor_observation persistido
```

## Escopo funcional

- Adicionar campo opcional `doctor_observation` em `Case`.
- Criar migration.
- Adicionar campo opcional `observation` no `DoctorDecisionForm` com limite de 500 caracteres.
- Renderizar textarea no formulário de decisão médica.
- Persistir a observação em `doctor_submit`.
- Garantir que decisão sem observação continua funcionando.
- Garantir que observação acima de 500 caracteres é inválida.

## Fora de escopo neste slice

- Badge em cards do NIR.
- Badge em cards do agendador.
- Exibição no detalhe NIR/supervisor/admin.
- Exibição na tela de confirmação do agendador.
- Comentários múltiplos/editáveis.
- Alterações de FSM.

## Arquivos prováveis

Mantenha o slice enxuto. Arquivos previstos:

1. `apps/cases/models.py`
2. `apps/cases/migrations/0003_case_doctor_observation.py` ou próximo número disponível
3. `apps/doctor/forms.py`
4. `apps/doctor/views.py`
5. `templates/doctor/decision.html`
6. testes existentes em `apps/doctor/tests/` e/ou `apps/cases/tests/`
7. `openspec/changes/doctor-observation/tasks.md`

Se tocar outros arquivos, justifique no relatório final.

## Plano TDD obrigatório

### RED — testes primeiro

Crie/atualize testes antes da implementação. Sugestões:

#### 1. Model/migration

Em teste de model do app cases:

- `Case` recém-criado tem `doctor_observation == ""`.
- `Case` aceita salvar observação de até 500 caracteres.

Se o projeto não costuma testar migrations diretamente, não crie teste artificial de migration; o campo será validado pelos testes de model/form/view.

#### 2. Formulário médico

Em testes de `DoctorDecisionForm`:

- form válido com decisão `accept`, campos obrigatórios de aceite, e `observation` vazia.
- form válido com `observation` de 500 caracteres.
- form inválido com `observation` de 501 caracteres.
- form válido com decisão `deny`, motivo de negativa preenchido, e observação opcional preenchida.

#### 3. View submit médico

Em testes de view do app doctor:

- POST de aceite com observação persiste `case.doctor_observation`.
- POST de negativa com observação persiste `case.doctor_observation`.
- POST sem observação persiste string vazia e não quebra fluxo atual.
- POST com observação acima de 500 caracteres re-renderiza formulário com erro e não muda o status do caso.

Use helpers/fixtures existentes para colocar o caso em `WAIT_DOCTOR` sem violar FSM. Se não houver helper, siga o padrão dos testes existentes.

### GREEN — implementação mínima

#### 1. `apps/cases/models.py`

Adicionar em “Doctor decision”:

```python
doctor_observation = models.CharField(max_length=500, blank=True)
```

Opcional, apenas se simplificar código/testes:

```python
@property
def has_doctor_observation(self) -> bool:
    return bool(self.doctor_observation.strip())
```

#### 2. Migration

Gerar migration com:

```bash
uv run python manage.py makemigrations cases --settings=config.settings.dev
```

Confira se a migration contém apenas o novo campo.

#### 3. `apps/doctor/forms.py`

Adicionar ao `DoctorDecisionForm`:

```python
observation = forms.CharField(
    required=False,
    max_length=500,
    widget=forms.Textarea(attrs={"rows": 2, "maxlength": 500}),
)
```

Use label/help_text se fizer sentido. Não torne obrigatório em nenhum caminho.

#### 4. `templates/doctor/decision.html`

Adicionar textarea visível sempre, fora das seções condicionais de aceite/negação.

Texto recomendado:

```text
Observação médica opcional
Visível para NIR, agendamento, supervisão e administração. Máx. 500 caracteres.
```

Garantir que, ao re-renderizar form inválido, o valor submetido permaneça no campo.

#### 5. `apps/doctor/views.py`

No `doctor_submit`, após `form.is_valid()` e antes de salvar/transicionar:

```python
case.doctor_observation = form.cleaned_data.get("observation", "")
```

Não altere a lógica existente de `doctor_reason`.

## Critérios de aceitação do slice

- [ ] Migration adiciona somente o campo `doctor_observation`.
- [ ] Campo é opcional e limitado a 500 caracteres.
- [ ] Tela de decisão médica mostra textarea opcional.
- [ ] Submit médico com observação persiste o texto.
- [ ] Submit médico sem observação continua funcionando.
- [ ] Observação acima de 500 caracteres é rejeitada pelo form.
- [ ] Fluxos accept scheduled, accept immediate e deny não são quebrados.
- [ ] Testes do slice passam.
- [ ] `openspec/changes/doctor-observation/tasks.md` é atualizado marcando este slice como concluído, somente ao final.

## Gates de autoavaliação

Antes de finalizar, responda no relatório:

1. O campo novo ficou semanticamente separado de `doctor_reason`?
2. Alguma transição FSM foi alterada? Se sim, por quê?
3. O limite de 500 caracteres é imposto no form e no banco?
4. Casos sem observação continuam válidos?
5. O formulário preserva o valor em caso de erro de validação?
6. Quantos arquivos foram tocados e por quê?

## Comandos de validação

Rode no mínimo:

```bash
uv run pytest apps/doctor/tests apps/cases/tests -q
uv run ruff check apps/cases/models.py apps/doctor/forms.py apps/doctor/views.py apps/doctor/tests apps/cases/tests
uv run ruff format --check apps/cases/models.py apps/doctor/forms.py apps/doctor/views.py apps/doctor/tests apps/cases/tests
uv run mypy apps/cases apps/doctor
```

Ao final, se possível, rode o quality gate completo do `AGENTS.md`:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

Se algum comando não puder ser executado, registre motivo e saída relevante no relatório.

## Relatório final obrigatório

Crie relatório temporário em:

```text
/tmp/ats-web-slice-001-doctor-observation-capture-report.md
```

O relatório deve conter:

- resumo do que foi implementado;
- lista de arquivos alterados;
- snippets antes/depois dos pontos principais;
- testes adicionados/alterados;
- comandos executados e resultados;
- riscos/observações;
- confirmação de atualização de `tasks.md`;
- commit hash e push, quando realizados.

Na resposta final, informe exatamente:

```text
REPORT_PATH=/tmp/ats-web-slice-001-doctor-observation-capture-report.md
```

Depois pare e peça confirmação explícita antes de iniciar o próximo slice.
