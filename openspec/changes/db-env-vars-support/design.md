# Design: Suporte a variáveis individuais de banco de dados

## Estado atual

- Três módulos de settings: `dev.py`, `test.py`, `prod.py` — todos importam `dj_database_url` e chamam `dj_database_url.config(...)` com parâmetros diferentes.
- `prod.py`: `dj_database_url.config(conn_max_age=600, conn_health_checks=True)` — lê exclusivamente `DATABASE_URL`.
- `dev.py`: `dj_database_url.config(default=..., conn_max_age=0, conn_health_checks=False)` — fallback localhost:5432.
- `test.py`: `dj_database_url.config(default=..., conn_max_age=0, conn_health_checks=False, env="TEST_DATABASE_URL")`.
- `docker-compose.prod.yml` passa `DATABASE_URL` como connection string completa.
- `docker-compose.dev.yml` e `docker-compose.test.yml` não passam `DATABASE_URL` (usam defaults dos settings).

## Decisões de design

### D1. Helper centralizado em `config/settings/db.py`

Criar módulo `config/settings/db.py` com função `get_db_config(**overrides)` e helpers privados `_required_environment` e `_environment_or_file`.

Assinatura:

```python
def get_db_config(
    conn_max_age: int = 0,
    conn_health_checks: bool = False,
    default_db_host: str = "db",
    default_db_port: str = "5432",
    default_db_name: str = "ats_web",
    default_db_user: str = "ats_web",
    default_db_password: str | None = None,
    default_application_name: str = "ats_web",
) -> dict:
```

Justificativa para módulo separado:
- Evita duplicação em 3 settings files.
- Testável isoladamente sem carregar Django settings.
- As funções privadas `_required_environment` e `_environment_or_file` ficam encapsuladas.

### D2. Precedência de variáveis

```
1. DATABASE_URL setado?
   → SIM: usa dj_database_url.parse(url, conn_max_age=..., conn_health_checks=...)
          DB_CONN_MAX_AGE pode sobrescrever conn_max_age
   → NÃO: vai para variáveis individuais

2. DB_PASSWORD_FILE setado?     → lê arquivo, usa como senha
3. DB_PASSWORD setado?          → usa como senha
4. Nenhum dos dois?             → usa default_db_password (se não-None)
                                  ou raise ImproperlyConfigured

DB_HOST, DB_PORT, DB_NAME, DB_USER:
   → lê do env, fallback para default_db_* do parâmetro
   → se env não setado E default for None → ImproperlyConfigured

DB_CONN_MAX_AGE (env):
   → se setado, sobrescreve o conn_max_age do parâmetro em ambos os caminhos

DB_APPLICATION_NAME (env):
   → se setado, aparece em OPTIONS.application_name
   → fallback para default_application_name
```

### D3. Caminho de variáveis individuais: dict direto (não URL)

**Importante**: o caminho de vars individuais monta o dict Django diretamente, **sem** construir URL string intermediária e parsear de volta. Isso evita bugs com encoding de senha contendo `@`, `:`, `/`, `%` e outros caracteres especiais.

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": host,
        "PORT": port,
        "NAME": name,
        "USER": user,
        "PASSWORD": password,
        "CONN_MAX_AGE": conn_max_age,
        "CONN_HEALTH_CHECKS": conn_health_checks,
        "OPTIONS": {
            "application_name": application_name,
        },
    }
}
```

### D4. Padrão `{NAME}_FILE` para secrets (`_environment_or_file`)

```python
def _environment_or_file(name: str, default: str | None = None) -> str:
    """Lê NAME do env ou, como alternativa, o arquivo indicado por NAME_FILE."""
    value = os.environ.get(name)
    if value:
        return value

    file_path = os.environ.get(f"{name}_FILE")
    if not file_path:
        if default is not None:
            return default
        raise ImproperlyConfigured(
            f"Defina {name} ou {name}_FILE para configurar o banco de dados."
        )

    try:
        secret = Path(file_path).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ImproperlyConfigured(
            f"Não foi possível ler o segredo em {file_path}."
        ) from exc

    if not secret:
        raise ImproperlyConfigured(f"O arquivo indicado por {name}_FILE está vazio.")

    return secret
```

Este padrão é idiomático em Docker/K8s e mais genérico que um `DB_PASSWORD_FILE` fixo — se amanhã precisarem de `DB_HOST_FILE`, já funciona.

### D5. `conn_max_age` configurável via env var

```python
conn_max_age = int(os.environ.get("DB_CONN_MAX_AGE", str(conn_max_age)))
```

O parâmetro da função fornece o default por ambiente (600 prod, 0 dev/test), mas `DB_CONN_MAX_AGE` permite ajuste sem redeploy.

### D6. `application_name` nas OPTIONS

```python
application_name = os.environ.get("DB_APPLICATION_NAME", default_application_name)
```

Útil para identificar conexões no `pg_stat_activity`, especialmente em ambientes com múltiplas instâncias conectadas ao mesmo banco.

### D7. Chamadas por ambiente

```python
# prod.py — sem default de senha (fail fast se ausente)
DATABASES = {"default": get_db_config(conn_max_age=600, conn_health_checks=True)}

# dev.py — defaults completos para ambiente local
DATABASES = {"default": get_db_config(
    default_db_host="localhost",
    default_db_port=os.environ.get("POSTGRES_HOST_PORT", "5432"),
    default_db_name="ats_web_dev",
    default_db_password="ats_web_dev",
    conn_max_age=0,
    conn_health_checks=False,
)}

# test.py — defaults completos para ambiente de teste
DATABASES = {"default": get_db_config(
    default_db_host="localhost",
    default_db_port=os.environ.get("POSTGRES_TEST_HOST_PORT", "5433"),
    default_db_name="ats_web_test",
    default_db_password="ats_web_dev",
    conn_max_age=0,
    conn_health_checks=False,
)}
```

### D8. Caminho `DATABASE_URL`: compatibilidade com query params

Quando `DATABASE_URL` está presente, usamos `dj_database_url.parse()` que interpreta query params (`?sslmode=require`, `?application_name=...`). Esses params são preservados no dict resultante. O `conn_max_age` e `conn_health_checks` aplicados pela função são sobrescritos no dict parseado (se o URL já definir, vence o URL).

## Arquivos afetados

| Arquivo | Mudança |
|---------|---------|
| `config/settings/db.py` | NOVO — `_required_environment`, `_environment_or_file`, `get_db_config()` |
| `config/settings/prod.py` | MODIFICAR — substituir `dj_database_url.config(...)` por `get_db_config(conn_max_age=600, conn_health_checks=True)` |
| `config/settings/dev.py` | MODIFICAR — substituir `dj_database_url.config(...)` por `get_db_config(...)` com defaults dev |
| `config/settings/test.py` | MODIFICAR — substituir `dj_database_url.config(...)` por `get_db_config(...)` com defaults test |
| `config/settings/tests/__init__.py` | NOVO — init do pacote de testes |
| `config/settings/tests/test_db.py` | NOVO — testes unitários do helper |

Total: 6 arquivos. Remover `import dj_database_url` dos settings que não precisarem mais (prod e test; dev pode precisar? Não, ninguém vai precisar).

## Testes

Testes unitários isolados (monkeypatch de `os.environ`, não carregam Django settings):

1. `test_database_url_takes_precedence` — `DATABASE_URL` setado, individuais também → usa `DATABASE_URL`.
2. `test_individual_vars_dict_direct` — vars individuais → dict Django montado diretamente (sem URL intermediária).
3. `test_password_file_read` — `DB_PASSWORD_FILE` → senha lida do arquivo.
4. `test_password_file_precedence_over_password` — ambos setados → `DB_PASSWORD_FILE` vence.
5. `test_password_special_chars` — senha com `@:;/%` → preservada intacta no dict (prova que não passou por URL).
6. `test_default_port_5432` — `DB_PORT` não setado → default 5432.
7. `test_default_host_db` — `DB_HOST` não setado → default `"db"`.
8. `test_missing_password_raises_when_no_default` — sem `DATABASE_URL`, sem `DB_PASSWORD`, sem `DB_PASSWORD_FILE`, sem `default_db_password` → `ImproperlyConfigured`.
9. `test_password_file_not_found_raises` — `DB_PASSWORD_FILE` inexistente → `ImproperlyConfigured`.
10. `test_password_file_empty_raises` — `DB_PASSWORD_FILE` aponta para arquivo vazio → `ImproperlyConfigured`.
11. `test_conn_max_age_from_env_overrides_param` — `DB_CONN_MAX_AGE=30`, param=600 → 30.
12. `test_conn_max_age_defaults_to_param` — sem `DB_CONN_MAX_AGE` → usa param.
13. `test_application_name_from_env` — `DB_APPLICATION_NAME=myapp` → `OPTIONS["application_name"] == "myapp"`.
14. `test_dev_defaults_scenario` — simula ambiente dev com defaults.

## Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| Quebrar prod que já usa `DATABASE_URL` | `DATABASE_URL` tem precedência total; teste cobre |
| Senha com caracteres especiais quebrar URL | Caminho de vars individuais monta dict direto, não URL; teste cobre `@:;/%` |
| Quebrar dev/test que usam defaults | Defaults preservados via kwargs; testes cobrem |
| Leitura de arquivo de senha falhar | `OSError` vira `ImproperlyConfigured`; arquivo vazio também falha |
| Regressão com `dj_database_url` removido | Mantemos `dj_database_url` como dependência; só usamos no caminho `DATABASE_URL` |
