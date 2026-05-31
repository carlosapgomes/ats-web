# Slice 006: NIR — lease para confirmação de recebimento

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`. Os slices anteriores implementaram serviço de lock e filas compartilhadas. O Slice 005 tornou todos os casos operacionais NIR (`status != CLEANED`) visíveis para todos os NIR. Este slice impede que dois NIR confirmem o mesmo resultado ao mesmo tempo.

Leia:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/shared-work-queue-leases/proposal.md`
4. `openspec/changes/shared-work-queue-leases/design.md`
5. slices anteriores desta change
6. Este arquivo

Implemente **somente este slice** com TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Aplicar reserva temporária à ação final do NIR:

```text
NIR A abre detalhe de resultado pendente compartilhado
→ backend reserva o caso para NIR A com context nir_receipt
→ NIR B vê que o resultado está reservado por NIR A
→ NIR B não consegue confirmar recebimento
→ NIR A confirma com token válido
→ caso segue CLEANUP_RUNNING → CLEANED
```

## Escopo funcional

- Ao abrir `case_detail` de caso em `WAIT_R1_CLEANUP_THUMBS`, adquirir lock com context `nir_receipt`.
- Incluir `lock_token` no formulário de confirmação de recebimento.
- `confirm_receipt` deve exigir lock válido para casos em `WAIT_R1_CLEANUP_THUMBS`.
- Reutilizar `static/js/work_lock.js` para heartbeat/release na tela de detalhe quando houver lock NIR.
- Criar endpoints intake/NIR de renew/release.
- Lista NIR deve mostrar quando resultado pendente está reservado por outro NIR.
- Expiração deve registrar `WORK_LOCK_EXPIRED` com usuário anterior.

## Fora de escopo

- Alterar novamente a regra de visibilidade NIR definida no Slice 005.
- Alterar médico/agendador.
- Criar página separada para fila de resultados.
- Override por manager/admin.

## Arquivos prováveis

1. `apps/intake/views.py`
2. `apps/intake/urls.py`
3. `templates/intake/_my_cases_content.html`
4. `templates/intake/case_detail.html`
5. testes em `apps/intake/tests/`
6. talvez pequeno ajuste em `apps/cases/services.py`
7. `openspec/changes/shared-work-queue-leases/tasks.md` ao final

## Plano TDD obrigatório

### RED — detalhe/claim

1. NIR abre detalhe de caso `WAIT_R1_CLEANUP_THUMBS` disponível e lock é criado com context `nir_receipt`.
2. Template contém hidden `lock_token` no formulário de confirmação.
3. Segundo NIR abrindo detalhe de caso reservado por outro não recebe formulário confirmável ativo, ou é redirecionado com mensagem clara.
4. Lock expirado pode ser assumido por outro NIR e gera `WORK_LOCK_EXPIRED` com dados do NIR anterior.

### RED — confirmação

1. POST `confirm_receipt` com token válido executa cleanup e conclui caso.
2. POST sem token/token inválido não altera status.
3. POST por outro NIR sem lock não altera status.
4. Repetição de POST após `CLEANED` não reexecuta transições nem quebra.

### RED — heartbeat endpoints

1. Renew/release NIR exigem papel ativo `nir`.
2. Renew com token válido estende lock.
3. Release com token válido limpa lock.
4. Token inválido não limpa/renova.

### RED — lista

1. Resultado pendente reservado por outro NIR mostra quem reservou.
2. Resultado pendente reservado pelo usuário atual permite continuar.

## GREEN — implementação mínima

### Case detail

No detalhe, se `case.status == WAIT_R1_CLEANUP_THUMBS`:

- tentar `claim_case_lock` com:

```python
expected_status=CaseStatus.WAIT_R1_CLEANUP_THUMBS
context="nir_receipt"
role="nir"
```

- se lock pertence a outro usuário, não mostrar botão ativo de confirmação;
- se claim ok, passar token ao template.

### Confirm receipt

Antes de `cleanup_triggered`:

```python
assert_case_lock(... context="nir_receipt")
```

Somente depois executar transições FSM.

Após cleanup, limpar lock.

### Heartbeat

Reutilizar JS do Slice 003, sem duplicação.

### Queue/lista

Chamar expiração lazy para `WAIT_R1_CLEANUP_THUMBS` antes de montar cards.
Enviar flags de lock ao template somente para casos confirmáveis em `WAIT_R1_CLEANUP_THUMBS`; os demais casos operacionais compartilhados podem continuar visíveis sem ação de confirmação.

## Critérios de aceitação

- [ ] NIR adquire lock ao abrir resultado pendente confirmável.
- [ ] Dois NIR não confirmam o mesmo resultado simultaneamente.
- [ ] Confirmação exige `user + token + context` válidos.
- [ ] Lista NIR comunica reserva ativa.
- [ ] Heartbeat/release funcionam na tela NIR.
- [ ] Lock expirado pode ser assumido e audita usuário anterior.
- [ ] Caso concluído sai da fila operacional.
- [ ] Testes passam.

## Gates de autoavaliação

Responder no relatório:

1. O NIR só usa lock para `WAIT_R1_CLEANUP_THUMBS`?
2. O POST de confirmação valida lock antes das transições FSM?
3. Como o template evita botão ativo para outro usuário?
4. A auditoria de expiração contém o NIR anterior?
5. O JS foi reutilizado sem duplicação?

## Comandos de validação mínimos

```bash
uv run pytest apps/intake/tests apps/cases/tests -q
uv run ruff check apps/intake apps/cases static/js/work_lock.js
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
/tmp/ats-web-slice-006-nir-receipt-lease-report.md
```

Incluir resumo, arquivos, snippets, testes, validações, riscos, atualização de `tasks.md`, commit hash e push.

Resposta final:

```text
REPORT_PATH=/tmp/ats-web-slice-006-nir-receipt-lease-report.md
```

Pare e peça confirmação antes do próximo slice.

## Prompt pronto para implementador

```text
Read AGENTS.md, PROJECT_CONTEXT.md and shared-work-queue-leases OpenSpec through Slice 006.
Implement ONLY Slice 006 using TDD.
Apply the existing Case lock service to NIR receipt confirmation: claim on case_detail for WAIT_R1_CLEANUP_THUMBS with context nir_receipt, hidden token, assert on confirm_receipt, heartbeat/release endpoints using existing work_lock.js, and list indicators for active locks on confirmable results. Do not change the NIR operational visibility rule from Slice 005.
Run validations, update tasks.md, create /tmp/ats-web-slice-006-nir-receipt-lease-report.md, commit and push, reply REPORT_PATH and stop.
```
