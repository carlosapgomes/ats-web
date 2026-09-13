# Runbook de Deploy — `support-independent-echoendoscopy-cpre-workflows`

**Change:** `support-independent-echoendoscopy-cpre-workflows` (Slices 001–009)
**Branch:** `feature/support-independent-echoendoscopy-cpre-workflows` → `main`
**Classificação de risco:** 🔴 CRÍTICO / HIGH-ARCH — cutover do writer LLM strict
**3.0**, nova hard rule determinística de imagem abdominal, decisão médica
`trocar e aprovar` sem reanálise e ativação **sequencial** de dois procedimentos
independentes (Ecoendoscopia antes de CPRE).

> Leia o runbook inteiro antes de executar qualquer bloco. Os passos mutáveis
> (parar writers → migrate → seed prompts → verificar → subir → ativar flags)
> são serializados e **não devem ser executados fora de ordem**.

---

## Quick reference

Cópia de mão — para uso **após** o Passo 1 (backup) e com o Passo 2 (build)
concluído. Executar como `apps`. Caminhos absolutos: nada depende do diretório
corrente.

```bash
PROJECT_DIR=/opt/ats-web/app
BACKUP_DIR=/archive/backups/2026-XXX-specialized-eco-cpre
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

set -euo pipefail

# 1. Backup já feito e validado por conteúdo (Passo 1).

# 2. Preflight fail-closed com a imagem NOVA: flags false + precheck de
#    downgrade `allowed` (Passo 3).

# 3. JANELA: parar TODOS os writers, migrate, seed_prompts, verificar prompts
#    3.0 e schema ANTES de subir (Passos 4–6).

# 4. Subir SOMENTE a imagem nova com as duas flags false (Passo 7).

# 5. Smoke de regressão EDA/Colonoscopia PRIMEIRO (Passo 8), registrar a
#    evidência da fronteira de rollback (Passo 9) e só então ativar
#    Ecoendoscopia (Passo 10) e, após aceite humano, CPRE (Passo 11).

# 6. Monitoramento (Passo 12).
```

---

## 1. Análise de risco

| Aspecto | Avaliação |
|---|---|
| **Risco global** | 🔴 **CRÍTICO / HIGH-ARCH** — catálogo/matriz clínicos passam de dois para quatro procedimentos, o writer de produção passa a ser exclusivamente o contrato strict 3.0 e uma hard rule determinística de imagem passa a compor a sugestão automática. |
| **Migrations** | Uma única migration: `cases.0019_alter_caseprocedure_procedure_type` (`AlterField` de choices — **sem data migration e sem backfill**). Não altera dados, índices nem constraints; o downtime é dominado pela parada/verificação, não pela migration. |
| **Compatibilidade** | A imagem anterior conhece apenas o writer 2.0 e os tipos `eda|colonoscopy`; por isso `web`, `worker` e `pdf_worker` são **parados** durante a janela e somente a imagem nova volta ao ar. Depois do **primeiro write 3.0** (mesmo de EDA/Colonoscopia) ou da primeira row especializada, o retorno à imagem antiga deixa de ser seguro (Seção 4). |
| **FSM / permissões** | 17 estados, roles, locks, intranet guard e um único `appointment_at` por caso preservados. Ecoendoscopia/CPRE **não** recebem agendamento casado (exclusivo de `{EDA, Colonoscopia}`). |
| **Dados sensíveis** | Precheck, verificação e monitoramento usam **apenas contagens, estados, tipos e UUIDs de caso** — sem `extracted_text`, PDF, `structured_data` completo ou conteúdo de mensagem. |
| **Variáveis de ambiente** | Nenhuma variável nova de infraestrutura: `ECHOENDOSCOPY_INTAKE_ENABLED` e `CPRE_INTAKE_ENABLED` já existem em `config/settings/base.py` (default `false`) e são propagadas **somente ao serviço `web`** no Compose (`docker-compose.prod.yml`, `docker-compose.shared-postgres.yml`, `docker-compose.dev.yml`). `worker`/`pdf_worker` **não** recebem nem consultam as flags — caso existente sempre conclui. |
| **Prompts** | `seed_prompts` garante exatamente uma versão **ativa** por nome neutro (`exam_llm1_system`, `exam_llm1_user`, `exam_llm2_system`, `exam_llm2_user`) com conteúdo **3.0** e desativa toda versão ativa dos oito nomes legados, preservando linhas/versões para auditoria. Reexecutar é idempotente. |
| **Rollout** | **Sequencial e independente**: Ecoendoscopia primeiro (passo próprio + janela piloto + aceite humano) e CPRE somente depois. Cada flag é ligada/desligada sozinha, apenas recriando o serviço `web`. |
| **Rollback** | **Fronteira = primeiro write 3.0**, não a ativação das flags. Pós-fronteira o caminho suportado é: desligar as flags, **manter imagem/schema 3.0**, drenar jobs e **corrigir para frente**. Não há deleção de rows/artefatos nem reverse migration destrutiva. Retorno à imagem antiga só é admissível **antes do cutover**, com o precheck do Passo 3 retornando `allowed`. |

### O que o change entrega

- Catálogo e matriz fechados: `eda`, `colonoscopy`, `eda_colonoscopy`,
  `echoendoscopy`, `cpre`. Ecoendoscopia e CPRE são procedimentos
  independentes — nunca subtipo/sinal de EDA nos artefatos 3.0.
- Intake NIR com declaração de Ecoendoscopia/CPRE sob flags próprias
  (upload, correção e reenvio); a detecção divergente continua **fail-closed**
  em revisão NIR quando a flag está desligada.
- Pipeline 3.0: uma análise por caso, evidência ancorada no relatório
  principal, hard rule de imagem abdominal (TC/RM de abdome ou abdome superior
  para Ecoendoscopia; USG abdominal/hepatobiliar, TC/RM abdominal ou CPRM para
  CPRE) com predicado positivo/heading estrito e **pendências agregadas**.
  Qualquer falha força sugestão de negativa; a decisão médica permanece livre.
- Decisão médica `trocar e aprovar`: origem negada + destino aprovado com
  justificativa, **sem** nova chamada LLM, sem repolicy e sem nova
  apresentação de sugestão. Evento `DOCTOR_PROCEDURE_SET_CHANGED` e mensagem
  sistêmica idempotente (sem `UserNotification`).
- Anexos clínicos **não** entram na sugestão automática neste rollout; o
  relatório médico informa esse limite técnico.
- CHD/NIR recebem o conjunto **autorizado** e a comparação
  detectado → autorizado; filtros, analytics e follow-up reconhecem os quatro
  tipos sem dupla contagem de casos.

---

## 2. Pré-requisitos (no servidor de produção)

- Acesso de shell ao servidor como `apps`, com `docker compose` funcional e
  `--project-directory` apontando para a instalação real.
- Acesso ao registry (GHCR) com a tag nova e, para o caminho excepcional da
  Seção 4.1, a tag do release anterior.
- **Backup do Postgres e do volume de mídia `media_prod`** antes de qualquer
  passo mutável (Passo 1), validado **por conteúdo** (procedimento completo em
  [`shared-postgres-production.md`](./shared-postgres-production.md), Seções de
  backup; o runbook
  [`support-combined-eda-colonoscopy-workflow.md`](./support-combined-eda-colonoscopy-workflow.md)
  traz um bloco pronto com validação por conteúdo).
- **Janela de baixa atividade acordada** com a operação (Passo 4) e downtime
  comunicado (parada → migrate → seed → verificação → subida).
- Aceite humano prévio para o **piloto de Ecoendoscopia** — CPRE só é ativada
  após esse aceite (Passo 11).
- Comunicar NIR/médico/CHD que os dois procedimentos serão liberados em passos
  separados e observáveis.

---

## 3. Passos de deploy

### Passo 1 — Backup fail-closed (obrigatório, validado por conteúdo)

Executar o bloco de backup do runbook de referência com os mesmos asserts
binários (dump do Postgres + snapshot do volume real montado em `/app/media`),
usando `BACKUP_DIR=/archive/backups/2026-XXX-specialized-eco-cpre`:

- [`support-combined-eda-colonoscopy-workflow.md`](./support-combined-eda-colonoscopy-workflow.md) — Passo 1 completo (`gzip -t`, marker do PostgreSQL, contagem mínima de linhas, `tar -tzf` do volume resolvido via `docker inspect`).

Nenhum passo adiante é executado sem dump **e** mídia validados. Rollback
suportado não apaga dados, mas o backup continua sendo a rede de segurança da
janela.

### Passo 2 — Atualizar código e construir a imagem nova

O precheck do Passo 3 é um comando de management desta release: a imagem nova
precisa existir antes do preflight (os writers antigos continuam no ar até o
Passo 4).

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

git -C "$PROJECT_DIR" fetch origin && git -C "$PROJECT_DIR" checkout main && git -C "$PROJECT_DIR" pull origin main
git -C "$PROJECT_DIR" log --oneline -5        # confirmar os commits do change no topo
$DPROD build --pull web worker pdf_worker
```

### Passo 3 — Preflight fail-closed: flags false, drenagem e precheck de downgrade

Roda **antes** de qualquer write 3.0 (schema ainda sem artefatos 3.0). Cada
assert é binário e manda PARAR em caso de falha.

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# 3a. As três flags de intake precisam estar false/ausentes no .env de produção
#     (default do Compose e do settings é false). O rollout liga cada uma.
for flag in COLONOSCOPY_INTAKE_ENABLED ECHOENDOSCOPY_INTAKE_ENABLED CPRE_INTAKE_ENABLED; do
  if grep -qE "^${flag}=(true|1|yes)$" "${PROJECT_DIR}/.env" 2>/dev/null; then
    echo "ERRO: ${flag}=true no .env — desligar antes do deploy"; exit 1
  fi
done
echo "OK: flags de intake false (ou ausentes → default false)"

# 3b. As flags especializadas chegam ao serviço web (não ao worker). O .env de
#     produção já fornece as variáveis obrigatórias do Compose.
$DPROD config | awk '/^  [a-z_]+:/{svc=$1} /ECHOENDOSCOPY_INTAKE_ENABLED|CPRE_INTAKE_ENABLED/{print svc, $0}'
# Esperado: somente linhas começando com "web:" — nenhuma com "worker:"/"pdf_worker:"

# 3c. Drenagem: nenhum caso em estado de pipeline 3.0 pode restar antes do
#     cutover (o writer ativo passa a ser exclusivamente o 3.0).
PIPE_STATES=$($DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM cases_case WHERE status IN
   ('NEW','R1_ACK_PROCESSING','EXTRACTING','LLM_STRUCT','LLM_SUGGEST');")
[ "${PIPE_STATES}" = "0" ] || { \
  echo "ERRO: ${PIPE_STATES} caso(s) em estados de pipeline — drenar antes do cutover"; \
  $DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
    "SELECT id, status FROM cases_case WHERE status IN ('NEW','R1_ACK_PROCESSING','EXTRACTING','LLM_STRUCT','LLM_SUGGEST') ORDER BY status;"; \
  exit 1; }

# 3d. PRECHECK DE DOWNGRADE (machine-readable, não destrutivo). Pré-cutover
#     DEVE retornar status "allowed" e exit code 0. Qualquer classe bloqueante
#     significa que a fronteira do write 3.0 já foi cruzada — PARAR e ir para a
#     Seção 4.2 (rollback suportado), nunca para a imagem antiga.
$DPROD run --rm web uv run python manage.py check_specialized_procedure_downgrade \
  --settings=config.settings.prod

# 3e. Validar localmente que o seed produz exatamente uma versão 3.0 por nome
#     neutro (a execução binária é o Passo 6, depois do seed).
$DPROD run --rm web uv run python manage.py shell --settings=config.settings.prod -c "
from apps.llm.management.commands.seed_prompts import DEFAULT_CONTENTS, LEGACY_PROMPT_NAMES, PROMPT_NAMES
for name in PROMPT_NAMES:
    assert DEFAULT_CONTENTS[name].strip(), name
print('OK: 3.0 candidato definido para', len(PROMPT_NAMES), 'prompts neutros')
print('OK: nomes legados monitorados:', len(LEGACY_PROMPT_NAMES))
"
```

**Saída esperada do 3d (pré-cutover):** um JSON com `"status": "allowed"`,
`"blocking_checks": []` e os cinco checks com `count: 0`
(`pipeline_job_in_flight`, `specialized_case_procedure`,
`specialized_case_event`, `legacy_echo_artifact`, `v3_artifact_write`).

**Se o precheck sair com exit code 1:** a fronteira já foi cruzada. **PARAR** o
deploy de cutover e seguir a Seção 4.2 — sem reagendar o writer 2.0.

### Passo 4 — JANELA DE MANUTENÇÃO: parar todos os writers e aplicar migrations

**Por que parar também o `web`:** o `web` aceita uploads/escritas HTTP e o
código da imagem antiga não conhece Ecoendoscopia/CPRE nem o contrato 3.0.
`worker`/`pdf_worker` processariam novos casos com prompts 2.0 e schema
incompatível. O `db` permanece no ar.

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# a) Janela acordada com a operação (fora do horário de pico).
# b) PARAR TODOS os writers.
$DPROD stop web worker pdf_worker

# c) Migrations com a imagem NOVA (serviços parados; db no ar).
#    Saída esperada: Applying cases.0019_alter_caseprocedure_procedure_type... OK
$DPROD run --rm web uv run python manage.py migrate --settings=config.settings.prod
```

Se a migration falhar: **NÃO continuar** — ir para a Seção 4. Não há write 3.0
antes deste ponto.

### Passo 5 — Seed dos prompts 3.0 (imagem nova, serviços ainda parados)

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

$DPROD run --rm web uv run python manage.py seed_prompts --settings=config.settings.prod
```

Garante **exatamente uma versão ativa** por nome neutro com o conteúdo 3.0 e
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

# 6a. Prompts 3.0: quatro neutros ativos com conteúdo 3.0; zero legados ativos.
$DPROD run --rm web uv run python manage.py shell --settings=config.settings.prod -c "
from apps.llm.management.commands.seed_prompts import DEFAULT_CONTENTS, LEGACY_PROMPT_NAMES, PROMPT_NAMES
from apps.llm.models import PromptTemplate
for name in PROMPT_NAMES:
    active = PromptTemplate.get_active(name)
    if active is None or active.content != DEFAULT_CONTENTS[name]:
        print('PRECHECK FALHOU — nome neutro sem versão 3.0 ativa:', name); raise SystemExit(1)
legacy_active = PromptTemplate.objects.filter(name__in=LEGACY_PROMPT_NAMES, is_active=True).count()
if legacy_active != 0:
    print('PRECHECK FALHOU — versões legadas ainda ativas:', legacy_active); raise SystemExit(1)
print('OK — 4 prompts neutros 3.0 ativos; 0 legados ativos')
"
# Se falhar: corrigir pela Gestão de Prompts (admin) ou reexecutar o seed.
# NUNCA subir com um prompt ativo 2.0 ou com prompt legado ativo.

# 6b. Schema de choices alinhado (sem constraint de banco; validação é de
#     aplicação) e rows CaseProcedure com tipos válidos do catálogo.
BAD_PROC_TYPES=$($DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM cases_caseprocedure WHERE procedure_type NOT IN ('eda','colonoscopy','echoendoscopy','cpre');")
[ "${BAD_PROC_TYPES}" = "0" ] || { echo "ERRO: tipo de procedimento fora do catálogo"; exit 1; }
CONSTRAINT_N=$($DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM pg_constraint WHERE conname='uniq_case_procedure_type';")
[ "${CONSTRAINT_N}" = "1" ] || { echo "ERRO: constraint uniq_case_procedure_type ausente"; exit 1; }

# 6c. O precheck de downgrade ainda deve estar `allowed` — prova de que nenhum
#     write 3.0 existia quando a janela abriu.
$DPROD run --rm web uv run python manage.py check_specialized_procedure_downgrade \
  --settings=config.settings.prod
```

### Passo 7 — Subir a imagem nova com as duas flags especializadas false

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# Nenhuma flag ligada. Recriação forçada garante a imagem do Passo 2 — nunca
# "start" dos containers antigos.
$DPROD up -d --force-recreate web worker pdf_worker
$DPROD ps
```

### Passo 8 — Smoke de REGRESSÃO (EDA/Colonoscopia) — obrigatório antes das flags

Com as flags especializadas `false`, o fluxo convencional precisa rodar
**idêntico** ao baseline. Nenhuma ativação especializada ocorre antes deste
smoke verde.

| # | Cenário | Procedimento | Resultado esperado |
|---|---|---|---|
| 1 | **EDA simples** | Upload de relatório EDA com seleção **EDA** | Pipeline 3.0 conclui; badge EDA; fila médica; decisão e fluxo normais até resposta NIR |
| 2 | **Colonoscopia simples** | Upload com seleção **Colonoscopia** | Processa com prompts neutros 3.0; fluxo idêntico a EDA |
| 3 | **Combinado EDA + Colonoscopia** | Upload com seleção **EDA + Colonoscopia** | **UM** caso com 2 componentes; badge combinado; decisão por componente; **agendamento casado** no CHD (um único `appointment_at`) |
| 4 | **Ecoendoscopia desabilitada** | Tentar upload com seleção **Ecoendoscopia** | Opção desabilitada/bloqueada no intake com explicação; nenhum caso criado |
| 5 | **CPRE desabilitada** | Tentar upload com seleção **CPRE** | Opção desabilitada/bloqueada no intake com explicação; nenhum caso criado |
| 6 | **Casos em voo** | Acompanhar casos não `CLEANED` anteriores | Continuam processando; nenhuma flag interrompe pipeline/fila |

### Passo 9 — Evidência da fronteira de rollback (após o primeiro write 3.0)

O smoke do Passo 8 já produziu writes 3.0. Rodar o precheck e **registrar** o
resultado como evidência de que o caminho de retorno à imagem antiga foi
fechado — o bloqueio aqui é o comportamento **esperado**.

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# Exit code 1 esperado a partir daqui. Capturar o JSON no relatório da janela.
$DPROD run --rm web uv run python manage.py check_specialized_procedure_downgrade \
  --settings=config.settings.prod || true
# Esperado: "status": "blocked" com "v3_artifact_write" (e eventualmente
# "pipeline_job_in_flight" se houver caso em processamento no instante da
# leitura). A partir deste ponto o rollback suportado é a Seção 4.2.
```

### Passo 10 — Rollout de Ecoendoscopia (Eco ANTES de CPRE)

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# 1. Definir ECHOENDOSCOPY_INTAKE_ENABLED=true no .env de produção.
#    CPRE permanece false.
# 2. Recriar APENAS o serviço que lê a flag:
$DPROD up -d --force-recreate web
```

Smoke de Ecoendoscopia (com casos controlados, acompanhados pelo NIR):

| # | Cenário | Resultado esperado |
|---|---|---|
| 1 | **Declaração** | Upload com seleção **Ecoendoscopia** cria **um** caso com row declarada `echoendoscopy` |
| 2 | **Detecção** | Nenhum sinal legado `echoendoscopy` é criado no artefato 3.0; badge do procedimento coerente |
| 3 | **Policy negativa (imagem sem laudo)** | Relatório só com *solicitação* de TC/RM (sem conclusão/achado) gera pendências agregadas e **sugestão de negativa**; caso segue para o médico (não bloqueia) |
| 4 | **Policy negativa (modalidade/sítio)** | Imagem com modalidade ou localização não aceita também entra como pendência de imagem |
| 5 | **Policy positiva** | Laudo de TC/RM de abdome/abdome superior com conclusão/achado satisfaz o requisito; sugestão segue os critérios comuns |
| 6 | **Anexos fora da automação** | Anexo com a imagem **não** satisfaz a hard rule; relatório mostra o aviso de limite técnico |
| 7 | **Decisão médica** | Aprovar/negar normalmente, com pendências visíveis |
| 8 | **Trocar e aprovar** | Caso detectado simples trocado para Ecoendoscopia: origem negada + destino aprovado com justificativa, **sem** nova análise; evento `DOCTOR_PROCEDURE_SET_CHANGED` e mensagem sistêmica na thread |
| 9 | **CHD** | Card/detalhe mostram o procedimento **autorizado** sem sufixo de agendamento casado |
| 10 | **Resposta NIR** | Resposta final com Solicitado / Detectado / Autorizado e razões por componente |

**Janela piloto:** monitorar (Passo 12) por pelo menos um ciclo operacional.
Manter CPRE `false` durante todo o piloto.

### Passo 11 — Rollout de CPRE (somente após aceite humano do piloto)

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# 1. Definir CPRE_INTAKE_ENABLED=true no .env (Ecoendoscopia permanece true).
# 2. Recriar APENAS o serviço web:
$DPROD up -d --force-recreate web
```

Smoke de CPRE (mesma matriz, com os requisitos próprios):

| # | Cenário | Resultado esperado |
|---|---|---|
| 1 | **Declaração** | Upload com seleção **CPRE** cria um caso com row declarada `cpre` |
| 2 | **USG hepatobiliar** | USG de abdome/abdome superior/hepatobiliar com conclusão/achado satisfaz |
| 3 | **CPRM** | CPRM/colangiorressonância é normalizada como modalidade de ressão hepatobiliar e satisfaz |
| 4 | **Imagem sem sítio aceito** | Modalidade aceita com localização não aceita → pendência `abdominal_imaging_site_not_accepted` |
| 5 | **Imagem sem achado** | Laudo citado sem conclusão/achado → pendência `abdominal_imaging_finding_absent`; sugestão de negativa |
| 6 | **Trocar e aprovar** | Troca de EDA detectada para CPRE com justificativa, sem reanálise; evento + mensagem sistêmica |
| 7 | **CHD/NIR** | Autorizado projetado; sem agendamento casado; resposta final com as três dimensões |

As duas flags continuam **independentes**: qualquer uma pode ser desligada
sozinha, apenas recriando o `web`.

### Passo 12 — Monitoramento (contagens/eventos, sem texto clínico)

Nunca selecionar `structured_data`, `extracted_text`, PDF ou conteúdo de
mensagem. Monitorar durante a janela piloto e por 24h após a ativação de CPRE.

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

$DPROD exec -T web uv run python manage.py shell --settings=config.settings.prod -c "
from collections import Counter
from django.db.models import Count
from apps.cases.models import Case, CaseEvent, CaseProcedure

print('— Volume por procedimento (rows CaseProcedure) —')
print(' ', dict(CaseProcedure.objects.values_list('procedure_type').annotate(n=Count('id'))))

print('— Casos em voo por status —')
for st in ('WAIT_DOCTOR', 'WAIT_APPT', 'WAIT_R1_CLEANUP_THUMBS', 'FAILED'):
    print(' ', st, Case.objects.filter(status=st).count())

print('— Revisão NIR por reason_code (CASE_PROCEDURES_DETECTED/REVIEW) —')
reasons = Counter()
for payload in CaseEvent.objects.filter(event_type__in=('EDA_SCOPE_GATED_MANUAL_REVIEW',)).values_list('payload', flat=True):
    if isinstance(payload, dict):
        reasons[str(payload.get('reason_code'))] += 1
print(' ', dict(reasons))

print('— Negativas por imagem (policy por procedimento) —')
imaging = Counter()
for payload in CaseEvent.objects.filter(event_type='EDA_PREOP_POLICY_DECISION').values_list('payload', flat=True):
    if isinstance(payload, dict) and str(payload.get('reason_code', '')).startswith('abdominal_imaging_'):
        imaging[str(payload['reason_code'])] += 1
print(' ', dict(imaging))

print('— Eventos estruturais (contagens) —')
for et in ('CASE_PROCEDURES_DETECTED', 'DOCTOR_PROCEDURE_SET_CHANGED',
           'LLM1_OK', 'LLM2_OK', 'PIPELINE_FAILED'):
    print(' ', et, CaseEvent.objects.filter(event_type=et).count())
"
```

**Alertas:** pico de `FAILED` ou de `WAIT_R1_CLEANUP_THUMBS` acima do baseline;
crescimento anômalo de `abdominal_imaging_*` (sinaliza regra/qualidade do
laudo, não erro de código); `DOCTOR_PROCEDURE_SET_CHANGED` sem mensagem
sistêmica correspondente na thread do caso; qualquer `UserNotification`
originada de mensagem sistêmica (invariante: não deve existir).

---

## 4. Plano de Rollback

### 4.1 Camada de flags (sempre disponível, não destrutiva)

Desligar as flags de intake **não** interrompe casos existentes e não exige
migration: `worker`/`pdf_worker` nunca consultam as flags.

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# .env de produção: ECHOENDOSCOPY_INTAKE_ENABLED=false e CPRE_INTAKE_ENABLED=false
$DPROD up -d --force-recreate web
```

Efeito: novos uploads/correções/reenvios dos tipos especializados ficam
bloqueados no intake; casos existentes concluem; o médico continua podendo
trocar para qualquer procedimento do catálogo. Use esta camada como primeira
resposta a qualquer incidente operacional, **independentemente** da fronteira.

### 4.2 Rollback suportado APÓS o primeiro write 3.0 (caminho padrão)

Depois do primeiro write 3.0 — mesmo de EDA/Colonoscopia — ou da primeira row
especializada, o caminho suportado é **fix-forward**:

1. **Desligar as duas flags** (Seção 4.1) e recriar apenas o `web`.
2. **Manter a imagem nova e o schema pós-0019 rodando.** Não reagendar o writer
   2.0, não reativar prompts 2.0, não rodar reverse migration destrutiva.
3. **Drenar/encerrar casos em voo**: acompanhar o Passo 12 e deixar os fluxos
   concluírem; se necessário, encerrar administrativamente pelo dashboard
   (manager/admin) com motivo — o caso sai das filas e permanece na auditoria.
4. **Corrigir para frente**: a correção é um novo commit/imagem que mantém o
   schema 3.0 e as rows/artefatos existentes; a única forma de voltar atrás é
   uma release nova com o fix.
5. **Nunca apagar** rows `CaseProcedure`, `structured_data`,
   `suggested_action`, `CaseEvent`, `priority_signals` ou o histórico de
   prompts. **Deleção para viabilizar downgrade está fora de escopo.**

### 4.3 Retorno à imagem anterior (exceção, somente PRÉ-cutover)

Admissível **apenas** se o precheck do Passo 3 retornar `allowed` (zero write
3.0, zero row/evento especializado, zero artefato derivado do sinal legado, zero
job em voo). Sequência:

1. `$DPROD stop web worker pdf_worker` (nenhum writer ativo na janela).
2. Reativar a matriz de prompts compatível com a imagem anterior (o writer 2.0
   usa os nomes legados) via `manage.py shell` — exatamente uma versão ativa por
   nome, sem apagar o histórico (padrão do Bloco B em
   [`support-combined-eda-colonoscopy-workflow.md`](./support-combined-eda-colonoscopy-workflow.md)).
3. Subir a imagem do release anterior com `up -d --force-recreate web worker pdf_worker`.
4. Validar um envio EDA em homologação antes de liberar para a operação.

O precheck (`check_specialized_procedure_downgrade`) é o gate **binário** desse
caminho: exit code 1 significa que a exceção **não** está disponível — voltar à
Seção 4.2.

---

## 5. Pós-deploy (fechamento)

- Manter as duas flags documentadas no `.env` privado de produção (default
  `false`); `.env.example` as traz como `false` e o Compose as propaga apenas
  para o serviço `web`.
- Manter `PROJECT_CONTEXT.md` e `docs/manual/manual-usuarios.md` alinhados ao
  comportamento real.
- Monitorar por 24h conforme o Passo 12 (contagens/eventos, sem texto clínico).
- Aprovação humana é pré-requisito para ativar CPRE e para arquivar o change;
  não arquivar sem confirmação explícita.

## 6. Notas operacionais

- **Fronteira de rollback é o primeiro write 3.0**, não a ativação das flags de
  intake. Ativar Ecoendoscopia/CPRE não cria obrigação de downgrade; o caminho
  suportado pós-write é flags off + imagem/schema 3.0 + fix-forward.
- **Flags são web-only e independentes**: bloqueiam apenas novos
  uploads/correções/reenvios do próprio tipo; nenhum worker, pipeline, fila ou
  decisão médica as consulta.
- **Eco antes de CPRE, sempre**: CPRE só é ativada após aceite humano do piloto
  de Ecoendoscopia.
- **Detecção divergente com flag desligada** permanece fail-closed em revisão
  NIR — não existe downgrade silencioso do procedimento para EDA.
- **Sem regra de sala**: `appointment_location` continua texto livre; o ATS não
  valida compatibilidade entre procedimento e sala.
- **Anexos fora da automação**: anexos clínicos não participam da sugestão
  automática; apenas o relatório principal alimenta detecção e policy.
- **Sem `UserNotification` de mensagem sistêmica**: a projeção de
  `DOCTOR_PROCEDURE_SET_CHANGED` na thread é idempotente e não incrementa badge.
- **Monitoramento sem expor texto clínico**: somente contagens, estados, tipos e
  UUIDs de caso.
