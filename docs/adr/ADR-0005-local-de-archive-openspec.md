# ADR-0005: Local de archive dos changes OpenSpec

## Status

Accepted

**Aceita em:** 2026-08-18

**Change associado:**
[`dashboard-active-cases-compact-pagination`](../../openspec/archive/dashboard-active-cases-compact-pagination/proposal.md)
(incidente que motivou a decisão, durante a release `v0.4.0-rc.1`).

## Contexto

O projeto usa o CLI `@fission-ai/openspec` (1.4.1) para spec-driven development.
A convenção histórica do repositório — consolidada em mais de 75 changes
arquivados e referenciada pelos Release Evidence Packs e por ADRs anteriores
(por exemplo, ADR-0004) — é versionar archives em:

```text
openspec/archive/<change-name>/
```

O CLI, porém, grava o archive em um caminho **hardcoded** (verificado no
código-fonte, `dist/core/archive.js`: `path.join(changesDir, 'archive')` com
prefixo de data):

```text
openspec/changes/archive/YYYY-MM-DD-<change-name>/
```

Não existe opção de configuração (global ou por projeto) para alterar esse
caminho na versão 1.4.1 — `openspec config` não expõe chave para o local de
archive.

Agravando o problema, o `.gitignore` do repositório exclui
`openspec/changes/archive/`, pois a convenção original do CLI tratava o
archive como artefato local não versionado. Resultado do incidente real em
2026-08-18: ao executar `openspec archive
dashboard-active-cases-compact-pagination`, o change saiu de
`openspec/changes/` e caiu em diretório invisível ao Git; o archive foi
resgatado com move manual para `openspec/archive/` (commit `3b8d7a9`, que o
Git registrou como rename, preservando histórico). Sem a correção manual, o
archive teria sido perdido do repositório.

Requisitos não negociáveis:

- Archives são patrimônio auditável do projeto público: devem ser versionados.
- Links existentes em `docs/releases/*.md` e ADRs apontam para
  `openspec/archive/<change-name>/` e não podem quebrar.
- O fluxo de archive deve ser à prova de esquecimento: falhar alto e cedo,
  não silenciosamente.

## Decisão

1. **Manter a convenção do repositório** `openspec/archive/<change-name>/`
   (sem prefixo de data) como único local versionado de archives OpenSpec.

2. **Não invocar `openspec archive` diretamente** para changes reais. Usar o
   wrapper `scripts/openspec-archive.sh <change-name> [opções]`, que:
   - valida a existência do change em `openspec/changes/<change-name>/`;
   - executa `openspec archive <change-name> "$@"`;
   - localiza o diretório criado em `openspec/changes/archive/`;
   - move para `openspec/archive/<change-name>/`, falhando com erro se o
     destino já existir ou o diretório de origem não for encontrado;
   - imprime o caminho final e lembra de commitar o resultado.

3. **Manter `openspec/changes/archive/` no `.gitignore`** como tripwire: se
   alguém rodar o CLI puro e esquecer de mover, o Git exibirá as deleções do
   change em `openspec/changes/` (sinal visível de que algo incompleto
   aconteceu) e o archive esquecido ficará apenas local, sem poluir o repo.

4. A promoção de specs (`openspec/specs/`) feita pelo comando `archive`
   permanece válida e inalterada; o wrapper não interfere nela.

## Alternativas Consideradas

1. **Adotar a convenção do CLI** (`openspec/changes/archive/`, remover a
   entrada do `.gitignore`):
   - **Vantagens**: zero manutenção de wrapper; caminho nativo em upgrades do
     CLI.
   - **Desvantagens**: quebra dezenas de links em `docs/releases/*.md` e
     ADRs; bifurca a convenção (75+ archives antigos no caminho novo ficariam
     órfãos ou exigiriam migração em massa); o prefixo de data no nome
     conflita com os nomes canônicos usados na rastreabilidade.
   - **Por que não escolhida**: custo de migração e quebra de rastreabilidade
     superam o benefício.

2. **Move manual documentado apenas nesta ADR** (sem wrapper):
   - **Vantagens**: nenhum código adicional.
   - **Desvantagens**: dependente de memória humana; o esquecimento volta a
     produzir archive invisível ao Git — exatamente o incidente que motivou
     a decisão.
   - **Por que não escolhida**: viola o requisito de falhar alto e cedo.

3. **Pinar/forkar o CLI** para tornar o caminho configurável upstream:
   - **Vantagens**: solução "definitiva".
   - **Desvantagens**: manutenção de fork, risco em upgrades, alteração
     externa fora do controle do projeto para um problema de uma linha.
   - **Por que não escolhida**: YAGNI; o wrapper resolve com complexidade
     mínima. Reavaliar se uma versão futura do CLI vier a suportar
     configuração do caminho (então o wrapper se torna um alias fino ou é
     removido).

## Consequências

### Positivas

- Convenção única de archive, versionada e rastreável, sem quebra de links
  históricos.
- Fluxo automatizado e à prova de esquecimento: o wrapper falha com erro
  claro antes de qualquer perda silenciosa.
- `.gitignore` continua protegendo o repositório de archives não movidos.
- O wrapper preserva as opções do CLI (por exemplo, `--skip-specs`,
  `--no-validate`) via repasse de argumentos.

### Negativas/Trade-offs

- O wrapper é convenção local: novos colaboradores precisam conhecê-lo
  (mitigado pelo registro desta ADR e pela mensagem do próprio CLI ao ser
  usado diretamente em changes reais não existir — aceitamos o risco
  residual do tripwire).
- Upgrades do CLI podem alterar o comportamento interno do archive (mitigação:
  o wrapper valida a existência do diretório de origem após a execução e
  falha alto se não encontrá-lo).

### Riscos e Mitigações

- **Risco**: execução de `openspec archive` puro (bypassando o wrapper)
  **Mitigação**: tripwire do `.gitignore` + revisão de PR (deleções em
  `openspec/changes/` sem adição em `openspec/archive/` são sinal de alerta).
- **Risco**: mudança de formato do archive pelo CLI em upgrades
  **Mitigação**: wrapper valida o resultado pós-execução; testar o wrapper ao
  atualizar o CLI.

## Histórico de Mudanças

- 2026-08-18: Criada após incidente de archive invisível ao Git na release
  `v0.4.0-rc.1` (resgate manual no commit `3b8d7a9`).
