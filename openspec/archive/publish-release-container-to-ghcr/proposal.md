# Proposal: Publicação da imagem de release no GHCR

**Change ID**: `publish-release-container-to-ghcr`  
**Fase**: infraestrutura / release engineering  
**Risco**: PROFISSIONAL — introduz integração externa com GitHub Container Registry e permissão de escrita em packages, mas não altera runtime, banco, FSM ou deploy de produção  
**Branch sugerida**: `ci/publish-release-container-to-ghcr`

## Problema

O repositório possui `Dockerfile` de produção, mas não possui `.github/workflows/` nem automação para transformar uma GitHub Release em uma imagem versionada e publicá-la no GitHub Container Registry.

Hoje uma release não gera um artefato OCI rastreável. Qualquer imagem precisa ser construída manualmente, o que permite divergência entre o commit da release e o conteúdo implantado.

## Objetivo

Entregar o fluxo vertical:

```text
Mantenedor publica uma GitHub Release com tag SemVer
→ GitHub Actions faz checkout do commit/tag da release
→ Buildx constrói o Dockerfile existente para linux/amd64
→ workflow autentica no GHCR com GITHUB_TOKEN
→ imagem recebe tags determinísticas
→ imagem e aliases permitidos são publicados em ghcr.io/carlosapgomes/ats-web
```

## Escopo incluído

1. Criar `.github/workflows/release-image.yml` acionado exclusivamente por `release.published`.
2. Conceder permissões mínimas: `contents: read` e `packages: write`.
3. Autenticar em `ghcr.io` com `${{ github.actor }}` e `${{ secrets.GITHUB_TOKEN }}`.
4. Publicar em `ghcr.io/${{ github.repository }}` usando `docker/metadata-action` e `docker/build-push-action`.
5. Para release estável `v1.2.3`, publicar:
   - `v1.2.3` — referência exata da GitHub Release;
   - `1.2.3` — versão SemVer normalizada;
   - `1.2` — alias estável de minor;
   - `latest` — somente para release não-prerelease.
6. Para prerelease, não atualizar `latest` nem alias estável `major.minor`.
7. Construir apenas `linux/amd64` neste change.
8. Usar cache nativo do GitHub Actions (`type=gha`).
9. Adicionar teste de contrato versionado para os invariantes críticos do workflow.
10. Executar smoke build local do `Dockerfile` como inspeção obrigatória do slice.

## Fora de escopo

- Alterar `Dockerfile` ou `.dockerignore`.
- Alterar `docker-compose.prod.yml` para consumir a imagem do GHCR.
- Automatizar deploy, migrations, rollback ou restart de produção.
- Executar o quality gate da aplicação dentro do workflow de release; o quality gate continua obrigatório para o implementador do slice e para a preparação da release.
- Publicar imagens multi-arquitetura ou `linux/arm64`.
- Assinatura Cosign, SBOM, provenance/attestations ou scan de vulnerabilidades.
- Criar credencial PAT; a publicação deve usar somente `GITHUB_TOKEN`.
- Adicionar `workflow_dispatch`, trigger por `push` ou publicação por tag sem GitHub Release.
- Alterar visibilidade do package no GHCR, pois isso é configuração administrativa do GitHub.
- Criar alias mutável somente de major, como `1`.

## Dimensionamento dos slices

O change terá **um único slice vertical**.

A menor entrega útil exige o teste de contrato e o workflow juntos: somente o teste não publica imagem, e somente o YAML sem teste não protege os contratos de trigger, permissões, tags e push. A implementação deve tocar apenas dois arquivos funcionais, além da atualização de `tasks.md`:

1. `.github/workflows/release-image.yml`;
2. `tests/test_release_image_workflow.py`.

Separar autenticação, metadata e build em slices distintos criaria fatias horizontais sem valor operacional independente.

## Critérios globais de sucesso

- O workflow é disparado por uma GitHub Release publicada, não por `push`.
- O destino da imagem é `ghcr.io/${{ github.repository }}`.
- A autenticação usa `GITHUB_TOKEN`, sem secret customizado.
- As permissões são mínimas e suficientes para leitura do conteúdo e escrita do package.
- Releases estáveis atualizam tag exata, SemVer normalizada, minor e `latest`.
- Prereleases não atualizam `latest` nem o alias estável `major.minor`.
- O build usa o `Dockerfile` raiz, Buildx, cache GHA e `linux/amd64`.
- O teste de contrato falha sem o workflow e passa com todos os invariantes presentes.
- O `Dockerfile` existente conclui um smoke build local.
- Nenhum arquivo de aplicação, Compose, dependência, model, migration, FSM ou setting é alterado.
- Quality gate completo do `AGENTS.md` passa.

## Avaliação de ADR

Este change integra um registry externo, mas a decisão é pequena, reversível e restrita ao empacotamento: o deploy de produção permanece inalterado e o OpenSpec registra contexto, alternativas e consequências. Portanto, **não é exigida uma ADR neste slice**. Uma ADR deve ser reconsiderada quando o ambiente de produção passar a consumir obrigatoriamente imagens do GHCR, quando houver assinatura/attestation obrigatória ou quando a política de distribuição/deploy mudar.
