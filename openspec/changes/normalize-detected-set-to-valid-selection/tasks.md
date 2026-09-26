# Tasks: Conjunto detectado normalizado para seleção válida

## 0. Precondições do change

- [x] 0.1 Aceite humano da `ADR-0011` (`docs/adr/ADR-0011-conjunto-detectado-
  normalizado-para-selecao-valida.md`): mudar status para `Accepted`,
  registrar histórico e verificar o índice `docs/adr/README.md` antes de
  qualquer código. *(Aceita pelo operador em 2026-09-26; status Accepted +
  histórico com a revisão de planejamento incorporada; índice atualizado.)*
- [x] 0.2 Criar `feature/normalize-detected-set-to-valid-selection` a partir
  do `main` (`53d7967`), registrar `BASE_REF` e confirmar working tree
  adequada. Baseline confiável: gate do rc.3 (suíte completa 4541 passed,
  `docs/releases/2026-09-26_v0.10.0-rc.3.md`) + guarda focada do rc.4
  (69 passed em `test_exam_type_correction.py`, incluindo guarda nova);
  reexecutar a suíte só se a tree divergir em código. Neste host o pytest
  exige `POSTGRES_TEST_HOST_PORT=55433` (porta 5433 pertence a outro
  projeto). *(BASE_REF `53d7967` — main avançou além do `212014d` com o
  change `detect-report-body-procedure-clues` (rc.2), hardening 1.0 (rc.3) e
  fix de template do card (rc.4) de outra sessão; âncoras dos slices
  reverificadas contra `53d7967`, com Ponto B corrigido para a matriz do
  detectado `:535-543`. Coordenação: change ativo
  `followup-body-clue-detection-hardening` itens 1.1-1.3 pendentes — sem
  conflito de requirements; item 1.3 (polimento card/reason_text) deve ser
  reavaliado após este change.)*

## 1. Slices

- [x] 1.1 Implementar o Slice 001
  (`slices/slice-001-best-covering-helper.md`) e provar a tabela verdade
  exaustiva de `best_covering_selection` (absorção base⊂pacote; `invalid`
  para não-cobertos; sem imports de `apps.pipeline` em produção).
  *(1 rodada de review, veredito `OK with notes`, 0 P0/P1. P2s: linha do
  índice ADR fora do blast radius do slice (decisão: commit próprio de
  docs, precondição 0.1) e wording de R4 emendado para "código de
  produção" (import em teste é aceitável para o pin anti-drift).
  Validação parent: 43 passed novos; 860 passed em apps/cases; mypy 66
  arquivos; ruff/format OK.)*
- [x] 1.2 Implementar o Slice 002
  (`slices/slice-002-declared-aware-conflict-gate.md`) e provar: regra
  declarado-aware (`any_set ≠ ∅` + `declared == best`) nos DOIS pontos,
  payload normalizado só fora da matriz, evento bruto em todos os desfechos,
  fail-closed da coincidência sem evidência atual intacto e a regressão
  end-to-end do beco sem saída (correção para `eda_dilation` prossegue até
  `WAIT_DOCTOR` com LLM2 e evento bruto).
  *(1 rodada de review, veredito `OK with notes`, 0 P0/P1 + micro-fix de
  validação do parent: mypy `attr-defined` no pin anti-drift (import
  estático → introspecção runtime), sem mudança semântica. Durante a
  implementação o worker escalou um 3º teste simétrico (reto) que flipped
  pelo Ponto B — decisão de planner: re-baseline intencional (regra genérica
  D2); D7/R3 emendados. P2s diferidos: pin de teste para a classe "negado
  coberto por declarado mais amplo com any≠∅" (sancionada pela ADR dec.2);
  `conflicting_evidence_types or detected` conflita vazio-não-setado
  (latente, sem 3º caller); nomes antigos no D7 corrigidos. Validação
  parent: 188 passed focados; 892 pipeline+correção; mypy 129 arquivos;
  ruff/format OK.)*
- [x] 1.3 Implementar o Slice 003
  (`slices/slice-003-correction-card-label.md`) e provar o label sem
  duplicação de base (unit + card), incluindo o caso inválido com dois
  pacotes (" e ").
  *(1 rodada de review, veredito `OK with notes`, 0 P0/P1. P2s diferidos:
  assert positivo do card não-escopado à célula "Tipo detectado" (a string
  também aparece como option do combobox — endurecer com regex na
  próxima passada no arquivo); separadores mistos ≥2 pacotes + identidade;
  ordem não-determinística de códigos desconhecidos (pré-existente);
  consolidação da projeção order→label (3 lugares) como follow-up em
  apps.cases. Validação parent: 83 passed focados; ruff/format/mypy OK.)*

## 2. Gate final e encerramento

- [x] 2.1 Gate global: `uv run ruff check . && uv run ruff format --check .`
  e `uv run mypy .` e `POSTGRES_TEST_HOST_PORT=55433 uv run pytest` e
  `node --test static/js/tests/*.test.js`.
  *(2026-09-26: ruff/format OK; mypy 324 arquivos sem issues; node exit 0;
  pytest 4602 passed — baseline ~4542 (rc.3 4541 + guarda rc.4) + 60 novos,
  0 falhas.)*
- [x] 2.2 `openspec validate --strict`; atualizar o histórico da ADR-0011
  (implementada); commit dos artefatos de planejamento + ADR no
  encerramento (política do projeto).
  *(valid; histórico da ADR com nota de implementação; artefatos commitados
  no encerramento do change.)*
- [ ] 2.3 Evidência operacional: reproduzir o cenário do caso real em
  ambiente de validação (fixture sintética; SEM dados de paciente real no
  repo) e registrar no relatório final — em produção, o caso preso deve ser
  re-corrigido pelo NIR após o deploy e prosseguir (fase de smoke do fix).
- [ ] 2.4 Nota de deploy: entra na sequência da `v0.10.0-rc.2` (junto das
  affordances já mergeadas); sem migrations novas previstas — confirmar no
  slice 002 (qualquer migração imprevista = escalonamento imediato).
