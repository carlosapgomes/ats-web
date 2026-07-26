# Design: Baseline de testes isolado e determinístico

## Estado atual comprovado

Sem expor senha, a inspeção de `settings.DATABASES["default"]` mostrou:

- `uv run ... config.settings.test` → `localhost:5432/ats_web_dev` quando `DATABASE_URL` genérica está presente;
- `DATABASE_URL="" uv run ... config.settings.test` → `localhost:5433/ats_web_test`.

O teste flakey usa:

```python
created_str = case.created_at.strftime("%d/%m/%Y")
```

mas o template usa:

```django
{{ item.case.created_at|date:"d/m/Y H:i" }}
```

Com `USE_TZ=True`, o filtro `date` localiza o datetime para `America/Bahia`; `datetime.strftime()` no objeto retornado pelo model permanece em UTC.

## Decisões

### D1. Test settings têm boundary próprio

Restaurar em `config/settings/test.py` a configuração explícita anterior:

```python
import dj_database_url

DATABASES = {
    "default": dj_database_url.config(
        default=(
            f"postgres://ats_web:ats_web_dev@localhost:"
            f"{postgres_test_host_port}/ats_web_test"
        ),
        conn_max_age=0,
        conn_health_checks=False,
        env="TEST_DATABASE_URL",
    )
}
```

Remover o uso de `get_db_config()` somente de `test.py`.

Justificativa:

- o ambiente de teste precisa ignorar deliberadamente `DATABASE_URL` e `DB_*` de dev/prod;
- `TEST_DATABASE_URL` é o override explícito e semântico do banco de teste;
- `dj-database-url` já é dependência do projeto;
- evita adicionar flags genéricas ao helper de produção apenas para um boundary de teste;
- restaura o comportamento existente antes da regressão.

`dev.py`, `prod.py` e `db.py` permanecem inalterados.

### D2. Testar settings em subprocesso

Criar `config/settings/tests/test_test_settings.py` usando stdlib (`json`, `os`, `subprocess`, `sys`). Cada cenário inicia subprocesso Python com `DJANGO_SETTINGS_MODULE=config.settings.test`, garantindo import fresco dos settings.

Casos obrigatórios:

1. Ambiente contém `DATABASE_URL` e `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD` hostis, não contém `TEST_DATABASE_URL`, e define `POSTGRES_TEST_HOST_PORT=5433`:
   - resultado deve ser host `localhost`, porta `5433`, name `ats_web_test`, user `ats_web`;
   - nenhum valor genérico pode vencer.
2. Ambiente contém `TEST_DATABASE_URL=postgres://test_user:test_pass@test-db:6543/custom_test` e também variáveis genéricas hostis:
   - resultado deve refletir somente `TEST_DATABASE_URL` (`test-db`, `6543`, `custom_test`, `test_user`).

O subprocesso deve imprimir somente JSON com `ENGINE`, `HOST`, `PORT`, `NAME`, `USER`; nunca imprimir `PASSWORD` ou URL completa.

### D3. Teste temporal determinístico

Ajustar somente `test_regression_date_time_present` em `apps/dashboard/tests/test_dashboard.py`:

1. criar o caso normalmente;
2. fixar `created_at` via `Case.objects.filter(pk=case.pk).update(...)` em `2026-07-26 00:37:00 UTC`;
3. calcular a expectativa com `timezone.localtime(fixed_utc).strftime("%d/%m/%Y %H:%M")`;
4. confirmar que `25/07/2026 21:37` aparece no HTML.

Esse instante cruza a fronteira de data entre UTC e `America/Bahia`, eliminando dependência do relógio de execução e provando o mesmo comportamento do filtro Django.

Não alterar template ou view: a renderização existente está correta; o defeito está na expectativa do teste.

## Arquivos esperados

| Arquivo | Mudança |
| --- | --- |
| `config/settings/test.py` | restaurar `TEST_DATABASE_URL` e default test isolado |
| `config/settings/tests/test_test_settings.py` | testes subprocess-isolated do boundary |
| `apps/dashboard/tests/test_dashboard.py` | tornar uma regressão temporal determinística |
| `openspec/changes/restore-isolated-deterministic-test-baseline/tasks.md` | status após gates |

## Estratégia RED

Este é um slice de reparo do próprio baseline, portanto a exceção é explícita: baseline inicial vermelho ou apontando para DB incorreto é evidência do bug, não condição para abandonar este slice.

- RED A: novos testes subprocess falham com settings atual porque `DATABASE_URL`/`DB_*` genéricos vencem.
- RED B: fixar o instante UTC no teste existente mantendo temporariamente a expectativa UTC produz falha determinística (`26/07` esperado versus `25/07 21:37` renderizado).
- GREEN: restaurar `TEST_DATABASE_URL` e usar `timezone.localtime()` na expectativa.

## Rollback

Reverter os três arquivos. Não há migration ou alteração de dados. O rollback reintroduziria o baseline não isolado/flakey e, portanto, só deve ocorrer se substituído por solução equivalente.

## Riscos

| Risco | Mitigação |
| --- | --- |
| Teste subprocess vazar segredo | imprimir somente chaves não sensíveis; nunca PASSWORD/URL |
| Testes ainda usarem DB genérico | cenário hostil cobre `DATABASE_URL` e `DB_*` |
| Override de CI deixar de funcionar | cenário explícito cobre `TEST_DATABASE_URL` |
| Corrigir app em vez do teste | proibir mudanças em template/view; usar expectativa localizada |
| RED inicial não ser reproduzível pelo relógio | instante UTC fixo na fronteira local |
