# Runbook de Deploy — `introduce-colonoscopy-exam-workflow`

**Change:** `introduce-colonoscopy-exam-workflow` (8 slices, do Slice 001 ao Slice 008)
**Branch:** `feature/colonoscopy-exam-workflow` → `main`
**Classificação de risco:** 🟡 Médio (ativação de novo tipo de exame em produção)

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

# 3. Build das novas imagens
$DPROD build --pull web worker pdf_worker

# 4. Aplicar migrations (app no ar, zero downtime)
#    Saída esperada: Applying cases.0014_case_exam_type... OK
#    A migration faz AddField + backfill EDA idempotente (sem reprocessar).
$DPROD run --rm web uv run python manage.py migrate --settings=config.settings.prod

# 5. Seed dos prompts (idempotente) — cria/ativa os 8 nomes canônicos,
#    incluindo os 4 prompts de colonoscopia
$DPROD run --rm web uv run python manage.py seed_prompts --settings=config.settings.prod

# 6. Subir containers com a imagem nova
$DPROD up -d

# 7. Verificação imediata
$DPROD ps                                                   # todos "running"
$DPROD logs --tail=30 web worker pdf_worker                 # sem traceback
curl -sS -o /dev/null -w "%{http_code}\n" https://app.example.com/   # 200 ou 302

# 8. Flag de intake permanece DESLIGADA por padrão (ver Seção 3.4 para ativar)
```

> Passos 9 (validação funcional) e 10 (monitoramento 24h) seguem abaixo em
> formato completo. A ativação da flag é um passo **explícito e separado**
> (Seção 3.4) — o deploy do código não ativa colonoscopia sozinho.

---

## 1. Análise de risco

| Aspecto | Avaliação |
|---|---|
| **Migration** | `apps/cases/migrations/0014_case_exam_type.py` — **aditiva, não-bloqueante**. `AddField` com default histórico + `RunPython` (elidable) que força `exam_type='eda'` em todas as linhas existentes, **sem ler PDF/JSON/texto** e **sem reprocessar/alterar FSM, decisão, agenda ou eventos**. Índice composto `(status, exam_type)` adicionado. |
| **Compatibilidade** | Código velho ignora o novo campo → **zero downtime possível**. A migration pode rodar antes do restart. |
| **Mudanças de FSM / pipeline / schema existente** | Nenhum estado novo; 17 estados FSM preservados. Contrato LLM1 evolui de forma aditiva (`medications_described[]` e `exam_type=colonoscopy` aceito). |
| **Dados sensíveis** | Backfill não lê conteúdo clínico. Nenhum PDF/JSON/texto é migrado. Volume de mídia não é afetado. |
| **Variáveis de ambiente novas** | `COLONOSCOPY_INTAKE_ENABLED` (default `false`) — já documentada em `.env.example` e propagada para web/worker em `docker-compose.dev.yml`/`docker-compose.prod.yml`. |
| **Prompts** | `seed_prompts` cria os 8 nomes canônicos (4 EDA + 4 colonoscopia). Nomes EDA não são substituídos. |
| **Rollback** | Não destrutivo: desligar flag, drenar/encerrar casos em voo, reverter imagem, manter coluna/índice/prompts. Detalhes na Seção 5. |

### O que o change entrega

- `Case.exam_type` distingue **EDA** e **Colonoscopia**; upload exige escolha explícita e lote homogêneo.
- Pipeline LLM processa colonoscopia com prompts/pré-perfis próprios; política clínica comum sem exceção de corpo estranho para colonoscopia.
- Filtros por tipo em médico (Pendentes/Decididos Hoje), CHD (Pendentes/Processados/Histórico), NIR (operacionais/encerrados) e dashboard (tabela gerencial).
- Dashboard: métricas consolidadas preservadas + **breakdown EDA/Colonoscopia** por período.
- Alertas medicamentosos informativos (anticoagulante/antiagregante) no relatório médico — **sem** alterar decisão/sugestão e **sem** orientação de suspensão.
- Correção de tipo pelo NIR antes da fila médica / em revisão manual, com reprocessamento auditável do mesmo caso.

---

## 2. Pré-requisitos (no servidor de produção)

- Acesso de shell ao servidor de produção como `apps` (conforme operação atual).
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml` funcional.
- Acesso ao registry da imagem de release (GHCR) com a tag nova.
- Backup do Postgres e do volume de mídia **obrigatório** antes de qualquer passo (Seção 3, Passo 1).
- Comunicar aos times NIR/médico/CHD que o novo tipo de exame será ativado (a flag é ligada em momento explícito, ver Seção 3.4).

---

## 3. Passos de deploy

### Passo 1 — Backup (obrigatório)

```bash
mkdir -p /archive/backups/2026-XXX-colonoscopy && cd /archive/backups/2026-XXX-colonoscopy

# Dump do Postgres (produção)
$DPROD exec -T db pg_dump -U ats_web ats_web | gzip > ats_web_pre_colonoscopy_$(date +%Y%m%d_%H%M).sql.gz

# Snapshot do volume de mídia (PDFs/anexos)
$DPROD run --rm -v ats_web_media:/media:ro -v $(pwd):/backup alpine \
  tar czf /backup/media_pre_colonoscopy_$(date +%Y%m%d_%H%M).tar.gz -C /media .

# Confirmar que os arquivos não estão vazios
ls -lh ats_web_pre_colonoscopy_*.sql.gz media_pre_colonoscopy_*.tar.gz
```

> **Precheck:** antes do deploy, registrar o baseline de casos em voo
> (ver Seção 4.1) para comparar depois da ativação.

### Passo 2 — Atualizar código

```bash
cd <diretório de instalação>
git fetch origin && git checkout main && git pull origin main
git log --oneline -5        # confirmar os commits do change no topo
```

### Passo 3 — Build das novas imagens

```bash
$DPROD build --pull web worker pdf_worker
```

### Passo 4 — Aplicar a migration (app ainda no ar)

```bash
# Saída esperada: Applying cases.0014_case_exam_type... OK
$DPROD run --rm web uv run python manage.py migrate --settings=config.settings.prod
```

A migration `cases.0014_case_exam_type`:

1. adiciona `Case.exam_type` com default histórico `eda`;
2. **backfill idempotente** de todas as linhas existentes para `eda` (sem ler
   PDF/JSON/texto, sem reprocessar, sem criar eventos);
3. cria o índice composto `(status, exam_type)`.

Se erro: **NÃO continuar** — ir para a Seção 5 (Rollback).

### Passo 5 — Seed dos prompts (idempotente)

```bash
$DPROD run --rm web uv run python manage.py seed_prompts --settings=config.settings.prod
```

Cria (se ainda não existirem) versões ativas dos 8 nomes canônicos:

```text
llm1_system / llm1_user / llm2_system / llm2_user            (EDA — legados)
colonoscopy_llm1_system / colonoscopy_llm1_user
colonoscopy_llm2_system / colonoscopy_llm2_user              (Colonoscopia)
```

- Idempotente: não sobrescreve versões já ativas.
- Nomes EDA **não são substituídos** pelos de colonoscopia.
- Depois do seed, os prompts de colonoscopia são administráveis na UI de
  admin (Gestão de Prompts), com versionamento (1 ativo por nome).

### Passo 6 — Subir os containers com a imagem nova

```bash
$DPROD up -d
```

### Passo 7 — Verificação imediata

```bash
$DPROD ps                                                   # todos "running"
$DPROD logs --tail=30 web worker pdf_worker                 # sem traceback
curl -sS -o /dev/null -w "%{http_code}\n" https://app.example.com/   # 200 ou 302

# Migration aplicada?
$DPROD exec -T web uv run python manage.py showmigrations cases \
  --settings=config.settings.prod | tail -8                 # [X] 0014_case_exam_type

# Prompts colonoscopia presentes?
$DPROD exec -T web uv run python manage.py shell \
  --settings=config.settings.prod -c \
  "from apps.llm.models import PromptTemplate; \
print(list(PromptTemplate.objects.filter(name__startswith='colonoscopy_').values_list('name','is_active')))"
```

### Passo 8 — Flag de intake (default desligada)

O código já funciona com a flag **desligada** (`false`): o sistema roda
normalmente para EDA e casos colonoscopia **já existentes** continuam
processáveis. **Novos uploads** de colonoscopia são bloqueados até a flag ser
ligada.

**Como ativar globalmente (rollout):**

1. Definir `COLONOSCOPY_INTAKE_ENABLED=true` no ambiente de produção
   (`.env` privado ou orquestrador);
2. recriar os serviços que leem a variável:

```bash
$DPROD up -d --force-recreate web worker
```

> A flag é consultada **apenas no intake** (validação de novos uploads).
> Workers/pipeline **não** consultam a flag para bloquear casos existentes
> (Seção 4.3). Portanto, recriar o worker é uma boa prática de propagação,
> mas não é o mecanismo que bloqueia/libera casos em voo.

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
for t, label in Case.objects.order_by().values_list('exam_type', 'exam_type').distinct():
    print(label, Case.objects.filter(exam_type=t).count())

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
  apenas nos estados permitidos (antes de `WAIT_DOCTOR` ou revisão manual).
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
> reenvios corrigidos). Casos colonoscopia já criados continuam no pipeline,
> nas filas e na decisão mesmo com a flag desligada — por design (D2/D16).

---

## 5. Plano de Rollback

### 5.1 Rollback "suave" (recomendado — sem tocar no banco)

Usar quando a ativação causar problema operacional, mas sem corrupção de dados:

1. **Desligar o intake de colonoscopia:**

```bash
# .env de produção: COLONOSCOPY_INTAKE_ENABLED=false
$DPROD up -d --force-recreate web worker
```

2. **Drenar/encerrar casos colonoscopia em voo** (não `CLEANED`):

   - consultar os casos (Seção 4.1);
   - deixar que os fluxos concluam normalmente; ou
   - encerrar administrativamente, um a um, via dashboard gerencial
     (manager/admin) com motivo e texto — isso remove o caso das filas
     operacionais e o mantém na auditoria.

3. **Reverter a imagem** somente quando **não houver casos colonoscopia
   incompatíveis em voo** (nenhum caso colonoscopia com status que o código
   antigo não consiga ler). A coluna `exam_type`, o índice e os prompts
   permanecem no banco — **rollback destrutivo não é o padrão**.

### 5.2 Rollback de contrato medicamentoso (prompts EDA)

Se o rollback exigir reverter o contrato LLM1 para **sem** a coleção de
medicamentos (imagem antiga), reativar a versão **anterior** dos prompts EDA
canônicos (`llm1_system`/`llm1_user`/`llm2_system`/`llm2_user`):

- na UI de admin (Gestão de Prompts), localizar a versão anterior de cada
  nome, **desativar** a versão atual e **ativar** a anterior (1 ativo por nome);
- só então reverter o código para a imagem antiga;
- validar um upload EDA em homologação antes de liberar.

> Os prompts de colonoscopia podem permanecer inativos sem impacto enquanto
> a flag estiver desligada.

### 5.3 Rollback completo (última instância — restaurar backup)

Só se a migration tiver causado problema real de dados (não esperado: a
migration é aditiva e o backfill não lê artefatos):

1. restaurar o dump do Postgres (Passo 1) e a mídia (se necessário);
2. voltar o código para o commit anterior e rebuild;
3. `$DPROD up -d` e validar.

---

## 6. Pós-deploy (fechamento do change)

- Manter a flag documentada no `.env` privado de produção; `.env.example` já
  contém `COLONOSCOPY_INTAKE_ENABLED=false` como default seguro.
- Manter `PROJECT_CONTEXT.md` e o manual de usuário alinhados ao
  comportamento real (seleção homogênea, mixed PDFs separados, alerta
  medicamentoso informativo, correção antes da fila médica, flag não é
  assunto de usuário comum).
- O change **não** arquiva como concluído enquanto houver item do DoD global
  não comprovado em `openspec/changes/introduce-colonoscopy-exam-workflow/tasks.md`.

## 7. Notas operacionais

- **CPRE não é escopo** deste change; não prometer suporte a CPRE em
  documentos/smoke tests.
- Preparo intestinal/biópsia/diagnóstico-terapêutica **não** são gates da
  política de colonoscopia.
- Medicamentos: apenas alerta informativo; **nunca** orientação de suspensão,
  janela farmacológica ou dose.
- Regra de ouro do rollback: **flag desligada bloqueia novos uploads, nunca
  processamento de casos existentes**; nenhuma migration destrutiva é
  necessária para reverter.
