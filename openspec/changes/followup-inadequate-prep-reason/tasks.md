# Tasks: Causa "Preparo inadequado" no pós-procedimento

## Slices verticais (ordem executável)

- [x] Slice 001 — Causa "Preparo inadequado" end-to-end: enum + migração + gravação (service/form) + visibilidade no Histórico/CSV + manual (`slices/slice-001-preparo-inadequado.md`)

## Preflight (uma vez por change)

- [x] Working tree limpa em `main` @ `21d6348` (BASE_REF) — artefatos do change commitados no preflight (`docs(openspec): change followup-inadequate-prep-reason`)
- [x] Baseline verde conhecida: gate da estável v0.6.0 (deploy em produção, commit `21d6348`) — não repetir por slice
- [x] `openspec validate followup-inadequate-prep-reason` OK (--strict)
- [x] Review do change doc: r1 BLOCK (P1 handoff ausente + 2×P2) → corrigido pelo parent → r2 `Merge verdict: OK` sem novos achados (2026-09-08, subagent reviewer contexto fresco)

## Justificativa de blast radius ampliado (stop rule §6)

O Slice 001 declara 8 arquivos (> heurística ≤5), sendo **4 arquivos de
teste**, **1 migração auto-gerada** e **1 edição somente de comentário**: a
mudança real de código/conteúdo são ~3 arquivos (models.py com 1 linha +
docstring, manual §6 com ~6 linhas, views.py com 1 comentário). O
comportamento é único e end-to-end (a causa existe do formulário ao CSV ao
manual); fragmentá-lo criaria um slice 002 cujos testes de Histórico/CSV
passariam sem nenhuma edição de código (derivação do enum, design D5) —
fragmentação artificial proibida pela skill. O slice único também garante
que o repositório nunca fica num estado em que a causa grava mas não é
exibida/documentada.

## Registro de execução

### Slice 001

- Worker: RED confirmado (7 failed pelos motivos previstos no slice: `ValueError` enum fora em services/history-setup; `match` específico não bate na rejeição; opção ausente no GET; `200 != 302` no POST; assert do manual) → GREEN (7 passed, 143 passed nos módulos focados); `makemigrations cases --check` → "No changes detected"; ruff/format escopados OK; `mypy apps/cases apps/dashboard` OK (69 files). 8 arquivos exatamente no blast radius previsto, zero incidentais; diff de `views.py` = apenas o comentário.
- Review r1: `Merge verdict: OK` — sem achados; nenhuma validação adicional solicitada (1 rodada de review).
- Desvios: nenhum.

## Gate final (uma vez após todos os slices)

- [ ] `uv run ruff check . && uv run ruff format --check .`
- [ ] `uv run mypy .`
- [ ] `uv run pytest`
- [ ] `openspec validate followup-inadequate-prep-reason` OK
- [ ] Atualizar a enumeração de causas no Purpose da spec
  `supervisor-appointment-follow-up` no archive (convenção do projeto — D7)

## Definition of Done

- [ ] Causa "Preparo inadequado" gravável (service + form), com espelho em `CaseEvent` e submotivo/texto vazios
- [ ] Combinações inválidas (causa nova + submotivo/texto) rejeitadas com mensagens específicas
- [ ] Histórico: cards, filtro de causa e CSV exibem a causa nova sem edição de código nessas superfícies (D5)
- [ ] Manual §6 documenta a causa; teste de artefatos cobre
- [ ] Migração choices-only aplicada; constraints intactas
- [ ] Commits atômicos (parent, pós-review) + push conforme política do projeto
