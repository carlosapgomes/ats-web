<!-- markdownlint-disable MD013 -->

# Slice 001: Resolução de lease por contexto (médico 1h)

## Handoff para implementador LLM com contexto zero

Você está no monolito Django SSR em `/projects/dev/ats-web`. Este é o **único slice** do change `doctor-decision-lock-lease-1h`. Não existe slice futuro a antecipar.

Leia integralmente, nesta ordem, antes de planejar ou editar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/doctor-decision-lock-lease-1h/proposal.md`
4. `openspec/changes/doctor-decision-lock-lease-1h/design.md`
5. `openspec/changes/doctor-decision-lock-lease-1h/specs/case-work-lock/spec.md`
6. `openspec/changes/doctor-decision-lock-lease-1h/tasks.md`
7. este arquivo
8. `apps/cases/services.py` — `_get_lease_seconds` (~linha 44), `claim_case_lock` (resolve `seconds = _get_lease_seconds(lease_seconds)` logo no início), `renew_case_lock` (mesma resolução), `assert_case_lock`, `release_case_lock`
9. `config/settings/base.py` — bloco `# Case lock / lease settings` com `CASE_LOCK_LEASE_SECONDS`, `CASE_LOCK_HEARTBEAT_SECONDS`, `CASE_LOCK_ACTIVITY_GRACE_SECONDS`
10. `apps/cases/tests/test_lock_service.py` — helpers `_create_role`/`_advance_to` e classes `TestClaimCaseLock`/renew existentes
11. `apps/doctor/views.py` — somente leitura: `doctor_decision_page` (claim com `context="doctor_decision"`), `doctor_lock_renew` (renew com `context="doctor_decision"`)
12. `apps/doctor/tests/test_views.py` — testes existentes de lock/decision para copiar o setup (login como doctor, caso em `WAIT_DOCTOR`, GET da página de decisão)
13. `static/js/work_lock.js` — somente leitura, para entender o heartbeat; **não editar**

### Estado atual esperado

- `_get_lease_seconds(override: int | None) -> int`: retorna `override` se informado, senão `getattr(settings, "CASE_LOCK_LEASE_SECONDS", 300)`. Não conhece `context`.
- `claim_case_lock(*, case_id, user, expected_status, context, role, lease_seconds=None)` e `renew_case_lock(*, case_id, user, token, context, lease_seconds=None)` já recebem `context` e só não o usam para o lease.
- Contextos em produção: `doctor_decision` (apps/doctor/views.py), `nir_receipt` (apps/intake/views.py), `scheduler_confirm` (apps/scheduler/views.py).
- As views **não** passam `lease_seconds`; só testes usam (ex.: `lease_seconds=0` para forçar expiração).
- Não existe spec promovida para o lock; este change cria a capacidade `case-work-lock`.

Se qualquer premissa divergir, registre no relatório antes de editar. Se houver worktree sujo, baseline vermelho ou necessidade de JS/template/migration/FSM, reporte **INCOMPLETE/BLOQUEADO** e pare em vez de improvisar.

## Fluxo vertical a entregar

```text
Médico abre a página de decisão (GET /doctor/<id>/decision/)
→ claim_case_lock(context="doctor_decision") resolve lease 3600s
→ Case.locked_until ≈ now + 1h
→ heartbeat (work_lock.js, inalterado) renova para ≈ now + 1h
→ NIR/scheduler continuam com lease de 300s
→ lease_seconds explícito (testes) continua vencendo
```

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 Resolução por contexto com precedência | `apps/cases/services.py`, `config/settings/base.py`, `apps/cases/tests/test_lock_service.py` | testes de claim: doctor ≈3600, nir ≈300, scheduler ≈300, override=120 vence |
| R2 Renew usa a mesma resolução | `apps/cases/services.py`, `apps/cases/tests/test_lock_service.py` | renew doctor ≈ now+3600; renew de expirado falha (já coberto — mantenha verde) |
| R3 Prova vertical na view médica | `apps/doctor/tests/test_views.py` | GET decisão → `locked_until - now` ∈ [3500, 3600]s |
| R4 Sem expansão | — | `git diff --stat` limitado a `apps/cases/services.py`, `config/settings/base.py`, `apps/cases/tests/test_lock_service.py`, `apps/doctor/tests/test_views.py` |

## Requisitos verificáveis

### R1. `_get_lease_seconds` por contexto

- Adicionar mapping `_CONTEXT_LEASE_SETTINGS: dict[str, str] = {"doctor_decision": "CASE_LOCK_LEASE_SECONDS_DOCTOR"}` e estender a assinatura para `_get_lease_seconds(override: int | None = None, context: str | None = None) -> int` com precedência: override explícito > setting por contexto (via `getattr`) > `CASE_LOCK_LEASE_SECONDS`.
- Atualizar os dois call sites (`claim_case_lock` e `renew_case_lock`) para `seconds = _get_lease_seconds(lease_seconds, context=context)`.
- Adicionar `CASE_LOCK_LEASE_SECONDS_DOCTOR = 60 * 60` ao bloco `# Case lock / lease settings` de `config/settings/base.py`, com comentário curto de fallback.
- Testes de serviço com `override_settings(CASE_LOCK_LEASE_SECONDS_DOCTOR=3600)` usando tolerância em segundos (estilo do arquivo: `timedelta`), sem igualdade exata de relógio.

### R2. Renew consistente

- Teste: lock `doctor_decision` ativo → renew bem-sucedido → novo `locked_until ≈ now + 3600s`.
- Garantir que o teste existente de renew em lock expirado (e de takeover com `lease_seconds=0`) continua verde — não altere esses comportamentos.

### R3. Prova vertical na view

- Em `apps/doctor/tests/test_views.py`, novo teste (copiando setup existente de decisão): login doctor, caso `WAIT_DOCTOR`, GET na página de decisão retorna 200 e `Case.objects.get(...).locked_until - timezone.now()` fica entre 3500s e 3600s.
- Nenhuma alteração em `apps/doctor/views.py` deve ser necessária; se parecer necessária, é provável erro de implementação em R1 — reavalie antes de tocar a view.

### R4. Sem expansão

- Verificação por `git status --short` + `git diff --stat`: somente os 4 arquivos previstos (e artefatos deste change em `openspec/`).
- `static/js/work_lock.js`, templates e `apps/doctor/views.py` intocados.

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/cases/services.py
  - config/settings/base.py
  - apps/cases/tests/test_lock_service.py
  - apps/doctor/tests/test_views.py

allowed_incidental_files: []

out_of_scope:
  - alterar work_lock.js, templates, CSS, URLs, permissões
  - alterar CASE_LOCK_HEARTBEAT_SECONDS ou CASE_LOCK_ACTIVITY_GRACE_SECONDS
  - alterar contexts nir_receipt/scheduler_confirm ou seus tempos
  - mudar assinaturas públicas de claim/renew (além do parâmetro interno de _get_lease_seconds)
  - FSM, CaseEvent, migrations, env vars
```

Escale em vez de ampliar silenciosamente se precisar tocar qualquer arquivo fora da lista — em especial se achar que deve editar `apps/doctor/views.py` ou JS.

## Plano de testes do slice

### Baseline (antes de editar)

1. `git status --short` limpo (ignorando apenas as deleções pré-existentes não relacionadas em `.pi/skills/`); registre branch `change/doctor-decision-lock-lease-1h` criada a partir de `main` atualizado e `BASE_REF=$(git rev-parse HEAD)`.
2. `uv run pytest` — registre exit code e totais. Falha/erro pré-existente → pare e reporte bloqueio.

### RED

- Comando: `uv run pytest apps/cases/tests/test_lock_service.py -k "context_lease" -x`
- Escreva primeiro os testes novos de R1 (classe `TestContextLeaseResolution` ou nomes com `context_lease`) antes de qualquer edição de produção.
- Falha esperada: `assert` de `locked_until ≈ now + 3600s` falha porque o lease resolvido ainda é 300s (delta ≈ 300 ≠ 3600). RED por import/fixture não conta.

### GREEN / verificação local

- `uv run pytest apps/cases/tests/test_lock_service.py -k "context_lease"` — exit code 0.
- `uv run pytest apps/cases/tests/test_lock_service.py` — exit code 0 (regras de claim/renew/takeover intactas).
- `uv run pytest apps/doctor/tests/test_views.py -k "lock"` — exit code 0 (inclui o novo teste vertical).
- `uv run ruff check apps/cases config` e `uv run ruff format --check apps/cases config` — exit code 0.
- `uv run mypy apps/cases` — exit code 0.
- Inspeção: `rg -n "_get_lease_seconds" apps/cases/services.py` — os dois call sites (claim e renew) devem passar `context`.

### Gate final do change (após GREEN)

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

Pytest final: exit code 0, zero failures/errors, `passed_final >= passed_baseline`. Atenção especial: nenhuma regressão em `apps/intake`/`apps/scheduler` (locks desses contextos seguem em 300s).

## Critérios de aceitação

- [x] R1: precedência override > contexto > global comprovada nos 4 cenários de claim.
- [x] R2: renew médico estende ≈ 1h; renovar expirado continua falhando; takeover com `lease_seconds=0` verde.
- [x] R3: GET da decisão médica deixa `locked_until` em [3500, 3600]s.
- [x] R4: diff limitado aos 4 arquivos; JS/views intocados.
- [x] RED/GREEN comprovados no relatório; gate final completo verde.

> Loop parent-controlled concluído em 2026-09-05: reviewer `Merge verdict: OK`
> (0 findings). Conclusão (tasks.md, relatório, commit) executada pelo parent.

## Conclusão controlada

Somente após todos os gates: marque o Slice 001 e os itens comprovados em `tasks.md`, gere o relatório em `/tmp/doctor-decision-lock-lease-1h-slice-001-report.md` (baseline, RED/GREEN, snippets antes/depois, inspeções, gates, rerun, `Handoff para verificador`), faça commit rastreável (`feat(cases): one-hour doctor_decision lock lease`), push da branch, atualize o relatório com hash/push, responda com `REPORT_PATH` e **pare**.
