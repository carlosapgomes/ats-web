# Slice 002: NIR busca casos encerrados e abre intercorrência

## Handoff para implementador LLM com contexto zero

Este slice constrói a experiência NIR para localizar caso encerrado elegível e registrar intercorrência. O Slice 001 já deve ter implementado campos, FSM e serviços de domínio.

Leia:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/post-schedule-intercurrence/proposal.md`
4. `openspec/changes/post-schedule-intercurrence/design.md`
5. `openspec/changes/post-schedule-intercurrence/tasks.md`
6. `openspec/changes/post-schedule-intercurrence/slices/slice-001-domain-fsm-services.md`
7. Este arquivo
8. `apps/intake/views.py`, `apps/intake/urls.py`, templates e testes existentes do app intake

Implemente **somente este slice** com TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Permitir que NIR busque casos `CLEANED` por número da ocorrência ou nome do paciente e abra intercorrência quando o caso for elegível.

Fluxo end-to-end do slice:

```text
NIR acessa busca de casos encerrados
→ pesquisa por ocorrência ou nome
→ vê caso elegível com botão Registrar intercorrência
→ escolhe motivo e mensagem conforme regra
→ submit chama serviço do Slice 001
→ caso passa para WAIT_APPT
→ NIR recebe feedback e não consegue abrir outra intercorrência ativa
```

## Escopo funcional

- Criar rota/página NIR para busca de casos encerrados, por exemplo:
  - `/intake/closed-cases/`
  - `/intake/closed-cases/<uuid>/post-schedule-issue/`
- Busca mínima por:
  - `agency_record_number` parcial/exato;
  - nome do paciente extraído de `structured_data`.
- Mostrar resultados `CLEANED` com status de elegibilidade.
- Mostrar botão/form de abertura somente para elegíveis.
- Form NIR com motivo oficial e mensagem condicional.
- Ao abrir, redirecionar com mensagem de sucesso e caso deve aparecer na fila do agendador por estar em `WAIT_APPT`.
- Exibir badge/mensagem quando já houver intercorrência ativa.

## Fora de escopo

- Resolver intercorrência no agendador.
- Alterar confirmação NIR final.
- Criar busca avançada, paginação sofisticada ou índices novos, salvo necessidade clara.
- Mostrar timeline completa além do necessário.
- Permitir abrir intercorrência em casos negados ou não agendados.

## Arquivos prováveis

1. `apps/intake/views.py`
2. `apps/intake/urls.py`
3. `apps/intake/forms.py` se existir ou novo formulário enxuto
4. `templates/intake/closed_cases.html`
5. `templates/intake/post_schedule_issue_form.html`
6. `apps/intake/tests/test_post_schedule_issue.py`
7. `openspec/changes/post-schedule-intercurrence/tasks.md` ao final

## Plano TDD obrigatório

### RED — busca

Criar testes:

1. Usuário sem login é redirecionado.
2. Usuário sem papel ativo `nir` não acessa.
3. NIR acessa página de busca.
4. Busca por número da ocorrência encontra caso `CLEANED`.
5. Busca por nome do paciente encontra caso `CLEANED`.
6. Caso não `CLEANED` não aparece nessa busca de encerrados, exceto se necessário mostrar ativa por link direto; mantenha simples.
7. Caso não elegível aparece sem botão e com motivo de inelegibilidade.

### RED — abertura

1. GET do formulário abre para caso elegível.
2. GET do formulário retorna 404 ou mensagem bloqueada para caso inelegível.
3. POST com motivo `death` e mensagem vazia abre intercorrência.
4. POST com motivo `clinical_condition` e mensagem vazia mostra erro.
5. POST válido muda status para `WAIT_APPT` e grava evento.
6. Segunda tentativa de abertura no mesmo caso é bloqueada.

## GREEN

- Use serviço de domínio do Slice 001; não duplique regra de elegibilidade na view.
- Form deve delegar validação de mensagem condicional a constantes/helper compartilhado, se já existir.
- Busca por nome pode ser simples. Se `structured_data__patient__name__icontains` funcionar nos testes, use. Caso contrário, use abordagem clara e documente no relatório.

## REFACTOR

- Extrair helper de queryset somente se reduzir duplicação real.
- Manter templates simples com Bootstrap já usado.
- Não criar componente JS.

## Critérios de aceitação

- [ ] NIR busca casos encerrados por ocorrência e nome.
- [ ] Botão de abertura aparece somente para elegíveis.
- [ ] Form aplica mensagem condicional.
- [ ] Abertura muda caso para `WAIT_APPT` e cria intercorrência ativa.
- [ ] Segunda abertura ativa é bloqueada.
- [ ] Views respeitam `@role_required("nir")`.
- [ ] Código usa serviços do domínio, sem duplicar regras críticas.

## Gates de autoavaliação

Responder no relatório:

1. A busca é separada da fila operacional NIR atual?
2. Como a view evita abrir caso inelegível?
3. Onde está a validação condicional da mensagem?
4. Como o usuário percebe que já existe intercorrência ativa?
5. Quais limitações existem na busca por nome?

## Comandos de validação mínimos

```bash
uv run pytest apps/intake/tests/test_post_schedule_issue.py -q
uv run pytest apps/cases/tests -q
uv run ruff check apps/intake apps/cases
uv run ruff format --check apps/intake apps/cases
uv run mypy apps/intake apps/cases
```

Quality gate completo, se possível:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório final obrigatório

Criar:

```text
/tmp/ats-web-slice-002-nir-search-open-issue-report.md
```

Incluir resumo, arquivos, snippets, testes, validações, riscos, atualização de `tasks.md`, commit hash e push.

Resposta final:

```text
REPORT_PATH=/tmp/ats-web-slice-002-nir-search-open-issue-report.md
```

Pare e peça confirmação antes do próximo slice.

## Prompt pronto para implementador

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/post-schedule-intercurrence through Slice 002. Implement ONLY Slice 002 using TDD. Build NIR search/open UI for closed eligible cases: search by agency_record_number or patient name, show eligibility, form with official reasons and conditional message, call Slice 001 domain service to open issue, block duplicate active issue, respect nir role guard. Do not implement scheduler resolution yet. Keep code simple, DRY and YAGNI. Run validations, update tasks.md, create /tmp/ats-web-slice-002-nir-search-open-issue-report.md, commit and push, reply REPORT_PATH and stop.
```
