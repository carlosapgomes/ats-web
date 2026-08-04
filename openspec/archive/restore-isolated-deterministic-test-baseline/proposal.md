# Proposal: Restaurar baseline de testes isolado e determinístico

**Change ID**: `restore-isolated-deterministic-test-baseline`  
**Tipo**: bugfix pré-requisito / infraestrutura de testes  
**Risco**: PROFISSIONAL — altera somente settings e testes do ambiente de teste; produção/dev permanecem inalterados  
**Branch sugerida**: `fix/restore-isolated-deterministic-test-baseline`  
**Bloqueia**: `publish-release-container-to-ghcr`

## Problema

O baseline exigido pelo change de publicação no GHCR revelou dois defeitos preexistentes:

1. `config.settings.test` usa `get_db_config()`, que prioriza a variável genérica `DATABASE_URL` carregada por `base.py`. Assim, o comando canônico `uv run pytest` pode selecionar `ats_web_dev` em `localhost:5432`, contrariando o contrato do `AGENTS.md` de usar `ats_web_test` na porta `${POSTGRES_TEST_HOST_PORT:-5433}`.
2. `TestDashboardBadgeCompactoProximoPasso::test_regression_date_time_present` compara `case.created_at.strftime(...)` em UTC com o valor localizado pelo template Django. Entre 00:00 e 03:00 UTC, a data esperada pode ficar um dia à frente da data renderizada em `America/Bahia`, tornando o teste flakey.

O workaround `DATABASE_URL="" uv run pytest`, `xfail` ou aceitação de baseline vermelho não resolve o contrato: o quality gate oficial deve funcionar exatamente como documentado.

## Objetivo

Entregar um baseline confiável:

```text
contribuidor executa uv run pytest
→ config.settings.test ignora DATABASE_URL/DB_* genéricos
→ usa TEST_DATABASE_URL quando explicitamente fornecida
  ou localhost:${POSTGRES_TEST_HOST_PORT:-5433}/ats_web_test por padrão
→ teste de data usa instante fixo na fronteira UTC e expectativa local
→ suíte completa termina com exit code 0 e zero failures/errors
```

## Escopo incluído

- Restaurar em `config/settings/test.py` a semântica isolada baseada em `TEST_DATABASE_URL`.
- Ignorar `DATABASE_URL` e `DB_*` genéricos no settings de teste.
- Adicionar testes subprocess-isolated que provem a configuração efetiva sem abrir conexão com banco.
- Tornar o teste de data/hora do dashboard determinístico em uma fronteira UTC/local.
- Rodar o quality gate completo sem prefixar `DATABASE_URL=""`.

## Fora de escopo

- Alterar `.env` ou ler/expor seu conteúdo.
- Alterar `config/settings/base.py`, `dev.py`, `prod.py` ou `db.py`.
- Alterar Docker Compose, credenciais ou banco de produção/dev.
- Alterar template, view ou comportamento do dashboard.
- Usar `xfail`, `skip`, tolerância a baseline vermelho ou workaround no comando oficial.
- Implementar o workflow GHCR.

## Dimensionamento

Um único slice vertical e enxuto, tocando três arquivos funcionais. Os dois defeitos compõem um único valor observável: restaurar o quality gate canônico, isolado e determinístico, necessário para desbloquear o próximo change.

## Critérios globais de sucesso

- `uv run pytest` usa `ats_web_test`/porta 5433 por padrão mesmo com `DATABASE_URL` e `DB_*` genéricos presentes.
- `TEST_DATABASE_URL` continua permitindo override explícito do banco de teste.
- O teste do dashboard prova conversão UTC → `America/Bahia` com instante fixo.
- Nenhum teste é pulado ou marcado `xfail`.
- O comando exato `uv run pytest` passa sem limpar variáveis manualmente.
- Produção, desenvolvimento e comportamento renderizado permanecem inalterados.
