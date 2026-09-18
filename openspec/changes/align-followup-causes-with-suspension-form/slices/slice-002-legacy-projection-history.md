# Slice 002 — Consolidar causas legadas no Histórico oficial

## Objetivo

Entregar uma leitura analítica única entre eras: tabela, cards, filtro e CSV exibem/agregam os quatro códigos/detalhes legados sob as causas oficiais confirmadas, sem alterar rows ou `CaseEvent`. O manual passa a ensinar somente o formulário e a taxonomia atuais.

## Pré-condição

Slice 001 implementado, aceito por review independente e com catálogo atual disponível. Não iniciar se o service ainda aceitar `absenteeism` ou `resource_shortage` para novas gravações.

## Contexto necessário

Ler antes de editar:

- `design.md`, D5–D7;
- delta `specs/supervisor-followup-history/spec.md`;
- `_FOLLOWUP_REASON_*`, `_followup_history_rows`, `_apply_line_filters`, `_followup_history_summary` e `followup_history_export` em `apps/dashboard/views.py`;
- cenários/fábricas em `apps/dashboard/tests/test_followup_history.py`;
- regras de pós-procedimento em `docs/manual/manual-usuarios.md` §6.1 e guards em `tests/test_user_manual_artifacts.py`;
- append-only e projeção pura em `apps/cases/followup.py`.

## Requisitos verificáveis

- **R1 — projeção pura:** uma fonte única converte `absenteeism`→`patient_no_show` e os três detalhes de `resource_shortage`→`emergency_priority|time_exceeded|missing_equipment`; causas atuais passam sem mudança. A função não faz writes.
- **R2 — superfícies alinhadas:** `_followup_history_rows` projeta antes de compor labels; tabela, cards e CSV usam labels oficiais, agregam eras equivalentes e não exibem submotivo para as rows projetadas.
- **R3 — filtro oficial:** opções contêm somente as 24 choices atuais, na ordem D1; `?reason=<oficial>` inclui rows atuais e legadas equivalentes; `absenteeism`/`resource_shortage` na querystring são inválidos e equivalem a filtro ausente.
- **R4 — auditoria intacta:** abrir Histórico, filtrar e exportar não altera códigos/detalhes persistidos, não modifica eventos existentes e não cria evento novo.
- **R5 — documentação:** manual lista exatamente as 23 causas oficiais + **Outras causas**, descreve o select/texto obrigatório e não orienta submotivo/Absenteísmo/Cancelamento por falta de recursos.
- **R6 — compatibilidade CSV:** endpoint, BOM, `;`, header e ordem de colunas permanecem; coluna `Submotivo` fica vazia para rows projetadas conhecidas e `Outra causa (texto)` mantém escaping.
- **R7 — desconhecido fail-closed:** causa/detalhe legado fora dos quatro mapeamentos retorna `legacy_unmapped`/**Causa legada não mapeada**, preserva códigos técnicos no detalhe diagnóstico, não aparece no filtro oficial e não recebe equivalência inventada. Preflight ORM termina diferente de zero se encontrar esse estado e bloqueia rollout.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `apps/cases/followup.py`, `apps/cases/tests/test_followup_services.py` | teste parametrizado dos quatro mapeamentos + pass-through atual |
| R2–R4/R6 | `apps/dashboard/views.py`, `apps/dashboard/tests/test_followup_history.py` | cenários de eras mistas em rows, summary, filtro e CSV + snapshots DB/eventos |
| R5 | `docs/manual/manual-usuarios.md`, `tests/test_user_manual_artifacts.py` | teste de catálogo/manual e ausência das instruções legadas na seção §6.1 |
| R7 | domain/view/tests já listados | fallback técnico em tabela/cards/CSV, ausência no filtro e comando de preflight com exit não zero |

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/cases/followup.py
  - apps/cases/tests/test_followup_services.py
  - apps/dashboard/views.py
  - apps/dashboard/tests/test_followup_history.py
  - docs/manual/manual-usuarios.md
  - tests/test_user_manual_artifacts.py

allowed_incidental_files: []

out_of_scope:
  - models, migration ou constraints
  - template/layout do formulário já entregue no Slice 001
  - mudança de endpoint/header/colunas do CSV
  - backfill ou qualquer save/update/delete de ProcedureFollowUp/CaseEvent
  - transformar legacy_unmapped em causa oficial ou opção de filtro
  - tasks.md, commit e push (responsabilidade do parent)
```

O fallback técnico de R7 pertence ao slice e não é uma quinta equivalência de negócio. Escalar se o preflight encontrar dado real não mapeável ou se a projeção exigir tocar template/model/migration; não liberar rollout até decisão humana.

## Plano de testes

### RED

Adicionar primeiro testes de projeção e eras mistas, então executar:

```bash
uv run pytest apps/cases/tests/test_followup_services.py -k "legacy_reason_projection or legacy_unmapped" -q
uv run pytest apps/dashboard/tests/test_followup_history.py -k "legacy_projection or official_reason_filter or legacy_unmapped" -q
uv run pytest tests/test_user_manual_artifacts.py -k "followup and reason" -q
```

Falhas esperadas antes da implementação: rows legadas ainda aparecem/agregam como Absenteísmo ou Cancelamento por falta de recursos; filtro oficial não encontra equivalentes; estado desconhecido não possui fallback técnico; manual ainda documenta as quatro causas antigas.

### GREEN / verificação local

```bash
uv run pytest apps/cases/tests/test_followup_services.py -q
uv run pytest apps/dashboard/tests/test_followup_history.py -q
uv run pytest tests/test_user_manual_artifacts.py -q
uv run pytest apps/dashboard/tests -q
uv run ruff check apps/cases/followup.py apps/cases/tests/test_followup_services.py apps/dashboard/views.py apps/dashboard/tests/test_followup_history.py tests/test_user_manual_artifacts.py
uv run ruff format --check apps/cases/followup.py apps/cases/tests/test_followup_services.py apps/dashboard/views.py apps/dashboard/tests/test_followup_history.py tests/test_user_manual_artifacts.py
```

Executar também o preflight read-only abaixo no banco de teste/staging. Ele deve sair `0`; saída não zero bloqueia rollout e exige escalonamento. Ajustar apenas o módulo de settings ao ambiente, nunca os conjuntos permitidos:

```bash
uv run python manage.py shell --settings=config.settings.test -c '
from django.db.models import Q
from apps.cases.models import CURRENT_FOLLOWUP_NON_PERFORMANCE_REASON_VALUES, ProcedureFollowUp
current = set(CURRENT_FOLLOWUP_NON_PERFORMANCE_REASON_VALUES)
known = Q(non_performance_reason__in=current | {"absenteeism"}) | Q(non_performance_reason="resource_shortage", resource_shortage_detail__in={"emergency_occupied", "insufficient_time", "equipment_unavailable"})
unknown = ProcedureFollowUp.objects.filter(performed=False).exclude(known)
print({"unmapped_count": unknown.count(), "sample_ids": list(unknown.values_list("pk", flat=True)[:20])})
raise SystemExit(1 if unknown.exists() else 0)
'
```

Inspeção complementar do manual limitada à seção de pós-procedimento:

```bash
rg -n "TCLE|Não comparecimento do paciente|Prioridade para urgência|Outras causas" docs/manual/manual-usuarios.md
```

## Critérios de aceitação

- [ ] R1–R7 demonstrados pelos testes/checks acima.
- [ ] Os quatro mapeamentos são exatamente os confirmados pelo owner.
- [ ] Rows/eventos antes e depois das leituras são idênticos.
- [ ] Nenhum arquivo fora do blast radius e nenhuma mudança de schema.

## Handoff

O worker deve retornar: arquivos alterados; evidência RED/GREEN; tabela curta com os quatro mapeamentos efetivamente testados; prova de imutabilidade das rows/eventos; resultado do preflight; riscos residuais. Parar e escalar se o preflight real encontrar dado não mapeável ou houver necessidade de alterar contrato estrutural do CSV.
