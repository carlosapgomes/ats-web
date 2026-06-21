# Runbook de Deploy — `corrected-case-resubmission-linkage`

**Change:** `corrected-case-resubmission-linkage`
**Commits incluídos:** `05084cc`, `0b69b82`, `67edea9`, `8d138f7`
**Branch:** `main`
**Data de criação:** 2026-06-21
**Classificação de risco:** 🟢 Baixo

---

## 1. Análise de risco

| Aspecto | Avaliação |
|---|---|
| **Migration** | `apps/cases/migrations/0007_add_correction_fields.py` — **aditiva, não-bloqueante**. 4 `AddField` nullable/blank. Sem data migration, sem rename, sem drop. Roda em milissegundos, sem lock de tabela. |
| **Compatibilidade** | Código velho ignora os novos campos → **zero downtime possível**. A migration pode rodar antes do restart. |
| **Mudanças de FSM / pipeline / schema existente** | Nenhuma. Os 17 estados FSM são preservados. |
| **Dados sensíveis** | Nenhum dado em produção é migrado/tocado. Volume de mídia (`media_prod`) não é afetado. |
| **Variáveis de ambiente novas** | Nenhuma (confirmado em `docker-compose.prod.yml`). |
| **Classificação** | 🟢 **Baixo risco** (com plano de rollback anyway, conforme `PROJECT_CONTEXT.md`). |

### O que o change entrega

- Fluxo NIR de **reenvio corrigido explícito** a partir de um caso anterior
  (rota `<uuid:case_id>/corrected-resubmission/`), criando novo `Case`
  vinculado via `corrects_case`, sem sobrescrever/reabrir o original.
- 4 campos opcionais em `Case`: `corrects_case`, `correction_reason`,
  `correction_created_by`, `correction_created_at`.
- Eventos auditáveis `CASE_CORRECTION_CREATED` (novo caso) e
  `CASE_MARKED_SUPERSEDED` (caso anterior).
- Visibilidade NIR: cards "Reenvio corrigido" / "Caso corrigido por novo
  envio" no detalhe; botão/badge na busca de encerrados.
- Visibilidade médica: card "Reenvio corrigido" na tela de decisão, com
  motivo do NIR e aviso explícito de que documentos/anexos do caso
  anterior não foram herdados.
- Deduplicação visual: quando `corrects_case` aponta para o mesmo caso que
  o prior-case lookup, apenas o card explícito é renderizado.

---

## 2. Pré-requisitos (no servidor de produção)

```bash
cd /caminho/do/ats-web
git status          # deve estar limpo
git log --oneline -1 # anotar o ponto de partida (para rollback)
```

Confirmar que as variáveis de ambiente obrigatórias já estão
configuradas no host:

- `POSTGRES_PASSWORD`, `DJANGO_SECRET_KEY`, `OPENAI_API_KEY`
- `CSRF_TRUSTED_ORIGINS`, `ALLOWED_HOSTS`, `INTRANET_IP_RANGE`
- Demais vars esperadas por `docker-compose.prod.yml`

Confirmar a partição de backups:

```bash
df -h /archive/backups                 # uso < 80%, espaço livre suficiente
touch /archive/backups/.write-test && rm /archive/backups/.write-test
```

---

## 3. Passos de deploy

Defina o alias de Compose usado em todo o runbook:

```bash
DPROD="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
```

### Passo 1 — Backup (obrigatório)

```bash
# 1a. Snapshot do Postgres
$DPROD exec -T db pg_dump -U ats_web -d ats_web -Fc \
  > /archive/backups/pre-corrected-resubmission-$(date +%Y%m%d-%H%M).dump

# 1b. Snapshot do volume de media (PDFs/anexos) — opcional mas recomendado
docker run --rm -v ats-web-prod_media_prod:/data:ro \
  -v /archive/backups:/backup alpine \
  tar czf /backup/media-pre-corrected-resubmission-$(date +%Y%m%d-%H%M).tgz -C /data .

# Confirmar que os arquivos não estão vazios
ls -lh /archive/backups/pre-corrected-resubmission-*.dump
ls -lh /archive/backups/media-pre-corrected-resubmission-*.tgz
```

> Anote o nome do arquivo de dump gerado — ele é referenciado no
> **Plano de Rollback**.

### Passo 2 — Atualizar código

```bash
git fetch origin
git checkout main
git pull origin main
git log --oneline -3   # confirmar que 8d138f7 está presente (ou posterior)
```

### Passo 3 — Build das novas imagens

Os serviços `web`, `worker` e `pdf_worker` fazem `build` da imagem (o
código é copiado no build, **não** é volume mount), então precisam ser
recriados:

```bash
$DPROD build --pull web worker pdf_worker
```

> `--pull` garante imagem base `python:3.13-slim` atualizada.

### Passo 4 — Aplicar a migration (app ainda no ar)

A migration é aditiva e compatível com o código velho, então roda
**antes** do restart, com zero downtime:

```bash
$DPROD run --rm web uv run python manage.py migrate --settings=config.settings.prod
```

**Verificar saída esperada:**

```
Applying cases.0007_add_correction_fields... OK
```

> Se aparecer qualquer erro aqui: **NÃO prosseguir**. Restaurar o backup
> do Passo 1a (ver Seção 4) e parar.

### Passo 5 — Subir os containers com a imagem nova

```bash
$DPROD up -d
```

Isso recria apenas os serviços cuja imagem mudou. O `db` não é reiniciado.

### Passo 6 — Smoke tests pós-deploy

```bash
# 6a. Saúde dos containers
$DPROD ps                          # todos "running", sem Restarting
$DPROD logs --tail=30 web          # sem tracebacks no startup
$DPROD logs --tail=30 worker
$DPROD logs --tail=30 pdf_worker

# 6b. Verificar que a app responde
curl -sS -o /dev/null -w "%{http_code}\n" https://chd.projetoshgrs.com/
#    → esperar 200 ou 302 (login redirect)

# 6c. Checar migration aplicada
$DPROD exec -T web uv run python manage.py showmigrations cases \
  --settings=config.settings.prod | tail -10
#    → deve mostrar "[X] 0007_add_correction_fields"
```

### Passo 7 — Validação funcional (manual, opcional mas recomendada)

No app, com um usuário NIR em sessão real da intranet:

1. Abrir um caso qualquer → confirmar botão "↻ Reenviar caso corrigido".
2. Criar um caso de teste via reenvio corrigido (PDF qualquer + motivo).
3. Confirmar redirecionamento para o novo caso e o card
   "Reenvio corrigido".
4. No caso original, confirmar o card "Caso corrigido por novo envio".
5. Quando o novo caso chegar em `WAIT_DOCTOR`, abrir como médico e
   confirmar o card "Reenvio corrigido" com o motivo do NIR e o aviso de
   não-herança de documentos.

### Passo 8 — Monitoramento (próximas 24h)

```bash
# Erros 5xx / exceções
$DPROD logs --since=24h web 2>&1 \
  | grep -iE "error|traceback|exception" | grep -vi "warn"

# Workers saudáveis (processando tarefas)
$DPROD logs --since=1h worker pdf_worker 2>&1 | tail -20
```

---

## 4. Plano de Rollback

Caso ocorra regressão crítica, existem três níveis, do menos invasivo
ao mais invasivo.

### 4.1 Rollback "suave" (recomendado, sem mexer no DB)

Os 4 campos novos são nullable — o código anterior funciona perfeitamente
com eles presentes como colunas inertes. Basta voltar o código e rebuild:

```bash
git checkout <commit-anterior-ao-change>   # ex.: 78bb5b7
$DPROD build web worker pdf_worker
$DPROD up -d
```

**Não é necessário** reverter a migration. As colunas ficam inertes (sem
dados em produção, já que a feature acabou de entrar).

### 4.2 Rollback completo (só se a migration tiver causado problema)

```bash
# Reverter migration (seguro: nenhuma row produção tem dado nos campos novos)
$DPROD run --rm web uv run python manage.py migrate cases 0006 \
  --settings=config.settings.prod

# Voltar código e rebuild
git checkout <commit-anterior-ao-change>
$DPROD build web worker pdf_worker
$DPROD up -d
```

### 4.3 Rollback de última instância (restaurar backup)

Usar o snapshot criado no Passo 1. Substitua `<TIMESTAMP>` pelo nome do
arquivo anotado:

```bash
# Restaurar dump do Postgres
$DPROD exec -T db pg_restore -U ats_web -d ats_web -c -1 \
  < /archive/backups/pre-corrected-resubmission-<TIMESTAMP>.dump

# Restaurar mídia (se necessário)
docker run --rm -v ats-web-prod_media_prod:/data \
  -v /archive/backups:/backup alpine \
  tar xzf /backup/media-pre-corrected-resubmission-<TIMESTAMP>.tgz -C /data

# Voltar código
git checkout <commit-anterior-ao-change>
$DPROD build web worker pdf_worker
$DPROD up -d
```

---

## 5. Pós-deploy (fechamento do change)

Após o deploy verde, fechar o change no OpenSpec:

1. Confirmar que todos os itens do `tasks.md` do change estão marcados.
2. Mover `openspec/changes/corrected-case-resubmission-linkage/` para
   `openspec/archive/`.
3. Atualizar `PROJECT_CONTEXT.md` com a nova funcionalidade (se aplicável).

---

## 6. Notas operacionais

- **Sem janela obrigatória**: pela natureza aditiva da migration, o
  deploy pode ser feito a qualquer hora. Recomenda-se horário de baixo
  tráfego apenas como cuidado padrão.
- **Worker / pdf_worker**: precisam restart porque importam os models
  atualizados (a classe `Case` mudou de assinatura). O `up -d` do Passo
  5 cuida disso.
- **Sem configuração extra de LLM/pipeline**: o novo caso segue o fluxo
  normal de extração/LLM, sem prompts novos nem seeds necessários.
