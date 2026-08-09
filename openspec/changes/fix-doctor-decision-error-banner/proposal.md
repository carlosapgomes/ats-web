# Proposal: Banner de erro no topo da decisão médica em vez de scroll automático

**Change ID**: `fix-doctor-decision-error-banner`
**Fase**: bugfix de UX (QUICK — substitui mecanismo anterior que falhou em produção)
**Substitui**: comportamento entregue por `fix-doctor-decision-scroll-to-form-errors`
(scroll automático via `data-scroll-to-errors` + `scrollIntoView`), que não
produziu rolagem no teste manual em produção.

## Why

Após o deploy da `v0.3.0-rc.4`, o teste manual com múltiplos campos
obrigatórios vazios recarregou a página **sem rolar até o formulário** — o
comportamento permaneceu no topo. O scroll programático na carga revelou-se
frágil (timing de render/agentes de cache), enquanto a própria tela já possui
um padrão confiável de navegação por âncora nativa: o botão
“Decisão pendente · Ir para decisão” (`href="#doctor-decision-form"`).

Solução proposta pelo usuário e adotada: quando houver erro de validação,
exibir um **banner de erro no topo da página** com mensagem clara e botão de
âncora para o formulário — mecanismo determinístico, sem JS.

## What Changes

- Remove o marcador `data-scroll-to-errors` e o bloco de scroll em
  `static/js/decision.js`.
- Adiciona banner `alert-danger` no topo do conteúdo de
  `templates/doctor/decision.html` quando `form.errors` existe, com contagem
  de campos com erro e botão `Ir para o formulário` apontando para
  `#doctor-decision-form`.
- Testes SSR: banner presente em re-render de submit inválido; ausente em
  página sem erros; marcador de scroll removido.
- Spec `per-procedure-medical-decision`: requisito MODIFIED.

Fora de escopo: outras telas, validações, layout do formulário.

## Impact

- **Código**: `templates/doctor/decision.html`, `static/js/decision.js`,
  `apps/doctor/tests/test_views.py`.
- **Banco**: nenhuma migration.
- **Rollout**: próximo deploy; rollback por revert.
