<!-- markdownlint-disable MD013 -->

# Slice 002: Atualizar GitHub Actions para runtime Node.js 24

## Handoff para implementador LLM com contexto zero

Este é um follow-up vertical e enxuto do workflow de publicação no GHCR. A prerelease `v0.1.0-rc.1` executou o workflow, mas o GitHub exibiu a annotation:

```text
Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced to run on Node.js 24
```

A aplicação não usa Node.js. O aviso vem do runtime interno das actions de terceiros. **Não adicione `actions/setup-node`, Node ao Dockerfile, `package.json` ou dependência Node ao projeto.** A correção é atualizar os majors das actions para releases que declaram `using: node24`.

Leia integralmente, nesta ordem, antes de editar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/publish-release-container-to-ghcr/proposal.md`
4. `openspec/changes/publish-release-container-to-ghcr/design.md`
5. `openspec/changes/publish-release-container-to-ghcr/specs/release-container-publication/spec.md`
6. `openspec/changes/publish-release-container-to-ghcr/tasks.md`
7. `openspec/changes/publish-release-container-to-ghcr/slices/slice-001-release-image-to-ghcr.md`
8. este arquivo
9. `.github/workflows/release-image.yml`
10. `tests/test_release_image_workflow.py`
11. `Dockerfile`
12. `/tmp/publish-release-container-to-ghcr-slice-001-report.md`, se existir
13. `/tmp/fix-production-image-no-dev-tools-report.md`, se existir

### Estado esperado

- `main` contém o commit `ea5ba75` e a tag `v0.1.0-rc.1`, ou um descendente equivalente.
- O workflow está funcional e publicou a prerelease; somente a annotation de runtime Node 20 deve ser eliminada.
- Contratos de evento, permissões, GHCR, tags, prerelease, plataforma, cache e `UV_NO_SYNC` estão corretos e devem ser preservados.
- O baseline esperado é pelo menos `2223 passed`, zero failures/errors.
- O design D5 contém os majors originais; este slice **substitui somente as referências de versão de D5**, sem alterar as demais decisões.

## Versões alvo verificadas

Use exatamente estes majors, cujas releases atuais declaram `using: node24` em `action.yml`:

| Action | Atual | Alvo Node 24 |
| --- | --- | --- |
| `actions/checkout` | `@v4` | `@v7` |
| `docker/setup-buildx-action` | `@v3` | `@v4` |
| `docker/login-action` | `@v3` | `@v4` |
| `docker/metadata-action` | `@v5` | `@v6` |
| `docker/build-push-action` | `@v6` | `@v7` |

Não use `@main`, `@master`, versão floating sem major, nem SHA inventado. Pinning por SHA continua fora do escopo deste follow-up.

## Protocolo obrigatório para DeepSeek4-Flash

1. **Branch/worktree**: confirme worktree limpo. Crie/use `ci/upgrade-release-actions-node24`; não implemente diretamente em `main`.
2. **Baseline**: registre `BASE_REF=$(git rev-parse HEAD)` e rode `uv run pytest`. Deve ter exit code 0, zero failures/errors e pelo menos 2223 passed.
3. **Matriz antes de editar**: registre `R1..R6 → arquivos → testes/inspeções` no relatório.
4. **RED real**: altere primeiro o teste de contrato para exigir os majors Node 24 e proibir os majors antigos; rode o teste alvo antes de editar o workflow. A falha deve ser semântica por referências antigas.
5. **GREEN mínimo**: altere apenas as cinco referências `uses:` no workflow.
6. **REFACTOR**: preserve clean code, DRY e YAGNI; não reescreva workflow/testes sem necessidade.
7. **Inspeção externa**: prove via GitHub API que cada major alvo declara `using: node24`.
8. **Gates completos**: execute inspeções, quality gate e comparação baseline/final.
9. **Conclusão**: atualize `tasks.md`, relatório, commit e push somente se tudo passar; depois pare sem criar release.

Se qualquer baseline, RED, inspeção Node 24, teste ou quality gate falhar, o slice está INCOMPLETO: não marque tasks e não faça commit/push.

## Objetivo vertical

```text
Workflow usa actions suportadas em Node.js 24
→ GitHub não precisa forçar actions Node 20 para Node 24
→ build e publicação GHCR preservam todos os contratos existentes
→ projeto/container continuam sem dependência Node
```

## Requisitos

### R1. Checkout em Node 24

Em `.github/workflows/release-image.yml`:

```yaml
uses: actions/checkout@v7
```

Proibir `actions/checkout@v4`.

### R2. Docker setup/login em Node 24

Usar:

```yaml
uses: docker/setup-buildx-action@v4
uses: docker/login-action@v4
```

Proibir os respectivos `@v3`.

### R3. Metadata/build-push em Node 24

Usar:

```yaml
uses: docker/metadata-action@v6
uses: docker/build-push-action@v7
```

Proibir `metadata-action@v5` e `build-push-action@v6`.

### R4. Preservar comportamento do workflow

Não alterar:

- `release.published`;
- concurrency por `release.tag_name`;
- `contents: read` e `packages: write`;
- login com `github.actor` + `GITHUB_TOKEN`;
- imagem `ghcr.io/${{ github.repository }}`;
- tag raw, SemVer normalizada, minor estável e `latest`;
- guards `prerelease == false`;
- `context: .`, `./Dockerfile`, `push/pull: true`;
- `linux/amd64`;
- tags/labels da metadata;
- cache GHA.

### R5. Atualizar teste de contrato

Em `tests/test_release_image_workflow.py`, atualizar `test_workflow_uses_expected_action_major_versions` para exigir os cinco majors alvo.

Adicionar proteção explícita contra regressão para os cinco refs antigos. Pode ser no mesmo teste, com uma coleção `legacy_action_refs` e asserts acionáveis.

Não adicionar parser YAML, dependência, snapshot integral ou acesso à rede no pytest.

### R6. Sem Node no projeto

Não criar ou alterar:

- `package.json`/lockfiles Node;
- `actions/setup-node`;
- Dockerfile;
- pyproject/uv.lock;
- Compose;
- código Django.

As actions executam seu runtime Node internamente no runner GitHub-hosted.

## Arquivos esperados

Arquivos funcionais:

1. `.github/workflows/release-image.yml`
2. `tests/test_release_image_workflow.py`

Rastreabilidade após gates:

3. `openspec/changes/publish-release-container-to-ghcr/tasks.md`

Qualquer arquivo extra torna o slice INCOMPLETO e exige consulta ao planner.

## TDD obrigatório: RED → GREEN → REFACTOR

### Baseline

```bash
git status --short
git switch -c ci/upgrade-release-actions-node24  # ou use a branch já existente
git status --short
BASE_REF=$(git rev-parse HEAD)
printf 'BASE_REF=%s\n' "$BASE_REF"
uv run pytest
```

Não prossiga se o baseline estiver vermelho.

### RED

Atualize primeiro somente `tests/test_release_image_workflow.py`:

- expected: checkout v7, setup-buildx v4, login v4, metadata v6, build-push v7;
- forbidden: checkout v4, setup-buildx v3, login v3, metadata v5, build-push v6.

Rode antes de editar o YAML:

```bash
uv run pytest tests/test_release_image_workflow.py::test_workflow_uses_expected_action_major_versions -vv
```

Resultado obrigatório: falha pelo menos porque os refs alvo não estão presentes e/ou refs legados ainda existem. RED por sintaxe/import não vale.

### GREEN

Altere apenas as cinco linhas `uses:` no workflow e rode:

```bash
uv run pytest tests/test_release_image_workflow.py -v
```

Todos os testes do workflow devem passar.

### REFACTOR

- mensagens claras para major ausente/legado presente;
- coleções simples, sem abstração genérica;
- nenhum contrato existente enfraquecido;
- nenhum comentário desnecessário no YAML.

Rode novamente o teste alvo após refactor.

## Verificação externa obrigatória de Node 24

Execute e cole no relatório o ref consultado e a linha `using: node24`:

```bash
gh api -H 'Accept: application/vnd.github.raw+json' \
  'repos/actions/checkout/contents/action.yml?ref=v7' | rg -n "using: ['\"]?node24"

gh api -H 'Accept: application/vnd.github.raw+json' \
  'repos/docker/setup-buildx-action/contents/action.yml?ref=v4' | rg -n "using: ['\"]?node24"

gh api -H 'Accept: application/vnd.github.raw+json' \
  'repos/docker/login-action/contents/action.yml?ref=v4' | rg -n "using: ['\"]?node24"

gh api -H 'Accept: application/vnd.github.raw+json' \
  'repos/docker/metadata-action/contents/action.yml?ref=v6' | rg -n "using: ['\"]?node24"

gh api -H 'Accept: application/vnd.github.raw+json' \
  'repos/docker/build-push-action/contents/action.yml?ref=v7' | rg -n "using: ['\"]?node24"
```

Cada comando deve retornar uma ocorrência. Se algum ref não existir ou não declarar Node 24, pare como INCOMPLETO e consulte o planner; não escolha versão por suposição.

## Inspeções obrigatórias

### I1. Refs novos presentes

```bash
rg -n 'actions/checkout@v7|docker/setup-buildx-action@v4|docker/login-action@v4|docker/metadata-action@v6|docker/build-push-action@v7' \
  .github/workflows/release-image.yml tests/test_release_image_workflow.py
```

### I2. Refs antigos ausentes do workflow

```bash
if rg -n 'actions/checkout@v4|docker/setup-buildx-action@v3|docker/login-action@v3|docker/metadata-action@v5|docker/build-push-action@v6' \
  .github/workflows/release-image.yml; then
  echo 'ERRO: action legada Node 20 encontrada no workflow'
  exit 1
else
  echo 'OK: nenhum ref legado no workflow'
fi
```

Refs antigos devem aparecer no teste apenas como lista proibida.

### I3. Node não introduzido no projeto

```bash
if rg -n 'actions/setup-node' .github/workflows/release-image.yml; then
  echo 'ERRO: setup-node é desnecessário'
  exit 1
else
  echo 'OK: sem setup-node'
fi

git diff --name-only "$BASE_REF" -- | rg '(^|/)(package-lock\.json|package\.json|yarn\.lock|pnpm-lock\.yaml)$' && {
  echo 'ERRO: artefato Node introduzido'
  exit 1
} || echo 'OK: nenhum artefato Node introduzido'
```

### I4. Contratos existentes preservados

Execute todos os testes de contrato:

```bash
uv run pytest tests/test_release_image_workflow.py -v
```

E inspecione:

```bash
rg -n 'release:|types: \[published\]|contents: read|packages: write|GITHUB_TOKEN|prerelease == false|linux/amd64|push: true|cache-from: type=gha|cache-to: type=gha' \
  .github/workflows/release-image.yml
```

### I5. Escopo/diff

```bash
git diff --check
git diff --name-only "$BASE_REF" -- | sort
git status --short
```

Lista máxima final:

```text
.github/workflows/release-image.yml
openspec/changes/publish-release-container-to-ghcr/tasks.md
tests/test_release_image_workflow.py
```

## Critérios binários de sucesso

- [ ] Baseline limpo e verde, com hash/count registrados.
- [ ] RED real capturado antes da alteração do workflow.
- [ ] Cinco majors alvo presentes.
- [ ] Cinco refs legados ausentes do workflow e proibidos pelo teste.
- [ ] Cada action alvo comprovada como `using: node24` via API.
- [ ] Todos os demais contratos do workflow preservados.
- [ ] Nenhum setup-node, package/lockfile Node ou dependência nova.
- [ ] Testes do workflow passam.
- [ ] Quality gate completo passa.
- [ ] Pytest final tem exit code 0, zero failures/errors e `passed_final >= passed_baseline`.
- [ ] Escopo exato comprovado.
- [ ] Relatório, commit e push concluídos.

## Condições automáticas de INCOMPLETO

Marque INCOMPLETE, não atualize tasks e não faça commit/push se:

- baseline falhar;
- RED não for semântico ou for capturado depois do YAML;
- qualquer action alvo não declarar `using: node24`;
- ref legado permanecer no workflow;
- teste não proibir regressão aos refs legados;
- evento, permissões, tags, prerelease guards, plataforma, push ou cache mudar;
- setup-node/Node/dependência nova for introduzido;
- arquivo fora do escopo mudar;
- qualquer inspeção ou quality gate faltar/falhar;
- relatório temporário faltar;
- uma release real for publicada durante este slice.

## Quality gate completo

Execute separadamente:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

Registre exit codes, resumo final e comparação com baseline.

## Atualização de tasks

Somente após todos os gates, marque o Slice 002 e seu checklist em `openspec/changes/publish-release-container-to-ghcr/tasks.md`. Não altere checkboxes históricos dos trabalhos concluídos.

## Relatório obrigatório

Criar:

```text
/tmp/publish-release-container-to-ghcr-slice-002-node24-actions-report.md
```

Incluir:

- `Status: COMPLETE | INCOMPLETE`;
- branch, `BASE_REF`, commit e push;
- matriz requisito → arquivo → teste/inspeção;
- baseline;
- RED/GREEN/REFACTOR;
- snippets antes/depois das cinco actions;
- outputs `using: node24` das cinco APIs;
- prova de refs legados ausentes;
- prova de ausência de setup-node/artefatos Node;
- testes de contrato;
- quality gate completo;
- comparação pytest;
- diff de escopo;
- limitações: execução real será validada apenas em nova prerelease após merge;
- Handoff para verificador com comandos exatos.

## Prompt pronto para implementador

```text
Read completely AGENTS.md, PROJECT_CONTEXT.md and all artifacts listed in openspec/changes/publish-release-container-to-ghcr/slices/slice-002-upgrade-actions-node24.md. Implement ONLY Slice 002.

Create/use branch ci/upgrade-release-actions-node24 from clean main. Record BASE_REF and run the full pytest baseline (expected >=2223 passed, zero failures/errors).

Follow TDD: update tests/test_release_image_workflow.py first to require actions/checkout@v7, docker/setup-buildx-action@v4, docker/login-action@v4, docker/metadata-action@v6 and docker/build-push-action@v7, and explicitly forbid the old refs. Capture a semantic RED before editing the workflow. Then update only the five uses lines in .github/workflows/release-image.yml and capture GREEN. Preserve all event, permissions, GHCR, tags, prerelease guards, platform, push and cache behavior.

Prove each target major declares using: node24 via the exact gh api inspections in the slice. Do not add setup-node, package.json, Node dependencies, Dockerfile changes, Compose changes, pyproject/uv changes, deployment or release publication.

Run every inspection and the full quality gate: uv run ruff check .; uv run ruff format --check .; uv run mypy .; uv run pytest. If any required check fails, any legacy ref remains, any target is not node24, or any extra file changes, report INCOMPLETE and do not update tasks/commit/push.

If all gates pass, update only Slice 002/checklist in tasks.md, create /tmp/publish-release-container-to-ghcr-slice-002-node24-actions-report.md with full evidence and Handoff para verificador, commit `ci: upgrade release actions to node24`, push origin/ci/upgrade-release-actions-node24, reply REPORT_PATH=/tmp/publish-release-container-to-ghcr-slice-002-node24-actions-report.md, and STOP. Do not publish a release.
```
