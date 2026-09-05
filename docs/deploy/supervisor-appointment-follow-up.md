# Runbook de Deploy — `supervisor-appointment-follow-up`

**Change:** `supervisor-appointment-follow-up`
**Commits incluídos:** `0d004b6` (domínio), `0a373c2`/`ac8111b` (ajustes de review),
`8ece663` (aba de listagem), `bc07f99` (formulário), `bce62b3` (fix híbrido)
**Branch:** `main`
**Data de criação:** 2026-09-05
**Classificação de risco:** 🟢 Baixo

---

## Quick reference

Cópia de mão — para uso **após** leitura completa do runbook e após o
Passo 1 (backup) já estar em `/archive/backups/`. Executar como `apps`,
no diretório de instalação.

```bash
DPROD="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

# 1. (pré) Backup já feito e movido para /archive/backups/ pelo admin.

# 2. Atualizar código
git fetch origin && git checkout main && git pull origin main
git merge-base --is-ancestor bce62b3 HEAD && echo "change presente"   # bce62b3 (ou descendente) no histórico

# 3. Build das novas imagens
$DPROD build --pull web worker pdf_worker

# 4. Aplicar migration (app no ar, zero downtime)
#    Saída esperada: Applying cases.0017_casefollowup_procedurefollowup_and_more... OK
#    Se erro: NÃO continuar — ir para a Seção 4 (Rollback).
$DPROD run --rm web uv run python manage.py migrate --settings=config.settings.prod

# 5. Subir containers com a imagem nova
$DPROD up -d

# 6. Verificação imediata
$DPROD ps                                                   # todos "running"
$DPROD logs --tail=30 web worker pdf_worker                 # sem traceback

curl -sS -o /dev/null -w "%{http_code}\n" https://app.example.com/   # 200 ou 302

$DPROD exec -T web uv run python manage.py showmigrations cases \
  --settings=config.settings.prod | tail -5                 # [X] 0017_casefollowup_procedurefollowup_and_more
```

> Passos 7 (smoke funcional específico da feature) e 8 (monitoramento
> 24–48h) seguem abaixo em formato completo.

---

## 1. Análise de risco

| Aspecto | Avaliação |
|---|---|
| **Migration** | `apps/cases/migrations/0017_casefollowup_procedurefollowup_and_more.py` — **aditiva, não-bloqueante**. Cria 2 tabelas novas (`CaseFollowUp`, `ProcedureFollowUp`) com 2 unique + 6 check constraints. Sem data migration, sem rename, sem drop de tabela/coluna existente. Roda em milissegundos, sem lock relevante. |
| **Compatibilidade** | Código velho ignora as tabelas novas → **zero downtime possível**. A migration pode rodar antes do restart. |
| **Mudanças de FSM / pipeline / schema existente** | Nenhuma. FSM intocada (nenhum estado/transição alterado). Filas/pipeline inalterados: follow-up é registro síncrono, sem tarefa assíncrona nova e sem schedule novo no django-q2. |
| **Dados sensíveis** | Nenhum dado existente em produção é migrado/tocado. Volume de mídia (`media_prod`) não é afetado (a feature não grava arquivos). |
| **Variáveis de ambiente novas** | Nenhuma (confirmado em `docker-compose.prod.yml`). |
| **Classificação** | 🟢 **Baixo risco** (com plano de rollback anyway, conforme `PROJECT_CONTEXT.md`). |

### O que o change entrega

- **Aba "Follow-up"** na área do dashboard (rota `/dashboard/follow-ups/`),
  restrita a `manager`/`admin`, listando os casos elegíveis de **hoje e
  ontem** (dias locais, timezone `America/Bahia`): agendamentos confirmados
  e vindas imediatas autorizadas, agrupados por data ascendente e, dentro da
  data, por nome do paciente/horário. Suporta `?date=YYYY-MM-DD` e `?q=`
  (busca por ocorrência/nome em qualquer data, limite 50). Cada card mostra
  o badge "Follow-up pendente" ou "Follow-up registrado" (vN · data · autor)
  e linka ao formulário do caso.
- **Formulário por procedimento** (`/dashboard/follow-ups/cases/<uuid>/`):
  desfecho realizado/não realizado (não realizado exige causa estruturada:
  absenteísmo; falta de recursos no dia com submotivo; outras causas com
  texto) + internação do paciente. Somente casos elegíveis expõem o
  formulário (caso contrário, 404 com mensagem).
- **Registro versionado append-only**: cada gravação cria nova versão
  (`CaseFollowUp` + `ProcedureFollowUp` por procedimento, autor e instante
  por versão) com espelho em `CaseEvent` — `FOLLOWUP_RECORDED` na versão 1,
  `FOLLOWUP_UPDATED` nas seguintes — visível na trilha de auditoria do caso
  (labels PT-BR "Follow-up registrado"/"Follow-up atualizado"). Não altera a
  FSM do caso, não abre intercorrência e não reagenda.
- Detalhes de uso no manual oficial: `docs/manual/manual-usuarios.md` §6.1.

---

## 2. Pré-requisitos (no servidor de produção)

```bash
cd /caminho/do/ats-web
git status           # deve estar limpo
git log --oneline -1 # anotar o ponto de partida (para rollback)
```

Confirmar que as variáveis de ambiente obrigatórias já estão
configuradas no host:

- `POSTGRES_PASSWORD`, `DJANGO_SECRET_KEY`, `OPENAI_API_KEY`
- `CSRF_TRUSTED_ORIGINS`, `ALLOWED_HOSTS`, `INTRANET_IP_RANGE`
- Demais vars esperadas por `docker-compose.prod.yml`

> Este change **não adiciona** variável de ambiente nova.

Confirmar a partição de backups (leitura — qualquer usuário vê o uso):

```bash
df -h /archive/backups                 # uso < 80%, espaço livre suficiente
```

### Modelo de dois atores (segurança)

O usuário `apps` (que roda o Docker rootless e o deploy) é isolado e
**só pode escrever** no diretório de instalação e no seu `$HOME`. Ele
**não escreve** em `/archive/backups` (pertencente a `root`). Por isso,
todo I/O contra `/archive/backups` segue o padrão:

1. **`apps`** extrai os dados para um *staging* temporário (apps-owned).
2. Um **usuário administrativo com `sudo`** move os arquivos do staging
   para `/archive/backups/` (e, no rollback, o caminho inverso).

O *staging* usado no runbook é um diretório no `$HOME` do `apps`:

```bash
# Como apps:
export STAGING_DIR="${HOME}/backup-staging"   # ex.: /home/apps/backup-staging
mkdir -p "$STAGING_DIR"
```

> Qualquer caminho apps-owned serve; o `$HOME` é o default por ser
> persistente e fora de `/tmp` (que é limpo no reboot).

---

## 3. Passos de deploy

Defina o alias de Compose usado em todo o runbook:

```bash
DPROD="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
```

### Passo 1 — Backup (obrigatório)

O backup segue o modelo de dois atores: `apps` extrai para o staging,
um admin com `sudo` move para `/archive/backups/`.

O follow-up grava apenas no PostgreSQL (não toca o volume de mídia), então
o dump do banco é o snapshot obrigatório; o snapshot do volume `media_prod`
não é necessário para este change.

**Como `apps` (extração para staging):**

```bash
DPROD="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
export STAGING_DIR="${HOME}/backup-staging"
mkdir -p "$STAGING_DIR"
TS=$(date +%Y%m%d-%H%M)

# 1a. Extrair dump do Postgres para o staging
$DPROD exec -T db pg_dump -U ats_web -d ats_web -Fc \
  > "$STAGING_DIR/pre-follow-up-${TS}.dump"

# Confirmar que o arquivo não está vazio
ls -lh "$STAGING_DIR/pre-follow-up-${TS}.dump"

echo "TS=$TS"  # anote este timestamp — usado pelo admin e no rollback
```

**Como `admin` (move para `/archive/backups/`):**

Substitua `<TS>` pelo timestamp anotado acima.

```bash
STAGING_DIR="/home/apps/backup-staging"   # ajustar ao HOME do apps
ARCHIVE="/archive/backups"
TS=<TS>

sudo mv "$STAGING_DIR/pre-follow-up-${TS}.dump" "$ARCHIVE/"
sudo chown root:root "$ARCHIVE/pre-follow-up-${TS}.dump"
sudo chmod 640 "$ARCHIVE/pre-follow-up-${TS}.dump"

# Confirmar
sudo ls -lh "$ARCHIVE/pre-follow-up-${TS}.dump"
```

> Anote o `TS` — ele é referenciado no **Plano de Rollback**.

### Passo 2 — Atualizar código

```bash
git fetch origin
git checkout main
git pull origin main
git log --oneline -3
# confirmar que o change está presente no histórico (bce62b3 ou descendente):
git merge-base --is-ancestor bce62b3 HEAD && echo "change presente"
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
Applying cases.0017_casefollowup_procedurefollowup_and_more... OK
```

> Se aparecer qualquer erro aqui: **NÃO prosseguir**. Restaurar o backup
> do Passo 1 (ver Seção 4) e parar.

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
curl -sS -o /dev/null -w "%{http_code}\n" https://app.example.com/
#    → esperar 200 ou 302 (login redirect)

# 6c. Checar migration aplicada
$DPROD exec -T web uv run python manage.py showmigrations cases \
  --settings=config.settings.prod | tail -5
#    → deve mostrar "[X] 0017_casefollowup_procedurefollowup_and_more" por último
```

### Passo 7 — Validação funcional (smoke específico da feature)

No app, em sessão real da intranet/hospital. Guarde o `case_id` (uuid) do
caso usado — ele é referenciado na verificação de banco abaixo.

1. **Acesso permitido (manager/admin):** logar com perfil ativo
   **Supervisor** (`manager`) ou **Administrador** (`admin`) → acessar o
   Dashboard → a aba **Follow-up** aparece no menu. Abrir
   `/dashboard/follow-ups/`: a lista carrega os casos elegíveis de **hoje e
   ontem**, cada card com badge "Follow-up pendente" ou "Follow-up
   registrado". Testar os filtros `?date=YYYY-MM-DD` e a busca por
   ocorrência/nome (qualquer data).

2. **Acesso negado (demais papéis):** com papéis ativos `nir`, `doctor` e
   `scheduler` (um por vez), abrir `/dashboard/follow-ups/` e o formulário
   `/dashboard/follow-ups/cases/<uuid>/` de um caso elegível → **redirect
   com mensagem de erro** ("Você não tem permissão para acessar esta
   página.") e nenhum dado de follow-up é exposto.

3. **Registro (versão 1):** abrir um caso elegível da lista de hoje (o dia
   do exame já passou e o desfecho é conhecido), escolher o desfecho real de
   cada procedimento (realizado, ou não realizado com causa/submotivo/texto)
   e marcar/desmarcar internação conforme o caso → salvar. O sistema
   redireciona para a lista com a mensagem de sucesso "Follow-up registrado
   (versão 1) para o caso ...". O card do caso passa a exibir o badge
   "Follow-up registrado" (v1 · data · autor) e a trilha de auditoria do
   caso ganha o evento `FOLLOWUP_RECORDED` (label PT-BR "Follow-up
   registrado"). O status do caso permanece inalterado.

4. **Atualização (versão 2):** reabrir o formulário do **mesmo caso**,
   alterar o desfecho de um procedimento ou o flag de internação e salvar →
   mensagem "Follow-up registrado (versão 2) ...". A listagem mostra v2; o
   histórico do formulário exibe as versões 1 e 2 com autores/instantes
   preservados; a trilha de auditoria ganha `FOLLOWUP_UPDATED` (label PT-BR
   "Follow-up atualizado") e a versão 1 permanece imutável (append-only).

5. **Confirmação no banco:** substitua `<CASO_UUID>` pelo `case_id` do caso
   usado nos passos 3–4:

```bash
CASO_UUID=<CASO_UUID>
$DPROD exec -T web uv run python manage.py shell --settings=config.settings.prod -c "
from apps.cases.models import Case, CaseEvent
c = Case.objects.get(case_id='$CASO_UUID')
print('versoes:', [(v.version, v.patient_admitted) for v in c.follow_ups.all()])
print('eventos_followup:', list(CaseEvent.objects.filter(case=c, event_type__startswith='FOLLOWUP_').values_list('event_type', 'payload__version')))
"
#    → esperado: versoes com (1, ...) e (2, ...)
#      eventos_followup com ('FOLLOWUP_RECORDED', 1) e ('FOLLOWUP_UPDATED', 2)
```

6. **Filas/worker inalterados:** o registro/atualização **não** enfileira
   tarefa nova. Confirmar que `worker` e `pdf_worker` seguem apenas o
   processamento normal:

```bash
$DPROD logs --since=10m worker pdf_worker 2>&1 | tail -20
#    → sem traceback; nenhum job novo relacionado a follow-up aparece
```

### Passo 8 — Monitoramento (próximas 24–48h)

```bash
# Erros 5xx / exceções
$DPROD logs --since=24h web 2>&1 \
  | grep -iE "error|traceback|exception" | grep -vi "warn"

# Workers saudáveis (processando tarefas)
$DPROD logs --since=1h worker pdf_worker 2>&1 | tail -20
```

Observar também no app, com os supervisores usando a aba Follow-up, se
`CaseEvent FOLLOWUP_*` aparece corretamente na auditoria dos casos
registrados (ver Seção 5).

---

## 4. Plano de Rollback

Caso ocorra regressão crítica, existem três níveis, do menos invasivo
ao mais invasivo.

### 4.1 Rollback "suave" (recomendado, sem mexer no DB)

As tabelas `CaseFollowUp`/`ProcedureFollowUp` são novas e independentes —
o código anterior funciona perfeitamente com elas presentes como tabelas
inertes. Basta voltar o código e rebuild:

```bash
git checkout v0.5.2   # release estável anterior (ou <commit-anterior-ao-change>)
$DPROD build web worker pdf_worker
$DPROD up -d
```

**Não é necessário** reverter a migration. As tabelas ficam inertes e os
registros de follow-up gravados (append-only) **permanecem no banco**,
reaparecendo na UI quando a série `v0.6.0` for reimplantada. Não reverter
com o código antigo no ar: `v0.5.2` não conhece a migration `0017` e não
pode revertê-la (ver 4.2 para a ordem correta da reversão).

### 4.2 Rollback completo (reverter a migration)

Executar **antes** do checkout do código antigo — o comando precisa do
código novo no ar para enxergar a migration `0017` e revertê-la:

```bash
# (com o código novo ainda no ar)
$DPROD run --rm web uv run python manage.py migrate cases 0016 \
  --settings=config.settings.prod

# Voltar código e rebuild
git checkout v0.5.2
$DPROD build web worker pdf_worker
$DPROD up -d
```

> ⚠️ **Ressalva:** reverter `0017` **dropa as tabelas** `CaseFollowUp`/
> `ProcedureFollowUp`, perdendo permanentemente **apenas** as linhas
> relacionais de follow-up (versões e desfechos por procedimento). Os
> eventos de auditoria `CaseEvent` `FOLLOWUP_*` (`FOLLOWUP_RECORDED`/
> `FOLLOWUP_UPDATED`, com payload completo do snapshot) **permanecem
> intactos**: a tabela `CaseEvent` é independente da migration
> (append-only), então o histórico do que foi registrado continua
> consultável na trilha do caso mesmo após o rollback. Usar **apenas**
> quando não houver dados relacionais a preservar (ex.: rollback imediato
> antes de uso intenso pelos supervisores). Havendo registros, preferir o
> rollback suave (4.1).

### 4.3 Rollback de última instância (restaurar backup)

Usar o snapshot criado no Passo 1. Substitua `<TS>` pelo timestamp
anotado. Segue o modelo de dois atores (inverso do backup): o admin
copia de `/archive/backups/` para o staging e devolve a propriedade ao
`apps`, que então restaura.

**Como `admin` (copia do archive para o staging):**

```bash
STAGING_DIR="/home/apps/backup-staging"   # ajustar ao HOME do apps
ARCHIVE="/archive/backups"
TS=<TS>

sudo cp "$ARCHIVE/pre-follow-up-${TS}.dump" "$STAGING_DIR/"
sudo chown apps:apps "$STAGING_DIR/pre-follow-up-${TS}.dump"
```

> `apps:apps` assume user:group primário do `apps`; ajuste se o grupo
> for diferente.

**Como `apps` (restaura a partir do staging):**

```bash
DPROD="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
STAGING_DIR="${HOME}/backup-staging"
TS=<TS>

# Restaurar dump do Postgres
$DPROD exec -T db pg_restore -U ats_web -d ats_web -c -1 \
  < "$STAGING_DIR/pre-follow-up-${TS}.dump"

# Voltar código
git checkout v0.5.2
$DPROD build web worker pdf_worker
$DPROD up -d
```

---

## 5. Pós-deploy (fechamento do change)

Após o deploy verde e a janela de observação de 24–48h:

1. Confirmar no app que os `CaseEvent FOLLOWUP_*` dos registros feitos
   pelos supervisores aparecem na trilha de auditoria dos casos e que não
   houve `IntegrityError`/exceções nos logs (o service valida antes de
   gravar; nenhum erro é esperado).
2. Coletar o feedback dos supervisores sobre o formulário (causas/
   submotivos de não realização) antes de congelar o estável `v0.6.0`.
3. Publicado o estável, registrar o deploy na convenção de releases
   (`docs/releases/`), conforme `docs/releases/README.md`.

---

## 6. Notas operacionais

- **Registro puro ≠ intercorrência**: follow-up apenas registra o desfecho.
  Exame não realizado que precise de nova data segue o fluxo de
  reagendamento do CHD; mudança após o aceite segue a intercorrência
  pós-aceitação do NIR (manual §6.1). A FSM do caso nunca muda por causa do
  follow-up.
- **Sem janela obrigatória**: pela natureza aditiva da migration, o deploy
  pode ser feito a qualquer hora. Recomenda-se horário de baixo tráfego
  apenas como cuidado padrão.
- **web / worker / pdf_worker**: os três usam `build:` (código copiado no
  build), então o `up -d` do Passo 5 os recria com a imagem nova. O
  restart dos workers faz parte do deploy da rc (demais mudanças da série
  `v0.6.0` tocam pipeline/lease); o follow-up em si não enfileira tarefa.
- **Staging antes de produção**: a rc é validável em staging com a imagem
  OCI do GHCR `ghcr.io/carlosapgomes/ats-web:0.6.0-rc.1`; produção compila
  do fonte (compose `build:`). No staging, rodar o mesmo smoke do Passo 7.
- **Topologia de banco**: este runbook assume o compose standalone
  (`docker-compose.prod.yml`, PostgreSQL no mesmo stack). Para a topologia
  com PostgreSQL compartilhado (imagem imutável via `ATS_WEB_IMAGE`, serviço
  `migrate` por profile), seguir `shared-postgres-production.md`.
