# Runbook de Deploy — `support-expanded-endoscopy-procedure-catalog`

**Change:** `support-expanded-endoscopy-procedure-catalog` (Slices 001–010)
**Branch:** `feature/support-expanded-endoscopy-procedure-catalog` → `main`
**Classificação de risco:** 🔴 CRÍTICO / HIGH-ARCH — cutover **único** do writer
strict **4.0** e do catálogo de **dez identidades atômicas** (pacotes EDA + GTT/
Cápsula/Dilatação e família Retossigmoidoscopia), substituindo o writer **3.0**
de quatro identidades (`eda|colonoscopy|echoendoscopy|cpre`).

> Leia o runbook inteiro antes de executar qualquer bloco. Os passos mutáveis
> (pausar ingestão → drenar jobs 3.0 → stop dos writers → migrate 0021 →
> seed prompts 4.0 → verificar → subir a **mesma** imagem em `web` **e**
> workers → smoke → reabrir ingestão) são serializados e **não devem ser
> executados fora de ordem**. Depois do **primeiro write 4.0** ou da **primeira
> row de identidade nova**, o rollback suportado é **fix-forward** (Seção 4.2).

---

## Quick reference

Cópia de mão — para uso **após** leitura completa do runbook e com o backup do
Passo 1 já validado. Executar como `apps`. Caminhos absolutos: nada depende do
diretório corrente.

```bash
PROJECT_DIR=/opt/ats-web/app
BACKUP_DIR=/archive/backups/2026-XXX-expanded-endoscopy-catalog
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

set -euo pipefail

# 1. Backup do Postgres + mídia, validado por conteúdo (Passo 1).

# 2. Build ÚNICA da imagem nova, com as três tags que o Compose deriva para os
#    serviços de app (Passo 2): uma build → UM Image ID. O precheck do Passo 3 é
#    um management command DESTA release.

# 3. Preflight: flags de intake como hoje, zero job em voo e precheck
#    `allowed` (Passo 3).

# 4. JANELA: pausar ingestão e parar TODOS os writers (Passo 4), aplicar a
#    migration 0021 (Passo 4), seed dos quatro prompts 4.0 (Passo 5) e
#    verificação binária (Passo 6) — sempre ANTES de subir.

# 5. Subir essa MESMA imagem em web + worker + pdf_worker com
#    `up -d --no-build` e PROVAR o Image ID idêntico nos três containers de app
#    (Passo 7). Falha na prova ⇒ não seguir para o smoke nem reabrir a ingestão.

# 6. Smoke funcional (Passo 8) e acessível (Passo 9) — PENDENTE GATE nesta
#    entrega (sem browser/ambiente: ver as notas de gate dos Passos 8–9) — e
#    prova da fronteira de rollback (Passo 10).

# 7. Reabrir a ingestão (Passo 11) e monitorar (Passo 12).
```

---

## 1. Análise de risco

| Aspecto | Avaliação |
|---|---|
| **Risco global** | 🔴 **CRÍTICO / HIGH-ARCH** — o catálogo/matriz clínicos passam de quatro para **dez** identidades atômicas e o writer de produção passa a ser exclusivamente o contrato strict **4.0**. Mudança transversal: detecção/reconciliação, profiles, policy, presenters, filas, follow-up e analytics. |
| **Migrations** | Uma única migration: `cases.0021_alter_caseprocedure_procedure_type_catalog_expanded` (`AlterField` de `choices` e `max_length=20 → 32`; **sem** `RunPython`/`RunSQL`, sem backfill e sem alterar dados, índices ou constraints). O downtime é dominado pela parada/drenagem/verificação, não pela migration. |
| **Compatibilidade** | A imagem anterior conhece apenas o writer **3.0** e quatro identidades. Leitores/adapters continuam aceitando **1.1/2.0/3.0** (sem reescrever JSON histórico), mas **não** leem artefato 4.0 nem rows de identidade nova. Por isso `web`, `worker` e `pdf_worker` rodam a **mesma** imagem nova — uma única build, um único Image ID, provado no Passo 2c (artefato) e no Passo 7c (containers em execução). |
| **Fronteira de rollback** | **Primeiro write 4.0** ou **primeira row de identidade nova** (design D14). Artefato 3.0, row de Ecoendoscopia/CPRE e dado legado v2 são **baseline da imagem anterior** e **não** bloqueiam o retorno a ela (ver Seção 4 e o precheck do Passo 3d). |
| **FSM / permissões / flags** | 17 estados, roles, locks, intranet guard e um único `appointment_at` por caso preservados. **Nenhuma flag nova**: as flags preexistentes `COLONOSCOPY_INTAKE_ENABLED`, `ECHOENDOSCOPY_INTAKE_ENABLED` e `CPRE_INTAKE_ENABLED` continuam web-only e governando apenas os quatro procedimentos clássicos; os pacotes e a família Retossigmoidoscopia entram pelas dez chaves do catálogo, sem rollout gradual. |
| **Prompts** | `seed_prompts` é canônico para os **quatro** nomes neutros (`exam_llm{1,2}_{system,user}`) e garante **exatamente uma versão 4.0 ativa** por nome, desativando toda versão ativa dos oito nomes legados. Preserva linhas/versões; reexecutar é idempotente. |
| **Dados sensíveis** | Precheck, verificação e monitoramento usam **apenas contagens, estados, tipos, UUIDs de caso e marcadores de schema** — sem `extracted_text`, PDF, conteúdo clínico de JSON ou conteúdo de mensagem. |
| **Rollback** | **Fix-forward** após a fronteira: manter a imagem/schema 4.0, pausar a ingestão e corrigir para frente. **Nunca** reativar o writer 3.0, **nunca** apagar rows/artefatos (inclui migration reversa destrutiva) e **nunca** reclassificar identidade nova como EDA/Colonoscopia. A exceção de retorno à imagem anterior só é admissível **pré-cutover** e depende do precheck do Passo 3d. |

### O que o change entrega

- Catálogo e matriz fechados em dez identidades atômicas: `eda`,
  `eda_gastrostomy`, `eda_capsule`, `eda_dilation`, `colonoscopy`,
  `rectosigmoidoscopy`, `rectosigmoidoscopy_dilation`,
  `rectosigmoidoscopy_argon`, `echoendoscopy`, `cpre`.
- Pacotes com `+` são **uma** row, **uma** decisão e **uma** recomendação;
  `EDA + Colonoscopia` permanece **duas** rows com decisão independente e
  agendamento casado. Conjunto fora da matriz falha fechado para revisão NIR.
- Writer strict 4.0 com detalhes clínicos tipados: local anatômico informativo em
  `eda_dilation` e coleção factual de evidências em `eda_gastrostomy` (painel
  **consultivo**, com resultados normais visíveis e alerta apenas por
  preocupação explicitamente documentada; nunca altera policy/decisão/FSM).
- Combobox acessível (progressive enhancement de um `<select>` canônico) em
  upload, correção/reenvio e inclusão/substituição médica.
- Filas, follow-up e analytics consomem opções/categorias derivadas do catálogo,
  por **código exato** (sem equivalência por família/profile).

---

## 2. Pré-requisitos (no servidor de produção)

- Acesso de shell ao servidor como `apps`, com `docker compose` funcional e
  `--project-directory` apontando para a instalação real.
- Acesso ao registry (GHCR) com a tag nova e, para a exceção da Seção 4.3, a tag
  do release anterior.
- **Backup do Postgres e do volume de mídia `media_prod`** antes de qualquer
  passo mutável (Passo 1), validado **por conteúdo** (procedimento completo em
  [`shared-postgres-production.md`](./shared-postgres-production.md); bloco
  pronto com validação por conteúdo em
  [`support-combined-eda-colonoscopy-workflow.md`](./support-combined-eda-colonoscopy-workflow.md),
  Passo 1).
- **Janela de baixa atividade acordada** com a operação (Passo 4) e downtime
  comunicado (pausar ingestão → stop → migrate → seed → verificação → subida).
- Comunicar NIR/médico/CHD/gestão que dez identidades passam a existir no mesmo
  cutover e que **não há backfill**: analytics das identidades novas começam no
  cutover e não representam o histórico.
- Aceite humano permanece obrigatório para **arquivar** o change (Seção 5).

---

## 3. Passos de deploy

### Passo 1 — Backup fail-closed (obrigatório, validado por conteúdo)

Executar o bloco de backup do runbook de referência com os mesmos asserts
binários (dump do Postgres + snapshot do volume real montado em `/app/media`),
usando `BACKUP_DIR=/archive/backups/2026-XXX-expanded-endoscopy-catalog`:

- [`support-combined-eda-colonoscopy-workflow.md`](./support-combined-eda-colonoscopy-workflow.md) — Passo 1 completo (`gzip -t`, marker do PostgreSQL, contagem mínima de linhas, `tar -tzf` do volume resolvido via `docker inspect`).

Nenhum passo adiante é executado sem dump **e** mídia validados. O rollback
suportado não apaga dados, mas o backup continua sendo a rede de segurança da
janela.

### Passo 2 — Atualizar código e construir UMA imagem (uma build, um Image ID)

O precheck do Passo 3 é um management command **desta** release: a imagem nova
precisa existir antes do preflight (os writers 3.0 continuam no ar até o
Passo 4).

**Mecanismo real do Compose (conferido nos arquivos desta release):** em
`docker-compose.prod.yml` os três serviços de app (`web`, `worker`,
`pdf_worker`) declaram **apenas** `build:` (`context: .` + `dockerfile:
Dockerfile`) — **sem** `image:` e **sem** override por env var. O único hook de
imagem do repositório é `ATS_WEB_IMAGE` em `docker-compose.shared-postgres.yml`,
que **não** é o shape deste runbook. O Compose deriva, então, um nome local por
serviço a partir do projeto (`name: ats-web-prod`): `ats-web-prod-web`,
`ats-web-prod-worker` e `ats-web-prod-pdf_worker` (todos `:latest`); o `db`
continua `postgres:17`.

Consequência: o invariante D14 (“mesma imagem em `web` e workers”) é garantido
por **uma única build com as três tags** e provado por **Image ID** — nunca por
tag:

- `$DPROD build --pull web worker pdf_worker` **não** serve como prova: o
  Compose injeta o label `com.docker.compose.service` em cada imagem construída
  e gera **três Image IDs distintos** (camadas idênticas, labels diferentes) —
  comportamento verificado no host desta release (Compose v5.2 / Docker 29.6,
  com e sem bake). Com ele, a igualdade de Image ID seria impossível de
  satisfazer.
- `$DPROD ps` e `$DPROD config --images` mostram nomes/tags
  (`ats-web-prod-web`), **não** o ID da imagem em execução: não provam o
  invariante (é por isso que `config --images` aqui só serve para **derivar os
  nomes**, com o `db` excluído explicitamente).
- Um único `docker build` com as três tags (`<nome>:latest` e `<nome>:<sha>`)
  produz **um** Image ID compartilhado pelos três serviços.

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

git -C "$PROJECT_DIR" fetch origin && git -C "$PROJECT_DIR" checkout main && git -C "$PROJECT_DIR" pull origin main
git -C "$PROJECT_DIR" log --oneline -5        # confirmar os commits do change no topo
RELEASE_TAG="$(git -C "$PROJECT_DIR" rev-parse --short HEAD)"

# 2a. Derivar os nomes de imagem dos serviços de app. O `db` (postgres:17) fica
#     FORA do invariante e é excluído explicitamente.
APP_IMAGES="$($DPROD config --images | grep -v '^postgres:' | sort -u)"
[ "$(printf '%s\n' "$APP_IMAGES" | wc -l)" -eq 3 ] || {
  echo "ERRO: esperado 3 imagens de app (web/worker/pdf_worker); obtido:";
  printf '%s\n' "$APP_IMAGES"; exit 1; }

# 2b. UMA build → UMA imagem. Cada nome recebe a tag `:latest` (a que o Compose
#     resolve no `up`) e a tag imutável do release (`:$RELEASE_TAG`).
IMAGE_TAGS=()
while read -r image; do
  IMAGE_TAGS+=(-t "${image}:latest" -t "${image}:${RELEASE_TAG}")
done <<< "$APP_IMAGES"

#     Build direto no docker (não via Compose) porque os três serviços têm build
#     idêntico em docker-compose.prod.yml: `context: .` + `dockerfile: Dockerfile`.
docker build --pull "${IMAGE_TAGS[@]}" -f "${PROJECT_DIR}/Dockerfile" "${PROJECT_DIR}"

# 2c. PROVA, ANTES da ativação de prompts (Passo 5) e do smoke (Passos 8–9):
#     as três tags apontam para UM único Image ID. Esperado: 1.
IMAGE_IDS="$(while read -r image; do docker image inspect "${image}:${RELEASE_TAG}" --format '{{.Id}}'; done <<< "$APP_IMAGES" | sort -u)"
DISTINCT_IDS="$(printf '%s\n' "$IMAGE_IDS" | wc -l)"
printf 'Image IDs distintos entre as três tags: %s\n' "$DISTINCT_IDS"
[ "$DISTINCT_IDS" -eq 1 ] || {
  echo "ERRO: ${DISTINCT_IDS} Image IDs distintos entre as três tags de app — a build do Passo 2 não produziu uma imagem única:";
  printf '%s\n' "$IMAGE_IDS"; exit 1; }
```

**Se o 2c não imprimir `1`:** **PARAR** — não aplicar a migration (Passo 4),
não ativar prompts (Passo 5) e não subir (Passo 7). Refazer a build (uma única
invocação de `docker build`).

**Pré-requisito do mecanismo:** os três serviços precisam continuar com build
idêntico (`context` + `dockerfile`). Se `docker-compose.prod.yml` ganhar
`image:` ou build args por serviço, este passo deve ser revisto antes do uso.

### Passo 3 — Preflight: flags de intake, drenagem de jobs 3.0 e precheck de downgrade

Roda **antes** de qualquer write 4.0 (schema ainda 3.0). Cada assert é binário e
manda PARAR em caso de falha.

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# 3a. Flags de intake inalteradas por este change (nenhuma flag nova). As três
#     preexistentes continuam web-only e governam apenas Colonoscopia/
#     Ecoendoscopia/CPRE; os pacotes e Retossigmoidoscopia não têm flag.
$DPROD config | awk '/^  [a-z_]+:/{svc=$1} /COLONOSCOPY_INTAKE_ENABLED|ECHOENDOSCOPY_INTAKE_ENABLED|CPRE_INTAKE_ENABLED/{print svc, $0}'
# Esperado: somente linhas começando com "web:" — nenhuma com "worker:"/"pdf_worker:".

# 3b. DRENAGEM: nenhum job 3.0 (LLM_STRUCT/LLM_SUGGEST e demais estados de
#     pipeline) pode restar antes do cutover — o writer 4.0 substitui o 3.0 e
#     writers concorrentes são proibidos.
PIPE_STATES=$($DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM cases_case WHERE status IN
   ('NEW','R1_ACK_PROCESSING','EXTRACTING','LLM_STRUCT','LLM_SUGGEST');")
[ "${PIPE_STATES}" = "0" ] || { \
  echo "ERRO: ${PIPE_STATES} caso(s) em estados de pipeline — drenar antes do cutover"; \
  $DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
    "SELECT id, status FROM cases_case WHERE status IN ('NEW','R1_ACK_PROCESSING','EXTRACTING','LLM_STRUCT','LLM_SUGGEST') ORDER BY status;"; \
  exit 1; }

# 3c. Validar localmente que o seed 4.0 tem conteúdo canônico para os quatro
#     nomes neutros (a execução binária é o Passo 5, depois do corte).
$DPROD run --rm web uv run python manage.py shell --settings=config.settings.prod -c "
from apps.llm.management.commands.seed_prompts import DEFAULT_CONTENTS, LEGACY_PROMPT_NAMES, PROMPT_NAMES
for name in PROMPT_NAMES:
    assert DEFAULT_CONTENTS[name].strip(), name
print('OK: conteúdo 4.0 candidato definido para', len(PROMPT_NAMES), 'prompts neutros')
print('OK: nomes legados monitorados:', len(LEGACY_PROMPT_NAMES))
"

# 3d. PRECHECK DE DOWNGRADE (machine-readable, não destrutivo). A fronteira de
#     rollback DESTE change é o PRIMEIRO write 4.0 ou a PRIMEIRA row de
#     identidade nova (design D14). Pré-cutover DEVE retornar status "allowed"
#     e exit code 0: as classes de fronteira são `pipeline_job_in_flight`,
#     `new_identity_case_procedure` e `v4_artifact_write`. As classes de baseline
#     (`specialized_case_procedure`, `v3_artifact_write`,
#     `specialized_case_event`, `legacy_echo_artifact`) refletem o dado da
#     imagem anterior (writer 3.0) e NÃO bloqueiam o retorno à imagem 3.0 —
#     elas aparecem em `notes` e `old_image_return_available` continua true.
$DPROD run --rm web uv run python manage.py check_specialized_procedure_downgrade \
  --settings=config.settings.prod
```

**Saída esperada do 3d (pré-cutover):** um JSON com `"status": "allowed"`,
`"boundary": "first_4_0_write"`, `"blocking_checks": []` e as três classes de
**fronteira** com `count: 0` (`pipeline_job_in_flight`,
`new_identity_case_procedure`, `v4_artifact_write`). As classes de **baseline**
(`specialized_case_procedure`, `v3_artifact_write`, `specialized_case_event`,
`legacy_echo_artifact`) podem ter `count > 0` — isso é esperado em qualquer
banco que já rodou o writer 3.0, aparece em `"notes"` e **não** bloqueia o
cutover nem o retorno à imagem 3.0 (`"old_image_return_available": true`).

**Se o precheck sair com exit code 1:** alguma classe de fronteira existe e o
write 4.0 / row de identidade nova já ocorreu. **PARAR** o deploy de cutover e
seguir a Seção 4.2 (fix-forward) — nunca reativar o writer 3.0.

### Passo 4 — JANELA: pausar ingestão, parar todos os writers e aplicar a migration 0021

**Por que parar também o `web`:** o `web` aceita uploads/correções (a "ingestão"
do change) e o código 3.0 não conhece as dez identidades nem o contrato 4.0;
`worker`/`pdf_worker` processariam novos casos com os prompts/schema errados. O
`db` permanece no ar. Não existe flag que pause a ingestão de EDA: a pausa é a
**parada do serviço `web`** durante a janela.

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# a) Janela acordada com a operação (fora do horário de pico).
# b) PAUSAR A INGESTÃO e PARAR TODOS OS WRITERS.
$DPROD stop web worker pdf_worker

# c) Migration 0021 com a imagem NOVA (serviços parados; db no ar).
#    Saída esperada: Applying cases.0021_alter_caseprocedure_procedure_type_catalog_expanded... OK
$DPROD run --rm web uv run python manage.py migrate --settings=config.settings.prod
```

Se a migration falhar: **NÃO continuar** — ir para a Seção 4. Não há write 4.0
antes deste ponto (o precheck do Passo 3d já provou isso).

### Passo 5 — Seed dos quatro prompts 4.0 (imagem nova, serviços ainda parados)

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

$DPROD run --rm web uv run python manage.py seed_prompts --settings=config.settings.prod
```

Garante **exatamente uma versão ativa 4.0** por nome neutro
(`exam_llm1_system`, `exam_llm1_user`, `exam_llm2_system`, `exam_llm2_user`) e
**desativa** toda versão ativa dos oito nomes legados (`llm1_*`, `llm2_*`,
`colonoscopy_llm{1,2}_*`), preservando linhas/versões. Idempotente.

### Passo 6 — Verificação binária pós-migration (ANTES do up)

Cada assert compara saída (`-At`) e encerra com exit 1 em mismatch. Qualquer
falha: **PARAR**, não subir.

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# 6a. Prompts 4.0: quatro neutros ativos com o conteúdo 4.0 e EXATAMENTE uma
#     versão ativa por nome; zero legados ativos.
$DPROD run --rm web uv run python manage.py shell --settings=config.settings.prod -c "
from apps.llm.management.commands.seed_prompts import DEFAULT_CONTENTS, LEGACY_PROMPT_NAMES, PROMPT_NAMES
from apps.llm.models import PromptTemplate
for name in PROMPT_NAMES:
    active = PromptTemplate.get_active(name)
    if active is None or active.content != DEFAULT_CONTENTS[name]:
        print('PRECHECK FALHOU — nome neutro sem versão 4.0 ativa:', name); raise SystemExit(1)
    if PromptTemplate.objects.filter(name=name, is_active=True).count() != 1:
        print('PRECHECK FALHOU — mais de uma versão ativa para:', name); raise SystemExit(1)
legacy_active = PromptTemplate.objects.filter(name__in=LEGACY_PROMPT_NAMES, is_active=True).count()
if legacy_active != 0:
    print('PRECHECK FALHOU — versões legadas ainda ativas:', legacy_active); raise SystemExit(1)
print('OK — 4 prompts neutros 4.0 ativos (um por nome); 0 legados ativos')
"
# Se falhar: corrigir pela Gestão de Prompts (admin) ou reexecutar o seed.
# NUNCA subir com prompt 3.0 ativo ou com prompt legado ativo.

# 6b. Schema alinhado: choices com as dez identidades, max_length=32 e nenhuma
#     row fora do catálogo (validação é de aplicação, sem constraint de banco).
$DPROD run --rm web uv run python manage.py shell --settings=config.settings.prod -c "
from apps.cases.models import CaseProcedure, ProcedureType
from apps.cases.procedures import SUPPORTED_PROCEDURE_TYPES
codes = [value for value, _ in ProcedureType.choices]
assert codes == list(SUPPORTED_PROCEDURE_TYPES), codes
assert CaseProcedure._meta.get_field('procedure_type').max_length == 32
bad = CaseProcedure.objects.exclude(procedure_type__in=SUPPORTED_PROCEDURE_TYPES).count()
if bad:
    print('PRECHECK FALHOU — rows fora do catálogo:', bad); raise SystemExit(1)
print('OK — catálogo de dez identidades; max_length=32; 0 rows fora do catálogo')
"

# 6c. O precheck de downgrade ainda deve estar `allowed` (exit 0) — prova de que
#     nenhum write 4.0 / row de identidade nova existia quando a janela abriu.
$DPROD run --rm web uv run python manage.py check_specialized_procedure_downgrade \
  --settings=config.settings.prod
```

### Passo 7 — Subir a MESMA imagem em web + worker + pdf_worker e PROVAR o invariante

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# --no-build: o Compose só pode usar a imagem do Passo 2 — nunca construir/puxar
# outra imagem nesta janela. Recriação forçada evita "start" de container antigo.
$DPROD up -d --no-build --force-recreate web worker pdf_worker

# 7a. Visão legível por serviço (tag, não ID) — informativo, NÃO é a prova.
$DPROD ps --format 'table {{.Service}}\t{{.Image}}\t{{.Status}}'

# 7b. Resolver os container ids dos três serviços de app (o `db` fica de fora).
WEB_CID="$($DPROD ps -q web)"
WORKER_CID="$($DPROD ps -q worker)"
PDF_WORKER_CID="$($DPROD ps -q pdf_worker)"
for cid in "$WEB_CID" "$WORKER_CID" "$PDF_WORKER_CID"; do
  [ -n "$cid" ] || { echo "ERRO: serviço de app sem container em execução"; exit 1; }
done

# 7c. PROVA do invariante D14: Image ID idêntico nos TRÊS containers de app.
#     O `db` (postgres:17) é excluído — não faz parte do invariante.
docker inspect --format '{{.Image}}' "$WEB_CID" "$WORKER_CID" "$PDF_WORKER_CID"
# Esperado: TRÊS linhas IGUAIS, por exemplo
#   sha256:8c1b1e0f2a4d9c6b7f3a5e8d0b2c4a6f9e1d3c5b7a9f0e2d4c6b8a0f1e3d5c7b
#   sha256:8c1b1e0f2a4d9c6b7f3a5e8d0b2c4a6f9e1d3c5b7a9f0e2d4c6b8a0f1e3d5c7b
#   sha256:8c1b1e0f2a4d9c6b7f3a5e8d0b2c4a6f9e1d3c5b7a9f0e2d4c6b8a0f1e3d5c7b

DISTINCT_IDS="$(docker inspect --format '{{.Image}}' "$WEB_CID" "$WORKER_CID" "$PDF_WORKER_CID" | sort -u | wc -l)"
[ "$DISTINCT_IDS" -eq 1 ] || {
  echo "ERRO: ${DISTINCT_IDS} Image IDs distintos entre web/worker/pdf_worker — invariante D14 violado";
  exit 1; }
```

**Se qualquer Image ID diferir (7c ≠ 1 linha única): PARAR.** Não prosseguir
para o smoke funcional (Passo 8) nem acessível (Passo 9), não prosseguir para a
prova de fronteira (Passo 10) e não reabrir a ingestão (Passo 11). Refazer o
Passo 2 (uma única build, três tags), repetir `up -d --no-build --force-recreate`
e este assert. Com a ingestão pausada e sem write 4.0 anterior a este ponto, o
caminho de correção é o Passo 2 e, se necessário, a Seção 4.3 (retorno à imagem
anterior, admissível somente pré-cutover).

### Passo 8 — Smoke funcional das onze seleções — **PENDENTE GATE**

Cada cenário cria **um** caso controlado e é registrado (ambiente, ator, seleção,
case id e resultado) **sem copiar texto clínico sensível**. A ingestão ainda está
pausada (Passos 4–6): o operador de smoke envia os casos pelo próprio fluxo do
runbook (reabertura controlada do `web` + fila) ou pelo ambiente de homologação
equivalente, com o writer 4.0 ativo.

| # | Cenário | Seleção/entrada | Resultado esperado |
|---|---|---|---|
| 1 | **EDA** | `eda` | Pipeline 4.0 conclui; badge EDA; fila médica; fluxo normal |
| 2 | **EDA + GTT** | `eda_gastrostomy` | **Uma** row/pacote; painel consultivo de infecção; ver cenários 12–13 |
| 3 | **EDA + Cápsula** | `eda_capsule` | **Uma** row; sem sinal legado `capsule`; decisão única |
| 4 | **EDA + Dilatação** | `eda_dilation` | **Uma** row; local anatômico ancorado; ver cenários 14–15 |
| 5 | **Colonoscopia** | `colonoscopy` | Fluxo idêntico ao baseline |
| 6 | **Retossigmoidoscopia** | `rectosigmoidoscopy` | **Uma** row; profile Colonoscopia reutilizado **sem** equivalência de histórico/filtro |
| 7 | **Retossigmoidoscopia + Dilatação** | `rectosigmoidoscopy_dilation` | **Uma** row; sem síntese de local anatômico |
| 8 | **Retossigmoidoscopia + Argônio** | `rectosigmoidoscopy_argon` | **Uma** row |
| 9 | **Ecoendoscopia** | `echoendoscopy` | Procedimento independente; hard rule de imagem; sem sinal de EDA |
| 10 | **CPRE** | `cpre` | Procedimento independente; hard rule de imagem própria |
| 11 | **Combinado EDA + Colonoscopia** | `eda_colonoscopy` | **UM** caso com **duas** rows; badge combinado; decisão por componente; **agendamento casado** (um único `appointment_at`) |
| 12 | **GTT normal** | `eda_gastrostomy` com resultados normais/negativos explícitos | Resultados aparecem no painel; **sem** alerta; policy/recomendação/decisão idênticas |
| 13 | **GTT preocupante** | `eda_gastrostomy` com preocupação atual explícita | Alerta **consultivo** visível (“não altera a sugestão automática”); nenhuma pendência criada; decisão/FSM idênticas ao caso normal |
| 14 | **Dilatação com local** | `eda_dilation` com sítio ancorado | Local exibido; identidade continua `eda_dilation`; policy inalterada |
| 15 | **Dilatação sem local / não ancorado** | `eda_dilation` sem sítio, ou excerpt ausente do relatório | Local `unknown`; nenhuma pendência; fallback sem falhar o pipeline |
| 16 | **Conjunto proibido — variação + Colonoscopia** | `eda_capsule` + Colonoscopia | **Falha fechada** para revisão NIR; nenhum caso segue ao médico com conjunto inválido |
| 17 | **Conjunto proibido — duas variações** | EDA + GTT + EDA + Cápsula | **Falha fechada**; nenhuma identidade é reduzida a singleton |
| 18 | **Conjunto proibido — dois especializados** | Ecoendoscopia + CPRE | **Falha fechada**/revisão; nenhuma combinação nova |
| 19 | **Filtros exatos** | Filas NIR/médico/CHD e histórico | Filtro por identidade casa **só** o código exato; `eda_colonoscopy` casa o par exato; nenhuma equivalência por família/profile |
| 20 | **Analytics** | Dashboard gerencial | Categoria exclusiva por selection key; volume por componente (pacote = 1, combinado = 2 de 1 caso); bucket `invalid` explícito e nunca somado a categoria válida |

> **STATUS DESTA ENTREGA: PENDENTE GATE.** A execução do smoke funcional (linhas
> 1–20) **não foi realizada**: o host de implementação/validação **não possui
> browser** e **não possui ambiente ats-web de desenvolvimento/produção em
> execução**. A matriz fica registrada aqui como gate explícito e **não** pode
> ser considerada satisfeita (R4) até ser executada em ambiente real e anexada ao
> relatório de janela com ambiente/ator/seleção/case id/resultado.

### Passo 9 — Smoke acessível (combobox) — **PENDENTE GATE**

Superfícies migradas para o combobox: **upload NIR**, **correção/reenvio NIR** e
**inclusão/substituição médica**.

| # | Cenário | Resultado esperado |
|---|---|---|
| A1 | **Busca sem acentos** | `capsula` encontra “EDA + Cápsula”; `dilatacao` encontra as dilatações; `argonio`/`argonio` encontra Argônio |
| A2 | **Teclado** | ArrowDown/ArrowUp/Home/End navegam; Enter seleciona; Escape fecha; Tab sai; clique fora fecha |
| A3 | **Foco/ARIA** | `role="combobox"`, `aria-expanded`, `aria-controls`, `aria-autocomplete="list"`, `aria-activedescendant` e foco visível coerentes a cada interação |
| A4 | **Erro de validação** | Re-render com erro mantém o `<select>` autoritativo e o foco/estado de erro visíveis |
| A5 | **Fallback sem JavaScript** | Com JS desabilitado o `<select>` original continua visível, navegável e submetível; **nenhum** submit depende de JS |
| A6 | **Valor autoritativo** | Só a seleção de uma option atualiza o `<select>`; texto livre não é aceito e não cria caso |

> **STATUS DESTA ENTREGA: PENDENTE GATE.** Sem browser e sem ambiente em
> execução, os cenários A1–A6 **não foram executados**. A cobertura Django-side
> (contrato HTML/POST, re-render com erro e fallback SSR) integra o quality gate
> do repositório; teclado/leitor de tela e a busca sem acentos em navegador real
> permanecem gate manual explícito (R5) e **não** podem ser considerados
> satisfeitos até a execução em ambiente real.

### Passo 10 — Evidência da fronteira de rollback (após o primeiro write 4.0)

O smoke já produz writes 4.0. Rodar o precheck e **registrar** o resultado como
evidência de que o caminho de retorno à imagem 3.0 foi fechado — o bloqueio aqui
é o comportamento **esperado**.

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# Exit code 1 esperado a partir daqui. Capturar o JSON no relatório da janela.
$DPROD run --rm web uv run python manage.py check_specialized_procedure_downgrade \
  --settings=config.settings.prod || true
# Esperado: "status": "blocked" com "v4_artifact_write" (e "new_identity_case_procedure"
# se houver row de pacote/Retossigmoidoscopia já gravada, e "pipeline_job_in_flight"
# se houver caso processando no instante da leitura). A partir deste ponto o
# rollback suportado é a Seção 4.2 (fix-forward).
```

### Passo 11 — Reabrir a ingestão

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# A parada do `web` no Passo 4 já era a pausa da ingestão; reabri-la é subir o
# `web` da MESMA imagem (Passo 7) e confirmar saúde:
$DPROD ps
$DPROD logs --tail=50 web
```

Critérios para reabrir: Passo 6 verde, Passo 7 com **um único Image ID** nos três
containers de app (7c) e smoke funcional/acessível executado (Passos 8–9).
**Sem** os três, manter a ingestão pausada e seguir a Seção 4.

### Passo 12 — Monitoramento (contagens/eventos, sem texto clínico)

Nunca selecionar `structured_data`, `extracted_text`, PDF ou conteúdo de
mensagem. Monitorar durante a janela e por 24h após a reabertura.

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

$DPROD exec -T web uv run python manage.py shell --settings=config.settings.prod -c "
from collections import Counter
from django.db.models import Count
from apps.cases.models import Case, CaseEvent, CaseProcedure
from apps.cases.procedures import SUPPORTED_PROCEDURE_TYPES

print('— Volume por identidade (rows CaseProcedure; esperado: só códigos do catálogo) —')
print(' ', dict(CaseProcedure.objects.values_list('procedure_type').annotate(n=Count('id'))))
fora = CaseProcedure.objects.exclude(procedure_type__in=SUPPORTED_PROCEDURE_TYPES).count()
print('  rows fora do catálogo:', fora)

print('— Casos em voo por status —')
for st in ('WAIT_DOCTOR', 'WAIT_APPT', 'WAIT_R1_CLEANUP_THUMBS', 'FAILED'):
    print(' ', st, Case.objects.filter(status=st).count())

print('— Eventos estruturais (contagens) —')
for et in ('CASE_PROCEDURES_DETECTED', 'DOCTOR_PROCEDURE_SET_CHANGED',
           'LLM1_OK', 'LLM2_OK', 'PIPELINE_FAILED'):
    print(' ', et, CaseEvent.objects.filter(event_type=et).count())

print('— Retornos a revisão NIR por conjunto inválido (contagens) —')
reasons = Counter()
for payload in CaseEvent.objects.filter(event_type='EDA_SCOPE_GATED_MANUAL_REVIEW').values_list('payload', flat=True):
    if isinstance(payload, dict):
        reasons[str(payload.get('reason_code'))] += 1
print(' ', dict(reasons))
"
```

**Alertas:** pico de `PIPELINE_FAILED` ou de `WAIT_R1_CLEANUP_THUMBS` acima do
baseline; qualquer row `CaseProcedure` fora do catálogo; crescimento anômalo de
retornos a revisão NIR por conjunto inválido; qualquer prompt legado reativado;
`web` e workers com Image IDs diferentes (revalidar com o assert 7c).

---

## 4. Plano de Rollback

### 4.1 Camada de flags (não destrutiva, mas limitada)

Este change **não introduz flag**: não existe chave que desligue os pacotes EDA
ou a família Retossigmoidoscopia. As flags preexistentes
(`COLONOSCOPY_INTAKE_ENABLED`, `ECHOENDOSCOPY_INTAKE_ENABLED`,
`CPRE_INTAKE_ENABLED`) continuam web-only e bloqueiam apenas novos
uploads/correções/reenvios de Colonoscopia/Ecoendoscopia/CPRE — não interrompem
casos existentes e não devolvem o catálogo a quatro identidades. Use-as apenas
como contorno parcial de ingestão, **independentemente** da fronteira.

### 4.2 Rollback suportado APÓS o primeiro write 4.0 / row de identidade nova (caminho padrão)

Depois do primeiro write 4.0 — mesmo de EDA/Colonoscopia — ou da primeira row de
identidade nova, o caminho suportado é **fix-forward**:

1. **Pausar a ingestão** (Seção 4.1 / parar o `web`) e parar os writers.
2. **Manter a imagem nova e o schema pós-0021 rodando.** Não reagendar o writer
   3.0, não reativar prompts 3.0, não rodar reverse migration destrutiva.
3. **Drenar/encerrar casos em voo**: acompanhar o Passo 12 e deixar os fluxos
   concluírem; se necessário, encerrar administrativamente pelo dashboard
   (manager/admin) com motivo — o caso sai das filas e permanece na auditoria.
4. **Corrigir para frente**: a correção é um novo commit/imagem que mantém o
   schema 4.0 e as rows/artefatos existentes; a única forma de voltar atrás é uma
   release nova com o fix.
5. **Nunca apagar** rows `CaseProcedure`, `structured_data`,
   `suggested_action`, `CaseEvent`, `priority_signals` ou o histórico de
   prompts. **Nunca reclassificar** identidade nova como EDA/Colonoscopia e
   **nunca** transformar um pacote em outra identidade por conveniência
   operacional — **deleção/reclassificação para viabilizar downgrade está fora de
   escopo**.

### 4.3 Retorno à imagem anterior (exceção, somente PRÉ-cutover)

Admissível **apenas** enquanto o precheck do Passo 3d retornar `status:
"allowed"` (exit code 0) — isto é, zero job em voo, zero write 4.0 e zero row de
identidade nova. Artefato 3.0, row de Ecoendoscopia/CPRE e dado legado v2 são
baseline da própria imagem anterior e **não** impedem a exceção (aparecem em
`notes`; `old_image_return_available` é `true` exatamente quando o gate está
`allowed`). Sequência:

1. `$DPROD stop web worker pdf_worker` (nenhum writer ativo na janela).
2. Reativar a matriz de prompts compatível com a imagem anterior (o writer 3.0
   usa os quatro nomes neutros com conteúdo 3.0) via `manage.py shell` —
   exatamente uma versão ativa por nome, sem apagar o histórico.
3. Subir a imagem do release anterior com o mecanismo do Passo 2 (uma única
   build, com as três tags derivadas do Compose) e então
   `up -d --no-build --force-recreate web worker pdf_worker`, revalidando o
   assert de Image ID único (Passo 7c). **Nunca** `up` sem `--no-build` aqui —
   o Compose construiria uma imagem nova a partir do código no disco.
4. Validar um envio EDA em homologação antes de liberar para a operação.

O precheck (`check_specialized_procedure_downgrade`) é o gate **binário** desse
caminho: exit code 1 significa fronteira 4.0 cruzada — voltar à Seção 4.2. Com
exit 0 a exceção está disponível (o baseline 3.0/legado v2 não a bloqueia).

> **NOTA (2026-09-25, semântica evoluída por D14):** a fronteira deste change é o
> **primeiro write 4.0 / primeira row de identidade nova**. As classes de
> fronteira da release anterior (artefato 3.0 e row de Ecoendoscopia/CPRE) foram
> reclassificadas como **baseline informativo**: o writer 3.0 produziu e lê esses
> dados, então eles não podem bloquear o retorno à imagem 3.0 — caso contrário o
> gate seria insatisfazível em qualquer banco já operado. Comportamento esperado e
> documentado; não tratar como desvio.

---

## 5. Pós-deploy (fechamento)

- Confirmar que **nenhuma flag nova** foi adicionada ao `.env`/Compose; as três
  preexistentes permanecem web-only com o valor vigente.
- Manter `PROJECT_CONTEXT.md` e `docs/manual/manual-usuarios.md` alinhados ao
  catálogo de dez identidades e à ausência de backfill.
- Monitorar por 24h conforme o Passo 12 (contagens/eventos, sem texto clínico).
- Aprovação humana é pré-requisito para **arquivar** o change; não arquivar sem
  confirmação explícita.

### Checklist de verificação do invariante de imagem única (D14)

- [ ] **I1 — artefato:** uma única build com as três tags do Compose; os três
      nomes derivados resolvem para **um** Image ID (`docker image inspect
      "<nome>:<sha>" --format '{{.Id}}'` para cada nome, `sort -u | wc -l` = `1`
      — Passo 2c), verificado **antes** da ativação de prompts (Passo 5) e do
      smoke (Passos 8–9).
- [ ] **I2 — containers em execução:** `web`, `worker` e `pdf_worker` rodam com o
      **mesmo** Image ID — `docker inspect --format '{{.Image}}'` nos três
      containers de `ps -q` (três linhas iguais; Passo 7c), com a saída anexada
      ao relatório da janela.
- [ ] **I3 — escopo:** o container `db` (`postgres:17`) foi **excluído**
      explicitamente da comparação — o invariante cobre só os serviços de app.
- [ ] **I4 — bloqueio:** qualquer divergência em I1/I2 impede prosseguir para os
      prompts/smoke (Passos 8–9) e para a reabertura da ingestão (Passo 11); a
      correção é refazer o Passo 2 (uma única build) e repetir o Passo 7.
- [ ] **I5 — registro:** o Image ID compartilhado (e o `RELEASE_TAG` do Passo 2)
      constam do relatório da janela junto com o horário do `up`.

## 6. Notas operacionais

- **Sem flag nova e sem rollout gradual**: o catálogo de dez identidades entra em
  um único cutover; os commits intermediários da branch **não** são implantáveis
  isoladamente.
- **Fronteira de rollback é o primeiro write 4.0 / primeira row de identidade
  nova**, não a subida da imagem. Reabrir a ingestão não cria obrigação de
  downgrade; o caminho suportado pós-fronteira é fix-forward.
- **Mesma imagem em web e workers, sempre**: writers 3.0 e 4.0 não podem
  coexistir. O invariante é **Image ID idêntico** nos três containers de app —
  não basta a mesma tag, e o `db` (`postgres:17`) fica fora da comparação.
- **Sem backfill**: analytics das identidades novas começam no cutover; sinais
  legados (`gastrostomy`, `esophageal_dilation`) continuam apenas como leitura
  histórica e **não** são convertidos em identidades novas.
- **Sem threshold/reference range/score de infecção**: o painel GTT é consultivo,
  exibe todos os resultados presentes (inclusive normais) e nunca altera
  policy/recomendação/decisão/FSM.
- **Sem equivalência por família/profile**: histórico, filtros, eventos e
  analytics usam **código exato**; Retossigmoidoscopia nunca casa com
  Colonoscopia.
- **Monitoramento sem expor texto clínico**: somente contagens, estados, tipos,
  markers de schema e UUIDs de caso.
