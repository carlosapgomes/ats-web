# Slice 001b: Remediação — restaurar empilhamento mobile das fileiras de ação de página

## Objetivo

O Slice 001 escopou `.d-flex.gap-2:has(> .btn) { flex-direction: column }` para `.case-card`, corrigindo o header. Porém, 7 templates de **ação de página** (pares Submit + Cancelar, vários `btn-lg`) dependiam do empilhamento vertical no mobile e o perderam — regressão de UX. Este slice restaura o comportamento via opt-in explícito da classe utilitária `.btn-stack-mobile` (já exposta no Slice 001).

## Arquivos (7 templates)

- `templates/doctor/decision.html` (linha 140)
- `templates/scheduler/confirm.html` (linha 169)
- `templates/scheduler/confirm_post_schedule_issue.html` (linha 208)
- `templates/intake/closed_case_detail.html` (linhas 215 e 340)
- `templates/intake/corrected_resubmission.html` (linha 121)
- `templates/admin_ui/prompt_create.html` (linha 67)
- `templates/admin_ui/user_form.html` (linha 147)
- `tests/test_css_has_scope.py` (extensão — teste de caracterização dos templates)

## Decisão

- **D1. Opt-in explícito via `.btn-stack-mobile`.** Mantém a filosofia do Slice 001 (sem seletor global) e documenta a intenção de UX mobile no próprio template.
- **D2. Apenas pares com 2+ botões.** Fileiras de 1 botão (ex.: `case_detail.html:436`, `context_detail.html:252`) não mudam visualmente ao empilhar — não tocadas.

## TDD

### RED

Estender `tests/test_css_has_scope.py` com `test_action_rows_have_btn_stack_mobile`, listando os 8 locais (7 templates) que devem conter `.btn-stack-mobile`.

### GREEN

Adicionar a classe aos 7 templates (8 ocorrências).

### REFACTOR

Nenhum — adição pontual e consistente.

## Critérios de sucesso

- [ ] Os 7 templates contêm `.btn-stack-mobile` nas fileiras de ação.
- [ ] Teste novo passa.
- [ ] `uv run pytest` verde.
- [ ] Quality gate completo.

## Gates de autoavaliação

- [ ] Fileiras de 1 botão não tocadas.
- [ ] Visual mobile (360px) dos `btn-lg` de decisão/confirmação volta a empilhar.
- [ ] Commit rastreável (`fix(ui): restore mobile button stacking on page action rows`).
