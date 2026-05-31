# Slice 003: Visibilidade para agendador

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`, um monolito Django 5.2 SSR com templates Bootstrap, sem API REST e sem SPA.

Antes de codar, leia obrigatoriamente:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/doctor-observation/proposal.md`
4. `openspec/changes/doctor-observation/design.md`
5. `openspec/changes/doctor-observation/slices/slice-001-captura-persistencia-observacao-medica.md`
6. `openspec/changes/doctor-observation/slices/slice-002-visibilidade-nir-supervisor-admin.md`
7. Este arquivo de slice

Pré-condições:

- Slice 001 concluído, com `Case.doctor_observation` persistido.
- Slice 002 concluído, com padrão visual de badge/card definido para NIR/detalhes.

Implemente **somente este slice**. Não altere formulário médico nem telas NIR, exceto ajuste mínimo se um teste existente quebrar. Use TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Tornar a observação médica visível para o agendador nos pontos operacionais relevantes.

Este slice entrega o fluxo vertical:

```text
Caso aceito pelo médico com doctor_observation -> agendador vê badge na fila -> agendador vê texto completo na tela operacional
```

## Escopo funcional

- Na fila do agendador, exibir badge discreta quando o caso tiver observação médica.
- A badge deve aparecer em:
  - cards de `pending_cases` / casos `WAIT_APPT`;
  - cards de `immediate_notice_cases` / vinda imediata para ciência operacional.
- Na tela de confirmação de agendamento (`scheduler:confirm`), exibir o texto completo da observação.
- Para casos de vinda imediata, garantir que o card da fila oferece conteúdo suficiente ou, se não houver tela de detalhe, exibir o texto completo no próprio card de ciência operacional de forma compacta.

## Fora de escopo neste slice

- Persistência e validação da observação médica.
- NIR, manager e admin.
- Edição de observação pelo agendador.
- Filtros por observação.
- Alteração de status/FSM.

## Arquivos prováveis

Mantenha o slice enxuto. Arquivos previstos:

1. `apps/scheduler/views.py`
2. `templates/scheduler/_queue_content.html`
3. `templates/scheduler/confirm.html`
4. testes em `apps/scheduler/tests/`
5. `openspec/changes/doctor-observation/tasks.md`

Se tocar outros arquivos, justifique no relatório final.

## Estado técnico relevante

- `apps/scheduler/views.py::_scheduler_queue_context` monta:
  - `pending_cards` para casos `WAIT_APPT`;
  - `immediate_notice_cards` para vinda imediata.
- `_build_case_card` centraliza dados dos cards do agendador.
- `templates/scheduler/_queue_content.html` renderiza os dois tipos de card.
- `templates/scheduler/confirm.html` renderiza a tela de confirmação para `WAIT_APPT`.
- Para vinda imediata, atualmente o agendador confirma ciência diretamente pelo card; não há tela de detalhe separada.

## Plano TDD obrigatório

### RED — testes primeiro

Crie/atualize testes antes da implementação em `apps/scheduler/tests/`.

#### 1. Fila WAIT_APPT com badge

- criar usuário com role `scheduler` logado;
- criar caso `WAIT_APPT`, `doctor_decision="accept"`, `doctor_admission_flow="scheduled"`, `doctor_observation="Preparar sala com suporte X"`;
- acessar `scheduler:queue`;
- assert que aparece badge `Obs. médica` ou `Observação médica` no card.

Adicionar teste negativo:

- caso `WAIT_APPT` sem observação;
- assert que badge não aparece para esse cenário.

#### 2. Fila de vinda imediata

- criar caso com `doctor_admission_flow="immediate"` e evento `IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE` hoje;
- preencher `doctor_observation`;
- acessar `scheduler:queue`;
- assert que aparece badge e/ou texto da observação no card de ciência operacional.

Como não há tela de detalhe para vinda imediata, o texto completo deve aparecer no card, preferencialmente em bloco compacto.

#### 3. Tela de confirmação de agendamento

- criar caso `WAIT_APPT` com `doctor_observation` preenchida;
- acessar `scheduler:confirm`;
- assert que aparecem título `Observação Médica` e texto completo.

Adicionar teste negativo:

- caso sem observação;
- assert que o card/título não aparece.

### GREEN — implementação mínima

#### 1. `apps/scheduler/views.py`

Na `_build_case_card`, incluir:

```python
"has_doctor_observation": bool(case.doctor_observation.strip()),
"doctor_observation": case.doctor_observation,
```

Se Slice 001 criou property `has_doctor_observation`, pode usar:

```python
"has_doctor_observation": case.has_doctor_observation,
```

No `_build_confirm_context`, não é obrigatório adicionar nada, pois o template recebe `case`; use `case.doctor_observation` diretamente.

#### 2. `templates/scheduler/_queue_content.html`

Nos cards de `pending_cases`, adicionar badge discreta:

```django
{% if c.has_doctor_observation %}
<span class="badge bg-info text-dark">📝 Obs. médica</span>
{% endif %}
```

Nos cards de `immediate_notice_cases`, adicionar badge e texto completo compacto, por não haver tela de detalhe:

```django
{% if c.has_doctor_observation %}
<div class="alert alert-info py-2 px-3 mt-2 mb-0 small">
  <strong>📝 Observação médica:</strong> {{ c.doctor_observation }}
</div>
{% endif %}
```

Não use `safe`.

#### 3. `templates/scheduler/confirm.html`

No card “Decisão Médica”, adicionar bloco:

```django
{% if case.doctor_observation %}
<div class="summary-box mt-3 border-info">
  <div class="summary-label">Observação médica</div>
  <div class="summary-value" style="white-space: pre-wrap;">{{ case.doctor_observation }}</div>
</div>
{% endif %}
```

## Critérios de aceitação do slice

- [ ] Agendador vê badge em card `WAIT_APPT` quando há observação.
- [ ] Agendador não vê badge em card `WAIT_APPT` sem observação.
- [ ] Agendador vê observação completa na tela `scheduler:confirm`.
- [ ] Card/título de observação não aparece em `scheduler:confirm` sem observação.
- [ ] Agendador vê badge e texto completo no card de vinda imediata, pois não há detalhe separado.
- [ ] Nenhuma transição FSM foi alterada.
- [ ] Testes do slice passam.
- [ ] `openspec/changes/doctor-observation/tasks.md` é atualizado marcando este slice como concluído e, se todos os slices estiverem concluídos, marcando o DoD do change.

## Gates de autoavaliação

Antes de finalizar, responda no relatório:

1. A fila `WAIT_APPT` mostra somente badge, sem poluir o card?
2. A tela `scheduler:confirm` mostra o texto completo?
3. Vinda imediata mostra texto completo no próprio card por não ter detalhe separado?
4. Conteúdo da observação permanece autoescaped?
5. Casos sem observação não mostram UI vazia?
6. Quantos arquivos foram tocados e por quê?

## Comandos de validação

Rode no mínimo:

```bash
uv run pytest apps/scheduler/tests -q
uv run ruff check apps/scheduler/views.py apps/scheduler/tests
uv run ruff format --check apps/scheduler/views.py apps/scheduler/tests
uv run mypy apps/scheduler
```

Ao final, rode preferencialmente o quality gate completo do `AGENTS.md`, pois este é o slice final do change:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

Se algum comando não puder ser executado, registre motivo e saída relevante no relatório.

## Relatório final obrigatório

Crie relatório temporário em:

```text
/tmp/ats-web-slice-003-doctor-observation-scheduler-report.md
```

O relatório deve conter:

- resumo do que foi implementado;
- lista de arquivos alterados;
- snippets antes/depois dos pontos principais;
- testes adicionados/alterados;
- comandos executados e resultados;
- riscos/observações;
- confirmação de atualização de `tasks.md`;
- status final do DoD do change;
- commit hash e push, quando realizados.

Na resposta final, informe exatamente:

```text
REPORT_PATH=/tmp/ats-web-slice-003-doctor-observation-scheduler-report.md
```

Depois pare e peça confirmação explícita antes de qualquer novo trabalho.
