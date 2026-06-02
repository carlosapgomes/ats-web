# Slice 005: NIR — casos operacionais compartilhados

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`, monolito Django SSR. Os slices anteriores implementaram locks para médico/agendador. Este slice altera a visibilidade da lista NIR, mas ainda não implementa lock NIR de confirmação; isso fica no Slice 006.

Leia:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/shared-work-queue-leases/proposal.md`
4. `openspec/changes/shared-work-queue-leases/design.md`
5. Este arquivo

Implemente **somente este slice** com TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Permitir continuidade de plantão no NIR para todos os casos operacionais:

```text
NIR A criou um caso que ainda não está CLEANED
→ NIR B também vê esse caso na lista operacional NIR
→ NIR B consegue abrir o detalhe para acompanhar o caso
→ quando o caso vira CLEANED, ele deixa de aparecer na lista operacional compartilhada
```

## Regra de produto deste slice

Assumida pelo proposal/design:

```text
Todos os NIR veem todos os casos operacionais = todos os casos com status diferente de CLEANED.
```

Isso inclui casos em processamento, aguardando médico, aguardando agendamento, resultados pendentes e falhas ainda não concluídas. O objetivo é continuidade de plantão. A ação de confirmação de recebimento continua limitada aos casos `WAIT_R1_CLEANUP_THUMBS` e será protegida por lease no Slice 006.

## Escopo funcional

- Alterar `_my_cases_context` para listar todos os casos com `status != CLEANED`, independentemente de `created_by`.
- Ajustar acesso de `case_detail` para permitir NIR abrir qualquer caso operacional não `CLEANED`.
- Garantir que casos `CLEANED` não aparecem na fila operacional NIR.
- Indicar visualmente quando o caso foi criado por outro NIR, se isso for útil e simples.
- Manter confirmação de recebimento sem lock neste slice; a proteção por lease fica no Slice 006.

## Fora de escopo

- Lock NIR para confirmar recebimento.
- Permitir NIR alterar decisões médica/agendador.
- Permitir acesso a casos `CLEANED` pela fila operacional NIR.
- Alterar dashboard.
- Alterar médico/agendador.
- Criar nova página de fila NIR separada, salvo se estritamente necessário e aprovado.

## Arquivos prováveis

1. `apps/intake/views.py`
2. `templates/intake/_my_cases_content.html`
3. talvez `templates/intake/case_detail.html`
4. testes em `apps/intake/tests/`
5. `openspec/changes/shared-work-queue-leases/tasks.md` ao final

## Plano TDD obrigatório

### RED — lista NIR

Criar testes:

1. NIR vê seus próprios casos não `CLEANED` como antes.
2. NIR vê caso operacional criado por outro NIR em `WAIT_DOCTOR`.
3. NIR vê caso operacional criado por outro NIR em `WAIT_APPT`.
4. NIR vê caso operacional criado por outro NIR em `WAIT_R1_CLEANUP_THUMBS`.
5. NIR vê caso operacional criado por outro NIR em `FAILED`, se ainda não estiver `CLEANED`.
6. Caso `CLEANED` de qualquer NIR não aparece.
7. Filtro por status/search continua funcionando sobre todos os casos operacionais compartilhados.
8. Não há duplicidade de cards.

### RED — detalhe

1. NIR consegue abrir detalhe de caso operacional não `CLEANED` criado por outro NIR.
2. NIR não consegue abrir detalhe operacional de caso `CLEANED` pela rota da fila NIR.
3. Usuário sem papel NIR continua bloqueado pelo role guard existente.

## GREEN — implementação mínima

### Query da lista

Simplificar a query da fila operacional NIR:

```python
Case.objects.exclude(status=CaseStatus.CLEANED).select_related("doctor").order_by("-created_at")
```

Depois aplicar filtros existentes (`status` e `q`) sobre esse queryset.

### Detalhe

Substituir filtro rígido `created_by=request.user` por helper pequeno e testável, por exemplo:

```python
def _get_nir_operational_case_or_404(case_id):
    return get_object_or_404(
        Case.objects.select_related("created_by", "doctor").exclude(status=CaseStatus.CLEANED),
        case_id=case_id,
    )
```

Use nome claro. Não criar helper genérico demais.

### Template

Se simples, mostrar badge discreta:

```text
Criado por outro NIR
```

Mas não deixe esse detalhe atrasar o slice se os testes principais passarem.

## Critérios de aceitação

- [ ] Todos os NIR veem todos os casos operacionais não `CLEANED`, de todos os criadores.
- [ ] Detalhe de caso operacional compartilhado abre corretamente.
- [ ] Casos `CLEANED` continuam fora da fila operacional NIR e não são acessíveis pela rota operacional NIR.
- [ ] Filtros existentes continuam funcionando sobre a fila compartilhada.
- [ ] NIR não ganha permissão para alterar decisões médica/agendador.
- [ ] Testes passam.
- [ ] Não foi implementado lock NIR neste slice.

## Gates de autoavaliação

Responder no relatório:

1. A regra implementada foi exatamente “todos os casos operacionais não CLEANED”?
2. Casos `CLEANED` ficaram fora da lista e do detalhe operacional?
3. Houve duplicidade de cards?
4. O acesso ao detalhe está consistente com a lista?
5. Alguma confirmação de recebimento foi alterada? Se sim, por quê?

## Comandos de validação mínimos

```bash
uv run pytest apps/intake/tests -q
uv run ruff check apps/intake
uv run ruff format --check apps/intake
uv run mypy apps/intake
```

Quality gate completo, se possível:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório final obrigatório

Criar:

```text
/tmp/ats-web-slice-005-nir-shared-operational-cases-report.md
```

Incluir resumo, arquivos, snippets, testes, validações, riscos, atualização de `tasks.md`, commit hash e push.

Resposta final:

```text
REPORT_PATH=/tmp/ats-web-slice-005-nir-shared-operational-cases-report.md
```

Pare e peça confirmação antes do próximo slice.

## Prompt pronto para implementador

```text
Read AGENTS.md, PROJECT_CONTEXT.md and shared-work-queue-leases OpenSpec through Slice 005.
Implement ONLY Slice 005 using TDD.
Adjust NIR my_cases and case_detail so every active NIR sees and can open all operational cases, defined as all Case rows whose status is not CLEANED, regardless of created_by. Do not implement NIR locking yet. Do not allow access to CLEANED cases through the operational NIR route. Keep code simple, DRY and YAGNI.
Run validations, update tasks.md, create /tmp/ats-web-slice-005-nir-shared-operational-cases-report.md, commit and push, reply REPORT_PATH and stop.
```
