# Runbook de Deploy — `support-combined-eda-colonoscopy-workflow`

**Change:** `support-combined-eda-colonoscopy-workflow` (Slices 001–012)
**Branch:** `feature/support-combined-eda-colonoscopy-workflow` → `main`
**Classificação de risco:** 🔴 CRÍTICO / HIGH-ARCH — ativação do fluxo combinado
EDA + Colonoscopia: schema normalizado `CaseProcedure`, contrato LLM neutro 2.0,
quatro prompts neutros canônicos e cutover físico com remoção de
`Case.exam_type` (migrations `cases.0015_caseprocedure` e
`cases.0016_remove_case_exam_type`).

---

## Quick reference

Cópia de mão — para uso **após** leitura completa do runbook e após o
Passo 1 (backup) já estar em `/archive/backups/`. Executar como `apps`.
**Todos os comandos usam caminhos absolutos e `--project-directory` — não
dependem do diretório corrente.**

```bash
# Diretório real de instalação (ajustar para o ambiente)
PROJECT_DIR=/opt/ats-web/app
BACKUP_DIR=/archive/backups/2026-XXX-combined-eda-colonoscopy
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# FAIL-FAST (obrigatório em cópia de mão): qualquer falha de backup/preflight/
# stop/migrate/seed/up ABORTA o bloco imediatamente. Sem `|| true`/`&&` que
# engula erro: um migrate ou seed falho NUNCA pode chegar ao up. Em falha:
# PARAR (Seção 4).
set -euo pipefail

# 1. (pré) Backup já feito, validado por conteúdo e movido para /archive/backups/ (Passo 1).

# 2. Preflight de dados/estados/flag — mismatch termina não zero (Passo 2).

# 3. Atualizar código e buildar a imagem nova (Passo 3).

# 4. JANELA DE MANUTENÇÃO: parar TODOS os writers, aplicar migrations e seed
#    com a imagem nova, verificar schema/prompts ANTES de subir (Passos 4–6).

# 5. Subir somente a imagem nova com a flag desligada (Passo 7), smoke com
#    flag desligada (Passo 8) e só então ativar a flag no web (Passo 9).

# 6. Smoke positivo EDA/Colon/Combinado (Passo 10) e monitoramento (Passo 11).
```

> A sequência mutável (stop → migrate → seed → verify → up → flag) está
> explicitada e serializada nos Passos 4–9. Não executar fora de ordem e nunca
> `start` de containers antigos após a migration.

---

## 1. Análise de risco

| Aspecto | Avaliação |
|---|---|
| **Risco global** | 🔴 **CRÍTICO / HIGH-ARCH** — conforme `proposal.md`. Mudança transversal de schema (normalização `CaseProcedure`), contrato LLM (v2 neutro) e prompts (quatro neutros canônicos) em produção, com cutover físico e remoção de coluna. |
| **Migrations** | `cases.0015_caseprocedure` (CreateModel `CaseProcedure` + índices dimensionais + backfill conservador D3 a partir de `Case.exam_type`, sem ler texto clínico e sem reprocessar) e `cases.0016_remove_case_exam_type` (precheck fail-closed: exige 1–2 rows `CaseProcedure` válidas por caso antes de remover a coluna ponte). **Não é possível prometer downtime zero**: a janela de manutenção deixa o sistema indisponível (web fora do ar, workers e filas pausados) durante parada → migrations → seed → verificação → subida. Acordar e comunicar esse downtime à operação antes de abrir a janela. |
| **Compatibilidade** | Código antigo (release anterior) não conhece `CaseProcedure` nem o contrato 2.0 e usa os oito nomes de prompt legados. Por isso `web`, `worker` e `pdf_worker` são **parados** durante a janela (Passo 4) e só as imagens novas voltam ao ar (Passo 7). Rollback para a imagem antiga é **exceção** e exige bridge executável e fail-fast (Seção 4.2). |
| **Mudanças de FSM / pipeline** | 17 estados FSM preservados. Pipeline passa a executar somente o schema v2 com os quatro prompts neutros (`exam_llm{1,2}_{system,user}`); os oito nomes legados deixam de participar do dispatch e permanecem apenas como histórico inativo. |
| **Dados sensíveis** | Backfills não leem conteúdo clínico (sem PDF/JSON/texto). Queries de monitoramento usam apenas contagens/estados/tipos — **sem expor texto clínico**. |
| **Variáveis de ambiente novas** | Nenhuma variável nova neste change: `COLONOSCOPY_INTAKE_ENABLED` (default `false`) já existe e continua **somente no serviço `web`** (`docker-compose.prod.yml`); `worker`/`pdf_worker` **não** recebem nem consultam a flag. |
| **Prompts** | `seed_prompts` garante **exatamente uma versão ativa por nome neutro** (cria v1 ativa quando ausente) e **desativa toda versão ativa dos oito nomes legados**, preservando linhas/versões para auditoria/rollback. Reexecutar é idempotente. |
| **Rollback** | Não destrutivo e **preferido**: desligar a flag e **manter a imagem nova rodando** (schema pós-0016, sem coluna ponte). Reverter para a imagem antiga é **exceção** e exige bridge de schema/prompt verificável e fail-fast (Seção 4.2), com forward serializado (Seção 4.3). Nenhum caminho apaga `CaseProcedure`, JSON de artefatos nem histórico de prompts. |

### O que o change entrega

- Um PDF cria exatamente um `Case`; EDA e Colonoscopia são rows únicas de
  `CaseProcedure` (constraint `uniq_case_procedure_type`), inclusive para a
  solicitação combinada `EDA + Colonoscopia` — sem segundo caso e sem row
  genérica `combined`.
- Três dimensões autoritativas por componente: `declared_by_nir` (declaração
  do NIR), `detection_status` (detecção da análise) e `doctor_disposition`
  (autorização médica). Nenhuma dimensão sobrescreve outra; `CaseEvent`
  preserva os fatos append-only.
- Intake aceita EDA, Colonoscopia ou EDA + Colonoscopia. Single→combined com
  evidência forte recebe **upgrade automático** auditado
  (`PROCEDURE_SELECTION_AUTO_UPGRADED`) e segue ao médico sem ACK do NIR.
  Combinado→single, troca entre tipos únicos e unknown/non-supported retornam
  ao NIR.
- Pipeline v2: uma chamada LLM1 para história comum + `requested_procedures[]`,
  policy determinística por procedimento e uma chamada LLM2 com recomendação
  exata por componente. Artefatos 1.1 permanecem legíveis e não são reescritos.
- Decisão médica por componente: aprovar/negar/incluir/substituir, com razão
  por componente na negativa e na inclusão; inclusão não reexecuta LLM.
- Um **agendamento casado**: o CHD confirma uma única data/hora/local para o
  conjunto autorizado (`Agendamento casado`).
- Resposta final ao NIR com solicitado/detectado/autorizado e razões por
  componente; dashboard com dimensões e `1 caso / 2 componentes` no combinado.

---

## 2. Pré-requisitos (no servidor de produção)

- Acesso de shell ao servidor de produção como `apps` (conforme operação atual).
- `docker compose` funcional com acesso ao projeto (`--project-directory`).
- Acesso ao registry da imagem de release (GHCR) com a tag nova e a tag do
  release anterior (necessária apenas no caminho excepcional da Seção 4.2).
- **Backup do Postgres e do volume de mídia `media_prod` obrigatório** antes de
  qualquer passo mutável (Passo 1) — validado por conteúdo, não apenas tamanho.
- **Janela de baixa atividade acordada com a operação** (Passo 4) com downtime
  declarado (estimativa realista: minutos; dominado pelo backfill de `0015` e
  pela verificação, podendo ser maior em tabelas muito grandes).
- Comunicar aos times NIR/médico/CHD que o fluxo combinado será ativado em
  passo explícito e separado (Passo 9).

---

## 3. Passos de deploy

### Passo 1 — Backup fail-closed (obrigatório, validado por conteúdo)

```bash
# Caminhos absolutos — nada depende do diretório corrente.
PROJECT_DIR=/opt/ats-web/app
BACKUP_DIR=/archive/backups/2026-XXX-combined-eda-colonoscopy
mkdir -p "$BACKUP_DIR"
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# 1a. Dump do Postgres (produção) — pipeline FAIL-FAST. set -euo pipefail faz o
#     shell abortar se QUALQUER comando da pipeline falhar, incluindo o pg_dump à
#     esquerda do pipe: um dump falho nunca vira "gzip válido" aceito adiante.
set -euo pipefail
STAMP=$(date +%Y%m%d_%H%M)
DUMP="${BACKUP_DIR}/ats_web_pre_combined_${STAMP}.sql.gz"
$DPROD exec -T db pg_dump -U ats_web ats_web | gzip > "$DUMP"

# 1b. VALIDAÇÃO do dump por CONTEÚDO (não apenas tamanho) — cada check falho
#     encerra a execução (exit 1); nunca seguir com backup vazio/truncado.
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
  alpine tar czf "/backup/media_pre_combined_${STAMP}.tar.gz" -C /media .

# 1d. VALIDAÇÃO do tar por CONTEÚDO (listagem completa + mínimo de entradas).
#     Falha ABORTA a execução (exit 1) — sob set -e, um comando à esquerda de
#     `&&` que falha NÃO encerra o script; por isso usa-se `|| { ...; exit 1; }`.
MEDIA_TAR="${BACKUP_DIR}/media_pre_combined_${STAMP}.tar.gz"
tar -tzf "$MEDIA_TAR" > /dev/null \
  || { echo "ERRO: tar de mídia inválido/truncado: $MEDIA_TAR"; exit 1; }
MEDIA_ENTRIES=$(tar -tzf "$MEDIA_TAR" | wc -l)
[ "${MEDIA_ENTRIES}" -ge 1 ] \
  || { echo "ERRO: tar de mídia sem entradas: $MEDIA_TAR"; exit 1; }
echo "Tar de mídia OK: ${MEDIA_ENTRIES} entradas"

# Confirmar presença esperada dos artefatos
ls -lh "${BACKUP_DIR}"/ats_web_pre_combined_*.sql.gz "${BACKUP_DIR}"/media_pre_combined_*.tar.gz
```

### Passo 2 — Preflight de dados/estados (machine-readable, fail-closed)

Roda **antes** de qualquer escrita (schema ainda no release anterior, com
`Case.exam_type` presente e sem a tabela `cases_caseprocedure`). Cada assert
falho termina com exit 1 e manda PARAR — não é SELECT visual.

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# 2a. Estados de pipeline incompatíveis com o pipeline v2: LLM_STRUCT e
#     LLM_SUGGEST (além de NEW/R1_ACK_PROCESSING/EXTRACTING) precisam estar
#     drenados ou listados para tratamento ANTES do cutover. Qualquer caso
#     remanescente bloqueia o deploy (exit 1) — tratar primeiro.
PIPE_STATES=$($DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM cases_case WHERE status IN
   ('NEW','R1_ACK_PROCESSING','EXTRACTING','LLM_STRUCT','LLM_SUGGEST');")
[ "${PIPE_STATES}" = "0" ] || { \
  echo "ERRO: ${PIPE_STATES} caso(s) em estados de pipeline (LLM_STRUCT/LLM_SUGGEST etc.) — drenar ou listar para tratamento antes do deploy"; \
  $DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
    "SELECT id, status FROM cases_case WHERE status IN ('NEW','R1_ACK_PROCESSING','EXTRACTING','LLM_STRUCT','LLM_SUGGEST') ORDER BY status;"; \
  exit 1; }

# 2b. Valores de exam_type válidos: somente eda | colonoscopy. A seleção
#     combinada é representada pelo CONJUNTO de rows CaseProcedure (chave de
#     exibição eda_colonoscopy), nunca por um valor singular na coluna.
BAD_TYPES=$($DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM cases_case WHERE exam_type NOT IN ('eda','colonoscopy');")
[ "${BAD_TYPES}" = "0" ] || { echo "ERRO: ${BAD_TYPES} caso(s) com exam_type inválido"; exit 1; }

# 2c. Flag de intake desligada: COLONOSCOPY_INTAKE_ENABLED deve estar false
#     no ambiente (somente web lê a flag; assert aqui é do .env de produção).
if grep -qE "^COLONOSCOPY_INTAKE_ENABLED=(true|1|yes)$" "${PROJECT_DIR}/.env" 2>/dev/null; then
  echo "ERRO: COLONOSCOPY_INTAKE_ENABLED=true no .env — desligar antes do deploy"; exit 1
fi
echo "OK: flag false (ou ausente → default false)"

# 2d. Matriz de prompts (definição — execução binária no Passo 6, após o seed):
#     exatamente UMA versão ativa para cada um dos quatro nomes neutros
#     (versões históricas inativas podem coexistir) e ZERO versões ativas dos
#     oito nomes legados após o cutover.
#   Neutros:  exam_llm1_system, exam_llm1_user, exam_llm2_system, exam_llm2_user
#   Legados:  llm1_system, llm1_user, llm2_system, llm2_user,
#             colonoscopy_llm1_system, colonoscopy_llm1_user,
#             colonoscopy_llm2_system, colonoscopy_llm2_user
echo "Matriz de prompts definida (verificação binária no Passo 6)"

# 2e. Invariante pós-migration garantido pela própria migration 0016 (precheck
#     fail-closed): todo caso terá 1–2 rows CaseProcedure válidas (tipos
#     eda|colonoscopy), sem duplicatas por caso/tipo e com ao menos uma row
#     declarada. O Passo 6 re-executa asserts binários desses mesmos
#     invariantes sobre o banco já migrado.
echo "Invariante 1–2 rows CaseProcedure por caso: fail-closed na 0016, reassert no Passo 6"
```

### Passo 3 — Atualizar código e build da imagem nova

```bash
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

git -C "$PROJECT_DIR" fetch origin && git -C "$PROJECT_DIR" checkout main && git -C "$PROJECT_DIR" pull origin main
git -C "$PROJECT_DIR" log --oneline -5        # confirmar os commits do change no topo
$DPROD build --pull web worker pdf_worker
```

### Passo 4 — JANELA DE MANUTENÇÃO: parar todos os writers e aplicar migrations

**Por que parar TAMBÉM o `web` (e não só os workers):** a migration `0016`
remove `Case.exam_type` (NOT NULL sem default desde `0014`) e o código da
imagem ANTIGA insere `Case` com esse campo — qualquer escrita do web antigo
durante ou depois do cutover falharia. `worker`/`pdf_worker` também não podem
continuar processando durante o backfill de `0015` e a remoção de coluna/índice
de `0016` (locks e contratos LLM diferentes). O db permanece no ar.

**Downtime esperado (honesto):** a janela de manutenção deixa o sistema
indisponível durante parada → migrations → seed → verificação → subida.
Estimativa realista: **minutos** (dominado pelo backfill `0015`), podendo ser
maior em tabelas muito grandes. Acordar e comunicar esse downtime à operação
antes de abrir a janela.

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# a) Janela de manutenção acordada com a operação (fora do horário de pico).
# b) PARAR TODOS os writers: web (uploads/escritas HTTP), worker e pdf_worker
#    (pipeline/extração). NENHUM writer antigo permanece ativo na migration.
$DPROD stop web worker pdf_worker

# c) Aplicar as migrations COM A IMAGEM NOVA (serviços parados; db no ar).
#    Saída esperada: Applying cases.0015_caseprocedure... OK;
#                    Applying cases.0016_remove_case_exam_type... OK
$DPROD run --rm web uv run python manage.py migrate --settings=config.settings.prod

# d) Verificar locks/atividade durante a janela (em outro shell, se necessário):
$DPROD exec -T db psql -U ats_web -d ats_web -c \
  "SELECT pid, state, wait_event_type, query FROM pg_stat_activity WHERE state <> 'idle';"

# e) NÃO "start" dos containers antigos depois da migration: o código antigo
#    desconhece o schema pós-0016 (sem exam_type) e os prompts neutros.
#    Subir somente as imagens novas no Passo 7.
```

Se erro na migration: **NÃO continuar** — ir para a Seção 4 (Rollback).

### Passo 5 — Seed dos quatro prompts neutros (idempotente; imagem nova, serviços ainda parados)

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

$DPROD run --rm web uv run python manage.py seed_prompts --settings=config.settings.prod
```

Roda com a imagem nova (mesma do Passo 4c), com `web`/`worker`/`pdf_worker`
ainda parados; o db permanece no ar. Garante **exatamente uma versão ativa**
por nome neutro (`exam_llm1_system`, `exam_llm1_user`, `exam_llm2_system`,
`exam_llm2_user`) e **desativa toda versão ativa dos oito nomes legados**
(`llm1_system`, `llm1_user`, `llm2_system`, `llm2_user`,
`colonoscopy_llm1_system`, `colonoscopy_llm1_user`, `colonoscopy_llm2_system`,
`colonoscopy_llm2_user`) — preservando linhas/versões históricas. Idempotente:
reexecutar é no-op (não cria versões extras nem reativa nomes antigos).

### Passo 6 — Verificação pós-migration: schema, rows e prompts (ANTES do up)

Cada assert é binário (saída `-At` comparada, exit 1 em mismatch) — não basta
comentário ou SELECT visual. Qualquer falha: PARAR; não subir (Passo 7).

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# 6a. Coluna legada AUSENTE (removida pela 0016)
LEGACY_COLUMN=$($DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM information_schema.columns \
   WHERE table_name='cases_case' AND column_name='exam_type';")
[ "${LEGACY_COLUMN}" = "0" ] || { echo "ERRO: coluna exam_type ainda presente"; exit 1; }

# 6b. Toda row CaseProcedure com tipo válido; zero duplicatas (constraint) —
#     reassert do invariante fail-closed da migration 0016.
BAD_PROC_TYPES=$($DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM cases_caseprocedure WHERE procedure_type NOT IN ('eda','colonoscopy');")
[ "${BAD_PROC_TYPES}" = "0" ] || { echo "ERRO: tipo de procedimento inválido"; exit 1; }
DUP_PROC=$($DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM (SELECT case_id, procedure_type FROM cases_caseprocedure \
   GROUP BY case_id, procedure_type HAVING count(*) > 1) x;")
[ "${DUP_PROC}" = "0" ] || { echo "ERRO: duplicatas em cases_caseprocedure"; exit 1; }

# 6c. Todo caso com 1–2 rows CaseProcedure e ao menos uma declaração NIR
ZERO_ROWS=$($DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM cases_case c WHERE NOT EXISTS \
   (SELECT 1 FROM cases_caseprocedure cp WHERE cp.case_id = c.id);")
[ "${ZERO_ROWS}" = "0" ] || { echo "ERRO: caso(s) sem rows CaseProcedure"; exit 1; }
MULTI_ROWS=$($DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM (SELECT case_id FROM cases_caseprocedure GROUP BY case_id \
   HAVING count(*) > 2) x;")
[ "${MULTI_ROWS}" = "0" ] || { echo "ERRO: caso(s) com mais de 2 rows"; exit 1; }
NO_DECLARED=$($DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM cases_case c WHERE NOT EXISTS \
   (SELECT 1 FROM cases_caseprocedure cp WHERE cp.case_id = c.id AND cp.declared_by_nir);")
[ "${NO_DECLARED}" = "0" ] || { echo "ERRO: caso(s) sem row declarada pelo NIR"; exit 1; }

# 6d. Constraints/indexes dimensionais presentes
CONSTRAINT_N=$($DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM pg_constraint WHERE conname='uniq_case_procedure_type';")
[ "${CONSTRAINT_N}" = "1" ] || { echo "ERRO: constraint uniq_case_procedure_type ausente"; exit 1; }

# 6e. Prompts: exatamente UMA versão ativa por nome neutro; ZERO ativas legadas
$DPROD exec -T web uv run python manage.py shell --settings=config.settings.prod -c "
from apps.llm.models import PromptTemplate
neutral = ['exam_llm1_system','exam_llm1_user','exam_llm2_system','exam_llm2_user']
legacy = ['llm1_system','llm1_user','llm2_system','llm2_user',
          'colonoscopy_llm1_system','colonoscopy_llm1_user',
          'colonoscopy_llm2_system','colonoscopy_llm2_user']
for name in neutral:
    if PromptTemplate.objects.filter(name=name, is_active=True).count() != 1:
        print('PRECHECK FALHOU — nome neutro sem exatamente uma ativa:', name)
        raise SystemExit(1)
active_legacy = PromptTemplate.objects.filter(name__in=legacy, is_active=True).count()
if active_legacy != 0:
    print('PRECHECK FALHOU — versões legadas ainda ativas:', active_legacy)
    raise SystemExit(1)
print('OK — 4 neutros com exatamente uma ativa; 0 legados ativos')
"
```

**Se falhar:** PARAR e não subir. Corrigir pela UI de admin (Gestão de
Prompts) quando for ativação manual de versão inativa, ou investigar a
divergência de schema antes de qualquer `up`.

### Passo 7 — Subir a imagem nova com a flag desligada

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# COLONOSCOPY_INTAKE_ENABLED continua false (Passo 2c). Recriação forçada
# garante a imagem do Passo 3 — nunca "start" dos containers antigos.
$DPROD up -d --force-recreate web worker pdf_worker
$DPROD ps
```

### Passo 8 — Smoke com a flag desligada

Com `COLONOSCOPY_INTAKE_ENABLED=false`, o sistema já roda o fluxo **EDA**
normalmente (uploads, pipeline v2, fila médica, decisão, agendamento, resposta
NIR). Colonoscopia e combinado são bloqueados **apenas no intake**; casos
existentes seguem processando (nenhum worker/pipeline consulta a flag).

| Cenário | Procedimento | Resultado esperado |
|---|---|---|
| **EDA simples (positivo)** | Upload de um relatório EDA com seleção **EDA** | Caso processa com pipeline v2/prompt neutro; badge EDA; chega à fila médica; decisão e fluxo normais |
| **Colon simples (negativo)** | Upload com seleção **Colonoscopia** | Bloqueado no upload com explicação (flag desligada); nenhum caso criado |
| **Combinado (negativo)** | Upload com seleção **EDA + Colonoscopia** | Bloqueado no upload com explicação; nenhum caso criado |
| **Casos existentes** | Acompanhar casos já em voo (não CLEANED) | Continuam processando normalmente; flag não interrompe pipeline/filas |

> A ativação da flag é o Passo 9, **somente após este smoke passar**. Não
> ativar a flag com smoke vermelho.

### Passo 9 — Ativar a flag somente no serviço web (após smoke)

A variável `COLONOSCOPY_INTAKE_ENABLED` existe somente no serviço `web`
(`docker-compose.prod.yml`); os demais serviços não a recebem nem a consultam
— recriá-los por esse motivo seria inútil. A ativação recria **apenas** o
serviço web.

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# 1. Definir COLONOSCOPY_INTAKE_ENABLED=true no .env de produção.
# 2. Recriar APENAS o serviço que lê a variável:
$DPROD up -d --force-recreate web
```

### Passo 10 — Smoke positivo: Colon, combinado e fluxos críticos

Executar com usuários reais em ambiente de homologação primeiro; em produção,
com casos controlados e acompanhamento do NIR.

| # | Cenário | Procedimento | Resultado esperado |
|---|---|---|---|
| 1 | **EDA simples** | Upload EDA com seleção **EDA** | Fluxo completo até resposta NIR; badge EDA |
| 2 | **Colon simples** | Upload de relatório de colonoscopia com seleção **Colonoscopia** | Processa com prompts neutros; badge Colonoscopia; fluxo idêntico a EDA |
| 3 | **Combinado declarado** | Upload com seleção **EDA + Colonoscopia** | **UM** caso com 2 componentes `CaseProcedure`; badge “EDA + Colonoscopia”; vai à fila médica como um caso |
| 4 | **Upgrade automático** | Declarar **EDA** em PDF com solicitações atuais de EDA + Colonoscopia (evidência forte) | Evento `PROCEDURE_SELECTION_AUTO_UPGRADED` na auditoria; caso segue ao médico **sem ACK do NIR**; declaração original visível no histórico |
| 5 | **Combinado→single** | Declarar **EDA + Colonoscopia** em PDF com apenas EDA na solicitação atual | Retorna ao NIR (revisão manual) para corrigir o conjunto declarado; sem decisão médica |
| 6 | **Decisão parcial** | Médico aprova EDA e nega Colonoscopia | Razão obrigatória por componente; caso segue com o conjunto autorizado resultante |
| 7 | **Inclusão** | Médico inclui um procedimento não detectado | Razão obrigatória na inclusão; **sem reexecução de LLM**; evento auditável |
| 8 | **Agendamento casado** | Ambos os procedimentos aprovados com fluxo de agendamento | CHD vê **“Agendamento casado”** com os dois componentes; confirma **uma única** data/hora/localização (`appointment_at` único) |
| 9 | **Resposta NIR** | Acompanhar o caso até o resultado | Resposta final com **Solicitado**, **Detectado** e **Autorizado** + razões por componente |
| 10 | **Dashboard** | Abrir dashboard gerencial no período | Caso combinado conta **1 caso / 2 componentes**; conversões declarado→detectado→autorizado e agendamentos casados nas métricas |

### Passo 11 — Monitoramento e checks de casos em voo

Consultas e eventos de monitoramento usam **apenas contagens, estados e tipos —
sem expor texto clínico** (nunca selecionar `structured_data`, `extracted_text`,
PDF ou conteúdo de mensagens).

```bash
$DPROD exec -T web uv run python manage.py shell --settings=config.settings.prod -c "
from apps.cases.models import Case, CaseStatus, CaseEvent, CaseProcedure
from apps.cases.procedures import get_declared_procedure_types
from collections import Counter
from django.db.models import Count

print('— Casos em voo (não CLEANED) por conjunto declarado —')
counter = Counter()
for case in Case.objects.exclude(status=CaseStatus.CLEANED).iterator(chunk_size=200):
    counter[len(get_declared_procedure_types(case))] += 1
print('  single:', counter[1], '| combinado (2 componentes):', counter[2])

print('— Volume por tipo (rows CaseProcedure, contagens) —')
print(' ', dict(CaseProcedure.objects.values_list('procedure_type').annotate(n=Count('id'))))

print('— Esperas por etapa (snapshot, contagens) —')
for st in ('WAIT_DOCTOR', 'WAIT_APPT', 'WAIT_R1_CLEANUP_THUMBS', 'FAILED'):
    print(' ', st, Case.objects.filter(status=st).count())

print('— Eventos estruturais (contagens; payload sem texto clínico) —')
for et in ('PROCEDURE_SELECTION_AUTO_UPGRADED', 'CASE_READY_FOR_DOCTOR',
           'CASE_PROCEDURES_DETECTED', 'DOCTOR_ACCEPT', 'APPT_CONFIRMED'):
    print(' ', et, CaseEvent.objects.filter(event_type=et).count())
"
```

**Em voo:** acompanhar por 24h. Alertas: pico de `FAILED` ou
`WAIT_R1_CLEANUP_THUMBS` acima do baseline; agendamentos casados confirmados
devem aparecer como `APPT_CONFIRMED` únicos por caso (um `appointment_at`).

---

## 4. Plano de Rollback

### 4.1 Rollback preferencial (sem tocar no banco — manter a imagem nova)

Usar quando a ativação causar problema operacional, mas sem corrupção de dados:

1. **Desligar a flag** (intake de Colonoscopia e combinado — apenas o serviço web lê a flag):

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# .env de produção: COLONOSCOPY_INTAKE_ENABLED=false
$DPROD up -d --force-recreate web
```

2. **Drenar/encerrar casos em voo** (não `CLEANED`): consultar o Passo 11 e
   deixar os fluxos concluírem normalmente; ou encerrar administrativamente,
   um a um, via dashboard gerencial (manager/admin) com motivo e texto — isso
   remove o caso das filas operacionais e o mantém na auditoria.
3. **MANTER a imagem nova rodando** e o schema pós-0016: com a flag desligada,
   EDA segue normal e Colon/combinado não aceitam novos uploads; casos
   existentes continuam processáveis. Nenhuma migration destrutiva e nenhum
   bridge são necessários neste caminho.
4. **Prompts neutros permanecem ativos enquanto houver casos v2 em voo** —
   nunca desativar um prompt v2 com caso em voo (o processamento contínuo
   depende deles). Desativação só após drenagem/encerramento comprovado.
5. **Nunca apagar** `CaseProcedure`, JSON de artefatos (1.1/2.0) nem o
   histórico de prompts (linhas/versões preservadas para auditoria/rollback).

### 4.2 Bridge para imagem antiga (exceção — fail-fast e binária)

Aplicar **somente** se a operação exigir voltar ao release anterior. A imagem
antiga desconhece `CaseProcedure` e o contrato 2.0, lê/grava `Case.exam_type`
e usa os oito nomes de prompt legados. Pré-condições (todas obrigatórias):

- backup fresco do Passo 1 disponível;
- **writers parados**: `$DPROD stop web worker pdf_worker` **antes** de
  qualquer `ALTER TABLE`;
- **ausência comprovada de casos incompatíveis em voo** (asserts binários
  abaixo): zero casos combinados (2 declarações), zero casos sem declaração e
  zero casos em estados de pipeline.

Cada bloco abaixo é autocontido (`set -euo pipefail` próprio) e NÃO depende de
shell de sessão anterior.

**Bloco A — recusar incompatíveis, criar a coluna ponte e backfilla somente seleção única inequívoca:**

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# A1. RECUSAR combinado: qualquer caso com 2 declarações (eda_colonoscopy)
#     bloqueia a bridge — a imagem antiga não suporta combinação. Drenar antes.
COMBINED=$($DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM (SELECT case_id FROM cases_caseprocedure \
   WHERE declared_by_nir GROUP BY case_id HAVING count(*) > 1) x;")
[ "${COMBINED}" = "0" ] || { \
  echo "ERRO: ${COMBINED} caso(s) combinado(s) em voo — bridge recusa (drenar/encerrar primeiro)"; \
  $DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
    "SELECT case_id FROM cases_caseprocedure WHERE declared_by_nir GROUP BY case_id HAVING count(*) > 1;"; \
  exit 1; }

# A2. RECUSAR ausência de declaração (ambiguidade: nada a backfilla)
ZERO_DECLARED=$($DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM cases_case c WHERE NOT EXISTS \
   (SELECT 1 FROM cases_caseprocedure cp WHERE cp.case_id = c.id AND cp.declared_by_nir);")
[ "${ZERO_DECLARED}" = "0" ] || { echo "ERRO: ${ZERO_DECLARED} caso(s) sem declaração — bridge recusa"; exit 1; }

# A3. RECUSAR casos em pipeline (imagem antiga processaria com contrato legado)
PIPE_STATES=$($DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM cases_case WHERE status IN \
   ('NEW','R1_ACK_PROCESSING','EXTRACTING','LLM_STRUCT','LLM_SUGGEST');")
[ "${PIPE_STATES}" = "0" ] || { echo "ERRO: ${PIPE_STATES} caso(s) em pipeline — drenar antes da bridge"; exit 1; }

# A4. Criar a coluna ponte NULLABLE (fail-closed: nada é preenchido por default)
$DPROD exec -T db psql -U ats_web -d ats_web -v ON_ERROR_STOP=1 -c \
  "ALTER TABLE cases_case ADD COLUMN exam_type varchar(20);"

# A5. Backfill SOMENTE seleção única inequívoca (exatamente 1 row declarada)
$DPROD exec -T db psql -U ats_web -d ats_web -v ON_ERROR_STOP=1 -c \
  "UPDATE cases_case c SET exam_type = cp.procedure_type \
   FROM cases_caseprocedure cp \
   WHERE cp.case_id = c.id AND cp.declared_by_nir \
     AND (SELECT count(*) FROM cases_caseprocedure cp2 WHERE cp2.case_id = c.id) = 1;"

# A6. Assert binário: zero casos sem exam_type após o backfill
NULLS=$($DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM cases_case WHERE exam_type IS NULL;")
[ "${NULLS}" = "0" ] || { echo "ERRO: ${NULLS} caso(s) sem exam_type após backfill — PARAR"; exit 1; }

# A7. NOT NULL + DEFAULT 'eda' (a imagem antiga insere sem o campo)
$DPROD exec -T db psql -U ats_web -d ats_web -v ON_ERROR_STOP=1 -c \
  "ALTER TABLE cases_case ALTER COLUMN exam_type SET NOT NULL, \
   ALTER COLUMN exam_type SET DEFAULT 'eda';"

# A8. Assert binário final do schema ponte
DEFAULT_NOW=$($DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
  "SELECT column_default FROM information_schema.columns \
   WHERE table_name='cases_case' AND column_name='exam_type';")
[ "${DEFAULT_NOW}" = "'eda'::character varying" ] || { \
  echo "ERRO: default inesperado: '${DEFAULT_NOW}' — PARAR; NÃO subir a imagem antiga"; exit 1; }
echo "OK: bridge de schema instalada e verificada (sem conversão ambígua)"
```

**Bloco B — reativar exatamente uma versão compatível por nome legado (writers ainda parados):**

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# B1. Reativar EXATAMENTE uma versão por nome legado (a mais recente disponível
#     de cada um dos oito nomes — preserva o histórico; nunca apaga versões).
#     Os quatro prompts neutros permanecem ativos (imagem antiga não os
#     consulta; casos v2 em voo continuam legíveis para auditoria).
$DPROD run --rm web uv run python manage.py shell --settings=config.settings.prod -c "
from apps.llm.models import PromptTemplate
names = ['llm1_system','llm1_user','llm2_system','llm2_user',
         'colonoscopy_llm1_system','colonoscopy_llm1_user',
         'colonoscopy_llm2_system','colonoscopy_llm2_user']
for name in names:
    latest = PromptTemplate.objects.filter(name=name).order_by('-version').first()
    if latest is None:
        print('FALHA: nome legado sem versão disponível:', name); raise SystemExit(1)
    PromptTemplate.objects.filter(name=name, is_active=True).exclude(pk=latest.pk).update(is_active=False)
    latest.is_active = True
    latest.save(update_fields=['is_active'])
print('OK: uma versão ativa por nome legado')
"

# B2. Assert binário do modo legado: 8 legados ativos, 4 neutros ativos
LEGACY_ACTIVE=$($DPROD run --rm web uv run python manage.py shell --settings=config.settings.prod -c "
from apps.llm.models import PromptTemplate
names = ['llm1_system','llm1_user','llm2_system','llm2_user',
         'colonoscopy_llm1_system','colonoscopy_llm1_user',
         'colonoscopy_llm2_system','colonoscopy_llm2_user']
print(PromptTemplate.objects.filter(name__in=names, is_active=True).count())
")
[ "${LEGACY_ACTIVE}" = "8" ] || { echo "ERRO: ${LEGACY_ACTIVE} legados ativos (esperado 8) — PARAR"; exit 1; }
NEUTRAL_ACTIVE=$($DPROD run --rm web uv run python manage.py shell --settings=config.settings.prod -c "
from apps.llm.models import PromptTemplate
names = ['exam_llm1_system','exam_llm1_user','exam_llm2_system','exam_llm2_user']
print(PromptTemplate.objects.filter(name__in=names, is_active=True).count())
")
[ "${NEUTRAL_ACTIVE}" = "4" ] || { echo "ERRO: ${NEUTRAL_ACTIVE} neutros ativos (esperado 4) — PARAR"; exit 1; }
echo "OK: modo legado verificado — 8 legados e 4 neutros com uma versão ativa cada"
```

**Bloco C — subir a imagem antiga somente após os asserts binários:**

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# C1. Imagem ANTIGA (tag do release anterior, já buildada/puxada com o registry)
$DPROD up -d --force-recreate web worker pdf_worker
# C2. Validar um upload EDA em homologação antes de liberar; a flag permanece
#     desligada (a imagem antiga só aceita EDA no intake).
```

> **Se qualquer check falhar:** os writers já estão parados — **manter parados**
> e **não continuar**; **não subir a imagem antiga**. Investigar o estado
> (consultas do Passo 6/Bloco A), restaurar a imagem nova se necessário e só
> retomar após nova verificação. Nenhum caminho da bridge converte combinado
> silenciosamente: `eda_colonoscopy` é sempre recusado.

### 4.3 Forward: retorno seguro à imagem nova (serializado)

Sequência única e executável, na mesma janela de manutenção. A imagem nova é
construída **antes** do downtime; os writers antigos são parados **antes** de
qualquer mudança; o modo neutro é restabelecido e a ponte é removida **antes**
de subir os writers novos. Cada bloco tem `set -euo pipefail` próprio.

```bash
set -euo pipefail
PROJECT_DIR=/opt/ats-web/app
DPROD="docker compose --project-directory ${PROJECT_DIR} \
  -f ${PROJECT_DIR}/docker-compose.yml -f ${PROJECT_DIR}/docker-compose.prod.yml"

# 1. Build/pull da imagem NOVA antes do downtime (janela de manutenção reduzida)
$DPROD build --pull web worker pdf_worker

# 2. Parar os writers da imagem antiga (dependem da ponte exam_type)
$DPROD stop web worker pdf_worker

# 3. Modo neutro: seed idempotente garante exatamente uma versão ativa por
#    nome neutro e DESATIVA versões ativas dos nomes legados
$DPROD run --rm web uv run python manage.py seed_prompts --settings=config.settings.prod

# 4. Assert binário de prompts: 4 neutros ativos, 0 legados ativos
LEGACY_ACTIVE=$($DPROD run --rm web uv run python manage.py shell --settings=config.settings.prod -c "
from apps.llm.models import PromptTemplate
names = ['llm1_system','llm1_user','llm2_system','llm2_user',
         'colonoscopy_llm1_system','colonoscopy_llm1_user',
         'colonoscopy_llm2_system','colonoscopy_llm2_user']
print(PromptTemplate.objects.filter(name__in=names, is_active=True).count())
")
[ "${LEGACY_ACTIVE}" = "0" ] || { echo "ERRO: ${LEGACY_ACTIVE} legados ainda ativos — PARAR"; exit 1; }
NEUTRAL_ACTIVE=$($DPROD run --rm web uv run python manage.py shell --settings=config.settings.prod -c "
from apps.llm.models import PromptTemplate
names = ['exam_llm1_system','exam_llm1_user','exam_llm2_system','exam_llm2_user']
print(PromptTemplate.objects.filter(name__in=names, is_active=True).count())
")
[ "${NEUTRAL_ACTIVE}" = "4" ] || { echo "ERRO: ${NEUTRAL_ACTIVE} neutros ativos (esperado 4) — PARAR"; exit 1; }

# 5. Migrations (no-op se já aplicadas; garante estado 0015/0016 consistente)
$DPROD run --rm web uv run python manage.py migrate --settings=config.settings.prod

# 6. Casos criados pela imagem antiga (sem rows CaseProcedure) ganham a row
#    declarada a partir da ponte exam_type — antes de remover a coluna
$DPROD exec -T db psql -U ats_web -d ats_web -v ON_ERROR_STOP=1 -c \
  "INSERT INTO cases_caseprocedure (case_id, procedure_type, declared_by_nir) \
   SELECT c.id, c.exam_type, true FROM cases_case c \
   WHERE NOT EXISTS (SELECT 1 FROM cases_caseprocedure cp WHERE cp.case_id = c.id);"

# 7. Remover a ponte (coluna criada pela bridge 4.2)
$DPROD exec -T db psql -U ats_web -d ats_web -v ON_ERROR_STOP=1 -c \
  "ALTER TABLE cases_case DROP COLUMN IF EXISTS exam_type;"

# 8. Assert binário de schema: coluna ausente; invariante 1–2 rows preservado
LEGACY_COLUMN=$($DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM information_schema.columns \
   WHERE table_name='cases_case' AND column_name='exam_type';")
[ "${LEGACY_COLUMN}" = "0" ] || { echo "ERRO: coluna exam_type ainda presente — PARAR"; exit 1; }
ZERO_ROWS=$($DPROD exec -T db psql -U ats_web -d ats_web -At -v ON_ERROR_STOP=1 -c \
  "SELECT count(*) FROM cases_case c WHERE NOT EXISTS \
   (SELECT 1 FROM cases_caseprocedure cp WHERE cp.case_id = c.id);")
[ "${ZERO_ROWS}" = "0" ] || { echo "ERRO: caso(s) sem rows CaseProcedure — PARAR"; exit 1; }

# 9. Só agora subir a imagem NOVA
$DPROD up -d --force-recreate web worker pdf_worker
```

**Se qualquer check falhar:** os writers já estão parados — **manter parados**,
**não subir a imagem nova** e investigar (consultas do Passo 6). Restaurar a
ponte (Bloco A) se necessário e só retomar após nova verificação.

> A coluna ponte, as rows `CaseProcedure`, o JSON e o histórico de prompts
> permanecem preservados em todos os caminhos — **rollback destrutivo não é o
> padrão**.

---

## 5. Pós-deploy (fechamento do change)

- Manter a flag documentada no `.env` privado de produção (default `false`);
  `.env.example` já contém `COLONOSCOPY_INTAKE_ENABLED=false` como default
  seguro; a variável é propagada apenas para `web`.
- Manter `PROJECT_CONTEXT.md` e o manual de usuário alinhados ao
  comportamento real (seleção EDA/Colonoscopia/EDA + Colonoscopia, upgrade
  automático, decisão por componente, agendamento casado, resposta final com
  solicitado/detectado/autorizado; flag não é assunto de usuário comum).
- Monitorar por 24h conforme Passo 11 (contagens/eventos, sem texto clínico).
- O change **não** arquiva como concluído enquanto houver item do DoD global
  não comprovado em `openspec/changes/support-combined-eda-colonoscopy-workflow/tasks.md`.

## 6. Notas operacionais

- **CPRE não é escopo** deste change; não prometer suporte a CPRE em
  documentos/smoke tests.
- **Flag desligada bloqueia novos uploads, nunca processamento**: a flag é
  lida somente no intake (serviço `web`); casos existentes sempre concluem.
- **Quatro prompts neutros são canônicos**; os oito nomes legados permanecem
  apenas como histórico inativo. Prompts neutros não podem ser desativados
  enquanto houver casos v2 em voo (não `CLEANED`).
- **Decisão por componente**: negativa e inclusão exigem razão por componente;
  inclusão não reexecuta LLM.
- **Bridge é exceção**: o rollback preferencial mantém a imagem nova e o
  schema pós-0016; a imagem antiga exige bridge binária/fail-fast (4.2) e
  forward serializado (4.3), sempre com writers parados.
- **Monitoramento sem expor texto clínico**: apenas contagens, estados e tipos
  de evento (Passo 11).
