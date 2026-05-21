# Slice 001 — Clusters django-q2 e Compose

## Handoff para Implementador LLM

Leia antes de codar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/multi-pdf-async-intake/proposal.md`
4. `openspec/changes/multi-pdf-async-intake/design.md`
5. Este arquivo.

Implemente somente este slice.

## Problema

O projeto usa `django-q2`, mas hoje a configuração efetiva é uma fila/cluster principal. Para suportar upload múltiplo com extração PDF em background sem interferir na pipeline LLM, precisamos separar operacionalmente os clusters `pdf` e `llm`.

Além disso, `retry` está menor que `timeout` em configurações atuais, o que pode causar reexecução indevida de tasks longas.

## Objetivo

Configurar `django-q2` para clusters separados e ajustar Docker Compose para subir workers distintos:

- `pdf_worker` usando `Q_CLUSTER_NAME=pdf`;
- `worker`/LLM usando `Q_CLUSTER_NAME=llm`.

Também alterar `enqueue_pipeline` para enviar tasks LLM explicitamente ao cluster `llm`.

## Escopo Preferencial

Arquivos prováveis:

- `config/settings/base.py`
- `config/settings/prod.py`
- `docker-compose.dev.yml`
- `docker-compose.prod.yml`
- `apps/pipeline/tasks.py`
- `apps/pipeline/tests/test_orchestrator.py` ou teste novo focado em task enqueue

Evite tocar no upload ou criar task PDF neste slice.

## Requisitos Funcionais

1. `Q_CLUSTER` deve ter `ALT_CLUSTERS` com `pdf` e `llm`.
2. `retry` deve ser maior que `timeout` nos clusters configurados.
3. `enqueue_pipeline(case_id)` deve chamar `async_task` com `q_options={"cluster": "llm", ...}`.
4. `docker-compose.dev.yml` deve definir serviço `pdf_worker`.
5. Serviço worker LLM deve definir `Q_CLUSTER_NAME=llm`.
6. Serviço `pdf_worker` deve definir `Q_CLUSTER_NAME=pdf`.
7. `docker-compose.prod.yml` deve incluir `pdf_worker` e volume `media_prod` compartilhado ao menos entre `web` e `pdf_worker`.
8. Não implementar ainda `apps.intake.tasks.execute_pdf_extraction`.

## TDD — Testes RED Esperados

Antes de implementar, adicione/ajuste teste que falhe mostrando:

1. `enqueue_pipeline` envia `q_options["cluster"] == "llm"`.
2. Configuração `Q_CLUSTER["ALT_CLUSTERS"]` contém `pdf` e `llm`.
3. Para cada cluster, `retry > timeout`.

Testes de Compose podem ser validação por inspeção manual no relatório, se não houver parser YAML no projeto.

## Critérios de Sucesso

- LLM passa a ser roteado explicitamente para cluster `llm`.
- Compose tem serviço `pdf_worker` pronto para receber tasks futuras.
- Produção tem volume de media compartilhado para a futura extração em background.
- Nenhuma mudança de comportamento do upload ainda.

## Comandos de Validação Focados

```bash
uv run pytest apps/pipeline/tests -q
uv run ruff check config apps/pipeline docker-compose.dev.yml docker-compose.prod.yml
uv run mypy config apps/pipeline
```

Se `ruff` não aceitar YAML como argumento, rode nos diretórios Python e registre validação manual do Compose no relatório.

## Relatório Obrigatório

Crie:

```text
/tmp/ats-web-slice-001-q2-clusters-compose-report.md
```

Inclua:

- snippet antes/depois de `Q_CLUSTER`;
- snippet antes/depois de `enqueue_pipeline`;
- snippet dos serviços Compose;
- testes executados;
- riscos/pendências.

Responda com:

```text
REPORT_PATH=/tmp/ats-web-slice-001-q2-clusters-compose-report.md
```

## Stop Rule

Pare após este slice. Não implemente upload múltiplo nem extração PDF assíncrona neste slice.
