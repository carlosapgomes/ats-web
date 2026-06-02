# Slice 001: Campos de conselho profissional no usuário

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`, um monolito Django SSR. Antes de codar, leia obrigatoriamente:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/user-professional-council/proposal.md`
4. `openspec/changes/user-professional-council/design.md`
5. Este arquivo de slice

Implemente **somente este slice**. Não inicie outro slice. Siga TDD: primeiro adicione/ajuste testes que falhem, depois implemente o mínimo necessário, depois refatore com segurança.

## Objetivo

Adicionar dados facultativos de conselho profissional ao usuário, com choices restritas a `COREN` e `CRM`, edição na gestão de usuários e exibição compacta na listagem.

## Requisito funcional

Cada usuário pode ter opcionalmente:

- `professional_council`: conselho profissional, choices `COREN` ou `CRM`.
- `professional_council_number`: número do conselho profissional.

Validação obrigatória:

- os dois campos vazios são válidos;
- os dois campos preenchidos são válidos;
- preencher apenas um dos dois campos é inválido.

Exibição esperada na listagem de usuários:

```text
CRM 12345
COREN 67890
—
```

## Arquivos prováveis

Mantenha o slice enxuto. Arquivos previstos:

1. `apps/accounts/models.py`
2. `apps/accounts/migrations/000X_user_professional_council.py`
3. `apps/accounts/admin.py`
4. `apps/accounts/tests/test_models.py`
5. `apps/admin_ui/forms.py`
6. `templates/admin_ui/user_form.html`
7. `templates/admin_ui/user_list.html`
8. `apps/admin_ui/tests/test_users_crud.py`
9. `openspec/changes/user-professional-council/tasks.md`

Se precisar tocar mais arquivos, justifique no relatório do slice.

## Plano sugerido TDD

### RED

Adicione testes antes da implementação:

1. Em `apps/accounts/tests/test_models.py`:
   - usuário novo tem `professional_council == ""` e `professional_council_number == ""`;
   - `full_clean()` passa quando ambos vazios;
   - `full_clean()` passa quando `professional_council="CRM"` e `professional_council_number="12345"`;
   - `full_clean()` falha quando só conselho está preenchido;
   - `full_clean()` falha quando só número está preenchido.

2. Em `apps/admin_ui/tests/test_users_crud.py`:
   - create aceita `professional_council="CRM"` + número e persiste;
   - update aceita `professional_council="COREN"` + número e persiste;
   - form rejeita preenchimento parcial;
   - listagem mostra `CRM 12345` ou `COREN 67890`;
   - listagem mostra `—` para usuário sem registro profissional.

### GREEN

Implemente:

1. `apps/accounts/models.py`
   - importar `ValidationError` se necessário;
   - adicionar `ProfessionalCouncil(models.TextChoices)` dentro de `User` ou no módulo;
   - adicionar os dois campos opcionais;
   - implementar/estender `clean()` preservando comportamento de `AbstractUser` com `super().clean()`.

2. Migration
   - gerar com `uv run python manage.py makemigrations accounts --settings=config.settings.dev` ou criar manualmente seguindo padrão do projeto;
   - a migration deve ser aditiva e não exigir backfill.

3. `apps/accounts/admin.py`
   - incluir campos no Django Admin em `fieldsets`;
   - opcionalmente adicionar ao `list_display`.

4. `apps/admin_ui/forms.py`
   - incluir os campos em `UserCreateForm.Meta.fields` e `UserUpdateForm.Meta.fields`;
   - aplicar widgets Bootstrap:
     - `professional_council`: `form-select`;
     - `professional_council_number`: `form-control`.

5. `templates/admin_ui/user_form.html`
   - adicionar bloco visual para os dois campos após email ou após papéis;
   - renderizar erros por campo.

6. `templates/admin_ui/user_list.html`
   - adicionar coluna `Conselho`;
   - exibir `{{ u.professional_council }} {{ u.professional_council_number }}` quando ambos existirem;
   - caso contrário, `—`.

### REFACTOR

- Evite duplicação excessiva no template.
- Mantenha nomes claros e em português na UI.
- Não adicione filtros/busca por conselho neste slice.

## Critérios de sucesso

- [ ] Campos existem no modelo e na migration.
- [ ] Choices aceitam apenas `COREN` e `CRM`.
- [ ] Campos são opcionais quando ambos vazios.
- [ ] Validação impede preenchimento parcial.
- [ ] Create/update da gestão de usuários persiste os campos.
- [ ] Listagem mostra registro profissional ou `—`.
- [ ] Django Admin expõe os campos.
- [ ] Testes relevantes passam.
- [ ] `openspec/changes/user-professional-council/tasks.md` atualizado com status do slice.

## Gates de autoavaliação

Antes de finalizar, responda no relatório:

1. A migration é aditiva e segura para usuários existentes?
2. A validação está no modelo, não só no form?
3. O formulário administrativo chama a validação via `ModelForm`?
4. A UI continua SSR/Bootstrap, sem framework JS?
5. O slice evitou implementar filtros ou features fora de escopo?

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

1. Gere um relatório detalhado em markdown temporário, por exemplo:
   - `/tmp/ats-web-slice-001-user-professional-council-report.md`
2. O relatório deve conter:
   - resumo;
   - arquivos alterados;
   - snippets antes/depois dos pontos principais;
   - testes adicionados;
   - resultado dos comandos de validação;
   - respostas aos gates de autoavaliação.
3. Atualize `openspec/changes/user-professional-council/tasks.md` marcando o slice como concluído e incluindo commit/report.
4. Faça commit com mensagem rastreável, sugestão:

```bash
git add apps/accounts apps/admin_ui templates/admin_ui openspec/changes/user-professional-council
git commit -m "feat(accounts): add professional council fields to users"
git push
```

5. Responda ao usuário/planner somente com resumo curto e:

```text
REPORT_PATH=/tmp/ats-web-slice-001-user-professional-council-report.md
```

6. **Pare** e peça confirmação explícita antes de qualquer próximo slice.

## Prompt pronto para o implementador LLM

```text
Read AGENTS.md and PROJECT_CONTEXT.md first.
Implement ONLY openspec/changes/user-professional-council/slices/slice-001-user-professional-council.md.
Use vertical slicing end-to-end and TDD: RED failing tests, GREEN minimal implementation, REFACTOR safely.
Add optional User fields professional_council and professional_council_number with choices COREN/CRM and model-level validation requiring both or neither.
Expose fields in Django Admin and admin_ui user create/update forms; show compact value in admin_ui user list.
Do not add search/filter by council and do not implement multiple professional registrations.
Run ruff check, ruff format --check, mypy, pytest, and git status.
Update openspec/changes/user-professional-council/tasks.md, create a temporary markdown implementation report with before/after snippets, commit, push, then reply with REPORT_PATH and stop.
```
