# Tasks: Publicação da imagem de release no GHCR

## Status

**PLANNED — nenhuma implementação iniciada.**

## Slices verticais

- [ ] Slice 001 — GitHub Release → build e publicação versionada no GHCR (`slices/slice-001-release-image-to-ghcr.md`)

Apenas um slice foi planejado porque workflow + teste de contrato formam a menor entrega vertical verificável. Dividir trigger, login, metadata e build criaria slices horizontais incapazes de publicar uma imagem isoladamente.

## Definition of Done do change

### Evento e segurança

- [ ] `.github/workflows/release-image.yml` existe.
- [ ] Trigger exclusivo em `release` com `types: [published]`.
- [ ] Não há trigger top-level por `push` ou `workflow_dispatch`.
- [ ] Permissões são `contents: read` e `packages: write`.
- [ ] Login usa `ghcr.io`, `${{ github.actor }}` e `${{ secrets.GITHUB_TOKEN }}`.
- [ ] Nenhum PAT, secret customizado ou credencial é passado ao Docker build.

### Metadata e publicação

- [ ] Imagem canônica é `ghcr.io/${{ github.repository }}`.
- [ ] Tag raw exata usa `${{ github.event.release.tag_name }}`.
- [ ] Tag SemVer normalizada `{{version}}` é publicada.
- [ ] Alias `{{major}}.{{minor}}` só é publicado para release estável.
- [ ] `latest` só é publicado para release estável.
- [ ] Alias somente de major não é criado.
- [ ] `flavor: latest=false` evita `latest` implícito.
- [ ] Build usa `context: .`, `file: ./Dockerfile`, `push: true` e `pull: true`.
- [ ] Build usa somente `linux/amd64`.
- [ ] Tags e labels vêm da saída de `docker/metadata-action`.
- [ ] Cache usa backend GHA para leitura e escrita.
- [ ] Concorrência é agrupada por release tag e não cancela build em andamento.

### Testabilidade e escopo

- [ ] `tests/test_release_image_workflow.py` cobre os contratos críticos com stdlib, sem dependência nova.
- [ ] RED real registrado antes da criação do workflow.
- [ ] GREEN do teste alvo registrado.
- [ ] Smoke build `docker build --pull --tag ats-web:release-image-smoke .` passa.
- [ ] `Dockerfile`, `.dockerignore`, Compose, `pyproject.toml`, `uv.lock` e código Django permanecem inalterados.
- [ ] Nenhum deploy, migration, auto-restart, multiarch, assinatura, SBOM ou scan foi antecipado.

### Gates e entrega

- [ ] Baseline inicial `uv run pytest` registrado com exit code 0, zero failures/errors e total de passed.
- [ ] `uv run ruff check .` passa.
- [ ] `uv run ruff format --check .` passa.
- [ ] `uv run mypy .` passa.
- [ ] `uv run pytest` final passa com exit code 0, zero failures/errors e `passed_final >= passed_baseline`.
- [ ] Checks de inspeção do slice foram executados e interpretados.
- [ ] `git diff --check` passa.
- [ ] Relatório `/tmp/publish-release-container-to-ghcr-slice-001-report.md` contém todas as evidências e handoff ao verificador.
- [ ] `tasks.md` só é marcado após todos os itens anteriores passarem.
- [ ] Commit rastreável criado e push realizado na branch atual.

## Regra de parada

Após concluir o Slice 001, retornar `REPORT_PATH=/tmp/publish-release-container-to-ghcr-slice-001-report.md` e **PARAR** para revisão do planner/terceiro LLM. Não iniciar hardening, consumo no Compose ou automação de deploy sem novo change e confirmação explícita.
