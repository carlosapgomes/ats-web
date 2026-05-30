# Design: Exibição da Unidade de Origem nos Cards e Detalhes de Caso

## Contexto

O sistema extrai a unidade de origem dos encaminhamentos via LLM e armazena em `Case.structured_data.origin_context` (campos: `city`, `hospital`, `unit`, `state_uf`). O presenter `DoctorReportPresenter._build_origin_line()` já formata esses dados para o relatório médico, mas eles não são exibidos nas interfaces principais de listagem e detalhamento.

## Objetivo

1. Exibir a unidade de origem nos **cards de listagem** para NIR, Agendador e Médico
2. Exibir a unidade de origem nos **detalhes do caso** para Supervisor e Admin
3. Nos cards do NIR: **remover o case_id** (ID do BD) e **parar de truncar** o nome do paciente

## Decisões de Design

### Formato de exibição

**Cards (compacto):**
```
🏥 {hospital} · {unit}
```
Se não houver `hospital`, usa só `unit`. Se não houver `unit`, usa só `hospital`. Se nenhum, não exibe.

**Detalhes do caso (completo):**
```
{city} ({state_uf}) · {hospital} · {unit}
```

### Helper compartilhado

Método `Case.get_origin_unit_display(compact: bool = True) -> str` no model `Case`.
- Centraliza a lógica de extração
- Reutilizável por todas as views
- Testável em isolamento

### Slices

| # | Escopo | Arquivos |
|---|--------|----------|
| S1 | Helper + NIR cards (remove ID, destruncar, add origem) | `models.py`, `views.py`, 2 templates |
| S2 | Scheduler + Doctor cards | 2 `views.py`, 2 templates |
| S3 | Case detail Supervisor/Admin + dashboard table | `dashboard/views.py`, `case_detail.html`, `dashboard/index.html` |

## Não-escopo

- Alterar o presenter do médico (já tem `_build_origin_line`)
- Alterar a página de decisão médica (`decision.html`)
- Alterar a página de confirmação do agendador (`confirm.html`)
