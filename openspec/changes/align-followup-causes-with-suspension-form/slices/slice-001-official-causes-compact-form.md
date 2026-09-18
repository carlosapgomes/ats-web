# Slice 001 — Registrar causas oficiais em formulário compacto

## Objetivo

Entregar o fluxo observável de nova gravação: o supervisor marca **Não realizado**, escolhe uma das 23 causas oficiais em um `select` compacto ou **Outras causas** com texto, e o sistema persiste/eventa apenas códigos atuais. Códigos legados continuam reconhecíveis no storage, mas são rejeitados para novas versões.

## Contexto necessário

Ler antes de editar:

- `design.md`, D1–D4 e D7 — catálogo/códigos, separação storage×entrada, validação e UI;
- `apps/cases/models.py`, de `FollowUpNonPerformanceReason` até `ProcedureFollowUp`;
- `apps/cases/followup.py::_validate_outcomes` e `record_case_follow_up`;
- `apps/dashboard/forms.py::FollowUpForm`;
- bloco `data-followup-reason-section` em `templates/dashboard/followup_form.html`;
- `static/js/followup_form.js`;
- testes atuais em `apps/cases/tests/test_followup_services.py`, `apps/dashboard/tests/test_followup_form_view.py` e helpers/cenários legados de `apps/dashboard/tests/test_followup_history.py`.

Restrições: o service permanece autoritativo; JS é apenas apresentação; registros/eventos existentes não podem ser atualizados; cobertura por procedimento autorizado e versionamento não mudam.

## Requisitos verificáveis

- **R1 — catálogo:** model state reconhece os códigos legados persistidos e as 24 choices atuais de D1; uma constante atual ordenada é a única fonte das choices de entrada. `inadequate_prep`/`other` preservam seus códigos; nenhum código excede 30 caracteres.
- **R2 — validação/gravação:** cada uma das 23 causas oficiais é aceita sem submotivo/texto; `other` exige texto; qualquer outra causa rejeita texto; todo submotivo é rejeitado em nova gravação; `absenteeism`, `resource_shortage`, vazio e desconhecido são rejeitados sem persistência/evento.
- **R3 — UI compacta:** cada bloco renderiza um único `<select>` Bootstrap com placeholder, ordem/labels exatos e **Outras causas** por último; não renderiza rádios de causa nem opções legadas. Selecionar `other` revela textarea; marcar **Realizado** desabilita e limpa a seleção; load e re-render pós-erro preservam estado coerente.
- **R4 — migration não destrutiva:** criar migration `0020` contendo somente alteração de metadados do field de causa; sem `RunPython`, remoção de coluna/constraint ou transformação de dados. Teste com `MigrationExecutor` percorre `0019 → 0020 → 0019 → 0020` e prova preservação de row legada.
- **R5 — fixtures históricas coerentes:** cenários do Histórico que representam `absenteeism`/`resource_shortage` deixam de chamar `record_case_follow_up` e usam helper explícito de fixture legada via ORM; expectativas do Histórico continuam antigas neste slice. A suíte inteira de Histórico passa ao final.
- **R6 — não regressão:** `performed=True`, internação, múltiplos procedimentos autorizados, versionamento e snapshots de evento permanecem com o comportamento existente.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `apps/cases/models.py`, migration `0020` | novos testes de catálogo + `makemigrations --check` |
| R2 | `apps/cases/followup.py`, `apps/cases/tests/test_followup_services.py` | parametrização das 24 choices e rejeição dos legados |
| R3 | `apps/dashboard/forms.py`, template, JS, `test_followup_form_view.py` | GET/POST renderizado + `node --check` |
| R4 | migration `0020`, novo teste de migration | inspeção sem operações destrutivas + ida/volta com `MigrationExecutor` |
| R5 | `apps/dashboard/tests/test_followup_history.py` | fixtures legadas diretas + suíte de Histórico verde sem mudar labels ainda |
| R6 | fontes/testes acima | suítes focadas completas de follow-up service/form/history |

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/cases/models.py
  - apps/cases/migrations/0020_alter_procedurefollowup_non_performance_reason.py
  - apps/cases/followup.py
  - apps/cases/tests/test_followup_services.py
  - apps/dashboard/forms.py
  - templates/dashboard/followup_form.html
  - static/js/followup_form.js
  - apps/dashboard/tests/test_followup_form_view.py
  - apps/dashboard/tests/test_followup_history.py
  - apps/cases/tests/test_followup_reason_migration.py

allowed_incidental_files: []

out_of_scope:
  - projeção/normalização do Histórico, cards, filtros e CSV (Slice 002)
  - remoção de resource_shortage_detail ou constraints
  - CSS customizado, autocomplete, dependência frontend
  - FSM, elegibilidade, roles, cobertura de procedimentos, eventos novos
  - tasks.md, commit e push (responsabilidade do parent)
```

O blast radius excede cinco arquivos porque este slice fecha, de ponta a ponta, model state → validação → form SSR → comportamento JS → persistência/evento e mantém as fixtures históricas compatíveis com a nova autoridade de escrita. Não separar por camada. Escalar antes de tocar qualquer arquivo adicional ou alterar schema físico/constraints.

## Plano de testes

### RED

1. Adicionar primeiro testes com nomes/filtros inequívocos para catálogo oficial, rejeição legada e select compacto.
2. Executar:

```bash
uv run pytest apps/cases/tests/test_followup_services.py -k "official_reason or legacy_reason" -q
uv run pytest apps/dashboard/tests/test_followup_form_view.py -k "official_reason or compact_reason_select or legacy_reason" -q
```

Falhas esperadas antes da implementação: choices oficiais ausentes, service ainda aceita `absenteeism`/`resource_shortage`, HTML ainda contém rádios/submotivo em vez de select e ainda não existe prova de ida/volta da migration. Depois de tornar o service estrito, a suíte de Histórico deve inicialmente expor as fixtures legadas que ainda chamam o service; corrigi-las diretamente, sem antecipar a projeção do Slice 002.

### GREEN / verificação local

```bash
uv run pytest apps/cases/tests/test_followup_services.py -q
uv run pytest apps/dashboard/tests/test_followup_form_view.py -q
uv run pytest apps/dashboard/tests/test_followup_history.py -q
uv run pytest apps/cases/tests/test_followup_reason_migration.py -q
uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test
node --check static/js/followup_form.js
uv run ruff check apps/cases/models.py apps/cases/followup.py apps/cases/tests/test_followup_services.py apps/cases/tests/test_followup_reason_migration.py apps/dashboard/forms.py apps/dashboard/tests/test_followup_form_view.py apps/dashboard/tests/test_followup_history.py
uv run ruff format --check apps/cases/models.py apps/cases/followup.py apps/cases/tests/test_followup_services.py apps/cases/tests/test_followup_reason_migration.py apps/dashboard/forms.py apps/dashboard/tests/test_followup_form_view.py apps/dashboard/tests/test_followup_history.py
```

Check estrutural complementar, pois a ausência de operação destrutiva não é bem expressa pelos testes:

```bash
! rg -n "RunPython|RemoveField|RemoveConstraint|DeleteModel" apps/cases/migrations/0020_*.py
```

## Critérios de aceitação

- [ ] R1–R6 demonstrados pelos testes/checks acima.
- [ ] Lista e ordem visual correspondem exatamente a D1.
- [ ] Nenhuma row/evento legado é atualizado.
- [ ] Diff restrito ao blast radius e sem trabalho do Slice 002.

## Handoff

O worker deve retornar: arquivos alterados; comandos RED com falha esperada; comandos GREEN/verificação com exit code; confirmação de que a migration é metadata-only e reversível antes de writes; lista dos testes de Histórico adaptados para fixture legada direta; riscos residuais. Parar e escalar se Django gerar qualquer operação além de `AlterField`, se a ida/volta alterar dados, ou se a UI exigir CSS/dependência nova.
