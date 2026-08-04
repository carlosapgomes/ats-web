# Design: Publicação da imagem de release no GHCR

## Estado atual

- O repositório remoto é `github.com/carlosapgomes/ats-web`.
- Não existe diretório `.github/workflows/`.
- O `Dockerfile` raiz já:
  - usa Python 3.13 slim;
  - instala dependências com `uv sync --frozen --no-dev --no-install-project`;
  - copia o código;
  - executa `collectstatic` com `config.settings.prod`;
  - inicia Gunicorn por padrão.
- `.dockerignore` já exclui `.git`, `.env`, `.venv`, caches, artefatos temporários e documentação não necessária ao build.
- `docker-compose.prod.yml` ainda constrói `web`, `worker` e `pdf_worker` localmente. Esse comportamento não será alterado aqui.
- Não existe teste de contrato para workflow de publicação.

## Fluxo projetado

```text
release.published
  → checkout do ref da release
  → setup do Docker Buildx
  → login em ghcr.io com GITHUB_TOKEN
  → metadata calcula nome, labels e tags
  → build do Dockerfile raiz para linux/amd64
  → push de todas as tags válidas
```

## Decisões técnicas

### D1. Trigger somente por GitHub Release publicada

O workflow deve declarar:

```yaml
on:
  release:
    types: [published]
```

Não usar `push.tags`, `workflow_dispatch` ou `release.created`.

Motivos:

- `published` representa a decisão explícita de disponibilizar a release;
- drafts não geram imagem;
- o checkout padrão do evento aponta para o ref associado à release;
- evita publicar uma imagem apenas porque uma tag foi enviada.

Prereleases publicadas também executam o workflow, porém recebem política de aliases restrita em D4.

### D2. Registry e nome canônico derivados do repositório

Declarar:

```yaml
env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}
```

A imagem resultante deste repositório é:

```text
ghcr.io/carlosapgomes/ats-web
```

Não codificar owner em secret nem criar variável administrativa. `github.repository` mantém o workflow reutilizável caso o repositório seja transferido, desde que owner/repository continuem compatíveis com nomes OCI em lowercase.

### D3. Autenticação e permissões mínimas

Permissões no nível do workflow:

```yaml
permissions:
  contents: read
  packages: write
```

Login:

```yaml
with:
  registry: ${{ env.REGISTRY }}
  username: ${{ github.actor }}
  password: ${{ secrets.GITHUB_TOKEN }}
```

Não usar PAT, password fixo, secret customizado, `contents: write` ou permissões globais amplas. Configuração administrativa de visibilidade/acesso do package permanece fora do Git.

### D4. Política de tags determinística

Usar `docker/metadata-action` com `flavor: latest=false`, evitando que a action crie `latest` implicitamente.

Entradas de tags esperadas:

```yaml
tags: |
  type=raw,value=${{ github.event.release.tag_name }}
  type=semver,pattern={{version}},value=${{ github.event.release.tag_name }}
  type=semver,pattern={{major}}.{{minor}},value=${{ github.event.release.tag_name }},enable=${{ github.event.release.prerelease == false }}
  type=raw,value=latest,enable=${{ github.event.release.prerelease == false }}
```

Resultados:

| Release | Tags esperadas |
| --- | --- |
| `v1.2.3`, estável | `v1.2.3`, `1.2.3`, `1.2`, `latest` |
| `v1.3.0-rc.1`, prerelease | `v1.3.0-rc.1`, `1.3.0-rc.1`; sem `1.3` e sem `latest` |

Não publicar alias de major (`1`) para reduzir aliases mutáveis e evitar promessas de compatibilidade não definidas.

A tag exata raw preserva rastreabilidade com o nome visível da GitHub Release. A tag SemVer normalizada facilita consumo por ferramentas que preferem versão sem prefixo `v`.

### D5. Buildx, plataforma e cache

Usar:

- `actions/checkout@v4`;
- `docker/setup-buildx-action@v3`;
- `docker/login-action@v3`;
- `docker/metadata-action@v5`;
- `docker/build-push-action@v6`.

Configuração do build:

```yaml
with:
  context: .
  file: ./Dockerfile
  push: true
  pull: true
  platforms: linux/amd64
  tags: ${{ steps.metadata.outputs.tags }}
  labels: ${{ steps.metadata.outputs.labels }}
  cache-from: type=gha,scope=release-image
  cache-to: type=gha,mode=max,scope=release-image
```

A plataforma única mantém o slice enxuto e atende o servidor x86_64 assumido. Multiarch exigiria QEMU, maior tempo de build e validação adicional; pertence a change futuro.

`pull: true` atualiza imagens-base durante o build da release. Fixação por digest e endurecimento do `Dockerfile` são preocupações válidas, mas fora deste change.

### D6. Concorrência por release

Evitar dois jobs simultâneos para a mesma tag:

```yaml
concurrency:
  group: release-image-${{ github.event.release.tag_name }}
  cancel-in-progress: false
```

Não cancelar build já iniciado: a publicação de um artefato de release deve terminar ou falhar explicitamente.

### D7. Teste de contrato sem nova dependência

Criar `tests/test_release_image_workflow.py` usando apenas `pathlib` e asserts de texto/regex da stdlib. Não adicionar PyYAML, actionlint, plugin ou dependência de teste.

O teste deve proteger comportamentos, não reproduzir um parser YAML completo. Casos mínimos:

1. workflow existe no caminho canônico;
2. trigger é `release.published` e não declara trigger top-level por `push`/`workflow_dispatch`;
3. permissões incluem `contents: read` e `packages: write`, sem `contents: write`;
4. login aponta para GHCR e usa apenas `GITHUB_TOKEN` como credencial;
5. metadata contém tag exata, SemVer normalizada, minor estável condicionado a `prerelease == false` e `latest` com a mesma condição;
6. build usa `Dockerfile` raiz, `push: true`, `linux/amd64`, tags/labels da metadata e cache GHA;
7. versões major das actions acordadas estão presentes.

Os asserts devem produzir mensagens claras. Evitar helper genérico excessivo, parser YAML caseiro ou snapshot do arquivo inteiro.

### D8. Validação operacional do build

Além do teste de contrato, o slice deve executar:

```bash
docker build --pull --tag ats-web:release-image-smoke .
```

Isso prova que o mesmo contexto/Dockerfile apontado pelo workflow constrói localmente. O comando não autentica nem publica nada.

A publicação real no GHCR depende do ambiente GitHub e só ocorrerá após uma release publicada. Essa limitação deve constar no relatório.

## Arquivos de implementação esperados

| Arquivo | Mudança |
| --- | --- |
| `.github/workflows/release-image.yml` | novo workflow de release → GHCR |
| `tests/test_release_image_workflow.py` | novo teste de contrato do workflow |
| `openspec/changes/publish-release-container-to-ghcr/tasks.md` | marcar slice/DoD somente após todos os gates |

Não alterar `Dockerfile`, `.dockerignore`, Compose, `pyproject.toml`, `uv.lock`, código Django ou documentação operacional neste slice.

## Segurança e supply chain

- `GITHUB_TOKEN` é efêmero e scoped ao repositório/job.
- O workflow recebe apenas as permissões necessárias.
- Nenhum secret é passado como build arg ou environment do build.
- O evento de release exige ação de usuário com permissão de manutenção; contribuições comuns não publicam package diretamente.
- Actions por major tag equilibram manutenção e previsibilidade neste slice. Pinning por SHA e atualização automatizada podem ser tratados em hardening futuro.
- SBOM, assinatura, provenance e scan de vulnerabilidades ficam explicitamente fora de escopo, sem impedir adoção posterior.

## Rollback

1. Remover/desabilitar `.github/workflows/release-image.yml`.
2. Remover `tests/test_release_image_workflow.py` ou adaptar ao novo mecanismo aprovado.
3. Excluir manualmente tags/packages publicados no GHCR se necessário.

Não há migration, alteração de dados ou mudança no deploy atual. Rollback do Git não remove automaticamente imagens já publicadas.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Prerelease sobrescrever `latest` ou alias estável | condições explícitas `prerelease == false` e teste de contrato |
| Permissão excessiva do token | bloco mínimo `contents: read`, `packages: write` e teste |
| Imagem publicada com tag sem rastreabilidade | tag raw exata da release + SemVer normalizada |
| Builds repetidos concorrendo pela mesma release | concurrency por `tag_name`, sem cancelamento silencioso |
| Dockerfile deixar de construir | smoke build obrigatório no slice |
| YAML aceito pelos asserts mas inválido no GitHub | estrutura simples baseada em exemplos oficiais; inspeção explícita e verificação opcional pós-push via `gh workflow view` |
| Registry privado impedir pull no servidor | fora deste change; deploy futuro deve autenticar com credencial `read:packages` |
| Bases mudarem por tags mutáveis | risco aceito neste slice; hardening futuro pode fixar versões/digests |

## Limitações aceitas

- O teste local não publica no GHCR e não simula integralmente o evento GitHub Release.
- O workflow não promove nem implanta a imagem.
- O workflow não executa testes da aplicação; uma release deve ser criada somente a partir de commit previamente aprovado.
- A imagem é apenas `linux/amd64`.
- O Compose de produção continua usando `build:` local.
