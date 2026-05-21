# Slice 005 — Hardening Operacional e Quality Gate

## Handoff para Implementador LLM

Leia:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/multi-pdf-async-intake/proposal.md`
4. `openspec/changes/multi-pdf-async-intake/design.md`
5. Slices 001–004 deste change
6. Este arquivo.

Implemente somente este slice.

## Problema

Após clusters, task PDF, backend e UI, ainda precisamos fechar o change com garantias operacionais para lotes reais: limites claros, testes de lote maior, documentação de operação e quality gate completo.

## Objetivo

Consolidar a feature para MVP com evidências de qualidade e operação.

## Escopo Preferencial

Arquivos prováveis:

- `config/settings/base.py` / `prod.py` — limites finais se ainda não centralizados
- `README.md` ou documentação operacional existente
- `PROJECT_CONTEXT.md` ou docs do change, se necessário
- testes focados em lote maior e falhas parciais
- `openspec/changes/multi-pdf-async-intake/tasks.md` — marcar status final

Evite mudança funcional grande. Este slice é de fechamento/hardening.

## Requisitos Funcionais/Operacionais

1. Limites de upload por arquivo, por lote e quantidade máxima devem estar centralizados em settings.
2. Tests devem cobrir lote representativo sem custo alto, por exemplo 20 ou 30 arquivos pequenos em memória.
3. Deve haver teste de falha parcial: um arquivo inválido não deve criar caso; válidos seguem regra definida.
4. Documentar como subir workers:
   - dev: `web`, `worker`/LLM e `pdf_worker`;
   - prod: volume de media compartilhado;
   - escala recomendada inicial de `pdf_worker` e `worker` LLM.
5. Documentar alerta de rate limit/custo da LLM e manter LLM com concorrência conservadora.
6. Verificar que `retry > timeout` permanece verdadeiro.
7. Atualizar `tasks.md` deste change com conclusão dos slices implementados.
8. Executar quality gate completo.

## TDD — Testes RED Esperados

Antes de implementar ajustes finais, adicione testes que falhem se ainda não existirem:

1. Upload de 20 ou 30 PDFs pequenos cria o mesmo número de casos e enfileira extração para todos.
2. Lote acima do limite é rejeitado de forma determinística.
3. Limite por arquivo é aplicado server-side.
4. Configuração de clusters mantém `retry > timeout`.

## Critérios de Sucesso

- Feature está documentada para operação local/prod.
- Teste de lote representativo passa.
- Quality gate completo foi executado.
- `tasks.md` reflete status final.
- Relatório final do slice registra evidências.

## Comandos de Validação Obrigatórios

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

Também executar:

```bash
git status --short
```

## Relatório Obrigatório

Crie:

```text
/tmp/ats-web-slice-005-multi-pdf-hardening-quality-report.md
```

Inclua:

- resumo final da feature;
- evidência dos limites configurados;
- evidência de teste de lote;
- resultados do quality gate;
- pendências conhecidas para pós-MVP, se houver.

Responda com:

```text
REPORT_PATH=/tmp/ats-web-slice-005-multi-pdf-hardening-quality-report.md
```

## Stop Rule

Pare após o fechamento do change. Não inicie novas features como OCR, upload resumable, dashboard de fila ou migração para Celery.
