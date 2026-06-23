# Relatório Slice 002 — Labels downstream alinhados

## Resumo

Alinhada a nomenclatura downstream para o campo `doctor_observation`: todos os
badges, cards e labels visíveis ao usuário foram alterados de "Observação Médica"
/ "Obs. médica" para "Orientações médicas" / "Orientação médica".

Nenhuma lógica de negócio, modelo, migration, FSM ou comunicação operacional foi
alterada. Apenas nomenclatura em templates e asserts de testes.

## Arquivos tocados

| Arquivo | Mudança |
|---|---|
| `templates/intake/_my_cases_content.html` | Badge: `Obs. médica` → `Orientação médica` |
| `templates/intake/case_detail.html` | Card: `Observação Médica` → `Orientações médicas` |
| `templates/scheduler/_queue_content.html` | 2 badges + 1 label: `Obs. médica`/`Observação médica:` → `Orientação médica`/`Orientação médica:` |
| `templates/scheduler/confirm.html` | Label: `Observação Médica` → `Orientações médicas` |
| `templates/scheduler/confirm_post_schedule_issue.html` | Label: `Observação Médica` → `Orientações médicas` |
| `apps/intake/tests/test_my_cases.py` | Assert `Obs. médica` → `Orientação médica` |
| `apps/intake/tests/test_case_detail.py` | Asserts + docstring + data: `Observação Médica` → `Orientações médicas` |
| `apps/dashboard/tests/test_dashboard.py` | Assert `Observação Médica` → `Orientações médicas` (2 ocorrências) |
| `apps/scheduler/tests/test_views.py` | Asserts: `Obs. médica` → `Orientação médica`, `Observação médica:` → `Orientação médica:`, `Observação Médica` → `Orientações médicas` (4 ocorrências) |

## Snippets antes/depois dos labels principais

### intake/_my_cases_content.html (badge)
```diff
-<span class="badge bg-info text-dark ms-1">📝 Obs. médica</span>
+<span class="badge bg-info text-dark ms-1">📝 Orientação médica</span>
```

### intake/case_detail.html (card title)
```diff
-<h5 class="mb-3">📝 Observação Médica</h5>
+<h5 class="mb-3">📝 Orientações médicas</h5>
```

### scheduler/_queue_content.html (badge x2 + label)
```diff
-<span class="badge bg-info text-dark mb-2">📝 Obs. médica</span>
+<span class="badge bg-info text-dark mb-2">📝 Orientação médica</span>
-<strong>📝 Observação médica:</strong> {{ c.doctor_observation }}
+<strong>📝 Orientação médica:</strong> {{ c.doctor_observation }}
```

### scheduler/confirm.html e confirm_post_schedule_issue.html
```diff
-<div class="summary-label">Observação Médica</div>
+<div class="summary-label">Orientações médicas</div>
```

## Evidência TDD

### RED (antes da implementação): 5 testes falhando

| Teste | Motivo |
|---|---|
| `test_my_cases_shows_doctor_observation_badge...` | Badge ainda diz "Obs. médica" |
| `test_case_detail_shows_doctor_observation_for_manager_and_admin[manager]` | Card ainda diz "Observação Médica" |
| `test_case_detail_shows_doctor_observation_for_manager_and_admin[admin]` | Card ainda diz "Observação Médica" |
| `test_queue_shows_doctor_observation_badge_only_for_filled_pending_cases` | Badge pendentes ainda diz "Obs. médica" |
| `test_queue_shows_immediate_admission_doctor_observation_in_card` | Label imediata ainda diz "Observação médica:" |
| `test_confirm_shows_doctor_observation_when_filled` | Confirm ainda diz "Observação Médica" |

### GREEN (após implementação): todos passando

Todos os 9 testes que passaram na rodada final GREEN incluem os 5 que falharam em RED + 4 que sempre passaram (casos vazios/espaços).

## Busca de regressão textual

```bash
rg "Observação Médica|Obs\. médica|Observação médica" templates apps -g '*.html' -g '*.py'
```

Resultado:
```
apps/doctor/tests/test_views.py:        """R1: Form label shows 'Orientações...', not 'Observação Médica'."""
apps/doctor/tests/test_views.py:        assert "Observação Médica" not in content
```

**Análise:** As duas ocorrências restantes estão no teste do Slice 001 que
*verifica* que "Observação Médica" NÃO aparece na tela médica. São intencionais
e corretas. Nenhum label visível ao usuário usa nomenclatura antiga.

## Quality Gate

| Comando | Resultado |
|---|---|
| `ruff check .` | All checks passed ✅ |
| `ruff format --check .` | 165 files already formatted ✅ |
| `mypy .` | Success: no issues found ✅ |
| `pytest` | 1504 passed ✅ |

## Respostas aos Gates de Autoavaliação

1. **`rg` ainda encontra labels visíveis ao usuário?**
   Não. As duas únicas ocorrências restantes são no teste que *verifica a ausência*
   do label antigo na tela médica. Nenhum label visível ao usuário usa nomenclatura antiga.

2. **Quais templates downstream foram alterados?**
   5 templates: `intake/_my_cases_content.html`, `intake/case_detail.html`,
   `scheduler/_queue_content.html`, `scheduler/confirm.html`,
   `scheduler/confirm_post_schedule_issue.html`.

3. **Alguma view/service/model/migration foi alterada?**
   Não. Apenas templates e asserts de testes. Nenhum modelo, migration, FSM,
   serviço de comunicação, view ou query foi alterado.

4. **Como os testes provam que casos sem orientação não exibem badge/card vazio?**
   - `test_case_detail_hides_doctor_observation_card_when_empty_or_spaces`:
     verifica que `"Orientações médicas" not in content` para caso vazio e com espaços.
   - `test_confirm_hides_doctor_observation_when_empty_or_spaces`: idem.
   - `test_case_detail_hides_empty_doctor_observation_for_manager`: idem.

5. **Como os testes provam que NIR, scheduler e dashboard continuam vendo o texto completo?**
   - NIR: `test_case_detail_shows_doctor_observation` — verifica "Orientações médicas completas"
     e "Preservar quebras de linha." no conteúdo.
   - Dashboard: `test_case_detail_shows_doctor_observation_for_manager_and_admin` —
     verifica "Orientações médicas" e texto completo.
   - Scheduler queue: `test_queue_shows_doctor_observation_badge_only_for_filled_pending_cases`
     e `test_queue_shows_immediate_admission_doctor_observation_in_card` — verifica badges
     e texto completo.
   - Scheduler confirm: `test_confirm_shows_doctor_observation_when_filled` —
     verifica label "Orientações médicas" e texto completo.

6. **A nomenclatura escolhida é consistente entre badge e card?**
   Sim. Badges usam `Orientação médica` (singular, para badge compacto) e
   cards/blocos usam `Orientações médicas` (plural, para seção/título), mesma
   convenção do Slice 001.

## Riscos/Observações

- Nenhum dado foi migrado; casos antigos mantêm `doctor_observation` com nomenclatura
  antiga no storage, mas a UI sempre apresenta como "Orientação/Orientações médicas".
- Nenhuma lógica de negócio foi alterada.
- Change completo: Slice 001 + Slice 002 entregam o change `clarify-doctor-writing-ux`
  conforme DoD.
