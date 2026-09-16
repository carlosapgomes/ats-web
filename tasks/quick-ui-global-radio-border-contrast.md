# QUICK UI: contraste global da borda dos radio buttons

## Status

- [x] Concluído

## Classificação

- **Tipo:** QUICK bugfix simples e reversível de apresentação.
- **Risco:** baixo; altera somente o estado visual de repouso dos radio buttons.
- **Design separado:** dispensado pela exceção QUICK do `AGENTS.md`.

## Problema

No modo claro, radio buttons não selecionados herdam a borda clara do Bootstrap e quase desaparecem sobre superfícies brancas, especialmente na seleção de tipo de exame da tela de upload.

## Slice vertical

```text
Usuário abre qualquer formulário com radio buttons
→ controles não selecionados têm contorno perceptível
→ controles selecionados e foco preservam as cores hospitalares existentes
```

## Handoff para implementador LLM com contexto zero

1. Leia `AGENTS.md`, este arquivo, `static/css/app.css` na seção Forms e `apps/accounts/tests/test_templates.py`.
2. Faça TDD real: adicione primeiro uma guarda falhando para o token e para a regra global de repouso.
3. Crie `--hospital-control-border` com contraste mínimo 3:1 sobre branco.
4. Aplique `border: 2px solid var(--hospital-control-border)` somente a `.hospital-shell .form-check-input[type="radio"]`.
5. Preserve as regras existentes de `:checked` e `:focus`; não altere cards, templates ou outros controles.
6. Rode o teste focado e o quality gate completo.
7. Gere relatório temporário, faça commit/push e pare.

## Critérios de sucesso

- [x] Radio buttons não selecionados recebem borda global de 2 px.
- [x] A cor da borda tem contraste WCAG não textual de pelo menos 3:1 sobre branco.
- [x] Checkbox, card, markup e lógica permanecem inalterados.
- [x] Estados selecionado e foco continuam governados pelas regras hospitalares existentes.
- [x] Testes e quality gates passam.

## RED / GREEN

```bash
POSTGRES_TEST_HOST_PORT=55433 uv run pytest \
  apps/accounts/tests/test_templates.py -k "radio_border" -x
```

RED esperado: ausência do token/regra global. GREEN esperado: guardas aprovadas após a alteração mínima em `static/css/app.css`.

## Blast radius

- `static/css/app.css`
- `apps/accounts/tests/test_templates.py`
- este arquivo apenas para rastreabilidade/status

## Fora de escopo

- mudar o fundo dos cards;
- converter opções em tiles/chips;
- alterar tamanho dos controles;
- alterar checkboxes, templates, JavaScript ou backend.
