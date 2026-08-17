# Deploy com PostgreSQL compartilhado

Este runbook descreve o primeiro deploy, as atualizações e o rollback do ATS Web
usando `docker-compose.shared-postgres.yml`.

Nesse modo, o servidor de aplicação não compila código e não cria PostgreSQL.
`ATS_WEB_IMAGE` aponta para uma tag estável explícita, como
`ghcr.io/carlosapgomes/ats-web:v0.1.0`, usada por todos os processos:

- `web`: Gunicorn/Django com role runtime;
- `worker`: pipeline LLM do django-q2 com role runtime;
- `pdf_worker`: extração de PDFs do django-q2 com role runtime;
- `migrate`: serviço temporário com role migrator, ativado por profile.

Não use `latest`: migration e runtime precisam executar exatamente a mesma
release imutável.

## Topologia

```text
PostgreSQL compartilhado
        │
        │ rede externa ${POSTGRES_DOCKER_NETWORK}
        ├────────────── web
        ├────────────── worker
        ├────────────── pdf_worker
        └────────────── migrate (efêmero)

web ─── rede externa edge-network ─── Cloudflared ─── HTTPS
 │
 └──── 127.0.0.1:${WEB_HOST_PORT:-8000} no host

worker ─── rede externa ${EGRESS_DOCKER_NETWORK} ─── provedor LLM HTTPS
```

O Cloudflared deve acessar a aplicação por `http://ats-web:8000`. O PostgreSQL deve
ter um nome ou alias DNS igual ao valor de `DB_HOST` na rede compartilhada. O
`worker` precisa de uma segunda rede, não interna, para resolver DNS e chamar o
provedor LLM; a rede compartilhada do PostgreSQL pode permanecer `internal=true`.

## 1. Pré-requisitos

No servidor de aplicação:

- Docker Engine e Docker Compose;
- acesso de saída do host ao GHCR;
- rede Docker externa do PostgreSQL já criada;
- rede externa `edge-network` já criada;
- rede Docker externa de egress já criada com `internal=false`;
- saída DNS e HTTPS (`443/tcp`) do worker até o provedor LLM permitida;
- Cloudflared conectado a `edge-network`;
- usuário de sistema `apps`;
- os dois arquivos contendo somente as senhas, provisionados fora do Git em
  `/srv/apps/ats-web/secrets/`;
- espaço e rotina de backup para o volume local de mídia.

Na instância PostgreSQL compartilhada:

- database exclusivo para o ATS Web;
- role migrator proprietária e role runtime limitada;
- acesso permitido a partir da rede Docker;
- extensão `unaccent` habilitada;
- rotina externa de backup e recuperação.

Mesmo compartilhando uma única instância PostgreSQL entre aplicativos, use um
database e um par de roles runtime/migrator diferentes para cada aplicativo.

## 2. Preparar o diretório

```bash
sudo install -d -o apps -g apps -m 0750 /srv/apps/ats-web
cd /srv/apps/ats-web

sudo -u apps curl -fsSLo docker-compose.shared-postgres.yml \
  https://raw.githubusercontent.com/carlosapgomes/ats-web/main/docker-compose.shared-postgres.yml

sudo -u apps curl -fsSLo .env.shared-postgres.example \
  https://raw.githubusercontent.com/carlosapgomes/ats-web/main/.env.shared-postgres.example

sudo -u apps cp .env.shared-postgres.example .env
sudo chmod 600 .env
sudo install -d -o apps -g apps -m 0700 /srv/apps/ats-web/secrets
sudo chmod 600 /srv/apps/ats-web/secrets/*.txt
```

O Compose é autônomo. Não baixe nem combine `docker-compose.yml` ou os overrides
de desenvolvimento/teste/produção tradicionais nesse deploy.

## 3. Preparar as redes externas

Defina os nomes reais apenas no `.env` privado e confirme-os com o administrador
da infraestrutura. Os exemplos abaixo são deliberadamente fictícios:

```bash
docker network inspect postgres-network
docker network inspect edge-network
docker network inspect egress-network >/dev/null 2>&1 || \
  docker network create --driver bridge egress-network

docker network inspect egress-network \
  --format 'name={{.Name}} internal={{.Internal}} driver={{.Driver}}'
```

A última inspeção precisa mostrar `internal=false`. Uma rede externa declarada no
Compose não é criada automaticamente: ela deve existir antes de `pull`, `run` ou
`up`.

O PostgreSQL deve participar da primeira rede com um alias DNS configurado em
`DB_HOST`. Não registre nomes, aliases ou subnets reais neste repositório.
A rede do PostgreSQL pode ser `internal=true`, desde que não seja a única rede do
worker LLM. Não altere a rede do banco para liberar Internet a todos os serviços
e não use a rede de ingress `edge-network` como substituta da rede de egress.

O contrato mínimo no Compose é:

```yaml
services:
  worker:
    networks:
      - shared_postgres
      - egress

networks:
  shared_postgres:
    external: true
    name: ${POSTGRES_DOCKER_NETWORK:?Set POSTGRES_DOCKER_NETWORK}
  egress:
    external: true
    name: ${EGRESS_DOCKER_NETWORK:?Set EGRESS_DOCKER_NETWORK}
```

O worker não publica portas na rede de egress. Ela existe somente para saída
DNS/HTTPS e mantém o tráfego do provedor separado da rede de ingress.

Conecte o Cloudflared à rede edge configurada se o Compose de infraestrutura
ainda não fizer isso:

```bash
docker network connect edge-network nome-do-container-cloudflared
```

Esses comandos são exemplos operacionais. Não os repita se os containers já
estiverem conectados às redes.

## 4. Preparar o PostgreSQL

A infraestrutura deve fornecer database, role proprietária migrator, role
runtime limitada, senhas SCRAM e as extensões necessárias. Os nomes abaixo são
somente exemplos. Migrations e restores usam o migrator; web e workers usam
somente runtime. O backup do PostgreSQL permanece fora do Compose da aplicação.

## 5. Configurar `.env`

Edite `/srv/apps/ats-web/.env` sem enviá-lo ao Git. Configuração mínima:

```dotenv
ATS_WEB_IMAGE=ghcr.io/carlosapgomes/ats-web:v0.1.0
POSTGRES_DOCKER_NETWORK=postgres-network
EDGE_DOCKER_NETWORK=edge-network
EGRESS_DOCKER_NETWORK=egress-network
WEB_DOCKER_ALIAS=ats-web
DB_HOST=postgres
DB_PORT=5432
DB_NAME=ats_web
DB_RUNTIME_USER=ats_web_runtime
DB_MIGRATOR_USER=ats_web_migrator
DB_RUNTIME_PASSWORD_FILE=./secrets/database-runtime-password.txt
DB_MIGRATOR_PASSWORD_FILE=./secrets/database-migrator-password.txt
DB_CONN_MAX_AGE=600

DJANGO_SECRET_KEY=substitua-por-um-segredo-longo-e-aleatorio
ALLOWED_HOSTS=app.example.com
CSRF_TRUSTED_ORIGINS=https://app.example.com
OPENAI_API_KEY=substitua-pela-chave-do-provedor
OPENAI_MODEL=gpt-4o
OPENAI_BASE_URL=https://api.openai.com/v1

WEB_HOST_PORT=8000
INTRANET_IP_RANGE=
APP_DISPLAY_NAME=ATS Web
TZ=UTC
```

Regras importantes:

- `ATS_WEB_IMAGE` é alterada explicitamente a cada release estável.
- Os nomes de rede, alias e banco exibidos são fictícios e devem ser
  substituídos somente no `.env` privado.
- `EGRESS_DOCKER_NETWORK` deve apontar para uma rede existente com
  `internal=false`; conecte a ela somente serviços que precisam de saída.
- `DB_HOST` usa o alias interno do PostgreSQL, nunca `localhost`.
- Não é necessário configurar TLS/SSL para o tráfego restrito à rede Docker
  interna descrita neste runbook.
- `ALLOWED_HOSTS` recebe hostnames sem esquema; `CSRF_TRUSTED_ORIGINS` recebe URLs
  completas com `https://`.
- Configure as variáveis `EMAIL_*`, `PUBLIC_APP_BASE_URL` e
  `INTERNAL_APP_BASE_URL` da `.env.example` quando utilizar emails transacionais.
- As senhas não ficam no `.env`: somente os caminhos locais são configurados em
  `DB_RUNTIME_PASSWORD_FILE` e `DB_MIGRATOR_PASSWORD_FILE`; o Compose monta os
  arquivos como secrets separados.

O Compose encaminha `DB_PASSWORD_FILE`, nunca `DB_PASSWORD` ou `DATABASE_URL`.

### Hardening dos containers

Todos os serviços usam `read_only`, `cap_drop: ALL`,
`no-new-privileges`, timezone configurável por `TZ`, `/tmp` em tmpfs e logs rotativos.
`HOME=/tmp`, `UV_CACHE_DIR=/tmp/uv-cache` e `PYTHONDONTWRITEBYTECODE=1` tornam a
imagem compatível com filesystem read-only. O tmpfs é 256 MB por padrão e 512 MB
(`512m` no Compose) no `pdf_worker`.

## 6. Validar sem expor segredos

Valide apenas o status da configuração. Não execute `docker compose config` sem
`--quiet`, pois a saída renderizada pode conter senhas:

```bash
docker compose --profile migration --env-file .env \
  -f docker-compose.shared-postgres.yml config --quiet
```

O comando deve terminar com exit code zero. Variáveis obrigatórias ausentes são
reportadas antes da criação dos containers.

## 7. Primeiro deploy

Baixe a imagem:

```bash
docker compose --profile migration --env-file .env \
  -f docker-compose.shared-postgres.yml pull
```

Em database novo, aplique migrations antes de liberar o serviço:

```bash
docker compose --profile migration --env-file .env \
  -f docker-compose.shared-postgres.yml run --rm migrate
```

Crie os prompts iniciais:

```bash
docker compose --env-file .env -f docker-compose.shared-postgres.yml run --rm web \
  uv run python manage.py seed_prompts --settings=config.settings.prod
```

Suba os três serviços:

```bash
docker compose --env-file .env -f docker-compose.shared-postgres.yml up -d
```

## 8. Validar o deploy

```bash
docker compose --env-file .env -f docker-compose.shared-postgres.yml ps

docker compose --env-file .env -f docker-compose.shared-postgres.yml logs \
  --tail 100 web worker pdf_worker

# Execute dentro do worker: testar no host ou no web não valida o egress do LLM.
docker compose --env-file .env -f docker-compose.shared-postgres.yml \
  exec -T worker uv run python - <<'PY'
import os
import socket
import ssl
from urllib.parse import urlparse

host = urlparse(os.environ["OPENAI_BASE_URL"]).hostname
if not host:
    raise SystemExit("OPENAI_BASE_URL não contém hostname")

answers = socket.getaddrinfo(host, 443)
with socket.create_connection((host, 443), timeout=10) as raw:
    with ssl.create_default_context().wrap_socket(raw, server_hostname=host) as tls:
        print(f"egress_ok host={host} dns_answers={len(answers)} tls={tls.version()}")
PY

curl --fail --silent --show-error \
  --output /dev/null \
  http://127.0.0.1:8000/login/
```

Verifique também:

1. os três serviços estão `Up`;
2. não há erro de DNS, autenticação ou migration nos logs;
3. o teste executado dentro do `worker` confirma DNS e TLS até o provedor;
4. `http://127.0.0.1:8000` responde apenas no host;
5. o hostname HTTPS do túnel abre a página de login;
6. o Cloudflared resolve o alias privado configurado em `WEB_DOCKER_ALIAS`;
7. upload e processamento de um PDF de teste chegam aos workers e concluem a
   chamada LLM sem `APIConnectionError`.

Se `WEB_HOST_PORT` for diferente de `8000`, ajuste a porta do comando `curl`.

## 9. Migrar uma instância PostgreSQL existente

Use este procedimento quando o ATS Web já estiver em produção em outro servidor
e o banco antigo será desativado. A migração inclui duas fontes de dados:

1. o database PostgreSQL, transferido com `pg_dump`/`pg_restore`;
2. o diretório de mídia, que contém os PDFs e não faz parte do dump PostgreSQL.

Não desative o servidor antigo nem remova seus volumes até concluir todas as
validações e manter um período de observação.

### 9.1. Compatibilidade e ensaio

A origem usa PostgreSQL 17 e o destino PostgreSQL 18.4. Use o client do destino,
`postgres:18.4-trixie`, tanto no dump quanto no restore. Um `pg_dump` 18 pode ler
a origem 17 e o `pg_restore` 18 é compatível com o destino 18.4.

Antes do corte definitivo:

1. faça um dump de ensaio enquanto a origem ainda atende usuários;
2. restaure em um database temporário;
3. meça duração e espaço necessários;
4. valide contagens e migrations;
5. defina a janela de indisponibilidade e o plano de retorno.

`pg_dump` produz um snapshot consistente mesmo com a origem ativa, mas não inclui
alterações confirmadas depois do início do dump. Por isso, o dump final exige uma
janela para interromper todas as escritas no sistema antigo.

### 9.2. Preparar credenciais temporárias do cliente

Não passe senhas na linha de comando e não use uma variável de senha inline.
Crie um arquivo temporário fora do Git:

```bash
cd /srv/apps/ats-web
install -m 600 /dev/null migration.pgpass
${EDITOR:-vi} migration.pgpass
```

Formato de cada linha:

```text
hostname:porta:database:usuario:senha
```

Adicione uma linha para a origem e outra para o destino. Caracteres `:` e `\` nas
senhas precisam ser escapados com `\`. Os comandos usam
`PGPASSFILE=/run/secrets/pgpass`, montado somente para leitura. Apague esse arquivo
assim que a migração terminar.

### 9.3. Gerar e verificar o dump da origem

Defina somente identificadores não secretos no shell:

```bash
BACKUP_DIR="$PWD/backups/$(date +%Y%m%d-%H%M%S)"
OLD_DB_HOST=ip-ou-dns-do-postgres-antigo
OLD_DB_PORT=5432
OLD_DB_NAME=ats_web
OLD_DB_USER=ats_web

install -d -m 700 "$BACKUP_DIR"
```

Gere um archive customizado, sem transportar proprietários ou ACLs do servidor
antigo:

```bash
docker run --rm \
  --volume "$BACKUP_DIR:/backup" \
  --volume "$PWD/migration.pgpass:/run/secrets/pgpass:ro" \
  --env PGPASSFILE=/run/secrets/pgpass \
  postgres:18.4-trixie \
  pg_dump \
    --host="$OLD_DB_HOST" \
    --port="$OLD_DB_PORT" \
    --username="$OLD_DB_USER" \
    --dbname="$OLD_DB_NAME" \
    --format=custom \
    --compress=9 \
    --no-owner \
    --no-acl \
    --file=/backup/ats_web.dump
```

Se o PostgreSQL antigo só for acessível pela rede Docker do servidor antigo,
execute esse bloco naquele servidor e acrescente
`--network nome-da-rede-antiga` ao `docker run`, usando em `OLD_DB_HOST` o alias
do PostgreSQL nessa rede. Depois transfira o diretório de backup para o novo
servidor por um canal autenticado.

Valide o archive e registre seu checksum:

```bash
docker run --rm \
  --volume "$BACKUP_DIR:/backup:ro" \
  postgres:18.4-trixie \
  pg_restore --list /backup/ats_web.dump \
  > "$BACKUP_DIR/ats_web.list"

test -s "$BACKUP_DIR/ats_web.dump"
test -s "$BACKUP_DIR/ats_web.list"
(
  cd "$BACKUP_DIR"
  sha256sum ats_web.dump > SHA256SUMS
  sha256sum --check SHA256SUMS
)
```

### 9.4. Copiar a mídia do servidor antigo

Descubra o nome do volume que contém `/app/media` no servidor antigo. Depois crie
um archive preservando a estrutura relativa dos arquivos:

```bash
OLD_MEDIA_VOLUME=nome-do-volume-de-media-antigo

docker run --rm \
  --volume "$OLD_MEDIA_VOLUME:/source:ro" \
  --volume "$BACKUP_DIR:/backup" \
  alpine:3.21 \
  tar -C /source -czf /backup/media.tar.gz .

tar -tzf "$BACKUP_DIR/media.tar.gz" >/dev/null
(
  cd "$BACKUP_DIR"
  sha256sum media.tar.gz >> SHA256SUMS
)
```

Se o dump foi produzido no servidor antigo, transfira os artifacts para o novo:

```bash
rsync --archive --partial --progress \
  usuario@servidor-antigo:/caminho/do/backup/ \
  "$BACKUP_DIR/"

(
  cd "$BACKUP_DIR"
  sha256sum --check SHA256SUMS
)
```

Nunca transfira somente o banco: registros `FileField` continuariam apontando
para PDFs ausentes.

### 9.5. Executar o corte definitivo

Na janela combinada:

1. ative uma página de manutenção ou retire o túnel do servidor antigo;
2. impeça novas escritas e aguarde as tasks em execução terminarem;
3. confirme que as filas estão drenadas;
4. pare `web`, `worker` e `pdf_worker` antigos;
5. gere novamente o dump e o archive de mídia com os comandos anteriores;
6. transfira e valide novamente os checksums.

Exemplo de parada no servidor antigo, ajustando o nome do Compose existente:

```bash
docker compose -f docker-compose-antigo.yml stop web worker pdf_worker
```

A partir desse ponto, não permita novos uploads, decisões ou alterações no
servidor antigo. Mantenha o PostgreSQL antigo ligado e intacto para rollback.

### 9.6. Preparar o database de destino

O database de destino precisa estar vazio, pertencer a `ats_web_migrator` e ter
a extensão `unaccent` disponível. Se você já executou o fluxo de primeiro deploy,
recrie o database vazio antes de restaurar. Em particular, **não execute
migrations antes da restauração** de um banco existente.

Configure no shell os identificadores do destino, usando exatamente a rede e o
alias definidos no `.env`:

```bash
NEW_DB_NETWORK=postgres-network
NEW_DB_HOST=postgres
NEW_DB_PORT=5432
NEW_DB_NAME=ats_web
NEW_DB_USER=ats_web_migrator
```

### 9.7. Restaurar no PostgreSQL compartilhado

O client temporário entra na mesma rede Docker do destino:

```bash
docker run --rm \
  --network "$NEW_DB_NETWORK" \
  --volume "$BACKUP_DIR:/backup:ro" \
  --volume "$PWD/migration.pgpass:/run/secrets/pgpass:ro" \
  --env PGPASSFILE=/run/secrets/pgpass \
  postgres:18.4-trixie \
  pg_restore \
    --host="$NEW_DB_HOST" \
    --port="$NEW_DB_PORT" \
    --username="$NEW_DB_USER" \
    --dbname="$NEW_DB_NAME" \
    --exit-on-error \
    --single-transaction \
    --no-owner \
    --no-acl \
    /backup/ats_web.dump
```

`--single-transaction` evita deixar uma restauração parcial se algum objeto
falhar. Como `--no-owner` e `--no-acl` são usados, os objetos restaurados ficam
sob o usuário de destino em vez de depender de roles do servidor antigo.

### 9.8. Restaurar a mídia

Crie o volume com o nome efetivo usado pelo projeto e extraia o archive:

```bash
docker volume create ats-web-shared-postgres_media_prod

docker run --rm \
  --volume ats-web-shared-postgres_media_prod:/target \
  --volume "$BACKUP_DIR:/backup:ro" \
  alpine:3.21 \
  tar -C /target -xzf /backup/media.tar.gz
```

Não use `down -v` depois dessa etapa.

### 9.9. Atualizar schema e iniciar a aplicação

Agora execute somente migrations ainda não presentes no banco importado:

```bash
docker compose --profile migration --env-file .env \
  -f docker-compose.shared-postgres.yml pull

docker compose --profile migration --env-file .env \
  -f docker-compose.shared-postgres.yml run --rm migrate

docker compose --env-file .env -f docker-compose.shared-postgres.yml run --rm web \
  uv run python manage.py seed_prompts --settings=config.settings.prod

docker compose --env-file .env -f docker-compose.shared-postgres.yml up -d
```

`seed_prompts` é idempotente e preserva prompts que já existem.

### 9.10. Validar antes de trocar o túnel

Compare na origem e no destino, no mínimo:

- quantidade de usuários;
- quantidade de casos;
- quantidade de eventos de auditoria;
- quantidade de prompts;
- quantidade e tamanho total dos arquivos de mídia;
- última migration aplicada;
- login e um fluxo operacional controlado.

No destino:

```bash
docker compose --env-file .env -f docker-compose.shared-postgres.yml run --rm web \
  uv run python manage.py check --database default --settings=config.settings.prod

docker compose --env-file .env -f docker-compose.shared-postgres.yml run --rm web \
  uv run python manage.py showmigrations --plan --settings=config.settings.prod

docker compose --env-file .env -f docker-compose.shared-postgres.yml ps

docker compose --env-file .env -f docker-compose.shared-postgres.yml logs \
  --tail 100 web worker pdf_worker
```

Somente depois dessa validação altere o túnel para o novo servidor. Monitore erros,
filas e uploads. **Não desative definitivamente o servidor antigo** até concluir
o período de observação e confirmar backups recuperáveis do banco e da mídia.

### 9.11. Rollback do corte

Se a validação falhar antes da abertura do novo servidor:

1. mantenha o novo ambiente sem tráfego;
2. não faça novas escritas no database novo;
3. reative `web` e workers antigos;
4. restaure o túnel para o servidor antigo;
5. preserve dump, logs e database novo para diagnóstico.

Se usuários já escreveram no novo servidor, não volte simplesmente para o banco
antigo: será necessário reconciliar os dados produzidos após o corte. Por isso, a
validação deve acontecer antes da troca do túnel e a janela deve permanecer
controlada.

Quando a migração for aceita, remova com segurança o arquivo temporário:

```bash
shred --remove migration.pgpass 2>/dev/null || rm -f migration.pgpass
```

Guarde os dumps criptografados e com retenção definida pela política operacional.

## 10. Atualizar para uma nova release estável

Faça backup do database e da mídia conforme a política do servidor. Atualize
`ATS_WEB_IMAGE` no `.env` para a nova tag estável explícita e depois execute:

```bash
docker compose --profile migration --env-file .env \
  -f docker-compose.shared-postgres.yml pull
docker compose --profile migration --env-file .env \
  -f docker-compose.shared-postgres.yml run --rm migrate
docker compose --env-file .env -f docker-compose.shared-postgres.yml up -d
```

As migrations devem ser compatíveis com a versão ainda ativa durante a pequena
janela entre `migrate` e a substituição dos containers. Se não forem, programe
janela de manutenção e pare os serviços antes da migration.

Repita as verificações de serviços, logs, localhost, túnel e fluxo de PDF. Como o
Compose declara `pull_policy: always`, o `up` também consulta o GHCR, mas o `pull`
explícito deixa a atualização visível antes da troca dos containers.

## 11. Desligar preservando dados

```bash
docker compose --env-file .env -f docker-compose.shared-postgres.yml down
```

Não use `down -v`: o volume `media_prod` armazena PDFs e outros uploads locais.
O `down` normal preserva o volume. O database compartilhado não é removido por
nenhum desses comandos.

## 12. Rollback

Antes de atualizar, registre a tag estável atual e confirme que existe backup
recuperável do database. Para voltar temporariamente a uma imagem imutável, crie
`docker-compose.rollback.yml`:

```yaml
services:
  web:
    image: ghcr.io/carlosapgomes/ats-web:v0.1.0
  worker:
    image: ghcr.io/carlosapgomes/ats-web:v0.1.0
  pdf_worker:
    image: ghcr.io/carlosapgomes/ats-web:v0.1.0
```

Substitua `v0.1.0` pela tag realmente validada e execute:

```bash
docker compose --env-file .env \
  -f docker-compose.shared-postgres.yml \
  -f docker-compose.rollback.yml pull

docker compose --env-file .env \
  -f docker-compose.shared-postgres.yml \
  -f docker-compose.rollback.yml up -d
```

Migrations podem não ser reversíveis. Se a release nova alterou o schema de forma
incompatível, restaure o backup PostgreSQL aprovado em vez de executar downgrade
improvisado. O volume `media_prod` deve ser preservado durante todo o rollback.

Para voltar ao canal estável atual, remova o override de rollback e execute
novamente `pull` e `up -d` somente com `docker-compose.shared-postgres.yml`.

## 13. Diagnóstico rápido

### Rede PostgreSQL ausente

```text
network ... declared as external, but could not be found
```

Confirme `POSTGRES_DOCKER_NETWORK` e crie/conecte a rede externamente.

### PostgreSQL não resolve

Confirme que `DB_HOST` corresponde ao alias do container PostgreSQL e que todos os
serviços estão conectados à mesma rede externa.

### Host rejeitado pelo Django

Confira `ALLOWED_HOSTS` e o hostname recebido pelo túnel. Para erros CSRF, confira
`CSRF_TRUSTED_ORIGINS` com esquema `https://`.

### Cloudflared não alcança o web

Confirme que Cloudflared e `web` participam de `edge-network` e use
`http://ats-web:8000` como origem do túnel.

### Worker LLM sem DNS ou acesso ao provedor

Sintomas típicos:

```text
socket.gaierror: Temporary failure in name resolution
httpcore.ConnectError
openai.APIConnectionError: Connection error
```

Primeiro confirme as redes efetivas do container e se a rede de egress não é
interna:

```bash
docker inspect nome-do-container-worker \
  --format '{{range $name, $network := .NetworkSettings.Networks}}{{$name}} {{end}}'

docker network inspect "$EGRESS_DOCKER_NETWORK" \
  --format 'name={{.Name}} internal={{.Internal}} driver={{.Driver}}'
```

Se o worker estiver somente na rede do PostgreSQL com `internal=true`, corrija o
Compose conforme a seção 3 e recrie apenas esse serviço:

```bash
docker compose --env-file .env -f docker-compose.shared-postgres.yml \
  config --quiet

docker compose --env-file .env -f docker-compose.shared-postgres.yml \
  up -d --no-deps --force-recreate worker
```

Repita o teste DNS/TLS da seção 8 dentro do novo container e examine os logs. Não
considere apenas `django_q_task.success`: o orquestrador pode capturar a exceção,
registrar `PIPELINE_FAILED` e concluir a task técnica. Casos que já chegaram a
`FAILED` não são reenfileirados automaticamente e exigem recuperação operacional
auditável; não altere o estado diretamente no banco.

### Imagem não baixa

O pacote é público. Confirme DNS, acesso HTTPS a `ghcr.io`, espaço em disco e a
disponibilidade da tag estável configurada em `ATS_WEB_IMAGE`.
