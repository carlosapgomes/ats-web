# Proposal: Suporte a variáveis individuais de banco de dados

**Change ID**: `db-env-vars-support`  
**Branch**: `feat/db-env-vars-support`  
**Fase**: infraestrutura / configuração  
**Risco**: PROFISSIONAL (toca configuração de banco em todos os ambientes)

## Problema

Atualmente os settings de produção (`config/settings/prod.py`) só aceitam a variável `DATABASE_URL` para configurar a conexão com o banco:

```python
DATABASES = {
    "default": dj_database_url.config(
        conn_max_age=600,
        conn_health_checks=True,
    )
}
```

Isso é inflexível para ambientes de deploy que injetam credenciais via variáveis individuais (`DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` ou `DB_PASSWORD_FILE`), prática comum em orquestradores e plataformas como Kubernetes (Secrets montados como arquivos), Docker Swarm, Dokku, etc.

## Objetivo

Permitir que a configuração do banco seja feita de duas formas, com `DATABASE_URL` tendo precedência para retrocompatibilidade:

1. **Modo atual (URL completa)**: `DATABASE_URL=postgres://...` — comportamento inalterado.
2. **Modo individual**: `DB_HOST` + `DB_NAME` + `DB_USER` + (`DB_PASSWORD` ou `DB_PASSWORD_FILE`) + `DB_PORT` (opcional).

## Escopo

### Funcionalidades

1. **Helper reutilizável** que resolve a config do banco a partir de `DATABASE_URL` ou variáveis individuais.
2. **Suporte a `DB_PASSWORD_FILE`**: lê o conteúdo do arquivo indicado (padrão Docker/Kubernetes secrets).
3. **Aplicar em todos os settings**: `dev.py`, `test.py` e `prod.py` — preservando defaults específicos de cada ambiente.
4. **Fallback seguro**: se nem `DATABASE_URL` nem variáveis suficientes forem fornecidas, erro claro (`ImproperlyConfigured`).

### Fora de escopo

- Alterar docker-compose files (eles continuam funcionando com `DATABASE_URL`).
- Suporte a outros bancos além de PostgreSQL.
- SSL/TLS settings individuais (manter `sslmode` via query params se necessário com `DATABASE_URL`).

## Decisões

- `DATABASE_URL` tem precedência total sobre variáveis individuais.
- `DB_PORT` default = `5432`.
- `DB_HOST` default = `db` (hostname do container no docker-compose).
- `DB_NAME` e `DB_USER` default = `ats_web`.
- `DB_PASSWORD_FILE` tem precedência sobre `DB_PASSWORD` quando ambos existem.
- Helper fica em módulo novo `config/settings/db.py` para evitar circular imports e manter testabilidade.

## Critérios de sucesso

- `DATABASE_URL` setado → comportamento idêntico ao atual (retrocompatibilidade total).
- Apenas variáveis individuais setadas → conexão funciona identicamente.
- `DB_PASSWORD_FILE` apontando para arquivo → senha lida corretamente.
- `DB_PASSWORD_FILE` + `DB_PASSWORD` ambos setados → `DB_PASSWORD_FILE` vence.
- Nenhuma variável setada → `ImproperlyConfigured` com mensagem clara.
- Quality gate do AGENTS.md passa.
- Dev e test continuam funcionando com seus defaults atuais.
