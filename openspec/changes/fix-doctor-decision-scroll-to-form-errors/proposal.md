# Proposal: Rolar até o formulário de decisão médica após erro de validação

**Change ID**: `fix-doctor-decision-scroll-to-form-errors`
**Fase**: bugfix de UX (QUICK — simples, localizado e reversível)
**Classificação**: ESSENTIAL/QUICK por análise manual (script de risco deu
falso positivo CRITICAL por keywords; sem auth, dados persistidos, API
externa, segurança ou migração; 3 arquivos; rollback trivial). Sem
`design.md` conforme política para QUICK.

## Why

Na tela de decisão do médico (`templates/doctor/decision.html`), o formulário
(`#decision-form`, card `#doctor-decision-form`) fica abaixo do resumo
clínico/laudo. Quando o submit tem erro de validação, a resposta SSR
re-renderiza a página completa e o navegador volta ao topo: o médico não vê
as mensagens de erro (`is-invalid`/`invalid-feedback`) nem os valores
preservados, deteriorando a UX e levando a reenvios confusos.

## What Changes

- O `<form id="decision-form">` recebe o marcador `data-scroll-to-errors`
  quando `form.errors` não está vazio (renderização server-side, testável).
- `static/js/decision.js`, na inicialização, detecta o marcador e rola
  suavemente até o primeiro campo `.is-invalid` dentro do formulário, dando
  foco sem novo salto de rolagem.
- Teste SSR: POST inválido re-renderiza com o marcador; página sem erros não
  o contém.

Fora de escopo: outras telas com formulário (podem receber o mesmo padrão em
change futuro), mudança de validação ou de layout.

## Impact

- **Código**: `templates/doctor/decision.html`, `static/js/decision.js`,
  `apps/doctor/tests/test_views.py`.
- **Banco**: nenhuma migration.
- **Rollout**: junto do próximo deploy (rebuild); sem etapa especial.
- **Rollback**: revert; sem efeito sobre dados.
