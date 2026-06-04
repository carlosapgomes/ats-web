# Proposal: Consolidar fixtures duplicadas de testes

**Change ID**: `consolidate-duplicated-test-fixtures`  
**Risco**: ESSENCIAL/PROFISSIONAL baixo (refactor de testes, sem mudança de
produto)

## Contexto

Durante o change `post-schedule-intercurrence`, verificadores apontaram que há
cópias quase idênticas de fixtures em arquivos `conftest.py` de múltiplos apps.
O projeto é greenfield, mas a duplicação aumenta custo de manutenção e risco de
fixtures divergirem.

## Objetivo

Extrair fixtures compartilhadas para um local comum de testes e remover
duplicação desnecessária entre apps, mantendo comportamento e cobertura.

## Escopo

- Inventariar duplicações em `apps/*/tests/conftest.py`.
- Criar módulo compartilhado de fixtures, se necessário.
- Migrar apps afetados para reutilizar fixtures comuns.
- Manter fixtures específicas em seus apps quando forem realmente locais.
- Garantir que a suíte completa continue verde.

## Fora de escopo

- Alterar lógica de produção.
- Refatorar factories para biblioteca externa.
- Trocar pytest por outra ferramenta.
- Reescrever testes sem necessidade.

## Critérios de sucesso

- Duplicações óbvias de fixtures comuns foram removidas.
- Testes seguem legíveis e fáceis de usar por app.
- `uv run pytest` permanece verde.
- Não há mudança funcional no sistema.
