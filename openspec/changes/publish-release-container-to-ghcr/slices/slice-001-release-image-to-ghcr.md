<!-- markdownlint-disable MD013 -->

# Slice 001: GitHub Release → imagem versionada no GHCR

## Handoff para implementador LLM com contexto zero

Você está no monolito Django SSR em `/projects/dev/ats-web`. Este slice é exclusivamente de release engineering: ele não altera comportamento Django, dados ou deploy.

Leia integralmente, nesta ordem, antes de planejar ou editar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/publish-release-container-to-ghcr/proposal.md`
4. `openspec/changes/publish-release-container-to-ghcr/design.md`
5. `openspec/changes/publish-release-container-to-ghcr/specs/release-container-publication/spec.md`
6. `openspec/changes/publish-release-container-to-ghcr/tasks.md`
7. este arquivo
8. `Dockerfile`
9. `.dockerignore`

### Estado atual esperado

- O remote `origin` aponta para `https://github.com/carlosapgomes/ats-web.git`.
- Não existe `.github/workflows/release-image.yml`.
- Não existe `tests/test_release_image_workflow.py`.
- O `Dockerfile` raiz constrói a aplicação de produção e executa `collectstatic` durante o build.
- `docker-compose.prod.yml` usa `build:` local e deve permanecer inalterado.
- O repositório não declara PyYAML/actionlint; não adicione dependência para testar este YAML.
- Este change possui somente este slice.

Se qualquer premissa divergir, registre no relatório antes de editar. Se já existir workflow conflitante ou o escopo não puder ser mantido, reporte **INCOMPLETE/BLOQUEADO** em vez de improvisar.

### Fluxo vertical a entregar

```text
Mantenedor publica release v1.2.3
→ workflow release.published inicia
→ checkout + Buildx + login GHCR com GITHUB_TOKEN
→ metadata gera v1.2.3, 1.2.3, 1.2 e latest
→ build do Dockerfile raiz para linux/amd64
→ push para ghcr.io/carlosapgomes/ats-web
```

Para uma prerelease como `v1.3.0-rc.1`, `latest` e `1.3` não podem ser atualizados.

## Protocolo obrigatório para implementador DeepSeek4-Flash

Este slice será implementado por um modelo rápido e com tendência a concluir cedo demais. Siga este protocolo literalmente. **Se qualquer item abaixo falhar, o slice está INCOMPLETO**: não marque `tasks.md`, não faça commit/push e responda com bloqueio + evidência.

1. **Plano antes de editar**: escreva no relatório uma mini matriz `Requisito → arquivo(s) → teste(s)/inspeção`. Não implemente requisito sem teste ou justificativa explícita.
2. **Worktree e baseline antes de editar**:
   - confirme `git status --short` limpo;
   - garanta que o PostgreSQL de testes dedicado está disponível conforme `AGENTS.md`, sem usar banco dev/prod;
   - registre `BASE_REF=$(git rev-parse HEAD)`;
   - rode `uv run pytest` no estado inicial limpo;
   - cole no relatório comando, exit code e linha de resumo com `passed`, `failed` e `errors`.
   Se o worktree estiver sujo ou houver `failed/error` no baseline, pare e reporte INCOMPLETE/BLOQUEADO antes de codar.
3. **RED real**: crie primeiro `tests/test_release_image_workflow.py`; rode `uv run pytest tests/test_release_image_workflow.py -v`. Pelo menos um teste novo deve falhar porque o workflow ainda não existe ou não satisfaz o contrato. Registre nome do teste, exit code e motivo esperado. Se tudo passar antes do workflow, o teste não prova a entrega; corrija-o.
4. **GREEN mínimo**: crie somente `.github/workflows/release-image.yml` com os contratos R1–R8 e faça os testes alvo passarem. Não altere o Dockerfile, Compose, dependências ou código Django.
5. **REFACTOR seguro**: elimine duplicação apenas dentro dos dois arquivos do slice. Use nomes claros e asserts com mensagens acionáveis. Aplique clean code, DRY e YAGNI; não crie parser YAML caseiro, framework/helper genérico ou abstração para um segundo registry inexistente.
6. **Verificação por inspeção**: execute todos os comandos `rg`, escopo Git, `git diff --check` e smoke build descritos neste slice. Cole resultados e interpretação no relatório.
7. **Quality gate completo e comparação pytest**: execute exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` e `uv run pytest`. O pytest final deve ter exit code 0, zero failures/errors e contagem `passed` maior ou igual ao baseline. Se exit code != 0, `failed > 0`, `errors > 0` ou `passed_final < passed_baseline`, o slice está INCOMPLETO.
8. **Relatório com evidência, não opinião**: inclua comandos, exit codes, resumos baseline/final, RED/GREEN, snippets antes/depois, inspeções, smoke build, diff de escopo e respostas aos gates. Inclua `Handoff para verificador` com arquivos alterados, comandos exatos para rerun, riscos/limitações e checklist R1–R8. Só escreva `Status: COMPLETE` se tudo estiver comprovado.
9. **Conclusão controlada**: somente após todos os gates passarem, marque o Slice 001 e os itens comprovados em `tasks.md`, atualize o relatório, faça commit claro, push da branch atual, acrescente commit/push ao relatório, responda com `REPORT_PATH` e pare.

## Objetivo do slice

Criar e proteger por teste um workflow GitHub Actions que, ao publicar uma GitHub Release, construa o `Dockerfile` raiz e publique a imagem no GHCR com autenticação mínima, tags estáveis corretas e proteção contra promoção acidental de prerelease.

Esse é um slice vertical completo porque vai do evento externo ao artefato OCI publicável e inclui regressão automatizada dos contratos críticos.

## Contexto técnico e restrições

- Stack da aplicação: Python 3.13+, Django 5.2+, uv e Docker.
- Registry: `ghcr.io`.
- Nome da imagem: `${{ github.repository }}`; neste remote, `carlosapgomes/ats-web`.
- Credencial: apenas `${{ secrets.GITHUB_TOKEN }}`.
- Arquitetura alvo: somente `linux/amd64`.
- O package poderá ser público ou privado conforme configuração administrativa do GitHub; não tente controlar visibilidade no YAML.
- O teste é de contrato estático com stdlib (`pathlib`, `re` se necessário). Ele não substitui a execução real do GitHub e não deve fingir que fez push.
- O smoke build valida o Dockerfile, mas não publica imagem.
- Releases devem partir de commits previamente validados; não adicione job horizontal de lint/test ao workflow neste slice.

## Escopo funcional

### R1. Arquivo e trigger da release

Criar `.github/workflows/release-image.yml` com nome humano claro, por exemplo `Publish release image`.

O único evento automático deve ser:

```yaml
on:
  release:
    types: [published]
```

Não declarar `push`, `pull_request`, `workflow_dispatch`, schedule ou `release.created`.

### R2. Concorrência e permissões mínimas

Declarar:

```yaml
concurrency:
  group: release-image-${{ github.event.release.tag_name }}
  cancel-in-progress: false

permissions:
  contents: read
  packages: write
```

Não usar `write-all`, `contents: write`, `actions: write`, `id-token: write` ou outra permissão não exigida neste change.

### R3. Registry e autenticação

Definir:

```yaml
env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}
```

Usar `docker/login-action@v3` com:

```yaml
registry: ${{ env.REGISTRY }}
username: ${{ github.actor }}
password: ${{ secrets.GITHUB_TOKEN }}
```

Não criar secret `GHCR_TOKEN`, PAT, Docker Hub login ou credencial customizada.

### R4. Checkout, Buildx e actions acordadas

O job deve rodar em `ubuntu-latest` e usar:

- `actions/checkout@v4`;
- `docker/setup-buildx-action@v3`;
- `docker/login-action@v3`;
- `docker/metadata-action@v5`, com `id: metadata`;
- `docker/build-push-action@v6`.

Não adicionar QEMU, setup Python, setup uv, service PostgreSQL ou steps de deploy.

### R5. Imagem e tags

Configurar metadata para:

```yaml
images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
flavor: |
  latest=false
tags: |
  type=raw,value=${{ github.event.release.tag_name }}
  type=semver,pattern={{version}},value=${{ github.event.release.tag_name }}
  type=semver,pattern={{major}}.{{minor}},value=${{ github.event.release.tag_name }},enable=${{ github.event.release.prerelease == false }}
  type=raw,value=latest,enable=${{ github.event.release.prerelease == false }}
```

Não criar alias apenas de major (`{{major}}`). A condição de prerelease deve estar explícita tanto no alias minor quanto em `latest`.

### R6. Build e push

O `docker/build-push-action@v6` deve usar:

```yaml
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

Não passar secrets, build args com credenciais, env de produção ou `load: true`.

### R7. Teste de contrato versionado

Criar `tests/test_release_image_workflow.py` sem dependência nova. O arquivo deve ter constantes claras para raiz do projeto e caminho do workflow e cobrir, no mínimo, testes com estas responsabilidades:

1. `test_release_image_workflow_exists`;
2. `test_workflow_triggers_only_for_published_release`;
3. `test_workflow_uses_minimum_package_permissions`;
4. `test_workflow_logs_in_to_ghcr_with_github_token`;
5. `test_workflow_tags_stable_and_prerelease_channels_safely`;
6. `test_workflow_builds_and_pushes_root_dockerfile_for_amd64_with_cache`;
7. `test_workflow_uses_expected_action_major_versions`.

Os nomes podem variar levemente apenas se continuarem autoexplicativos. Asserts devem ter mensagem de falha acionável.

O teste pode inspecionar texto/regex. Não deve:

- importar PyYAML não declarado;
- implementar parser YAML caseiro;
- reproduzir o workflow inteiro em snapshot;
- acessar rede/GitHub;
- exigir Docker para o pytest;
- executar ou publicar imagem.

### R8. Preservação de escopo

Somente estes arquivos funcionais podem ser criados:

1. `.github/workflows/release-image.yml`;
2. `tests/test_release_image_workflow.py`.

Também é obrigatório modificar apenas o status/checklists de:

3. `openspec/changes/publish-release-container-to-ghcr/tasks.md`.

Qualquer arquivo extra exige bloqueio e consulta ao planner, não apenas justificativa tardia, porque o design já cobre a entrega mínima. É proibido alterar:

- `Dockerfile`;
- `.dockerignore`;
- `docker-compose*.yml`;
- `pyproject.toml` ou `uv.lock`;
- `apps/`, `config/`, `templates/`, `static/`;
- models, migrations, FSM, permissões ou settings.

## TDD obrigatório: RED → GREEN → REFACTOR

### 1. Preparação e baseline

Sem editar:

```bash
git status --short
BASE_REF=$(git rev-parse HEAD)
printf 'BASE_REF=%s\n' "$BASE_REF"
uv run pytest
```

Se necessário, antes do baseline suba apenas o banco de teste conforme `AGENTS.md`. Não modifique configuração para contornar falha ambiental.

Registre no relatório:

- hash `BASE_REF`;
- exit code;
- resumo completo do pytest baseline;
- explicitamente `failed=0` e `errors=0`;
- número `passed_baseline`.

### 2. RED real

Crie apenas `tests/test_release_image_workflow.py` com os sete contratos de R7. Antes de criar o workflow, rode:

```bash
uv run pytest tests/test_release_image_workflow.py -v
```

Resultado obrigatório: exit code não zero e pelo menos um teste falhando pelo motivo esperado — ausência de `.github/workflows/release-image.yml` ou contrato ainda não satisfeito.

Cole no relatório o output relevante, nomes dos testes falhos e explique por que a falha prova o requisito. Não aceite RED por erro de import, sintaxe do teste, banco ou fixture.

### 3. GREEN mínimo

Crie `.github/workflows/release-image.yml` com R1–R6 e rode:

```bash
uv run pytest tests/test_release_image_workflow.py -v
```

Todos os testes alvo devem passar. Não altere o teste para aceitar contrato mais fraco do que proposal/design/spec.

### 4. REFACTOR seguro

Revise somente os dois arquivos:

- nomes e mensagens de asserts claros;
- sem strings críticas divergentes entre teste e workflow;
- sem helper genérico desnecessário;
- sem duplicação evitável dentro do teste;
- YAML legível, steps nomeados e sem comentários redundantes;
- sem trigger, tag, permission ou step futuro.

Rode novamente o teste alvo após qualquer refactor.

## Checks de inspeção obrigatórios antes de concluir

Execute todos os comandos abaixo e cole resultado + interpretação no relatório.

### I1. Contratos positivos do workflow

```bash
WORKFLOW=.github/workflows/release-image.yml
rg -n '^on:|^  release:|types: \[published\]|^permissions:|contents: read|packages: write' "$WORKFLOW"
rg -n 'ghcr\.io|github\.repository|docker/login-action@v3|github\.actor|secrets\.GITHUB_TOKEN' "$WORKFLOW"
rg -n 'docker/metadata-action@v5|tag_name|pattern=\{\{version\}\}|pattern=\{\{major\}\}\.\{\{minor\}\}|prerelease == false|latest=false|value=latest' "$WORKFLOW"
rg -n 'docker/build-push-action@v6|context: \.$|file: \./Dockerfile|push: true|pull: true|linux/amd64|cache-from: type=gha|cache-to: type=gha' "$WORKFLOW"
rg -n 'actions/checkout@v4|docker/setup-buildx-action@v3|cancel-in-progress: false|release-image-.*tag_name' "$WORKFLOW"
```

Interprete cada grupo: diga quais ocorrências correspondem a R1–R6 e confirme que não são apenas comentários.

### I2. Ausências críticas

```bash
if rg -n '^  (push|workflow_dispatch|pull_request|schedule):' "$WORKFLOW"; then
  echo 'ERRO: trigger fora de escopo encontrado'
  exit 1
else
  echo 'OK: nenhum trigger fora de release.published'
fi

if rg -n 'contents: write|write-all|GHCR_TOKEN|DOCKER_PASSWORD|build-args:|secrets:' "$WORKFLOW"; then
  echo 'ERRO: permissão/credencial/build secret fora do contrato'
  exit 1
else
  echo 'OK: nenhuma permissão ou credencial proibida'
fi

if rg --pcre2 -n 'pattern=\{\{major\}\}(?!\.\{\{minor\}\})' "$WORKFLOW"; then
  echo 'ERRO: alias somente de major encontrado'
  exit 1
else
  echo 'OK: nenhum alias somente de major'
fi
```

Observação: `push: true` dentro do step de build é obrigatório e não é trigger; o primeiro regex só aceita duas posições de indentação para detectar eventos top-level.

### I3. Escopo e integridade do diff

```bash
git diff --check
git diff --name-only "$BASE_REF" -- | sort
git status --short
```

Antes de marcar tasks, a lista deve conter apenas:

```text
.github/workflows/release-image.yml
openspec/changes/publish-release-container-to-ghcr/tasks.md
tests/test_release_image_workflow.py
```

Enquanto `tasks.md` ainda não tiver sido atualizado, é aceitável listar apenas os dois arquivos funcionais. Qualquer outro caminho torna o slice INCOMPLETO/BLOQUEADO.

### I4. Smoke build sem publicação

```bash
docker build --pull --tag ats-web:release-image-smoke .
```

Registrar exit code 0 e as últimas linhas que provam conclusão. Não executar `docker push`. Se Docker estiver indisponível, sem permissão ou o build falhar, o slice está INCOMPLETO/BLOQUEADO; não omita o gate.

### I5. Testes alvo após inspeção

```bash
uv run pytest tests/test_release_image_workflow.py -v
```

Registrar todos os testes e exit code 0.

## Critérios de sucesso binários

- [ ] S1. Baseline inicial foi executado em worktree limpo e passou com exit code 0, zero failures/errors.
- [ ] S2. RED real foi capturado antes de criar o workflow e falhou pelo contrato esperado, não por erro acidental.
- [ ] S3. `.github/workflows/release-image.yml` existe e usa somente `release.published`.
- [ ] S4. Concorrência é por `release.tag_name` e não cancela execução em andamento.
- [ ] S5. Permissões são somente `contents: read` e `packages: write`.
- [ ] S6. Login GHCR usa `github.actor` + `secrets.GITHUB_TOKEN`, sem PAT/secret customizado.
- [ ] S7. Nome da imagem é `ghcr.io/${{ github.repository }}`.
- [ ] S8. Release estável gera tag exata, SemVer normalizada, alias minor e `latest`.
- [ ] S9. Prerelease não atualiza alias minor nem `latest`.
- [ ] S10. Nenhum alias somente de major é configurado.
- [ ] S11. Build usa `context: .`, `./Dockerfile`, `push: true`, `pull: true` e `linux/amd64`.
- [ ] S12. Tags/labels vêm da metadata e cache GHA está configurado nos dois sentidos.
- [ ] S13. Os sete testes de contrato de R7 passam e não adicionam dependência.
- [ ] S14. Todos os checks `rg` foram executados e interpretados sem ocorrência proibida.
- [ ] S15. `git diff --check` e inspeção de arquivos alterados confirmam escopo R8.
- [ ] S16. Smoke build local concluiu com exit code 0 sem push.
- [ ] S17. Quality gate completo passou; pytest final tem zero failures/errors e `passed_final >= passed_baseline`.
- [ ] S18. Nenhum Dockerfile, Compose, dependência ou código da aplicação foi alterado.
- [ ] S19. Relatório temporário completo foi criado no caminho obrigatório.
- [ ] S20. `tasks.md` foi atualizado somente depois de S1–S19; commit e push foram realizados.

## Gates de autoavaliação

Responda objetivamente no relatório, citando teste, linha ou comando que prova cada resposta:

1. Qual evento exato dispara o workflow? Existe algum trigger além de `release.published`?
2. Draft ou simples `git push` de uma tag publica imagem? A resposta correta é não.
3. Quais são todas as permissões concedidas ao `GITHUB_TOKEN`? Existe alguma permissão além das duas projetadas?
4. Há qualquer PAT, `GHCR_TOKEN`, secret customizado ou credencial no build? A resposta correta é não.
5. Para `v1.2.3` estável, quais quatro tags são geradas segundo a configuração?
6. Para `v1.3.0-rc.1`, quais aliases estáveis são explicitamente bloqueados? Onde estão as duas condições?
7. Existe alias apenas de major (`1`/`{{major}}`)? A resposta correta é não.
8. Qual expressão forma o nome canônico da imagem? Ela resolve para qual nome neste repositório?
9. Qual plataforma é construída? QEMU ou multiarch foram adicionados? A resposta correta é somente `linux/amd64` e não.
10. O workflow usa tags e labels da mesma metadata action? Quais referências provam?
11. O cache GHA está configurado para leitura e escrita? Quais linhas provam?
12. Qual teste falhou no RED e por que a falha era semanticamente correta?
13. O teste usa somente stdlib? `pyproject.toml` e `uv.lock` permaneceram idênticos?
14. O smoke build prova o quê e o que ele não prova? Deve reconhecer que não valida autenticação/evento/push real no GitHub.
15. Quais arquivos mudaram desde `BASE_REF`? A lista coincide exatamente com R8?
16. `Dockerfile`, `.dockerignore` e todos os `docker-compose*.yml` permaneceram inalterados?
17. Alguma funcionalidade fora de escopo — deploy, migrations, multiarch, SBOM, assinatura, scan — foi antecipada? A resposta correta é não.
18. Pytest final teve exit code 0, `failed=0`, `errors=0` e total passed maior ou igual ao baseline? Informe números.
19. Qual é a limitação operacional restante antes de afirmar que uma imagem realmente existe no GHCR? Deve reconhecer a necessidade de publicar uma release após merge.

## Condições automáticas de INCOMPLETO

Marque o slice como **INCOMPLETE/BLOQUEADO**, não atualize `tasks.md` e não faça commit/push se ocorrer qualquer situação:

- worktree inicial não estava limpo;
- baseline `uv run pytest` não foi executado/registrado ou teve exit code diferente de 0, falha ou erro;
- teste planejado não foi escrito ou não foi executado;
- não houve RED real antes da criação do workflow;
- RED ocorreu por import/sintaxe/infraestrutura, e não pela ausência/violação do contrato;
- teste foi enfraquecido para fazer GREEN sem satisfazer proposal/design/spec;
- workflow usa trigger diferente ou adicional a `release.published`;
- prerelease pode atualizar `latest` ou alias `major.minor`;
- alias somente de major foi configurado;
- credencial diferente de `GITHUB_TOKEN` foi introduzida;
- permissão além de `contents: read` e `packages: write` foi concedida;
- `push: true`, plataforma, Dockerfile, metadata tags/labels ou cache exigido ficou ausente;
- qualquer check `rg` obrigatório não foi executado ou encontrou contrato proibido;
- `git diff --check` falhou;
- qualquer arquivo fora de R8 foi alterado;
- Docker smoke build não foi executado ou falhou;
- quality gate completo não foi executado;
- qualquer lint, format, mypy ou pytest falhou;
- pytest final teve exit code != 0, `failed > 0` ou `errors > 0`;
- `passed_final < passed_baseline`;
- relatório informa somente quantidade de passed sem registrar explicitamente exit code e zero failures/errors;
- limitação de não executar push real localmente foi ocultada;
- relatório temporário não existe no caminho exigido;
- relatório não contém snippets antes/depois, comandos de rerun ou `Handoff para verificador`;
- `tasks.md` foi marcado antes dos gates;
- commit/push foi feito apesar de gate faltante ou falho.

Em bloqueio ambiental, preserve evidências e responda com o motivo; não contorne removendo gate ou expandindo escopo.

## Quality gate obrigatório

Após GREEN, REFACTOR, inspeções e smoke build, execute separadamente para registrar cada exit code:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

Depois compare explicitamente:

```text
passed_final >= passed_baseline
failed_final = 0
errors_final = 0
exit_code_final = 0
```

Também execute:

```bash
git status --short
git diff --check
git diff --stat "$BASE_REF"
```

## Relatório markdown temporário obrigatório

Criar exatamente:

```text
/tmp/publish-release-container-to-ghcr-slice-001-report.md
```

O arquivo é temporário e não deve ser commitado. Estrutura mínima obrigatória:

```markdown
# Relatório — publish-release-container-to-ghcr — Slice 001

## Status
Status: COMPLETE | INCOMPLETE

## Identificação
- Branch:
- BASE_REF:
- Commit final:
- Push remoto:

## Matriz requisito → arquivo(s) → teste(s)/inspeção
| Requisito | Arquivos | Testes/inspeções | Resultado |
| --- | --- | --- | --- |

## Baseline antes de editar
- `git status --short`:
- `uv run pytest`:
- Exit code:
- Resumo: passed=?, failed=0, errors=0

## RED
- Estado do repositório nesse momento:
- Comando:
- Exit code:
- Teste(s) falhando:
- Motivo esperado:
- Trecho de output:

## GREEN
- Implementação mínima:
- Comando alvo:
- Exit code:
- Resumo:

## REFACTOR
- Limpezas realizadas:
- Confirmação DRY/YAGNI/sem escopo futuro:

## Snippets antes/depois
- Antes: evidência de ausência do workflow/teste ou `git show BASE_REF`:
- Depois: trigger/permissões:
- Depois: login/metadata/tags:
- Depois: build/push/cache:
- Depois: testes de contrato:

## Checks de inspeção obrigatórios
- I1 contratos positivos: comandos, outputs e interpretação
- I2 ausências críticas: comandos, outputs e interpretação
- I3 escopo/diff: comandos, outputs e interpretação
- I4 smoke build: comando, exit code e últimas linhas
- I5 pytest alvo: comando, exit code e resumo

## Pytest baseline vs final
- Baseline: exit code, passed, failed, errors
- Final: exit code, passed, failed, errors
- `passed_final >= passed_baseline`: Sim/Não

## Quality gate completo
- `uv run ruff check .`: exit code + resumo
- `uv run ruff format --check .`: exit code + resumo
- `uv run mypy .`: exit code + resumo
- `uv run pytest`: exit code + resumo
- `git diff --check`: exit code

## Snippet/diff de escopo
- Arquivos alterados desde BASE_REF:
- Justificativa: deve corresponder exatamente a R8
- Confirmação de arquivos proibidos inalterados:

## Gates de autoavaliação
1. ...
19. ...

## Limitações e riscos residuais
- Push real depende de release publicada após merge
- Visibilidade/pull do package depende de configuração administrativa
- Somente linux/amd64

## Handoff para verificador
- Arquivos alterados:
- Commit e branch remota:
- Comandos exatos para rerun:
- Evidência a conferir no GitHub após uma release real:
- Riscos/limitações:
- Checklist R1–R8:

## Resultado final
Status: COMPLETE
REPORT_PATH=/tmp/publish-release-container-to-ghcr-slice-001-report.md
```

O handoff ao verificador deve incluir, no mínimo, estes comandos de rerun:

```bash
uv run pytest tests/test_release_image_workflow.py -v
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
docker build --pull --tag ats-web:release-image-smoke .
git diff --check "$BASE_REF"..HEAD
git show --stat --oneline HEAD
```

Após uma release real futura, o verificador poderá conferir GitHub Actions/GHCR, mas isso não deve ser falsamente alegado como executado neste slice.

## Prompt pronto para implementador DeepSeek4-Flash

```text
Read completely: AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/publish-release-container-to-ghcr/proposal.md, design.md, specs/release-container-publication/spec.md, tasks.md, slices/slice-001-release-image-to-ghcr.md, Dockerfile and .dockerignore.

Implement ONLY Slice 001. Follow the DeepSeek4-Flash protocol literally: require a clean worktree, record BASE_REF, run the full pytest baseline before editing, create the contract tests first, capture a real RED for the missing workflow, implement the minimal workflow, capture GREEN, refactor safely, run every mandatory rg inspection, inspect changed-file scope, run git diff --check, perform the mandatory Docker smoke build, execute the complete quality gate, compare baseline vs final pytest, and create the evidence report.

Deliver the vertical flow GitHub Release published -> checkout -> Buildx -> GHCR login with GITHUB_TOKEN -> safe metadata tags -> linux/amd64 Docker build -> push. Create only .github/workflows/release-image.yml and tests/test_release_image_workflow.py, then update only this change's tasks.md after every gate passes.

Use release.published only. Grant only contents: read and packages: write. Publish ghcr.io/${{ github.repository }}. Use the exact release tag, normalized SemVer, stable major.minor alias and latest; both major.minor and latest must be disabled for prereleases. Do not create a major-only alias. Use actions/checkout@v4, docker/setup-buildx-action@v3, docker/login-action@v3, docker/metadata-action@v5 and docker/build-push-action@v6. Build context '.', file './Dockerfile', push/pull true, platform linux/amd64, metadata tags/labels and GHA cache.

Use TDD RED -> GREEN -> REFACTOR. Keep clean code, DRY and YAGNI. The test must use stdlib only and must not implement a YAML parser or access GitHub/network. Do not touch Dockerfile, .dockerignore, any docker-compose file, pyproject.toml, uv.lock, Django code, models, migrations, FSM, settings or deploy documentation. Do not add multiarch, auto-deploy, migrations, SBOM, signing, provenance, scans or custom secrets.

If baseline fails, RED is not semantic, any required inspection/smoke build/quality gate is missing or failing, pytest final has any failure/error or exit code != 0, passed_final < passed_baseline, a forbidden contract is found, or any extra file changes, report INCOMPLETE/BLOQUEADO. Do not update tasks.md and do not commit/push in that case.

If and only if all criteria pass: update openspec/changes/publish-release-container-to-ghcr/tasks.md, create /tmp/publish-release-container-to-ghcr-slice-001-report.md with baseline, RED/GREEN, before/after snippets, inspection outputs and interpretations, smoke build, full quality gate, pytest comparison, all self-evaluation answers, changed-file proof and Handoff para verificador. Commit with a traceable message such as `ci: publish release image to ghcr`, push the current branch, update the temporary report with commit/push evidence, reply exactly with REPORT_PATH=/tmp/publish-release-container-to-ghcr-slice-001-report.md, and STOP for planner review.
```
