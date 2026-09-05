# Slice 001 — Seção 6 do manual: Ações do usuário Supervisor

## Objetivo

Comportamento observável: o manual do usuário documenta a aba Follow-up do supervisor em uma nova seção de ações do usuário, com renumeração das seções gerais, mantendo todos os testes do manual verdes.

## Contexto necessário (ler antes de editar)

- `docs/manual/manual-usuarios.md` — estrutura atual: intro (lista 3 papéis operacionais, ~L5-15), 3 NIR, 4 Médico, 5 CHD, 6 Boas práticas (L1025+), 7 Observações finais (L1077+). Tom didático, imperativo, com passos numerados e regras destacadas.
- Fonte da verdade da feature: `openspec/specs/supervisor-appointment-follow-up/spec.md` (requisitos/cenários) e `openspec/archive/supervisor-appointment-follow-up/proposal.md` (escopo). Comportamento real: `/dashboard/follow-ups/` (aba no nav do dashboard, papéis manager/admin).
- Testes que precisam continuar verdes: `tests/test_user_manual_artifacts.py` (termos obrigatórios, PDF+TOC via `scripts/build_user_manual_pdf.py`), `tests/test_colonoscopy_rollout_docs.py`, `tests/test_combined_rollout_docs.py`.
- Não há referências cruzadas a "seção 6/7" no manual nem nos testes (renumerar é seguro).

## Requisitos verificáveis

- **R1** — Nova seção `# 6. Ações do usuário Supervisor` com `## 6.1 Registrar follow-up de agendamento` documentando: quando usar (desfecho do dia do exame), como abrir (Dashboard → Follow-up), o que a lista mostra (agendamentos confirmados + vindas imediatas autorizadas de hoje e ontem; seletor de data específica; busca por número da ocorrência ou nome; badge "Follow-up registrado/pendente"), como preencher (por procedimento: realizado; não realizado com causa — Absenteísmo / Cancelamento por falta de recursos no dia (urgências que ocuparam o horário, falta de tempo hábil, equipamento quebrado/não disponível) / Outras causas com descrição obrigatória; internação do paciente sempre informada), e o versionamento (salvar de novo cria nova versão; versões anteriores ficam preservadas com autor e data; puramente registro — não abre intercorrência nem reagenda).
- **R2** — Seções gerais renumeradas: "6. Boas práticas" → "7. Boas práticas" (subseções 6.1-6.4 → 7.1-7.4) e "7. Observações finais" → "8. Observações finais" (7.1-7.2 → 8.1-8.2).
- **R3** — Introdução atualizada: lista de papéis passa a citar também o Supervisor (registro de desfecho pós-exame), mantendo os três papéis operacionais como foco principal.
- **R4** — Testes do manual e lint do repo continuam verdes.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `docs/manual/manual-usuarios.md` | `rg "6. Ações do usuário Supervisor|6.1 Registrar follow-up" docs/manual/manual-usuarios.md` |
| R2 | idem | `rg "^# 7. Boas práticas|^# 8. Observações finais" docs/manual/manual-usuarios.md`; ausência de `^# 6. Boas práticas` |
| R3 | idem | inspeção (lista da intro) |
| R4 | — | `uv run pytest tests/test_user_manual_artifacts.py tests/test_colonoscopy_rollout_docs.py tests/test_combined_rollout_docs.py -q`; `uv run python scripts/build_user_manual_pdf.py` gera PDF com TOC (teste cobre); ruff/format se aplicável |

## Escopo e expected blast radius

```yaml
expected_files:
  - docs/manual/manual-usuarios.md

allowed_incidental_files:
  - docs/manual/dist/manual-usuarios.pdf   # se o PDF for regenerado na verificação

out_of_scope:
  - qualquer código/template/spec; outras seções do manual (além da renumeração R2/R3)
  - tasks.md (parent atualiza), commit/push (parent decide)
```

## Plano de testes do slice

### RED

Não há teste novo automatizado (documentação); a "prova" é a inspeção R1-R3 + suíte existente. `rg "6. Ações do usuário Supervisor" docs/manual/manual-usuarios.md` → vazio antes da edição.

### GREEN / verificação local

```bash
rg "6. Ações do usuário Supervisor" docs/manual/manual-usuarios.md   # ≥1
rg "^# 7. Boas práticas|^# 8. Observações finais" docs/manual/manual-usuarios.md  # ambos
uv run pytest tests/test_user_manual_artifacts.py tests/test_colonoscopy_rollout_docs.py tests/test_combined_rollout_docs.py -q   # exit 0
```

## Critérios de aceitação

- [ ] R1–R3 satisfeitos (seção completa, renumeração, intro).
- [ ] Suíte de docs/manual verde; PDF+TOC ok.
- [ ] Nenhum arquivo fora do blast radius.
