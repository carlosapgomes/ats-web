# Runbook de releases

Este documento descreve como publicar releases e prereleases do `ats-web` e
acompanhar a geração da imagem OCI no GitHub Container Registry (GHCR).

## O que a publicação dispara

O workflow `.github/workflows/release-image.yml` executa exclusivamente no evento
`release.published`. Criar ou enviar somente uma tag não publica a imagem; uma
release draft também não publica enquanto continuar como draft.

Ao publicar a GitHub Release, o workflow:

1. obtém o código associado à tag;
2. constrói o `Dockerfile` de produção para `linux/amd64`;
3. autentica no GHCR com o `GITHUB_TOKEN` temporário;
4. publica a imagem em `ghcr.io/carlosapgomes/ats-web`;
5. grava o cache de build no backend do GitHub Actions.

Esse processo publica o artefato, mas **não faz deploy**, migration ou reinício
dos serviços de produção.

## Política de versões e tags

Use Semantic Versioning com prefixo `v` na tag Git:

- `vX.Y.Z-rc.N`: prerelease candidata a validação;
- `vX.Y.Z`: release estável;
- incremente `X` para quebra de compatibilidade, `Y` para funcionalidade
  compatível e `Z` para correção compatível.

Exemplo de prerelease `v0.2.0-rc.1`:

```text
v0.2.0-rc.1
0.2.0-rc.1
```

Ela não atualiza `latest` e não atualiza `0.2`.

Exemplo de release estável `v0.2.0`:

```text
v0.2.0
0.2.0
0.2
latest
```

A flag GitHub `prerelease` controla a promoção dos aliases estáveis. Portanto,
não basta usar `-rc.1` no nome: o comando de prerelease deve obrigatoriamente
incluir `--prerelease`. O workflow não cria alias somente de major, como `0`.

## Pré-requisitos

- branch `main` sincronizada e worktree limpo;
- mudança revisada e já integrada em `main`;
- banco isolado de testes disponível;
- GitHub CLI (`gh`) autenticado com acesso ao repositório;
- Git e Docker Buildx disponíveis;
- versão escolhida ainda inexistente localmente e no remoto.

Verifique as ferramentas:

```bash
gh auth status
git --version
docker buildx version
```

## Preparação obrigatória

Execute na raiz do projeto:

```bash
set -euo pipefail

REPO="carlosapgomes/ats-web"

git fetch origin --prune --tags
git switch main
git pull --ff-only origin main

test -z "$(git status --porcelain)" || {
  git status --short
  echo "ERRO: worktree não está limpo"
  exit 1
}

test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
```

Suba o banco de teste, caso ainda não esteja disponível:

```bash
docker compose -f docker-compose.yml -f docker-compose.test.yml up -d
```

Rode o quality gate completo antes de criar a tag:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

Todos os comandos devem terminar com exit code zero. O workflow de release não
substitui esse gate.

## Publicar uma prerelease

O exemplo abaixo publica `v0.2.0-rc.1`. Substitua a versão pela próxima versão
válida do projeto.

### 1. Definir e validar a tag

```bash
REPO="carlosapgomes/ats-web"
TAG="v0.2.0-rc.1"
MINOR_ALIAS="0.2"
IMAGE="ghcr.io/carlosapgomes/ats-web"

if git rev-parse --verify --quiet "refs/tags/$TAG" >/dev/null || \
   git ls-remote --exit-code --tags origin "refs/tags/$TAG" >/dev/null 2>&1; then
  echo "ERRO: tag $TAG já existe; escolha o próximo rc"
  exit 1
fi
```

### 2. Registrar os aliases estáveis antes da publicação

Isso permite comprovar que a prerelease não promoveu nem alterou aliases
estáveis. A função retorna vazio quando o alias ainda não existe.

```bash
digest_or_empty() {
  docker buildx imagetools inspect "$1" \
    --format '{{.Manifest.Digest}}' 2>/dev/null || true
}

LATEST_BEFORE="$(digest_or_empty "$IMAGE:latest")"
MINOR_BEFORE="$(digest_or_empty "$IMAGE:$MINOR_ALIAS")"

printf 'latest antes: %s\n' "${LATEST_BEFORE:-ausente}"
printf '%s antes: %s\n' "$MINOR_ALIAS" "${MINOR_BEFORE:-ausente}"
```

### 3. Criar a tag anotada e publicar a GitHub prerelease

```bash
git tag -a "$TAG" -m "Prerelease $TAG"
git push origin "$TAG"

gh release create "$TAG" \
  --repo "$REPO" \
  --verify-tag \
  --prerelease \
  --latest=false \
  --title "$TAG" \
  --generate-notes
```

Não use `--draft` nesse fluxo. O comando publica a prerelease e dispara o
workflow imediatamente.

### 4. Acompanhar o workflow

```bash
RUN_ID=""

for attempt in $(seq 1 24); do
  RUN_ID="$(
    gh run list \
      --repo "$REPO" \
      --workflow release-image.yml \
      --event release \
      --branch "$TAG" \
      --limit 1 \
      --json databaseId \
      --jq '.[0].databaseId // empty'
  )"

  [ -n "$RUN_ID" ] && break
  echo "Aguardando workflow... tentativa $attempt/24"
  sleep 5
done

test -n "$RUN_ID" || {
  echo "ERRO: workflow não encontrado"
  exit 1
}

if ! gh run watch "$RUN_ID" --repo "$REPO" --exit-status; then
  gh run view "$RUN_ID" --repo "$REPO" --log-failed
  exit 1
fi
```

### 5. Verificar a imagem e a proteção dos aliases estáveis

```bash
docker buildx imagetools inspect "$IMAGE:$TAG"
docker buildx imagetools inspect "$IMAGE:${TAG#v}"

LATEST_AFTER="$(digest_or_empty "$IMAGE:latest")"
MINOR_AFTER="$(digest_or_empty "$IMAGE:$MINOR_ALIAS")"

test "$LATEST_AFTER" = "$LATEST_BEFORE" || {
  echo "ERRO: prerelease alterou latest"
  exit 1
}

test "$MINOR_AFTER" = "$MINOR_BEFORE" || {
  echo "ERRO: prerelease alterou $MINOR_ALIAS"
  exit 1
}

echo "Prerelease validada com sucesso"
```

## Publicar uma release estável

Publique a release estável somente depois que a candidata correspondente tiver
sido validada. O commit estável pode ser o mesmo da candidata ou um descendente
que tenha passado novamente pelo quality gate.

O exemplo abaixo publica `v0.2.0`.

### 1. Definir e validar a tag

```bash
REPO="carlosapgomes/ats-web"
TAG="v0.2.0"
VERSION="${TAG#v}"
MINOR_ALIAS="${VERSION%.*}"
IMAGE="ghcr.io/carlosapgomes/ats-web"

if git rev-parse --verify --quiet "refs/tags/$TAG" >/dev/null || \
   git ls-remote --exit-code --tags origin "refs/tags/$TAG" >/dev/null 2>&1; then
  echo "ERRO: tag $TAG já existe"
  exit 1
fi
```

Confirme novamente que `main` está limpa, sincronizada e com o commit correto:

```bash
git fetch origin --prune --tags
git switch main
git pull --ff-only origin main
test -z "$(git status --porcelain)"
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
git log -1 --oneline --decorate
```

### 2. Criar a tag e publicar a GitHub Release

```bash
git tag -a "$TAG" -m "Release $TAG"
git push origin "$TAG"

gh release create "$TAG" \
  --repo "$REPO" \
  --verify-tag \
  --latest \
  --title "$TAG" \
  --generate-notes
```

Não inclua `--prerelease` na release estável.

### 3. Acompanhar o workflow

Use o mesmo bloco de acompanhamento da prerelease ou execute, depois que o run
aparecer:

```bash
gh run list \
  --repo "$REPO" \
  --workflow release-image.yml \
  --event release \
  --branch "$TAG" \
  --limit 5

RUN_ID="$(
  gh run list \
    --repo "$REPO" \
    --workflow release-image.yml \
    --event release \
    --branch "$TAG" \
    --limit 1 \
    --json databaseId \
    --jq '.[0].databaseId'
)"

gh run watch "$RUN_ID" --repo "$REPO" --exit-status
```

### 4. Verificar todos os aliases da release estável

```bash
EXPECTED_DIGEST="$(
  docker buildx imagetools inspect "$IMAGE:$TAG" \
    --format '{{.Manifest.Digest}}'
)"

for IMAGE_TAG in "$VERSION" "$MINOR_ALIAS" latest; do
  ACTUAL_DIGEST="$(
    docker buildx imagetools inspect "$IMAGE:$IMAGE_TAG" \
      --format '{{.Manifest.Digest}}'
  )"
  test "$ACTUAL_DIGEST" = "$EXPECTED_DIGEST" || {
    echo "ERRO: $IMAGE_TAG não aponta para a imagem de $TAG"
    exit 1
  }
done

echo "Release estável e aliases GHCR validados"
```

Página do pacote:

<https://github.com/carlosapgomes/ats-web/pkgs/container/ats-web>

## Falhas e correções

- Se o workflow falhar por erro transitório de infraestrutura, inspecione os
  logs e use `gh run rerun "$RUN_ID" --failed` somente quando o código/tag
  continuarem válidos.
- Se o código precisar mudar, faça um novo commit, rode novamente o quality gate
  e publique uma nova versão.
- Para uma candidata defeituosa, incremente o RC, por exemplo de
  `v0.2.0-rc.1` para `v0.2.0-rc.2`.
- Para uma release estável defeituosa, publique uma correção, por exemplo
  `v0.2.1`.
- **Não reutilize, mova ou sobrescreva uma tag já publicada.** Tags e imagens de
  release devem permanecer rastreáveis ao commit original.

## Evidências

Registre evidências operacionais relevantes em
`docs/releases/YYYY-MM-DD_vX.Y.Z.md`, incluindo:

- tag, commit e URL da GitHub Release;
- URL e conclusão do workflow;
- tags e digest da imagem GHCR;
- resultado do quality gate;
- incidentes ou limitações observadas.
