# Tasks: Publicação da imagem de release no GHCR

## Status

**IN PROGRESS — Slice 001 e hardening da imagem concluídos; Slice 002 Node.js 24 planejado.**

## Slices verticais

- [x] Slice 001 — GitHub Release → build e publicação versionada no GHCR (`slices/slice-001-release-image-to-ghcr.md`)
- [ ] Slice 002 — Atualizar actions para runtime Node.js 24 (`slices/slice-002-upgrade-actions-node24.md`)

O Slice 001 entregou o fluxo vertical original. O Slice 002 é um follow-up vertical motivado pela annotation real da prerelease `v0.1.0-rc.1`: remove o fallback de actions Node.js 20 sem adicionar Node ao projeto nem alterar o comportamento de publicação.

## Definition of Done do change

### Evento e segurança

- [x] `.github/workflows/release-image.yml` existe.
- [x] Trigger exclusivo em `release` com `types: [published]`.
- [x] Não há trigger top-level por `push` ou `workflow_dispatch`.
- [x] Permissões são `contents: read` e `packages: write`.
- [x] Login usa `ghcr.io`, `${{ github.actor }}` e `${{ secrets.GITHUB_TOKEN }}`.
- [x] Nenhum PAT, secret customizado ou credencial é passado ao Docker build.

### Metadata e publicação

- [x] Imagem canônica é `ghcr.io/${{ github.repository }}`.
- [x] Tag raw exata usa `${{ github.event.release.tag_name }}`.
- [x] Tag SemVer normalizada `{{version}}` é publicada.
- [x] Alias `{{major}}.{{minor}}` só é publicado para release estável.
- [x] `latest` só é publicado para release estável.
- [x] Alias somente de major não é criado.
- [x] `flavor: latest=false` evita `latest` implícito.
- [x] Build usa `context: .`, `file: ./Dockerfile`, `push: true` e `pull: true`.
- [x] Build usa somente `linux/amd64`.
- [x] Tags e labels vêm da saída de `docker/metadata-action`.
- [x] Cache usa backend GHA para leitura e escrita.
- [x] Concorrência é agrupada por release tag e não cancela build em andamento.

### Testabilidade e escopo

- [x] `tests/test_release_image_workflow.py` cobre os contratos críticos com stdlib, sem dependência nova.
- [x] RED real registrado antes da criação do workflow.
- [x] GREEN do teste alvo registrado.
- [x] Smoke build `docker build --network=host --pull --tag ats-web:release-image-smoke .` passa.
- [x] `Dockerfile`, `.dockerignore`, Compose, `pyproject.toml`, `uv.lock` e código Django permanecem inalterados.
- [x] Nenhum deploy, migration, auto-restart, multiarch, assinatura, SBOM ou scan foi antecipado.

### Gates e entrega

- [x] Baseline inicial `uv run pytest` registrado com exit code 0, zero failures/errors e total de passed.
- [x] `uv run ruff check .` passa.
- [x] `uv run ruff format --check .` passa.
- [x] `uv run mypy .` passa.
- [x] `uv run pytest` final passa com exit code 0, zero failures/errors e `passed_final >= passed_baseline`.
- [x] Checks de inspeção do slice foram executados e interpretados.
- [x] `git diff --check` passa.
- [x] Relatório `/tmp/publish-release-container-to-ghcr-slice-001-report.md` contém todas as evidências e handoff ao verificador.
- [x] `tasks.md` só é marcado após todos os itens anteriores passarem.
- [x] Commit rastreável criado e push realizado na branch atual.

## Follow-up QUICK — imagem de produção sem dependências dev

- [x] `UV_NO_SYNC=1` definido após sync de produção e antes de collectstatic.
- [x] Teste de contrato do Dockerfile passa.
- [x] Imagem inspecionada sem pytest/mypy/ruff/django-stubs.
- [x] Runtime Django/Gunicorn funciona com network none e sem sync.
- [x] Quality gate completo passa.

## Follow-up Slice 002 — actions com runtime Node.js 24

- [x] `actions/checkout@v7` usa Node.js 24.
- [x] `docker/setup-buildx-action@v4` usa Node.js 24.
- [x] `docker/login-action@v4` usa Node.js 24.
- [x] `docker/metadata-action@v6` usa Node.js 24.
- [x] `docker/build-push-action@v7` usa Node.js 24.
- [x] Refs legados Node.js 20 estão ausentes do workflow e proibidos pelo teste.
- [x] Nenhum `actions/setup-node`, package/lockfile Node ou dependência Node foi adicionado.
- [x] Contratos existentes do workflow permanecem inalterados.
- [x] Quality gate completo passa.
- [x] Relatório `/tmp/publish-release-container-to-ghcr-slice-002-node24-actions-report.md` criado, commit e push realizados.

## Regra de parada

Após concluir o Slice 002, retornar `REPORT_PATH=/tmp/publish-release-container-to-ghcr-slice-002-node24-actions-report.md` e **PARAR** para revisão do planner/terceiro LLM. Não publicar nova release, iniciar consumo no Compose ou automatizar deploy sem confirmação explícita.
