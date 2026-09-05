# Proposal: Desabilitar causa de não realização quando o procedimento é realizado

**Change ID**: `followup-disable-cause-when-performed`
**Tipo**: QUICK bugfix (UI do formulário de follow-up)

## Why

Validação em produção (v0.6.0-rc.1, janela de 2026-09-05) constatou: após marcar **Realizado**, os radios de **Causa da não realização** continuam habilitados e selecionáveis (caso da ocorrência 4960219). O servidor se protege — o service normaliza os campos de causa para vazio quando `performed=True` (dados gravados ficaram íntegros; CheckConstraints seguram o resto) — mas a UI induz o supervisor a erro de entrada e à impressão de dado perdido.

## What Changes

- `templates/dashboard/followup_form.html`: o wrapper da seção de causa (`div.mb-2` que contém radios de `non_performance_reason` e os grupos condicionais de submotivo/texto) passa a ser `<fieldset data-followup-reason-section>` — desabilitável nativamente.
- `static/js/followup_form.js`: listener nos radios `performed`; quando **Realizado** marcado → `fieldset.disabled=true` (gray-out nativo de todos os radios/inputs de causa, submotivo e texto), desmarcar radios de causa e esconder grupos condicionais; quando **Não realizado** → reabilitar e aplicar a lógica atual de show/hide por causa. Estado inicial aplicado no load (inclui re-render pós-erro).
- Teste de template: formulário renderizado contém `data-followup-reason-section`.

Comportamento server-side permanece autoritativo e inalterado (normalização + validação + constraints); JS continua só apresentação (design D6).

### Impact

- 3 arquivos (JS, template, testes). Sem specs (`skip_specs: true`), sem models/migrations, sem mudança de contrato do form.

## Sucesso

Com "Realizado" marcado, os campos de causa ficam desabilitados e desmarcados (e não são submetidos); alternar de volta para "Não realizado" os reabilita; re-render pós-erro mantém o estado correto; suíte de dashboard verde.
