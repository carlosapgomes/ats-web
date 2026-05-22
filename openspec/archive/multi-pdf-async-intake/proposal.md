# Proposal: Upload Múltiplo NIR com Extração PDF Assíncrona

## Contexto

Na validação do fluxo principal com usuários, foi solicitado que a tela do NIR aceite upload simultâneo de múltiplos PDFs. O uso esperado não é eventual: o NIR pode precisar enviar 20–30 arquivos por lote, e o volume futuro pode chegar a aproximadamente 2000 PDFs/dia.

Hoje o ATS aceita apenas 1 PDF por POST. A view salva o arquivo, extrai texto de forma síncrona, avança a FSM até `LLM_STRUCT` e só então enfileira a pipeline LLM no `django-q2`. Esse desenho não é adequado para lotes grandes: a request pode ficar lenta, gerar timeout e criar má percepção inicial do produto.

A investigação comparou o padrão do projeto `sirhosp`, que usa filas model-backed no PostgreSQL com workers em loop e `select_for_update(skip_locked=True)`, e confirmou que o padrão é aplicável. Porém, ao revisar o `django-q2` instalado no ATS, foi confirmado que ele suporta clusters/filas separados via `cluster`/`Q_CLUSTER_NAME`/`ALT_CLUSTERS`. Portanto, não é necessário abandonar `django-q2` neste momento.

## Objetivos

1. Permitir que o NIR envie múltiplos PDFs em uma única submissão, com UX adequada para 20–30 arquivos.
2. Tornar a extração de PDF assíncrona em background, sem bloquear a request web.
3. Separar operacionalmente a fila/worker de extração PDF da fila/worker LLM.
4. Usar a FSM (`Case.status`) e `CaseEvent` como fonte de verdade de rastreabilidade clínica/operacional.
5. Manter `django-q2` como executor assíncrono, configurado com clusters separados:
   - `pdf` para extração de PDF;
   - `llm` para pipeline LLM.
6. Garantir que `web` e workers tenham acesso ao mesmo storage local de PDFs.
7. Preparar o desenho para escalar gradualmente até ~2000 PDFs/dia sem introduzir Celery/Redis neste MVP.

## Não Objetivos

- Não migrar para Celery, RQ, Redis ou RabbitMQ neste change.
- Não substituir toda a pipeline LLM por worker model-backed customizado.
- Não redesenhar o domínio clínico, prompts, contrato LLM ou rulebook.
- Não criar API REST/SPA.
- Não implementar upload chunked/resumable neste change.
- Não implementar processamento OCR para PDFs digitalizados sem texto.
- Não criar object storage/S3; o projeto continua com filesystem local compartilhado.

## Decisões Propostas

### D1. `django-q2` continua no MVP

O `django-q2` será mantido porque já está integrado, oferece task queue, retries, timeouts, results/admin/scheduler e suporta filas separadas por cluster. O problema atual é de configuração/uso como fila única, não uma limitação impeditiva.

### D2. Clusters separados

Configurar clusters `pdf` e `llm` via `ALT_CLUSTERS` e iniciar serviços separados no Compose:

- `pdf_worker`: `Q_CLUSTER_NAME=pdf`, mais concorrência, timeout menor;
- `worker` ou `llm_worker`: `Q_CLUSTER_NAME=llm`, concorrência controlada, timeout maior.

### D3. FSM como fonte de verdade

O `django-q2` executa tarefas, mas o estado operacional confiável fica em `Case.status` e `CaseEvent`.

Fluxo principal:

```text
NEW
→ R1_ACK_PROCESSING       # upload aceito / aguardando extração
→ EXTRACTING              # worker PDF iniciou extração
→ LLM_STRUCT              # texto extraído e pronto para IA
→ LLM_SUGGEST ...         # worker LLM atual
```

### D4. Request web deve ser rápida

A view do NIR deve apenas validar arquivos, criar `Case`, salvar PDFs, registrar eventos/transições iniciais e enfileirar extração. A extração de texto não deve ocorrer na request.

### D5. Storage local compartilhado

Como o PDF será salvo pelo `web` e lido pelo `pdf_worker`, o Compose de produção precisa montar um volume de media compartilhado entre `web`, `pdf_worker` e, opcionalmente, `llm_worker`.

## Riscos

- `retry <= timeout` pode causar reexecução indevida; corrigir para `retry > timeout` por cluster.
- Lotes grandes podem pressionar limites de upload HTTP/proxy; definir limites explícitos por arquivo e por lote.
- PDFs inválidos/corrompidos devem falhar individualmente sem comprometer o lote.
- Tasks podem ser reexecutadas; extração e enqueue da pipeline precisam ser idempotentes.
- Concorrência LLM excessiva pode gerar rate limit/custo; separar `llm` com poucos workers.
- Se o volume real superar o previsto, pode ser necessário migrar broker ORM para Redis/SQS ou Celery, mas isso não é necessário para o MVP.

## Referências

- Intake atual: `apps/intake/views.py`, `apps/intake/forms.py`, `static/js/upload.js`, `templates/intake/intake_home.html`
- Pipeline task atual: `apps/pipeline/tasks.py`
- Configuração atual `django-q2`: `config/settings/base.py`, `config/settings/prod.py`
- Compose atual: `docker-compose.dev.yml`, `docker-compose.prod.yml`
- Padrão investigado no SIRHOSP: `/home/carlos/projects/sirhosp/apps/ingestion/management/commands/process_ingestion_runs.py`
- `django-q2` instalado: suporte a `cluster` em `async_task(..., q_options={"cluster": ...})` e `Q_CLUSTER_NAME`/`ALT_CLUSTERS` em `django_q.conf.Conf`
