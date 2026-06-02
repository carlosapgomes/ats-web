# Slice 002: Visibilidade para NIR, supervisor e admin

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`, um monolito Django 5.2 SSR com templates Bootstrap, sem API REST e sem SPA.

Antes de codar, leia obrigatoriamente:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/doctor-observation/proposal.md`
4. `openspec/changes/doctor-observation/design.md`
5. `openspec/changes/doctor-observation/slices/slice-001-captura-persistencia-observacao-medica.md`
6. Este arquivo de slice

Pré-condição: Slice 001 concluído, com `Case.doctor_observation` persistido pelo formulário médico.

Implemente **somente este slice**. Não implemente telas do agendador neste slice. Use TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Tornar a observação médica visível para NIR e para supervisor/admin.

Este slice entrega o fluxo vertical:

```text
Caso com doctor_observation -> NIR vê badge na listagem -> NIR vê texto no detalhe -> manager/admin vê texto no detalhe pelo dashboard
```

## Escopo funcional

- Na listagem “Meus Casos” do NIR, exibir badge discreta quando houver observação médica.
- No detalhe do caso usado pelo NIR, exibir card com o texto completo da observação.
- Garantir que manager/admin, ao abrir detalhe do caso pelo dashboard, também veem o texto completo.
- Não exibir badge/card vazio quando não houver observação.

## Fora de escopo neste slice

- Formulário médico e persistência: já cobertos pelo Slice 001.
- Fila/tela do agendador: será Slice 003.
- Edição de observação.
- Filtros por observação.

## Arquivos prováveis

Mantenha o slice enxuto. Arquivos previstos:

1. `apps/intake/views.py`
2. `templates/intake/_my_cases_content.html`
3. `templates/intake/case_detail.html`
4. `apps/intake/tests/test_my_cases.py`
5. `apps/intake/tests/test_case_detail.py`
6. `apps/dashboard/tests/test_dashboard.py` somente para garantir manager/admin no detalhe
7. `apps/dashboard/views.py` somente se os testes mostrarem que o template compartilhado não basta
8. `openspec/changes/doctor-observation/tasks.md`

Se tocar outros arquivos, justifique no relatório final.

## Estado técnico relevante

- `apps/intake/views.py::_my_cases_context` monta `case_data` para `templates/intake/_my_cases_content.html`.
- `apps/intake/views.py::case_detail` renderiza `templates/intake/case_detail.html` para o NIR.
- `apps/dashboard/views.py::dashboard_case_detail` também renderiza `templates/intake/case_detail.html` para manager/admin.

Logo, um bloco bem colocado em `templates/intake/case_detail.html` deve cobrir NIR + manager/admin.

## Plano TDD obrigatório

### RED — testes primeiro

Crie/atualize testes antes da implementação.

#### 1. NIR listagem/cards

Em `apps/intake/tests/test_my_cases.py`:

- criar usuário NIR logado;
- criar caso desse NIR com `doctor_observation="Observação importante para logística"`;
- acessar `intake:my_cases`;
- assert que aparece badge/texto `Obs. médica` ou `Observação médica` no card.

Adicionar teste negativo:

- criar caso sem observação;
- acessar listagem;
- assert que a badge não aparece para esse caso.

Se a listagem contém múltiplos casos, monte cenário com um caso com observação e outro sem para evitar falso positivo global.

#### 2. NIR detalhe

Em `apps/intake/tests/test_case_detail.py`:

- criar caso do NIR com `doctor_observation` preenchido;
- acessar `intake:case_detail`;
- assert que aparecem o título `Observação Médica` e o texto completo.

Adicionar teste negativo:

- caso sem observação;
- assert que o título/card não aparece.

#### 3. Manager/admin detalhe via dashboard

Em `apps/dashboard/tests/test_dashboard.py`:

- login como `manager` ou `admin`;
- criar caso de qualquer usuário com `doctor_observation` preenchido;
- acessar `dashboard:case_detail`;
- assert que aparecem título e texto da observação.

Também garantir que manager/admin continuam sem botão de confirmar recebimento, se houver teste existente próximo.

### GREEN — implementação mínima

#### 1. `apps/intake/views.py`

Na montagem dos cards de `_my_cases_context`, incluir um booleano, preferindo property se existir:

```python
"has_doctor_observation": bool(c.doctor_observation.strip()),
```

ou:

```python
"has_doctor_observation": c.has_doctor_observation,
```

Não é necessário passar o texto completo para a listagem; a listagem só precisa da badge.

#### 2. `templates/intake/_my_cases_content.html`

No card, em local compacto próximo à decisão/status, adicionar:

```django
{% if item.has_doctor_observation %}
<span class="badge bg-info text-dark">📝 Obs. médica</span>
{% endif %}
```

Evite layout grande. A badge deve ser discreta.

#### 3. `templates/intake/case_detail.html`

Adicionar card dedicado, preferencialmente após o “Resultado Final” ou antes de “Ações”:

```django
{% if case.doctor_observation %}
<div class="card p-4 mb-4 border-info">
  <h5 class="mb-3">📝 Observação Médica</h5>
  <p class="mb-0" style="white-space: pre-wrap;">{{ case.doctor_observation }}</p>
</div>
{% endif %}
```

Use autoescape padrão do Django; não use `safe`.

#### 4. `apps/dashboard/views.py`

Evite alterar se o template compartilhado já resolver. Só toque se necessário para query/contexto/teste.

## Critérios de aceitação do slice

- [ ] NIR vê badge na listagem quando o caso tem observação médica.
- [ ] NIR não vê badge para caso sem observação.
- [ ] NIR vê texto completo no detalhe do caso.
- [ ] Manager/admin veem texto completo no detalhe pelo dashboard.
- [ ] Card de observação não aparece quando o campo está vazio ou só com espaços.
- [ ] Nenhuma tela do agendador foi alterada neste slice.
- [ ] Testes do slice passam.
- [ ] `openspec/changes/doctor-observation/tasks.md` é atualizado marcando este slice como concluído, somente ao final.

## Gates de autoavaliação

Antes de finalizar, responda no relatório:

1. A listagem mostra apenas badge e não o texto completo?
2. O detalhe mostra o texto completo com quebras preservadas?
3. O template usa autoescape padrão e não marca conteúdo como `safe`?
4. Manager/admin foram cobertos sem duplicar template?
5. Casos sem observação não mostram UI vazia?
6. Quantos arquivos foram tocados e por quê?

## Comandos de validação

Rode no mínimo:

```bash
uv run pytest apps/intake/tests/test_my_cases.py apps/intake/tests/test_case_detail.py apps/dashboard/tests/test_dashboard.py -q
uv run ruff check apps/intake/views.py apps/intake/tests/test_my_cases.py apps/intake/tests/test_case_detail.py apps/dashboard/tests/test_dashboard.py
uv run ruff format --check apps/intake/views.py apps/intake/tests/test_my_cases.py apps/intake/tests/test_case_detail.py apps/dashboard/tests/test_dashboard.py
uv run mypy apps/intake apps/dashboard
```

Ao final, se possível, rode o quality gate completo do `AGENTS.md`:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

Se algum comando não puder ser executado, registre motivo e saída relevante no relatório.

## Relatório final obrigatório

Crie relatório temporário em:

```text
/tmp/ats-web-slice-002-doctor-observation-nir-dashboard-report.md
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
REPORT_PATH=/tmp/ats-web-slice-002-doctor-observation-nir-dashboard-report.md
```

Depois pare e peça confirmação explícita antes de iniciar o próximo slice.
