# Slice 002 — Manual §6 reescrito: Pós-Procedimento + Histórico & Exportação + acesso CHD

## Objetivo

O manual do usuário (servido in-app) passa a refletir a aba com o rótulo novo,
documenta a sub-aba "Histórico & Exportação" (pendência do DoD de
`supervisor-followup-history-export`) e o acesso restrito a supervisores do CHD
e admin — um único rewrite da seção 6.

## Contexto necessário

- Design: D4 (estrutura do rewrite) de `design.md` do change.
- `docs/manual/manual-usuarios.md` — §6 "Ações do usuário Supervisor"
  (~linhas 1030–1140) + referência na introdução (~linha 15). Todo o texto do
  manual vem deste arquivo (servido via `apps/accounts/manual.py`).
- Comportamento a documentar: specs aplicadas `supervisor-appointment-follow-up`
  e `supervisor-followup-history` (janela por data de grupo, versão corrente,
  cards, filtros de linha, CSV fiel aos filtros) e o acesso CHD vigente do
  change `followup-chd-access-guard`.
- Testes existentes: `tests/test_user_manual_artifacts.py`.

## Requisitos verificáveis

- R1 §6 reescrito conforme estrutura D4: quem acessa (CHD+admin), aba
  Registrar (renomeada), sub-aba Histórico & Exportação (novo), tom
  passo-a-passo preservado.
- R2 Introdução (~:15) sem "follow-up" e com o rótulo novo.
- R3 Nenhum "follow-up" visível no manual inteiro (case-insensitive).
- R4 `tests/test_user_manual_artifacts.py` estendido: §6 menciona
  "Pós-Procedimento", "Histórico & Exportação" e o acesso CHD; asserção
  anti-anglicismo para o manual.

## Matriz requisito -> arquivo -> teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1/R2/R3 | `docs/manual/manual-usuarios.md` | R4 + `rg -in "follow.?up" docs/manual/manual-usuarios.md` → zero |
| R4 | `tests/test_user_manual_artifacts.py` | `uv run pytest tests/test_user_manual_artifacts.py -q` |

```yaml
expected_files:
  - docs/manual/manual-usuarios.md
  - tests/test_user_manual_artifacts.py

allowed_incidental_files: []

out_of_scope:
  - qualquer template/código (slice 001 encerrado)
  - outras seções do manual além de §6 e da referência de introdução
  - apps/accounts/manual.py (mecânica de servir; sem mudança)
```

## Plano de testes do slice

### RED

- comando: `uv run pytest tests/test_user_manual_artifacts.py -q`
- falha esperada: novos asserts falham — manual ainda usa "follow-up" em §6 e
  não documenta "Histórico & Exportação".

### GREEN / verificação local

- `uv run pytest tests/test_user_manual_artifacts.py -q` — exit 0
- `uv run pytest tests/ -q` — exit 0 (suíte de testes de docs/artefatos)
- `rg -in "follow.?up" docs/manual/manual-usuarios.md` — saída vazia

## Critérios de aceitação

- [ ] §6 cobre Registrar + Histórico & Exportação + acesso CHD com tom do manual
- [ ] Manual sem anglicismo (grep verde)
- [ ] Testes de manual estendidos e verdes
- [ ] Blast radius = 2 arquivos
