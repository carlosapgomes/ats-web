# Runbook de Deploy — `introduce-colonoscopy-exam-workflow`

**Change:** `introduce-colonoscopy-exam-workflow` (8 slices, do Slice 001 ao Slice 008)
**Branch:** `feature/colonoscopy-exam-workflow` → `main`
**Classificação de risco:** 🔴 CRÍTICO / HIGH-ARCH (ativação de novo tipo de exame em produção, migration com UPDATE full-row e AddIndex não-concorrente)

---

## Quick reference

Cópia de mão — para uso **após** leitura completa do runbook e após o
Passo 1 (backup) já estar em `/archive/backups/`. Executar como `apps`.
**Todos os comandos usam caminhos absolutos e `--project-directory` — não
dependem do diretório corrente.**

```bash
# Diretório real de instalação (ajustar para o ambiente)
PROJECT_DIR=/opt/ats-web/app
BACKUP_DIR=/archive/backups/2026-XXX-colonoscopy
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# FAIL-FAST (obrigatório em cópia de mão): qualquer falha de build/stop/migrate/
# seed/up ABORTA o bloco imediatamente. Sem `|| true`/`&&` que engula erro: um
# migrate ou seed falho NUNCA pode chegar ao up. Em falha: PARAR (Seção 5).
set -euo pipefail

# 1. (pré) Backup já feito, validado por conteúdo e movido para /archive/backups/ (Passo 1).

# 2. Atualizar código
git -C "$PROJECT_DIR" fetch origin && git -C "$PROJECT_DIR" checkout main && git -C "$PROJECT_DIR" pull origin main

# 3. Build das novas imagens
$DPROD build --pull web worker pdf_worker

# 4. JANELA DE MANUTENÇÃO (Passo 4) — parar TODOS os serviços. O web ANTIGO
#    não pode aceitar escritas durante a migration 0014 (o default de banco é
#    removido e o código antigo insere Case sem exam_type -> NOT NULL).
#    NUNCA "start" dos containers antigos depois: subir apenas as imagens novas.
$DPROD stop web worker pdf_worker

# 5. Migration + seed com a imagem NOVA (serviços parados; db permanece no ar)
$DPROD run --rm web uv run python manage.py migrate --settings=config.settings.prod
$DPROD run --rm web uv run python manage.py seed_prompts --settings=config.settings.prod

# 6. Subir apenas as imagens novas (recriação forçada garante a imagem do Passo 3)
$DPROD up -d --force-recreate web worker pdf_worker

# 7. PRECHECK BINÁRIO de prompts antes de ativar a flag (ver Passo 7) — STOP se falhar

# 8. Flag de intake permanece DESLIGADA por padrão (Passo 8 ativa apenas web)
```

> Passos 9 (validação funcional) e 10 (monitoramento 24h) seguem abaixo em
> formato completo. A ativação da flag é um passo **explícito e separado**
> (Passo 8) — o deploy do código não ativa colonoscopia sozinho, e a flag é
> lida **somente pelo serviço `web`**.

---

## 1. Análise de risco

| Aspecto | Avaliação |
|---|---|
| **Risco global** | 🔴 **CRÍTICO / HIGH-ARCH** — conforme `proposal.md`. Ativação de novo tipo de exame com mudança de schema e contratos LLM em produção. |
| **Migration** | `apps/cases/migrations/0014_case_exam_type.py` — **aditiva, mas NÃO é zero downtime**. Executa `AddField` (default histórico `eda`) + **`UPDATE` de todas as linhas existentes** (backfill `RunPython` elidable, sem ler PDF/JSON/texto, sem reprocessar) + **`AddIndex` normal (não `CONCURRENTLY`)** em `(status, exam_type)`. O `UPDATE` full-row e o `AddIndex` podem adquirir locks e contender com escrita. **Exige janela controlada de baixa atividade** (Passo 4). |
| **Compatibilidade** | Código velho ignora o novo campo após a migration, mas **não conhece `exam_type` NOT NULL (sem default)** — por isso `web`, `worker` e `pdf_worker` são **parados** durante a janela (Passo 4) e só as imagens novas voltam ao ar (Passo 6). |
| **Mudanças de FSM / pipeline / schema existente** | Nenhum estado novo; 17 estados FSM preservados. Contrato LLM1 evolui de forma aditiva (`medications_described[]` e `exam_type=colonoscopy` aceito). |
| **Dados sensíveis** | Backfill não lê conteúdo clínico. Nenhum PDF/JSON/texto é migrado. |
| **Variáveis de ambiente novas** | `COLONOSCOPY_INTAKE_ENABLED` (default `false`). No Compose de produção **somente o serviço `web` recebe a variável** (`docker-compose.prod.yml`); `worker`/`pdf_worker` **não** recebem nem consultam a flag. |
| **Prompts** | `seed_prompts` cria os 8 nomes canônicos (4 EDA + 4 colonoscopia) quando ausentes; **não** reativa versões inativas. Precheck binário exige os 4 nomes colonoscopia **ativos** antes de ligar a flag (Passo 7). |
| **Rollback** | Não destrutivo e **preferido**: desligar flag e **manter a imagem nova rodando** (schema-compatible; coluna sem default é ok porque a imagem nova sempre envia `exam_type`). Reverter para a imagem antiga é **exceção** e exige bridge de schema verificável (`SET DEFAULT 'eda'` após drenagem) — código antigo omite `exam_type` no INSERT. Detalhes na Seção 5. |

### O que o change entrega

- `Case.exam_type` distingue **EDA** e **Colonoscopia**; upload exige escolha explícita e lote homogêneo.
- Pipeline LLM processa colonoscopia com prompts/pré-perfis próprios; política clínica comum sem exceção de corpo estranho para colonoscopia.
- Filtros por tipo em médico (Pendentes/Decididos Hoje), CHD (Pendentes/Processados/Histórico), NIR (operacionais/encerrados) e dashboard (tabela gerencial).
- Dashboard: métricas consolidadas preservadas + **breakdown EDA/Colonoscopia** por período.
- Alertas medicamentosos informativos (anticoagulante/antiagregante) no relatório médico — **sem** alterar decisão/sugestão e **sem** orientação de suspensão.
- Correção de tipo pelo NIR em revisão manual (`WAIT_R1_CLEANUP_THUMBS` + `manual_review_required` com mismatch/mixed/unknown), com reprocessamento auditável do mesmo caso.

---

## 2. Pré-requisitos (no servidor de produção)

- Acesso de shell ao servidor de produção como `apps` (conforme operação atual).
- `docker compose` funcional com acesso ao projeto (`--project-directory`).
- Acesso ao registry da imagem de release (GHCR) com a tag nova.
- **Backup do Postgres e do volume de mídia `media_prod` obrigatório** antes de qualquer passo (Passo 1) — validado por conteúdo, não apenas tamanho.
- **Janela de baixa atividade acordada com a operação** para a migration (Passo 4).
- Comunicar aos times NIR/médico/CHD que o novo tipo de exame será ativado (a flag é ligada em momento explícito, ver Passo 8).

---

## 3. Passos de deploy

### Passo 1 — Backup (obrigatório, validado por conteúdo)

```bash
# Caminhos absolutos — nada depende do diretório corrente.
PROJECT_DIR=/opt/ats-web/app
BACKUP_DIR=/archive/backups/2026-XXX-colonoscopy
mkdir -p "$BACKUP_DIR"
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# 1a. Dump do Postgres (produção) — pipeline FAIL-FAST. set -euo pipefail faz o
#     shell abortar se QUALQUER comando da pipeline falhar, incluindo o pg_dump à
#     esquerda do pipe: um dump falho nunca vira "gzip válido" aceito adiante.
set -euo pipefail
STAMP=$(date +%Y%m%d_%H%M)
DUMP="${BACKUP_DIR}/ats_web_pre_colonoscopy_${STAMP}.sql.gz"
$DPROD exec -T db pg_dump -U ats_web ats_web | gzip > "$DUMP"

# 1b. VALIDAÇÃO do dump por CONTEÚDO (não apenas tamanho) — cada check falho
#     encerra a execução (exit 1); nunca seguir com backup vazio/truncado.
#     zgrep lê o gzip diretamente (sem pipeline zcat|grep, evitando SIGPIPE com pipefail).
gzip -t "$DUMP" || { echo "ERRO: gzip inválido/truncado: $DUMP"; exit 1; }
zgrep -q -- "PostgreSQL database dump" "$DUMP" \
  || { echo "ERRO: dump sem marker de PostgreSQL: $DUMP"; exit 1; }
DUMP_LINES=$(zgrep -c "" "$DUMP")
[ "${DUMP_LINES}" -ge 100 ] \
  || { echo "ERRO: dump com conteúdo suspeito (${DUMP_LINES} linhas): $DUMP"; exit 1; }
echo "Dump gzip OK: ${DUMP_LINES} linhas SQL, marker PostgreSQL presente"

# 1c. Snapshot do volume de mídia REAL herdado pelo serviço web (media_prod).
#     NUNCA inventar nome de volume: resolve-se o volume montado em /app/media
#     no container atual do serviço web (nome real: <projeto>_media_prod, ex.
#     ats-web-prod_media_prod). Se a resolução falhar, PARAR — não prosseguir.
WEB_CID="$($DPROD ps -q web)"
test -n "$WEB_CID" || { echo "ERRO: serviço web não encontrado"; exit 1; }
MEDIA_VOLUME="$(docker inspect "$WEB_CID" --format \
  '{{range .Mounts}}{{if eq .Destination "/app/media"}}{{.Name}}{{end}}{{end}}')"
test -n "$MEDIA_VOLUME" || { echo "ERRO: não foi possível resolver o volume media_prod de web"; exit 1; }
echo "Volume de mídia resolvido: $MEDIA_VOLUME"

docker run --rm \
  -v "${MEDIA_VOLUME}":/media:ro \
  -v "${BACKUP_DIR}":/backup \
  alpine tar czf "/backup/media_pre_colonoscopy_${STAMP}.tar.gz" -C /media .

# 1d. VALIDAÇÃO do tar por CONTEÚDO (listagem completa + mínimo de entradas).
#     Falha ABORTA a execução (exit 1) — sob set -e, um comando à esquerda de
#     `&&` que falha NÃO encerra o script; por isso usa-se `|| { ...; exit 1; }`.
MEDIA_TAR="${BACKUP_DIR}/media_pre_colonoscopy_${STAMP}.tar.gz"
tar -tzf "$MEDIA_TAR" > /dev/null \
  || { echo "ERRO: tar de mídia inválido/truncado: $MEDIA_TAR"; exit 1; }
MEDIA_ENTRIES=$(tar -tzf "$MEDIA_TAR" | wc -l)
[ "${MEDIA_ENTRIES}" -ge 1 ] \
  || { echo "ERRO: tar de mídia sem entradas: $MEDIA_TAR"; exit 1; }
echo "Tar de mídia OK: ${MEDIA_ENTRIES} entradas"

# Confirmar presença/ausência esperada de arquivos
ls -lh "${BACKUP_DIR}"/ats_web_pre_colonoscopy_*.sql.gz "${BACKUP_DIR}"/media_pre_colonoscopy_*.tar.gz
```

> **Precheck:** antes do deploy, registrar o baseline de casos em voo
> (ver Seção 4.1) para comparar depois da ativação.

### Passo 2 — Atualizar código

```bash
PROJECT_DIR=/opt/ats-web/app
git -C "$PROJECT_DIR" fetch origin && git -C "$PROJECT_DIR" checkout main && git -C "$PROJECT_DIR" pull origin main
git -C "$PROJECT_DIR" log --oneline -5        # confirmar os commits do change no topo
```

### Passo 3 — Build das novas imagens

```bash
$DPROD build --pull web worker pdf_worker
```

### Passo 4 — JANELA DE MANUTENÇÃO: migration 0014 com serviços parados (NÃO é zero downtime)

A migration `cases.0014_case_exam_type` executa o seguinte DDL (SQL gerado por
`uv run python manage.py sqlmigrate cases 0014`, reproduzido para raciocínio de
ordenação):

```sql
ALTER TABLE "cases_case" ADD COLUMN "exam_type" varchar(20) DEFAULT 'eda' NOT NULL;
ALTER TABLE "cases_case" ALTER COLUMN "exam_type" DROP DEFAULT;  -- default de banco REMOVIDO
-- RunPython (elidable): UPDATE full-row forçando exam_type='eda' em todas as linhas
CREATE INDEX "cases_status_exam_type_idx" ON "cases_case" ("status", "exam_type");  -- não-concorrente
```

**Por que parar TAMBÉM o `web` (e não só os workers):** após o `DROP DEFAULT`, o
banco exige `exam_type` NOT NULL em qualquer INSERT. O código da imagem ANTIGA
insere `Case` sem `exam_type` — qualquer escrita do `web` antigo durante ou
depois da migration falharia. O `web` antigo precisa estar **parado** até a
imagem nova estar no ar; `worker`/`pdf_worker` também não podem continuar
escrevendo durante o `UPDATE` full-row e o `AddIndex` não-concorrente (locks).

**Downtime esperado (honesto):** a janela de manutenção deixa o sistema
indisponível (web fora do ar, workers e filas pausados, uploads bloqueados)
durante parada → migration → seed → subida. Estimativa realista: **minutos**
(dominado pelo `UPDATE` full-row + `AddIndex`), podendo ser maior em tabelas
muito grandes. Acordar e comunicar esse downtime à operação antes de abrir a
janela.

Procedimento (executar como script; `set -euo pipefail` aborta em qualquer falha):

```bash
set -euo pipefail
# a) Janela de manutenção acordada com a operação (fora do horário de pico).
# b) PARAR todos os serviços que escrevem no banco: web (uploads/reenvios/escritas
#    HTTP), worker e pdf_worker (pipeline/extração). O db permanece no ar.
$DPROD stop web worker pdf_worker

# c) Aplicar a migration COM A IMAGEM NOVA (serviços parados; db no ar).
#    Saída esperada: Applying cases.0014_case_exam_type... OK
$DPROD run --rm web uv run python manage.py migrate --settings=config.settings.prod

# d) Verificar locks/atividade durante a janela (em outro shell, se necessário):
$DPROD exec -T db psql -U ats_web -d ats_web -c \
  "SELECT pid, state, wait_event_type, query FROM pg_stat_activity WHERE state <> 'idle';"

# e) NÃO "start" os containers antigos depois da migration: o código antigo não
#    conhece exam_type NOT NULL (sem default). Subir somente as imagens novas no
#    Passo 6 ($DPROD up -d --force-recreate web worker pdf_worker).
```

Se erro na migration: **NÃO continuar** — ir para a Seção 5 (Rollback).

### Passo 5 — Seed dos prompts (idempotente; imagem nova, serviços ainda parados)

```bash
$DPROD run --rm web uv run python manage.py seed_prompts --settings=config.settings.prod
```

Roda com a imagem nova (mesma do Passo 4c), com `web`/`worker`/`pdf_worker`
ainda parados; o db permanece no ar. Cria (se ainda não existirem) versões
ativas dos 8 nomes canônicos:

```text
llm1_system / llm1_user / llm2_system / llm2_user            (EDA — legados)
colonoscopy_llm1_system / colonoscopy_llm1_user
colonoscopy_llm2_system / colonoscopy_llm2_user              (Colonoscopia)
```

- Idempotente: não sobrescreve versões já ativas.
- Nomes EDA **não são substituídos** pelos de colonoscopia.
- **Limitação:** `seed_prompts` não reativa versões inativas. Se um nome
  colonoscopia já existir como versão **inativa**, o seed o ignora — a
  ativação deve ser feita na UI (Passo 7).

### Passo 6 — Subir os containers com a imagem nova

```bash
$DPROD up -d --force-recreate web worker pdf_worker
```

Força a recriação para garantir que os containers parados sejam substituídos
pelas imagens novas (Passo 3) — **nunca** `docker compose start` dos containers
antigos após a migration. Depois da subida, confirmar os três serviços de pé:
`$DPROD ps`. Só então seguir para o precheck binário de prompts (Passo 7).

### Passo 7 — PRECHECK binário de prompts (obrigatório, após a subida da imagem nova)

Depois do `up -d` do Passo 6 (web novo no ar), antes de ligar
`COLONOSCOPY_INTAKE_ENABLED`, os **quatro** nomes de prompt de colonoscopia
devem ter uma **versão ativa**. O comando abaixo falha (exit 1) se qualquer nome
não estiver ativo — **em caso de falha, PARAR e não ativar a flag**:

```bash
$DPROD exec -T web uv run python manage.py shell --settings=config.settings.prod -c "
from apps.llm.models import PromptTemplate
names = ['colonoscopy_llm1_system', 'colonoscopy_llm1_user',
         'colonoscopy_llm2_system', 'colonoscopy_llm2_user']
missing = [n for n in names
           if not PromptTemplate.objects.filter(name=n, is_active=True).exists()]
if missing:
    print('PRECHECK FALHOU — prompts colonoscopia sem versão ativa:', missing)
    raise SystemExit(1)
print('PRECHECK OK — 4 prompts colonoscopia ativos')
"
```

**Se falhar (versões inativas):** ativar na UI de admin — **Gestão de Prompts** —
localizar cada nome, **desativar** a versão ativa (se houver outra) e
**ativar** a versão de colonoscopia desejada (1 ativo por nome). Repetir o
precheck até passar. **Não ativar a flag com precheck vermelho.**

### Passo 8 — Flag de intake (default desligada; leitura apenas em `web`)

O código já funciona com a flag **desligada** (`false`): o sistema roda
normalmente para EDA e casos colonoscopia **já existentes** continuam
processáveis. **Novos uploads** de colonoscopia são bloqueados até a flag ser
ligada.

**Semântica da flag:** `COLONOSCOPY_INTAKE_ENABLED` existe **somente no
serviço `web`** (`docker-compose.prod.yml`). `worker` e `pdf_worker` **não
recebem a variável** e **nenhum worker/pipeline a consulta** — a flag nunca
bloqueia processamento de casos existentes.

**Como ativar globalmente (rollout):**

1. Definir `COLONOSCOPY_INTAKE_ENABLED=true` no ambiente de produção
   (`.env` privado ou orquestrador);
2. recriar **apenas** o serviço que lê a variável:

```bash
$DPROD up -d --force-recreate web
```

> Não é necessário recriar `worker`/`pdf_worker`: eles não recebem nem
> consultam a variável. Recriá-los por esse motivo seria uma operação inútil.

### Passo 9 — Smoke tests (após ativação da flag)

Executar com usuários reais em ambiente de homologação primeiro; em produção,
com casos controlados e acompanhamento do NIR.

| Cenário | Procedimento | Resultado esperado |
|---|---|---|
| **EDA** | Upload de um relatório EDA com tipo **EDA** | Caso segue o fluxo normal; badge EDA; sem mismatch; aparece na fila médica |
| **Colonoscopia** | Upload de um relatório de colonoscopia com tipo **Colonoscopia** | Caso processa com prompts colonoscopia; badge Colonoscopia; chega à fila médica; decisão/fluxos idênticos a EDA |
| **Mixed** | PDF com solicitações atuais de EDA **e** colonoscopia | Caso bloqueado para **Revisão Manual** (mixed) — NIR deve separar os PDFs e reenviar um por tipo |
| **Medicamentos** | Relatório EDA ou colonoscopia descrevendo anticoagulante/antiagregante | Relatório médico exibe **alerta informativo**; sugestão/decisão **não** mudam; **sem** orientação de suspensão |
| **Filtros** | Médico/CHD/NIR/dashboard filtram por tipo | Listas retornam somente o tipo selecionado; termo/status/datas compõem; paginação preserva o filtro |
| **Breakdown** | Dashboard com período contendo EDA e colonoscopia | Cards consolidados somam ambos; breakdown mostra linhas EDA e Colonoscopia; soma das linhas fecha com o consolidado |

---

## 4. Monitoramento e checks de casos em voo

### 4.1 Consultas de casos por tipo/status

```bash
$DPROD exec -T web uv run python manage.py shell --settings=config.settings.prod -c "
from apps.cases.models import Case, CaseStatus

print('— Casos por tipo (total) —')
for t in ('eda', 'colonoscopy'):
    print(t, Case.objects.filter(exam_type=t).count())

print('— Em voo (não CLEANED) por tipo —')
for t in ('eda', 'colonoscopy'):
    n = Case.objects.filter(exam_type=t).exclude(status=CaseStatus.CLEANED).count()
    print(t, n)

print('— Esperas por etapa (snapshot) —')
print('WAIT_DOCTOR', Case.objects.filter(status=CaseStatus.WAIT_DOCTOR).count())
print('WAIT_APPT', Case.objects.filter(status=CaseStatus.WAIT_APPT).count())
print('WAIT_R1_CLEANUP_THUMBS', Case.objects.filter(status=CaseStatus.WAIT_R1_CLEANUP_THUMBS).count())
print('FAILED', Case.objects.filter(status=CaseStatus.FAILED).count())
"
```

### 4.2 Monitoramento de falhas, mismatch e filas

- **Falhas:** `Case.status = FAILED` (query acima) — revisar daily; casos
  colonoscopia com falha são elegíveis a correção/reprocessamento pelo NIR
  apenas em revisão manual (`WAIT_R1_CLEANUP_THUMBS` + `manual_review_required`
  com motivo mismatch/mixed/unknown) — nunca em estados de worker ou após
  decisão médica.
- **Mismatch/mixed:** eventos `EXAM_TYPE_MISMATCH_DETECTED` e correções
  `EXAM_TYPE_CORRECTED` na auditoria:

```bash
$DPROD exec -T web uv run python manage.py shell --settings=config.settings.prod -c "
from apps.cases.models import CaseEvent
for et in ('EXAM_TYPE_MISMATCH_DETECTED', 'EXAM_TYPE_CORRECTED', 'CASE_REPROCESSING_REQUESTED'):
    print(et, CaseEvent.objects.filter(event_type=et).count())
"
```

- **Filas médica/CHD/NIR:** acompanhar os cards "Aguardando por etapa" e o
  breakdown por tipo no dashboard; picos de colonoscopia devem ser visíveis
  nas linhas EDA/Colonoscopia sem distorcer o consolidado.

### 4.3 Worker não usa a flag

Confirmar (uma vez) que o worker nunca consulta `COLONOSCOPY_INTAKE_ENABLED`
para bloquear casos existentes:

```bash
rg -n "COLONOSCOPY_INTAKE_ENABLED" apps/ | grep -v tests
# Saída esperada: apenas apps/intake/services.py (is_colonoscopy_intake_enabled)
# e config/settings/base.py (default da flag). Nenhum arquivo de pipeline/worker.
```

> A flag é consultada **somente no intake** (validação de novos uploads e
> reenvios corrigidos), que roda no serviço `web`. Casos colonoscopia já
> criados continuam no pipeline, nas filas e na decisão mesmo com a flag
> desligada — por design (D2/D16).

---

## 5. Plano de Rollback

### 5.1 Rollback "suave" (recomendado — sem tocar no banco)

Usar quando a ativação causar problema operacional, mas sem corrupção de dados:

1. **Desligar o intake de colonoscopia** (apenas `web` lê a flag):

```bash
# .env de produção: COLONOSCOPY_INTAKE_ENABLED=false
$DPROD up -d --force-recreate web
```

2. **Drenar/encerrar casos colonoscopia em voo** (não `CLEANED`):

   - consultar os casos (Seção 4.1);
   - deixar que os fluxos concluam normalmente; ou
   - encerrar administrativamente, um a um, via dashboard gerencial
     (manager/admin) com motivo e texto — isso remove o caso das filas
     operacionais e o mantém na auditoria.

3. **Caminho PREFERIDO — MANTER a imagem nova rodando.** A imagem nova é
   schema-compatible: `Case.exam_type` existe, a coluna fica **sem default**
   (`0014` removeu o default de banco) e **todo insert da imagem nova envia
   `exam_type` explicitamente**. Com a flag desligada, EDA continua normal e
   colonoscopia não aceita novos uploads; casos existentes seguem
   processáveis. Nenhum bridge de banco é necessário e **nenhuma** migration
   destrutiva.

4. **Reverter para a imagem ANTIGA — apenas se exigido, com bridge de schema
   binário, serializado e fail-fast.** A imagem antiga omite `exam_type` no
   INSERT; com a coluna `NOT NULL` **sem default**, **todo novo caso EDA
   falharia**. Drenar colonoscopias NÃO corrige isso. Antes de subir o código
   antigo, depois de confirmar **zero** casos colonoscopia em voo (Seção 4.1),
   restaurar o default temporário e verificá-lo com **assert binário** — o
   bloco pode rodar em shell novo e NÃO depende do fail-fast de outra sessão:

```bash
set -euo pipefail

# ALTER com SQL errors fatais: falha no SET DEFAULT aborta aqui (ON_ERROR_STOP)
$DPROD exec -T db psql -U ats_web -d ats_web -v ON_ERROR_STOP=1 -c \
  "ALTER TABLE cases_case ALTER COLUMN exam_type SET DEFAULT 'eda';"

# Assert binário: column_default DEVE ser exatamente o default EDA.
# psql -At sai limpo (sem cabeçalho); um SELECT simples retorna exit 0 mesmo
# com NULL — a comparação abaixo é quem garante o fail-fast real.
DEFAULT_NOW=$($DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
  "SELECT column_default FROM information_schema.columns \
   WHERE table_name='cases_case' AND column_name='exam_type';")
[ "${DEFAULT_NOW}" = "'eda'::character varying" ] \
  || { echo "ERRO: default inesperado: '${DEFAULT_NOW}' — PARAR; NÃO subir a imagem antiga"; exit 1; }
echo "OK: default temporário instalado e verificado ('eda')"
```

   Depois: rebuild da imagem antiga, `$DPROD up -d --force-recreate web worker
   pdf_worker` e validar um upload EDA em homologação antes de liberar.

   **Remoção do default temporário no redeploy forward (serializada e
   fail-fast):** a imagem antiga depende do default temporário — removê-lo
   antes de parar os writers reabre exatamente a race que o bridge evita.
   Sequência única e executável, na mesma janela de manutenção: a imagem nova
   é construída ANTES do downtime; os writers antigos são parados ANTES da
   remoção; a subida da imagem nova ocorre apenas após o assert binário de
   `NULL`:

```bash
set -euo pipefail

# 1. Build/pull da imagem NOVA antes do downtime (janela de manutenção reduzida)
$DPROD build --pull web worker pdf_worker

# 2. Parar os writers da imagem ANTIGA (dependem do default temporário)
$DPROD stop web worker pdf_worker

# 3. Remover o default com SQL errors fatais (ON_ERROR_STOP)
$DPROD exec -T db psql -U ats_web -d ats_web -v ON_ERROR_STOP=1 -c \
  "ALTER TABLE cases_case ALTER COLUMN exam_type DROP DEFAULT;"

# 4. Assert binário: column_default DEVE ser NULL/empty (não basta comentário)
DEFAULT_NOW=$($DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
  "SELECT column_default FROM information_schema.columns \
   WHERE table_name='cases_case' AND column_name='exam_type';")
[ -z "${DEFAULT_NOW}" ] \
  || { echo "ERRO: default ainda presente: '${DEFAULT_NOW}' — PARAR"; exit 1; }
echo "OK: sem default (NULL) — equivalente ao schema pós-0014"

# 5. Só agora subir a imagem NOVA
$DPROD up -d --force-recreate web worker pdf_worker
```

   **Se qualquer check falhar:** os writers já estão parados — **manter
   parados** e **não continuar**; **não subir a imagem nova**. Investigar o
   estado do default (`SELECT column_default ...`), restaurar o bridge se
   necessário (bloco de `SET DEFAULT` acima, com assert) e só retomar a
   sequência depois de nova verificação.

> A coluna `exam_type`, o índice e os prompts permanecem no banco em todos os
> caminhos — **rollback destrutivo não é o padrão**.

### 5.2 Rollback de contrato medicamentoso (prompts EDA)

Se o rollback exigir reverter o contrato LLM1 para **sem** a coleção de
medicamentos (imagem antiga), reativar a versão **anterior** dos prompts EDA
canônicos (`llm1_system`/`llm1_user`/`llm2_system`/`llm2_user`):

- na UI de admin (Gestão de Prompts), localizar a versão anterior de cada
  nome, **desativar** a versão atual e **ativar** a anterior (1 ativo por nome);
- só então reverter o código para a imagem antiga — **o que exige o bridge de
  schema da Seção 5.1** (`SET DEFAULT 'eda'` após drenagem, verificável) para
  a imagem antiga continuar aceitando inserts EDA;
- validar um upload EDA em homologação antes de liberar.

> **Os prompts de colonoscopia NÃO podem ser desativados enquanto houver casos em voo —
> devem permanecer ativos.** Desligar a flag bloqueia apenas novos uploads; casos
> colonoscopia existentes continuam processando e **precisam** dos prompts ativos (o
> precheck exige 1 versão ativa por nome; produção MUST seed templates ativos). A
> desativação de prompts colonoscopia só é permitida **após** drenagem/encerramento
> administrativo comprovado: rodar a consulta da Seção 4.1 e confirmar **zero**
> casos colonoscopia em voo (não `CLEANED`) antes de desativar qualquer nome.

### 5.3 Rollback completo (última instância — restaurar backup)

Só se a migration tiver causado problema real de dados (não esperado: a
migration é aditiva e o backfill não lê artefatos, mas o UPDATE/AddIndex
exigem janela controlada):

1. restaurar o dump do Postgres (Passo 1, validado por `gzip -t`) e a mídia
   (Passo 1, validada por `tar -tzf`), se necessário;
2. voltar o código para o commit anterior e rebuild;
3. `$DPROD up -d` e validar.

> O dump pré-migration (Passo 1) devolve o schema **anterior** (sem
> `exam_type`) — compatível com a imagem antiga; nesse caminho de restauração
> destrutiva não há coluna sem default, então **nenhum bridge é necessário**
> (o bridge da Seção 5.1 só se aplica ao rollback suave mantendo o schema
> pós-0014).

---

## 6. Pós-deploy (fechamento do change)

- Manter a flag documentada no `.env` privado de produção; `.env.example` já
  contém `COLONOSCOPY_INTAKE_ENABLED=false` como default seguro; a variável é
  propagada apenas para `web` (nenhum worker a recebe).
- Manter `PROJECT_CONTEXT.md` e o manual de usuário alinhados ao
  comportamento real (seleção homogênea, mixed PDFs separados, alerta
  medicamentoso informativo, correção em revisão manual com
  mismatch/mixed/unknown, flag não é assunto de usuário comum).
- O change **não** arquiva como concluído enquanto houver item do DoD global
  não comprovado em `openspec/archive/introduce-colonoscopy-exam-workflow/tasks.md`.

## 7. Notas operacionais

- **CPRE não é escopo** deste change; não prometer suporte a CPRE em
  documentos/smoke tests.
- Preparo intestinal/biópsia/diagnóstico-terapêutica **não** são gates da
  política de colonoscopia.
- Medicamentos: apenas alerta informativo; **nunca** orientação de suspensão,
  janela farmacológica ou dose.
- Correção de tipo: apenas em `WAIT_R1_CLEANUP_THUMBS` com
  `manual_review_required` e motivo `exam_type_mismatch`/`mixed_exam_request`/
  `unknown_exam_type`; nunca em estados de worker ou após decisão médica.
- Regra de ouro do rollback: **flag desligada bloqueia novos uploads, nunca
  processamento de casos existentes**; nenhuma migration destrutiva é
  necessária para reverter.
- **Prompts de colonoscopia permanecem ativos enquanto houver casos em voo**
  (não `CLEANED`); desativação só após drenagem/encerramento comprovado
  (Seção 5.2). Eles são necessários para o processamento contínuo de casos
  existentes mesmo com a flag de intake desligada.
