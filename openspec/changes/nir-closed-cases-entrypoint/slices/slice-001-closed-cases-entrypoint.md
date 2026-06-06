# Slice 001: Expor entrada de Casos Encerrados e corrigir filtro operacional

## Handoff para implementador LLM com contexto zero

Leia, nesta ordem:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/archive/post-schedule-intercurrence/tasks.md`
4. `openspec/archive/post-schedule-intercurrence/slices/slice-002-nir-search-open-issue.md`
5. `openspec/changes/nir-closed-cases-entrypoint/proposal.md`
6. `openspec/changes/nir-closed-cases-entrypoint/design.md`
7. `openspec/changes/nir-closed-cases-entrypoint/tasks.md`
8. Este arquivo

Implemente somente este slice.

## Contexto do bug

A busca de intercorrência pós-agendamento foi implementada na rota:

```text
/intake/closed-cases/
```

O NIR, porém, tende a procurar casos concluídos usando a página `Meus Casos`,
que é uma fila operacional e exclui `CLEANED` por design. O filtro dessa tela
pode induzir o usuário a selecionar status concluído, mas a lista nunca retorna
casos `CLEANED`.

## Objetivo

Tornar o caminho `Casos Encerrados` óbvio para o NIR e impedir que o filtro de
`Meus Casos` sugira busca por casos concluídos no lugar errado.

## Escopo

- Adicionar aba/link `Casos Encerrados` em:
  - `templates/intake/my_cases.html`
  - `templates/intake/intake_home.html`
- Ajustar contexto/template de `Meus Casos` para o select de status não incluir
  `CaseStatus.CLEANED`.
- Manter `Case.objects.exclude(status=CaseStatus.CLEANED)` em `Meus Casos`.
- Preservar `/intake/closed-cases/` como busca oficial para casos concluídos.
- Adicionar testes de regressão/UX.

## Fora de escopo

- Não incluir casos `CLEANED` em `Meus Casos`.
- Não alterar regras de elegibilidade de intercorrência.
- Não alterar FSM, modelos ou serviços de domínio.
- Não criar nova rota.
- Não criar JS.

## Plano TDD obrigatório

### RED

Adicionar testes antes da implementação:

1. `my_cases` renderiza link/aba para `Casos Encerrados` apontando para
   `intake:closed_cases_search`.
2. `intake_home` renderiza link/aba para `Casos Encerrados` apontando para
   `intake:closed_cases_search`.
3. O select de status de `my_cases` não inclui opção `CLEANED`.
4. `my_cases` continua sem listar caso `CLEANED` mesmo quando existe caso
   concluído no banco.
5. `closed_cases_search` continua encontrando caso `CLEANED` por número da
   ocorrência.

### GREEN

Implementar o mínimo:

- Alterar templates de navegação NIR.
- Criar helper simples para status operacionais, se necessário.
- Passar `status_labels` sem `CaseStatus.CLEANED` para `my_cases`.

### REFACTOR

- Evitar duplicação excessiva, mas não criar componente/template compartilhado se
  isso ampliar muito o escopo.
- Manter nomes explícitos, por exemplo `operational_status_labels`.

## Critérios de aceite

- [ ] NIR vê `Casos Encerrados` em `Meus Casos`.
- [ ] NIR vê `Casos Encerrados` em `Novo Encaminhamento`/home.
- [ ] Filtro de `Meus Casos` não mostra `CLEANED`.
- [ ] `Meus Casos` continua operacional e sem concluídos.
- [ ] `/intake/closed-cases/` continua encontrando casos concluídos.
- [ ] Testes relevantes passam.

## Gates de validação

Rodar no mínimo:

```bash
uv run pytest apps/intake/tests/test_post_schedule_issue.py apps/intake/tests/test_my_cases.py apps/intake/tests/test_nir_shared_operational.py -q
uv run ruff check apps/intake
uv run ruff format --check apps/intake
uv run mypy apps/intake
```

Se viável, rodar quality gate completo:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório obrigatório

Criar relatório em:

```text
/tmp/ats-web-nir-closed-cases-entrypoint-slice-001-report.md
```

O relatório deve conter:

- resumo do bug;
- arquivos alterados;
- snippets antes/depois;
- testes adicionados/ajustados;
- validações executadas;
- commit hash;
- confirmação de push.

Resposta final obrigatória:

```text
REPORT_PATH=/tmp/ats-web-nir-closed-cases-entrypoint-slice-001-report.md
```

Depois, parar e aguardar confirmação explícita.

## Prompt pronto para implementador

```text
Read AGENTS.md, PROJECT_CONTEXT.md, archived post-schedule-intercurrence Slice 002, and openspec/changes/nir-closed-cases-entrypoint through Slice 001. Implement ONLY Slice 001. Fix the NIR UX bug where users look for completed cases in Meus Casos: expose the Casos Encerrados entrypoint in NIR navigation, remove CLEANED from the operational status filter, keep Meus Casos excluding CLEANED, preserve /intake/closed-cases/ search behavior, add tests first, run validations, update tasks.md only after completion, create /tmp/ats-web-nir-closed-cases-entrypoint-slice-001-report.md, commit and push, reply with REPORT_PATH and stop.
```
