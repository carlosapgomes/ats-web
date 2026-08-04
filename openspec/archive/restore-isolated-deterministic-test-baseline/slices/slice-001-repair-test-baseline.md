<!-- markdownlint-disable MD013 -->

# Slice 001: Isolar settings de teste e eliminar regressão temporal flakey

## Handoff para implementador LLM com contexto zero

Este slice é um pré-requisito independente. **Não implemente nem altere o workflow GHCR.**

Leia integralmente antes de editar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/restore-isolated-deterministic-test-baseline/proposal.md`
4. `openspec/changes/restore-isolated-deterministic-test-baseline/design.md`
5. `openspec/changes/restore-isolated-deterministic-test-baseline/tasks.md`
6. este arquivo
7. `config/settings/base.py`
8. `config/settings/test.py`
9. `config/settings/db.py`
10. `config/settings/tests/test_db.py`
11. `apps/dashboard/tests/test_dashboard.py` em `TestDashboardBadgeCompactoProximoPasso`
12. `templates/dashboard/_case_list.html`

Estado atual:

- `base.py` chama `load_dotenv()`, mas você **não deve ler, imprimir ou alterar `.env`**.
- `test.py` chama `get_db_config()`, que prioriza `DATABASE_URL` e lê `DB_*` genéricos.
- O comando canônico pode apontar para `ats_web_dev`/5432 em vez de `ats_web_test`/5433.
- O template localiza `created_at` para `America/Bahia` com `date:"d/m/Y H:i"`.
- O teste usa `case.created_at.strftime()` diretamente e falha na janela UTC/local de troca de data.
- A aplicação está correta; os defeitos estão no boundary de settings de teste e na expectativa do teste.

## Protocolo obrigatório para DeepSeek4-Flash

Este slice repara o próprio baseline. Portanto, a regra normal “baseline inicial deve estar verde” tem uma **exceção explícita e limitada**: baseline vermelho pelo teste temporal conhecido ou configuração apontando para DB incorreto é evidência RED deste change. Nenhuma outra falha é aceitável.

1. **Plano antes de editar**: registre no relatório a matriz `R1..R6 → arquivos → testes/inspeções`.
2. **Worktree limpo**: rode `git status --short`, registre `BASE_REF=$(git rev-parse HEAD)`. Se houver alteração não pertencente aos artefatos já commitados, pare como INCOMPLETE.
3. **Não acessar segredos**: não abra `.env`, não imprima `PASSWORD`, DSN ou URLs completas. Inspeções de settings podem mostrar apenas `ENGINE`, `HOST`, `PORT`, `NAME`, `USER`.
4. **Baseline diagnóstico**:
   - prove sem conexão que o comando canônico seleciona hoje o DB errado, imprimindo somente campos não sensíveis;
   - rode o baseline isolado conhecido com `DATABASE_URL="" uv run pytest` e registre resumo. A única falha tolerada nessa fase é `test_regression_date_time_present`; qualquer outra falha/error bloqueia o slice.
5. **RED A real**: crie primeiro os testes subprocess de settings e mostre que falham porque variáveis genéricas vencem.
6. **RED B real e determinístico**: fixe o datetime do teste do dashboard em `2026-07-26 00:37 UTC`, mantenha temporariamente a expectativa UTC e mostre falha `26/07` versus `25/07 21:37`. RED por sintaxe/import/infra não vale.
7. **GREEN mínimo**: restaure `TEST_DATABASE_URL` em `test.py` e corrija apenas a expectativa do teste com `timezone.localtime()`.
8. **REFACTOR**: clean code, DRY e YAGNI. Não crie framework de settings, não altere helper de produção, não faça refactor amplo no arquivo de dashboard.
9. **Inspeções e quality gate**: execute todos os checks deste slice. O gate final deve usar exatamente `uv run pytest`, sem `DATABASE_URL=""`, e terminar com exit code 0, zero failures/errors.
10. **Conclusão**: somente com tudo verde, marque `tasks.md`, gere relatório, commit/push e pare. Se qualquer gate falhar, não marque tasks nem commit/push; reporte INCOMPLETE.

## Objetivo vertical

```text
uv run pytest
→ settings test isolados, mesmo com env genérico hostil
→ banco test default ou TEST_DATABASE_URL explícita
→ teste temporal independente do relógio
→ suíte completa verde
```

## Requisitos

### R1. Default de teste ignora variáveis genéricas

Em `config/settings/test.py`, restaurar configuração com `dj_database_url.config(..., env="TEST_DATABASE_URL")` e default:

```text
postgres://ats_web:<senha-de-teste-existente>@localhost:${POSTGRES_TEST_HOST_PORT:-5433}/ats_web_test
```

Preserve a senha de teste já versionada no arquivo/histórico; não busque nem copie segredo de `.env`.

Com `DATABASE_URL` e `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD` presentes, o resultado deve continuar:

- `HOST=localhost`;
- `PORT=5433` quando `POSTGRES_TEST_HOST_PORT=5433`;
- `NAME=ats_web_test`;
- `USER=ats_web`.

Remover `from config.settings.db import get_db_config` de `test.py`. Não alterar `db.py`.

### R2. Override explícito por `TEST_DATABASE_URL`

Quando `TEST_DATABASE_URL` estiver definida, ela deve vencer o default test. Variáveis genéricas continuam ignoradas.

O teste deve provar host, port, name e user customizados sem imprimir password/URL.

### R3. Testes subprocess-isolated

Criar `config/settings/tests/test_test_settings.py` usando somente stdlib e pytest existente.

Use subprocesso com `sys.executable`, `DJANGO_SETTINGS_MODULE=config.settings.test` e código curto que importa Django settings e imprime JSON contendo somente:

```text
ENGINE, HOST, PORT, NAME, USER
```

Testes mínimos:

1. `test_test_settings_ignore_generic_database_environment`;
2. `test_test_settings_honor_test_database_url`.

No primeiro, injete valores genéricos hostis e remova `TEST_DATABASE_URL`. No segundo, injete ambos e prove que `TEST_DATABASE_URL` vence.

Não conectar ao PostgreSQL. Não imprimir/capturar senha em assertion message.

### R4. Regressão temporal determinística

Em `test_regression_date_time_present`:

- usar `datetime(2026, 7, 26, 0, 37, tzinfo=UTC)`;
- persistir via `Case.objects.filter(pk=case.pk).update(created_at=fixed_utc)`;
- calcular `expected_local = timezone.localtime(fixed_utc).strftime("%d/%m/%Y %H:%M")`;
- provar explicitamente `expected_local == "25/07/2026 21:37"`;
- confirmar `expected_local in response.content.decode()`.

Use `UTC` da stdlib de modo coerente com o arquivo. Não use `timezone.now()`, freezegun ou mock do relógio.

### R5. Não mascarar falhas

Não adicionar:

- `pytest.mark.xfail`;
- `pytest.mark.skip`/`skipif`;
- retry de teste;
- tolerância de datas alternativas;
- `DATABASE_URL=""` em configuração pytest/AGENTS;
- alteração de timezone global;
- catches que transformem falha em pass.

### R6. Escopo mínimo

Arquivos funcionais permitidos:

1. `config/settings/test.py`;
2. `config/settings/tests/test_test_settings.py`;
3. `apps/dashboard/tests/test_dashboard.py`.

Mais `openspec/changes/restore-isolated-deterministic-test-baseline/tasks.md` apenas após gates.

Proibido alterar `base.py`, `db.py`, `dev.py`, `prod.py`, `.env`, Compose, templates, views, models, migrations e qualquer arquivo do change GHCR.

## TDD obrigatório

### Preparação e diagnóstico

```bash
git status --short
BASE_REF=$(git rev-parse HEAD)
printf 'BASE_REF=%s\n' "$BASE_REF"

uv run python - <<'PY'
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
import django
django.setup()
from django.conf import settings
cfg = settings.DATABASES["default"]
print({key: cfg.get(key) for key in ("ENGINE", "HOST", "PORT", "NAME", "USER")})
PY

DATABASE_URL='' uv run pytest
```

O primeiro Python não pode imprimir password/URL. Registre que o diagnóstico pré-fix aponta para DB genérico. No pytest diagnóstico, somente a falha temporal conhecida pode ser tolerada; qualquer outra falha/error bloqueia.

### RED A — isolamento

1. Crie `config/settings/tests/test_test_settings.py`.
2. Execute antes de editar `test.py`:

```bash
uv run pytest config/settings/tests/test_test_settings.py -v
```

Os novos testes devem falhar semanticamente porque o settings atual aceita env genérico ou ignora `TEST_DATABASE_URL`.

### RED B — timezone

1. Altere o arrange do teste existente para persistir `2026-07-26 00:37 UTC`.
2. Antes de usar `timezone.localtime`, mantenha expectativa UTC `%d/%m/%Y %H:%M`.
3. Rode:

```bash
DATABASE_URL='' uv run pytest apps/dashboard/tests/test_dashboard.py::TestDashboardBadgeCompactoProximoPasso::test_regression_date_time_present -vv
```

Registre a falha determinística: expectativa UTC em 26/07 não corresponde ao HTML local `25/07/2026 21:37`.

### GREEN

- Restaure `dj_database_url.config(..., env="TEST_DATABASE_URL")` em `test.py`.
- Troque somente a expectativa temporal para `timezone.localtime(fixed_utc)`.

Execute sem workaround:

```bash
uv run pytest config/settings/tests/test_test_settings.py -v
uv run pytest apps/dashboard/tests/test_dashboard.py::TestDashboardBadgeCompactoProximoPasso::test_regression_date_time_present -vv
```

### REFACTOR

- helper subprocess pequeno e coeso no teste;
- nomes claros;
- sem duplicar preparação de env hostil entre testes quando um helper local simples bastar;
- sem abstração genérica fora do arquivo de teste;
- diff temporal restrito a um único teste.

Rode os alvos novamente após refactor.

## Inspeções obrigatórias

### I1. Configuração efetiva final sem segredo

```bash
uv run python - <<'PY'
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
import django
django.setup()
from django.conf import settings
cfg = settings.DATABASES["default"]
public = {key: cfg.get(key) for key in ("ENGINE", "HOST", "PORT", "NAME", "USER")}
print(public)
assert str(public["PORT"]) == os.environ.get("POSTGRES_TEST_HOST_PORT", "5433")
assert public["NAME"] == "ats_web_test"
assert public["HOST"] == "localhost"
PY
```

Deve passar sem `DATABASE_URL=''`.

### I2. Contratos por busca

```bash
rg -n 'dj_database_url|TEST_DATABASE_URL|POSTGRES_TEST_HOST_PORT|ats_web_test' config/settings/test.py config/settings/tests/test_test_settings.py
rg -n '2026, 7, 26, 0, 37|timezone\.localtime|25/07/2026 21:37' apps/dashboard/tests/test_dashboard.py

if rg -n 'xfail|skipif|pytest\.mark\.skip' \
  config/settings/test.py config/settings/tests/test_test_settings.py apps/dashboard/tests/test_dashboard.py; then
  echo 'ERRO: xfail/skip encontrado'
  exit 1
else
  echo 'OK: sem xfail/skip'
fi

if rg -n "DATABASE_URL=''|DATABASE_URL=\"\"" \
  config/settings/test.py config/settings/tests/test_test_settings.py apps/dashboard/tests/test_dashboard.py; then
  echo 'ERRO: workaround de DATABASE_URL vazia encontrado'
  exit 1
else
  echo 'OK: sem workaround de DATABASE_URL vazia'
fi
```

Interprete ocorrências; confirme que `DATABASE_URL` aparece nos testes apenas como input hostil, não como workaround.

### I3. Escopo

```bash
git diff --check
git diff --name-only "$BASE_REF" -- | sort
git status --short
```

Lista máxima final:

```text
apps/dashboard/tests/test_dashboard.py
config/settings/test.py
config/settings/tests/test_test_settings.py
openspec/changes/restore-isolated-deterministic-test-baseline/tasks.md
```

Qualquer outro arquivo torna o slice INCOMPLETE.

## Critérios binários de sucesso

- [ ] Worktree inicial limpo e `BASE_REF` registrado.
- [ ] Diagnóstico inicial registrou somente campos não sensíveis.
- [ ] Baseline diagnóstico foi registrado; nenhuma falha diferente da temporal conhecida apareceu.
- [ ] RED A falhou pelo vazamento de env genérico.
- [ ] RED B falhou deterministicamente pela diferença UTC/local.
- [ ] `test.py` usa `TEST_DATABASE_URL` e ignora env genérico.
- [ ] Default é `ats_web_test`/porta test configurável.
- [ ] Dois testes subprocess passam sem conexão DB e sem segredo em output.
- [ ] Teste temporal usa instante fixo e `timezone.localtime()`.
- [ ] Nenhum xfail/skip/retry/workaround foi adicionado.
- [ ] Inspeção final sem prefixo confirma `localhost:5433/ats_web_test`.
- [ ] Arquivos alterados coincidem exatamente com R6.
- [ ] Quality gate completo passa sem prefixo de env.
- [ ] Pytest final tem exit code 0, failed=0, errors=0.
- [ ] Relatório completo, commit e push concluídos.

## Gates de autoavaliação

Responder no relatório com evidência:

1. Qual DB/porta o comando canônico selecionava antes? Mostre apenas campos não sensíveis.
2. Por que `load_dotenv()` não pode fazer `DATABASE_URL` genérica vencer no settings de teste?
3. Qual variável é o override explícito permitido?
4. O teste hostil cobre tanto `DATABASE_URL` quanto `DB_*`?
5. O subprocess abre conexão com banco? A resposta correta é não.
6. Algum password/DSN foi impresso? A resposta correta é não.
7. Qual instante UTC foi fixado e qual horário/data local ele representa?
8. Por que o template não foi alterado?
9. Qual teste prova que `TEST_DATABASE_URL` ainda funciona?
10. Há xfail/skip/tolerância de duas datas/workaround? A resposta correta é não.
11. O `uv run pytest` final foi executado exatamente, sem prefixo?
12. Produção/dev/helper DB permaneceram inalterados?
13. Quais arquivos mudaram desde `BASE_REF`?
14. O change GHCR foi tocado/implementado? A resposta correta é não.

## Condições automáticas de INCOMPLETO

Marque INCOMPLETE, não atualize tasks e não faça commit/push se:

- acessar, imprimir ou alterar `.env`;
- imprimir password, DSN ou URL completa;
- baseline diagnóstico tiver falha adicional à temporal conhecida;
- RED A ou RED B não for capturado pelo motivo esperado;
- `test.py` continuar aceitando `DATABASE_URL`/`DB_*` genéricos;
- `TEST_DATABASE_URL` deixar de funcionar;
- teste subprocess conectar ao banco ou depender de container;
- timezone continuar dependente de `now()`;
- template/view/app for alterado para satisfazer teste;
- xfail/skip/retry/workaround for adicionado;
- arquivo fora de R6 mudar;
- qualquer inspeção obrigatória faltar/falhar;
- qualquer comando do quality gate falhar;
- pytest final tiver exit code != 0, failure ou error;
- `uv run pytest` final usar `DATABASE_URL=''`;
- relatório temporário ou handoff ao verificador faltar.

## Quality gate final obrigatório

Executar separadamente e registrar exit codes:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

O último comando deve ser exatamente esse. Não prefixar, limpar ou sobrescrever variáveis.

## Relatório obrigatório

Criar:

```text
/tmp/restore-isolated-deterministic-test-baseline-slice-001-report.md
```

O relatório deve conter:

- `Status: COMPLETE | INCOMPLETE`;
- branch, `BASE_REF`, commit e push;
- matriz requisito → arquivo → teste/inspeção;
- diagnóstico pré-fix sem segredo;
- baseline diagnóstico e eventual única falha conhecida;
- RED A e RED B com comandos, exit codes e trechos;
- GREEN e REFACTOR;
- snippets antes/depois de `test.py` e do teste temporal;
- resultados dos dois testes subprocess;
- inspeção final do DB somente com campos públicos;
- outputs/interpretação de `rg`, diff e escopo;
- quality gate completo;
- respostas aos 14 gates;
- riscos/limitações;
- seção `Handoff para verificador` com arquivos, commit, comandos de rerun e checklist R1–R6.

Comandos de rerun para o verificador:

```bash
uv run pytest config/settings/tests/test_test_settings.py -v
uv run pytest apps/dashboard/tests/test_dashboard.py::TestDashboardBadgeCompactoProximoPasso::test_regression_date_time_present -vv
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
git show --stat --oneline HEAD
```

## Prompt pronto para enviar ao implementador

```text
Read completely: AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/restore-isolated-deterministic-test-baseline/proposal.md, design.md, tasks.md and slices/slice-001-repair-test-baseline.md. Also inspect config/settings/{base,test,db}.py, config/settings/tests/test_db.py, the class TestDashboardBadgeCompactoProximoPasso in apps/dashboard/tests/test_dashboard.py, and templates/dashboard/_case_list.html.

Implement ONLY this prerequisite slice. Do not implement or modify the GHCR workflow/change.

This slice repairs the baseline itself, so follow its special protocol: clean worktree and BASE_REF; diagnose the current selected DB without printing password/URL; run the documented diagnostic baseline; capture RED A with subprocess-isolated settings tests; capture deterministic RED B at 2026-07-26 00:37 UTC; then GREEN and REFACTOR. The only initial baseline failure tolerated is the already identified test_regression_date_time_present; any other failure blocks the slice.

Restore config.settings.test isolation using dj_database_url.config(..., env="TEST_DATABASE_URL") with the existing localhost/${POSTGRES_TEST_HOST_PORT:-5433}/ats_web_test default. Generic DATABASE_URL and DB_* must not affect tests. Add config/settings/tests/test_test_settings.py with subprocess tests proving generic env is ignored and TEST_DATABASE_URL is honored. Never read/modify .env and never print PASSWORD, DSN or full URLs.

Make only test_regression_date_time_present deterministic: persist created_at=2026-07-26 00:37:00 UTC, compute expected output with timezone.localtime(), prove it equals 25/07/2026 21:37, and assert it appears in HTML. Do not alter template/view/application behavior.

Use TDD RED -> GREEN -> REFACTOR, clean code, DRY and YAGNI. Do not add xfail, skip, retries, alternative-date tolerance, env workaround, dependency, helper redesign or broad refactor. Allowed functional files are only config/settings/test.py, config/settings/tests/test_test_settings.py and apps/dashboard/tests/test_dashboard.py; update this change's tasks.md only after all gates pass.

Run every inspection in the slice and the final quality gate exactly: uv run ruff check .; uv run ruff format --check .; uv run mypy .; uv run pytest. The final pytest must run without DATABASE_URL="" or any prefix and finish exit code 0 with zero failures/errors.

If any required RED/check/gate is missing, any secret is exposed, any extra file changes, or final pytest fails, report INCOMPLETE and do not update tasks.md or commit/push.

If all criteria pass, create /tmp/restore-isolated-deterministic-test-baseline-slice-001-report.md with diagnostic baseline, RED A/B, GREEN, before/after snippets, inspections, full quality gate, self-evaluation and Handoff para verificador. Update tasks.md, commit with a traceable message such as `fix(test): restore isolated deterministic baseline`, push the current branch, reply REPORT_PATH=/tmp/restore-isolated-deterministic-test-baseline-slice-001-report.md, and STOP. Do not resume the GHCR feature.
```
