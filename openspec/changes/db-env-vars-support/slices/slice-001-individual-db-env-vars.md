<!-- markdownlint-disable MD013 -->

# Slice 001: Helper `get_db_config()` + aplicação em dev/test/prod

## Contexto zero para implementador

Projeto Django SSR em `/projects/dev/ats-web`.

Leia primeiro:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/db-env-vars-support/proposal.md`
4. `openspec/changes/db-env-vars-support/design.md`
5. `openspec/changes/db-env-vars-support/tasks.md`
6. este arquivo de slice

Estado funcional antes deste slice:

- `config/settings/prod.py`, `dev.py`, `test.py` — cada um tem seu próprio bloco `DATABASES` usando `dj_database_url.config()` com parâmetros diferentes.
- Nenhum suporta variáveis individuais (`DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PASSWORD_FILE`).
- `docker-compose.prod.yml` passa `DATABASE_URL` como connection string.
- `docker-compose.dev.yml` e `docker-compose.test.yml` não passam `DATABASE_URL` (usam defaults dos settings).

## Objetivo do slice

Criar um helper `get_db_config()` em `config/settings/db.py` e aplicá-lo nos 3 settings, permitindo:

```text
Cenário A: DATABASE_URL=postgres://...          → conexão via dj_database_url.parse() (retrocompatível)
Cenário B: DB_HOST + DB_NAME + DB_USER + DB_PASSWORD  → conexão via dict Django direto
Cenário C: DB_HOST + DB_NAME + DB_USER + DB_PASSWORD_FILE → senha lida de arquivo (Docker/K8s secrets)
Cenário D: nenhuma credencial (prod)            → ImproperlyConfigured (fail fast)
Cenário E: nenhuma credencial (dev/test)         → usa defaults do ambiente (backward compat)
```

## Arquivos esperados

1. `config/settings/db.py` — NOVO: helpers `_required_environment`, `_environment_or_file`, `get_db_config()`
2. `config/settings/prod.py` — MODIFICAR: usar `get_db_config(conn_max_age=600, conn_health_checks=True)`
3. `config/settings/dev.py` — MODIFICAR: usar `get_db_config(...)` com defaults dev
4. `config/settings/test.py` — MODIFICAR: usar `get_db_config(...)` com defaults test
5. `config/settings/tests/__init__.py` — NOVO: init do pacote de testes
6. `config/settings/tests/test_db.py` — NOVO: 14 testes unitários

Total: 6 arquivos. Não tocar models, migrations, FSM, templates, views, docker-compose ou outros apps.

## Requisitos funcionais

### R1. Função `_environment_or_file(name, default=None)`

```python
def _environment_or_file(name: str, default: str | None = None) -> str:
```

1. Lê `os.environ.get(name)`. Se presente e não-vazio → retorna.
2. Senão, lê `os.environ.get(f"{name}_FILE")`. Se presente:
   - Abre o arquivo, lê conteúdo UTF-8, faz `.strip()`.
   - Se arquivo não encontrado → `ImproperlyConfigured`.
   - Se conteúdo vazio → `ImproperlyConfigured`.
   - Retorna o conteúdo.
3. Senão:
   - Se `default is not None` → retorna `default`.
   - Senão → `ImproperlyConfigured`.

### R2. Função `get_db_config(**overrides)`

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

**Caminho A: `DATABASE_URL` presente no env**

```python
database_url = os.environ.get("DATABASE_URL")
if database_url:
    conn_max_age = int(os.environ.get("DB_CONN_MAX_AGE", str(conn_max_age)))
    return dj_database_url.parse(
        database_url,
        conn_max_age=conn_max_age,
        conn_health_checks=conn_health_checks,
    )
```

**Caminho B: variáveis individuais (dict direto)**

```python
# Resolve host, port, name, user com fallback para defaults
db_host = os.environ.get("DB_HOST", default_db_host)
db_port = os.environ.get("DB_PORT", default_db_port)
db_name = os.environ.get("DB_NAME", default_db_name)
db_user = os.environ.get("DB_USER", default_db_user)

# Senha via _environment_or_file (pode usar default_db_password)
db_password = _environment_or_file("DB_PASSWORD", default=default_db_password)

# conn_max_age pode ser sobrescrito por env var
conn_max_age = int(os.environ.get("DB_CONN_MAX_AGE", str(conn_max_age)))

# application_name
application_name = os.environ.get("DB_APPLICATION_NAME", default_application_name)

return {
    "ENGINE": "django.db.backends.postgresql",
    "HOST": db_host,
    "PORT": db_port,
    "NAME": db_name,
    "USER": db_user,
    "PASSWORD": db_password,
    "CONN_MAX_AGE": conn_max_age,
    "CONN_HEALTH_CHECKS": conn_health_checks,
    "OPTIONS": {
        "application_name": application_name,
    },
}
```

**Nota crítica**: o caminho B monta o dict Django **diretamente**. Não constrói URL string intermediária (`f"postgres://{user}:{password}@{host}...`) nem chama `dj_database_url.parse()` para o caminho de vars individuais. Isso evita bugs com senhas contendo `@`, `:`, `/`, `%`.

### R3. `prod.py` — sem default de senha

```python
# config/settings/prod.py
from config.settings.db import get_db_config

DATABASES = {
    "default": get_db_config(conn_max_age=600, conn_health_checks=True)
}
```

Remove `import dj_database_url` e `import os` (se não usado para outra coisa). Como `default_db_password=None` (padrão), produção **exige** `DB_PASSWORD` ou `DB_PASSWORD_FILE` quando `DATABASE_URL` não está setado.

### R4. `dev.py` — defaults locais preservados

```python
# config/settings/dev.py
from config.settings.db import get_db_config

DATABASES = {
    "default": get_db_config(
        default_db_host="localhost",
        default_db_port=os.environ.get("POSTGRES_HOST_PORT", "5432"),
        default_db_name="ats_web_dev",
        default_db_password="ats_web_dev",
        conn_max_age=0,
        conn_health_checks=False,
    )
}
```

Remove `import dj_database_url`. Mantém `import os` (já era usado).

### R5. `test.py` — defaults de teste preservados

```python
# config/settings/test.py
from config.settings.db import get_db_config

DATABASES = {
    "default": get_db_config(
        default_db_host="localhost",
        default_db_port=os.environ.get("POSTGRES_TEST_HOST_PORT", "5433"),
        default_db_name="ats_web_test",
        default_db_password="ats_web_dev",
        conn_max_age=0,
        conn_health_checks=False,
    )
}
```

Remove `import dj_database_url`. Note que `TEST_DATABASE_URL` deixa de ser usado como `env=` do `dj_database_url.config()`. Em vez disso, se `DATABASE_URL` for acidentalmente setado no ambiente de teste, ele terá precedência. Isso é aceitável porque CI limpo não seta `DATABASE_URL`.

### R6. `DB_CONN_MAX_AGE` como env var

Em **ambos** os caminhos (A e B), `DB_CONN_MAX_AGE` do ambiente sobrescreve o valor do parâmetro:

```python
conn_max_age = int(os.environ.get("DB_CONN_MAX_AGE", str(conn_max_age)))
```

### R7. `DB_APPLICATION_NAME` como env var

Apenas no caminho B (vars individuais). No caminho A (URL), query params do URL já podem incluir `application_name`.

```python
application_name = os.environ.get("DB_APPLICATION_NAME", default_application_name)
```

## TDD obrigatório

Siga RED → GREEN → REFACTOR.

### Criar estrutura de testes

```bash
mkdir -p config/settings/tests
touch config/settings/tests/__init__.py
```

### Criar `config/settings/tests/test_db.py`

Antes de implementar o helper, crie os 14 testes abaixo. Rode com `uv run pytest config/settings/tests/test_db.py -v` e confirme RED (todos falham porque `config/settings/db.py` não existe).

Depois implemente `config/settings/db.py` e confirme GREEN. Por fim, atualize os 3 settings e rode a suíte completa.

```python
"""Testes unitários para get_db_config()."""

import os
import tempfile

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.settings.db import get_db_config


class TestGetDbConfig:
    """Cobre ambos os caminhos: DATABASE_URL e variáveis individuais."""

    # ── Caminho DATABASE_URL ──────────────────────────────────────────

    def test_database_url_takes_precedence(self, monkeypatch):
        """DATABASE_URL presente → ignora variáveis individuais."""
        monkeypatch.setenv("DATABASE_URL", "postgres://url_user:url_pass@url_host:9999/url_db")
        monkeypatch.setenv("DB_HOST", "individual_host")
        monkeypatch.setenv("DB_NAME", "individual_db")
        monkeypatch.setenv("DB_USER", "individual_user")
        monkeypatch.setenv("DB_PASSWORD", "individual_pass")

        config = get_db_config()

        assert config["HOST"] == "url_host"
        assert config["PORT"] == 9999
        assert config["NAME"] == "url_db"
        assert config["USER"] == "url_user"
        assert config["PASSWORD"] == "url_pass"

    # ── Caminho variáveis individuais (dict direto) ───────────────────

    def test_individual_vars_dict_direct(self, monkeypatch):
        """DB_HOST + DB_NAME + DB_USER + DB_PASSWORD → dict Django direto."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_HOST", "myhost")
        monkeypatch.setenv("DB_NAME", "mydb")
        monkeypatch.setenv("DB_USER", "myuser")
        monkeypatch.setenv("DB_PASSWORD", "mypass")
        monkeypatch.setenv("DB_PORT", "5433")

        config = get_db_config()

        assert config["ENGINE"] == "django.db.backends.postgresql"
        assert config["HOST"] == "myhost"
        assert config["PORT"] == "5433"  # str, pois é o que Django espera
        assert config["NAME"] == "mydb"
        assert config["USER"] == "myuser"
        assert config["PASSWORD"] == "mypass"

    def test_password_special_chars_preserved(self, monkeypatch):
        """Senha com @:;/% → preservada intacta (prova que não passou por URL)."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_HOST", "myhost")
        monkeypatch.setenv("DB_NAME", "mydb")
        monkeypatch.setenv("DB_USER", "myuser")
        special_password = "p@ss:word/with%special;chars"
        monkeypatch.setenv("DB_PASSWORD", special_password)

        config = get_db_config()

        assert config["PASSWORD"] == special_password

    # ── DB_PASSWORD_FILE ──────────────────────────────────────────────

    def test_password_file_read(self, monkeypatch):
        """DB_PASSWORD_FILE → senha lida do arquivo."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_HOST", "myhost")
        monkeypatch.setenv("DB_NAME", "mydb")
        monkeypatch.setenv("DB_USER", "myuser")

        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write("secret-from-file\n")
            tmp_path = f.name

        try:
            monkeypatch.setenv("DB_PASSWORD_FILE", tmp_path)
            config = get_db_config()
            assert config["PASSWORD"] == "secret-from-file"
        finally:
            os.unlink(tmp_path)

    def test_password_file_precedence_over_password(self, monkeypatch):
        """DB_PASSWORD_FILE + DB_PASSWORD → arquivo vence."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_HOST", "myhost")
        monkeypatch.setenv("DB_NAME", "mydb")
        monkeypatch.setenv("DB_USER", "myuser")
        monkeypatch.setenv("DB_PASSWORD", "ignored-pass")

        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write("file-pass\n")
            tmp_path = f.name

        try:
            monkeypatch.setenv("DB_PASSWORD_FILE", tmp_path)
            config = get_db_config()
            assert config["PASSWORD"] == "file-pass"
        finally:
            os.unlink(tmp_path)

    def test_password_file_not_found_raises(self, monkeypatch):
        """DB_PASSWORD_FILE inexistente → ImproperlyConfigured."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_HOST", "myhost")
        monkeypatch.setenv("DB_NAME", "mydb")
        monkeypatch.setenv("DB_USER", "myuser")
        monkeypatch.setenv("DB_PASSWORD_FILE", "/tmp/does-not-exist-12345")

        with pytest.raises(ImproperlyConfigured):
            get_db_config()

    def test_password_file_empty_raises(self, monkeypatch):
        """DB_PASSWORD_FILE aponta para arquivo vazio → ImproperlyConfigured."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_HOST", "myhost")
        monkeypatch.setenv("DB_NAME", "mydb")
        monkeypatch.setenv("DB_USER", "myuser")

        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            # arquivo vazio — não escreve nada
            tmp_path = f.name

        try:
            monkeypatch.setenv("DB_PASSWORD_FILE", tmp_path)
            with pytest.raises(ImproperlyConfigured):
                get_db_config()
        finally:
            os.unlink(tmp_path)

    # ── Defaults ──────────────────────────────────────────────────────

    def test_default_port_5432(self, monkeypatch):
        """DB_PORT não setado → default 5432 como str."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_HOST", "myhost")
        monkeypatch.setenv("DB_NAME", "mydb")
        monkeypatch.setenv("DB_USER", "myuser")
        monkeypatch.setenv("DB_PASSWORD", "mypass")

        config = get_db_config()
        assert config["PORT"] == "5432"

    def test_default_host_db(self, monkeypatch):
        """DB_HOST não setado → default 'db'."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_NAME", "mydb")
        monkeypatch.setenv("DB_USER", "myuser")
        monkeypatch.setenv("DB_PASSWORD", "mypass")

        config = get_db_config()
        assert config["HOST"] == "db"

    def test_missing_password_raises_when_no_default(self, monkeypatch):
        """Sem DATABASE_URL, sem DB_PASSWORD, sem DB_PASSWORD_FILE, sem default → erro."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("DB_PASSWORD", raising=False)
        monkeypatch.delenv("DB_PASSWORD_FILE", raising=False)
        monkeypatch.delenv("DB_HOST", raising=False)
        monkeypatch.delenv("DB_NAME", raising=False)
        monkeypatch.delenv("DB_USER", raising=False)

        # default_db_password=None (padrão) → deve falhar
        with pytest.raises(ImproperlyConfigured):
            get_db_config()

    # ── DB_CONN_MAX_AGE ───────────────────────────────────────────────

    def test_conn_max_age_from_env_overrides_param(self, monkeypatch):
        """DB_CONN_MAX_AGE setado → sobrescreve param."""
        monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h:5432/db")
        monkeypatch.setenv("DB_CONN_MAX_AGE", "30")

        config = get_db_config(conn_max_age=600)
        assert config["CONN_MAX_AGE"] == 30

    def test_conn_max_age_defaults_to_param(self, monkeypatch):
        """DB_CONN_MAX_AGE não setado → usa param."""
        monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h:5432/db")

        config = get_db_config(conn_max_age=600)
        assert config["CONN_MAX_AGE"] == 600

    # ── DB_APPLICATION_NAME ───────────────────────────────────────────

    def test_application_name_from_env(self, monkeypatch):
        """DB_APPLICATION_NAME setado → OPTIONS.application_name."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_HOST", "myhost")
        monkeypatch.setenv("DB_NAME", "mydb")
        monkeypatch.setenv("DB_USER", "myuser")
        monkeypatch.setenv("DB_PASSWORD", "mypass")
        monkeypatch.setenv("DB_APPLICATION_NAME", "myapp")

        config = get_db_config()
        assert config["OPTIONS"]["application_name"] == "myapp"

    # ── Cenário dev ───────────────────────────────────────────────────

    def test_dev_defaults_scenario(self, monkeypatch):
        """Simula ambiente dev: sem DATABASE_URL, com defaults de dev."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        # Não seta DB_HOST, DB_NAME, DB_USER, DB_PASSWORD — usa defaults

        config = get_db_config(
            default_db_host="localhost",
            default_db_port="5432",
            default_db_name="ats_web_dev",
            default_db_password="ats_web_dev",
            conn_max_age=0,
            conn_health_checks=False,
        )

        assert config["HOST"] == "localhost"
        assert config["PORT"] == "5432"
        assert config["NAME"] == "ats_web_dev"
        assert config["USER"] == "ats_web"
        assert config["PASSWORD"] == "ats_web_dev"
        assert config["CONN_MAX_AGE"] == 0
        assert config["CONN_HEALTH_CHECKS"] is False
```

## Critérios de sucesso

- [ ] TDD seguido: todos os 14 testes falham antes da implementação e passam após.
- [ ] `DATABASE_URL` permanece com precedência total (retrocompatibilidade).
- [ ] Caminho de vars individuais monta dict Django **direto** (sem URL string intermediária).
- [ ] `DB_PASSWORD_FILE` lê senha do arquivo corretamente e tem precedência sobre `DB_PASSWORD`.
- [ ] Arquivo de senha inexistente ou vazio → `ImproperlyConfigured`.
- [ ] Senhas com caracteres especiais (`@:;/%`) preservadas intactas.
- [ ] `DB_CONN_MAX_AGE` como env var sobrescreve o default do ambiente.
- [ ] `DB_APPLICATION_NAME` aparece em `OPTIONS["application_name"]`.
- [ ] `prod.py` sem default de senha → fail fast se mal configurado.
- [ ] `dev.py` e `test.py` com defaults preservados (localhost, portas, db names, senhas padrão).
- [ ] `import dj_database_url` removido dos 3 settings (só `db.py` importa).
- [ ] Nenhum docker-compose file alterado.
- [ ] Nenhum model, migration, FSM, template, view ou outro app alterado.
- [ ] Código limpo, coeso, DRY, sem abstrações YAGNI.
- [ ] Quality gate completo passa.

## Gates de autoavaliação

Responda no relatório final:

1. `DATABASE_URL` continua com precedência sobre variáveis individuais? Qual teste prova?
2. Senhas com `@:;/%` são preservadas intactas? Qual teste prova que NÃO passaram por construção de URL?
3. `DB_PASSWORD_FILE` tem precedência sobre `DB_PASSWORD` quando ambos presentes? Qual teste prova?
4. `DB_PASSWORD_FILE` inexistente gera erro? E arquivo vazio? Quais testes provam?
5. Os defaults de `dev.py` (localhost, `POSTGRES_HOST_PORT`, `ats_web_dev`, `ats_web_dev`) foram preservados? Qual teste prova?
6. Os defaults de `test.py` (localhost, `POSTGRES_TEST_HOST_PORT`, `ats_web_test`, `ats_web_dev`) foram preservados?
7. Os defaults de `prod.py` (`conn_max_age=600`, `conn_health_checks=True`, sem senha padrão) foram preservados?
8. `DB_CONN_MAX_AGE` do ambiente sobrescreve o parâmetro? Funciona em ambos os caminhos (URL e vars individuais)?
9. `DB_APPLICATION_NAME` aparece em `OPTIONS["application_name"]`? Qual teste prova?
10. O `import dj_database_url` foi removido de `prod.py`, `dev.py` e `test.py`? Eles importam apenas de `config.settings.db`?
11. Algum docker-compose file foi alterado? Não deveria.
12. O código ficou mais duplicado ou foi reduzido com o helper centralizado?

## Comandos de validação

Executar durante o slice:

```bash
# Rodar apenas os testes do helper (RED primeiro, depois GREEN)
uv run pytest config/settings/tests/test_db.py -v

# Rodar a suíte completa para garantir que nada quebrou
uv run pytest

# Lint dos arquivos alterados
uv run ruff check config/settings/db.py config/settings/prod.py config/settings/dev.py config/settings/test.py config/settings/tests/test_db.py
uv run ruff format --check config/settings/db.py config/settings/prod.py config/settings/dev.py config/settings/test.py config/settings/tests/test_db.py

# Type check
uv run mypy config/settings/
```

Antes de finalizar, executar o quality gate completo do `AGENTS.md`:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório esperado

Criar relatório temporário em:

```text
/tmp/ats-web-slice-001-db-env-vars-support-report.md
```

O relatório deve conter:

- resumo do problema e da solução;
- lista de arquivos alterados/criados;
- snippets antes/depois de `prod.py`, `dev.py`, `test.py` e `db.py`;
- evidência RED/GREEN dos testes (output do pytest);
- comandos de validação executados e resultados;
- respostas completas aos gates de autoavaliação;
- observações de rollback, se necessário.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/db-env-vars-support/{proposal.md,design.md,tasks.md,slices/slice-001-individual-db-env-vars.md} first.
Implement ONLY this slice.
Use TDD: first create config/settings/tests/__init__.py and config/settings/tests/test_db.py with the 14 failing tests. Run `uv run pytest config/settings/tests/test_db.py -v` to confirm RED.
Then create config/settings/db.py with _environment_or_file() and get_db_config() implementing both paths:
  A) DATABASE_URL → dj_database_url.parse()
  B) individual vars → dict Django direto (no URL construction!)
Then update config/settings/{prod,dev,test}.py to use get_db_config() instead of dj_database_url.config(), preserving each environment's defaults. Remove `import dj_database_url` from these three files.
Run GREEN: all 14 tests pass + full test suite passes.
REFACTOR: ensure clean code, DRY, YAGNI, clear names.
Critical: the individual-vars path MUST build the Django dict directly, NOT construct a URL string. This avoids bugs with passwords containing @:/% special characters.
Do NOT touch docker-compose files, models, migrations, FSM, templates, views, or other Django apps.
Run the full quality gate: `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest`
Create a detailed report at /tmp/ats-web-slice-001-db-env-vars-support-report.md with RED/GREEN evidence, before/after snippets, quality gate results, and self-evaluation gates.
Commit with a clear message and push to origin.
Reply with REPORT_PATH=/tmp/ats-web-slice-001-db-env-vars-support-report.md and STOP.
```
