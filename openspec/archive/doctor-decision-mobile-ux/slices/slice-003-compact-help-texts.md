# Slice 003: Refinos finais de UX mobile da decisão médica

## Objetivo

Reduzir ruído visual e reforçar feedback de interação no mobile em três pontos da página de avaliação médica:

1. Ajuda da `Comunicação operacional` hoje exibida como `alert alert-info` permanente no partial compartilhado.
2. Ajuda `Precisa de mais informações?` hoje exibida como `alert alert-info` dentro do formulário de decisão.
3. Cards `Aceitar`/`Negar`, cujo radio button visual rouba atenção e cujo estado selecionado ainda pode ficar discreto demais.

As orientações devem continuar disponíveis de forma discreta, e a seleção da decisão deve ficar inequívoca.

## Pré-requisito

Implementar somente depois dos Slices 001 e 002 concluídos e revisados.

## Valor entregue

A página fica mais enxuta no mobile sem perder orientações importantes. O médico ainda encontra instruções sobre:

- quando usar comunicação operacional;
- diferença entre mensagem operacional e decisões formais;
- uso de menções `@nir`, `@medico`, `@chd`, `@supervisor`, `@admin`;
- o que fazer quando faltam documentos/dados para decidir;
- qual decisão inicial está selecionada, sem depender da bolinha do radio.

## Arquivos esperados

Tocar o mínimo necessário:

- `templates/cases/_communication_thread.html`
- `templates/doctor/decision.html`
- `static/css/app.css` somente para reforçar visual dos cards de decisão, com CSS mínimo e escopado
- teste novo ou existente em `apps/doctor/tests/test_views.py`, `apps/doctor/tests/test_communication_views.py` ou `tests/`

Para os textos de ajuda, evitar tocar `static/css/app.css`: preferir Bootstrap 5.3 e HTML nativo (`collapse` Bootstrap ou `<details>/<summary>`). Para os cards `Aceitar`/`Negar`, é aceitável ajustar o CSS existente de `.decision-option`/`.is-selected`, mantendo-o curto e escopado.

Não tocar:

- models/migrations/FSM;
- views/services;
- JS customizado, salvo se estritamente necessário. Bootstrap collapse já está disponível no projeto. Se o estado selecionado já é controlado por `decision.js`, reaproveitar a classe existente (`.is-selected`) em vez de criar novo mecanismo.

## Handoff / prompt para implementador LLM com contexto zero

> Leia `AGENTS.md`, `PROJECT_CONTEXT.md`, `openspec/changes/doctor-decision-mobile-ux/design.md` e este arquivo.
>
> Antes de codar, confirme que está no branch dedicado do change, por exemplo `change/doctor-decision-mobile-ux`. Faça commit e push deste slice nesse branch separado.
>
> Contexto: os Slices 001 e 002 já reposicionaram e melhoraram o formulário de decisão em `templates/doctor/decision.html`. Agora reduza o peso visual de dois textos de ajuda que ocupam muito espaço vertical no mobile.
>
> Elemento 1 — `templates/cases/_communication_thread.html`:
>
> Hoje existe um alerta fixo logo abaixo do título `Comunicação operacional`:
>
> ```html
> <div class="alert alert-info small mb-3 py-2">
>   Use este espaço para esclarecimentos e coordenação sobre este caso.
>   Decisões formais, agendamento e encerramento continuam nos fluxos estruturados.
>   Use <strong>@nir</strong>, <strong>@medico</strong>, <strong>@chd</strong>, <strong>@supervisor</strong> ou <strong>@admin</strong> para notificar equipes.
> </div>
> ```
>
> Substitua por uma ajuda discreta e clicável. Preferência: Bootstrap collapse com link/botão pequeno `Como usar?`, por exemplo:
>
> ```html
> <div class="d-flex justify-content-between align-items-start gap-2 mb-2">
>   <h5 class="mb-0">💬 Comunicação operacional</h5>
>   <button class="btn btn-link btn-sm p-0 text-decoration-none" type="button"
>           data-bs-toggle="collapse" data-bs-target="#communication-help"
>           aria-expanded="false" aria-controls="communication-help">
>     Como usar?
>   </button>
> </div>
> <div class="collapse" id="communication-help">
>   <div class="text-muted small mb-3">
>     ...texto completo...
>   </div>
> </div>
> ```
>
> Atenção: esse partial é reutilizado em outras telas. Use um `id` com baixa chance de conflito, por exemplo `case-communication-help`, e mantenha HTML válido caso o partial apareça uma vez por página. Não use tooltip por hover como solução principal, porque a tela alvo é mobile.
>
> Elemento 2 — `templates/doctor/decision.html`:
>
> Hoje existe um alerta fixo antes do bloco de `lock_error` e antes dos botões:
>
> ```html
> <div class="alert alert-info small mb-4 py-2" role="alert">
>   💬 <strong>Precisa de mais informações?</strong>
>   Se faltam documentos ou dados para decidir, envie uma mensagem na
>   <strong>Comunicação operacional</strong> marcando o <strong>NIR</strong>
>   e <strong>volte sem decidir</strong>.
>   Não use negativa apenas para solicitar complemento.
> </div>
> ```
>
> Remova esse alerta pesado dessa posição e coloque uma orientação compacta **abaixo dos botões** `[Confirmar decisão]` e `[Voltar sem decidir]`, conforme preferência do usuário. Exemplo alvo:
>
> ```html
> <div class="d-flex gap-2 btn-stack-mobile">
>   ...botões...
> </div>
>
> <div class="small text-muted mt-2">
>   💬 Faltam informações? Use a Comunicação operacional e volte sem decidir.
>   <a data-bs-toggle="collapse" href="#missing-info-help" role="button"
>      aria-expanded="false" aria-controls="missing-info-help">
>     Detalhes
>   </a>
>   <div class="collapse mt-2" id="missing-info-help">
>     Se faltam documentos ou dados para decidir, envie uma mensagem na Comunicação operacional
>     marcando o NIR e volte sem decidir. Não use negativa apenas para solicitar complemento.
>   </div>
> </div>
> ```
>
> Use Bootstrap/HTML simples. Mantenha o texto essencial visível em uma linha curta; detalhes ficam sob click/tap. Não dependa de hover.
>
> Elemento 3 — cards `Aceitar`/`Negar` em `templates/doctor/decision.html` + `static/css/app.css`:
>
> O radio button deve continuar existindo no HTML por semântica, acessibilidade e submissão, mas não precisa aparecer visualmente. O objetivo é que o card inteiro seja o controle principal.
>
> Recomendação de template:
>
> - manter `<input type="radio" name="decision" ...>`;
> - adicionar `visually-hidden` ao input, por exemplo `class="form-check-input visually-hidden"`;
> - manter `<label for="decision-accept">` e `<label for="decision-deny">` para que o clique/toque no card continue selecionando a opção;
> - adicionar badge/indicador no label, visível quando selecionado por CSS/estrutura, por exemplo `Selecionado`.
>
> Recomendação visual para card selecionado:
>
> - `Aceitar`: borda `var(--hospital-success)` mais grossa, fundo verde muito claro, título verde e badge/ícone `Selecionado`;
> - `Negar`: borda `var(--hospital-danger)` mais grossa, fundo vermelho muito claro, título vermelho e badge/ícone `Selecionado`;
> - usar box-shadow sutil se ajudar, sem fugir do estilo hospitalar.
>
> Exemplo conceitual de CSS escopado:
>
> ```css
> .decision-radio-group .decision-option {
>   border: 1px solid var(--hospital-border);
>   border-radius: 0.75rem;
>   transition: border-color 0.2s, background-color 0.2s, box-shadow 0.2s;
> }
>
> .decision-radio-group .decision-option.is-selected {
>   border-width: 2px;
>   box-shadow: 0 0 0 0.15rem rgba(11, 66, 99, 0.08);
> }
>
> .decision-radio-group .decision-option--accept.is-selected {
>   border-color: var(--hospital-success);
>   background-color: rgba(27, 122, 74, 0.08);
> }
>
> .decision-radio-group .decision-option--deny.is-selected {
>   border-color: var(--hospital-danger);
>   background-color: rgba(181, 53, 53, 0.08);
> }
> ```
>
> O implementador pode ajustar os seletores conforme o código atual, mas deve manter CSS mínimo, DRY e escopado. Não remover o input radio do DOM e não usar `display:none` se isso prejudicar acessibilidade/foco; prefira `visually-hidden` do Bootstrap.
>
> Princípios: Clean Code, DRY, You Aren't Gonna Need It. Não crie componente genérico, template tag ou JS novo para apenas estes refinamentos.

## TDD obrigatório

### RED

Antes da implementação, adicione testes que falhem. Sugestões mínimas:

1. Comunicação operacional:
   - renderizar a página médica ou testar o partial;
   - afirmar que existe `Como usar?`;
   - afirmar que existe `case-communication-help` ou id equivalente de collapse;
   - afirmar que o texto `Decisões formais, agendamento e encerramento continuam nos fluxos estruturados` continua presente;
   - afirmar que o bloco não usa mais `alert alert-info` para essa ajuda fixa.

2. Formulário de decisão — ajuda compacta:
   - renderizar a página médica;
   - afirmar que existe `Faltam informações?`;
   - afirmar que existe `Detalhes` e `missing-info-help` ou id equivalente;
   - afirmar que `Faltam informações?` aparece depois de `Voltar sem decidir` no HTML;
   - afirmar que o texto `Não use negativa apenas para solicitar complemento` continua presente em área colapsável;
   - afirmar que o antigo alerta `Precisa de mais informações?` não aparece como `alert alert-info` fixo.

3. Formulário de decisão — cards `Aceitar`/`Negar`:
   - renderizar a página médica;
   - afirmar que os radios continuam presentes com `type="radio"` e `name="decision"`;
   - afirmar que os radios têm `visually-hidden` ou classe acessível equivalente;
   - afirmar que existe texto/indicador `Selecionado` no markup dos cards;
   - teste estático de CSS: afirmar que `.decision-option.is-selected` usa `border-width: 2px` ou regra equivalente de borda mais espessa;
   - teste estático de CSS: afirmar uso de `--hospital-success`, `--hospital-danger` e fundo sutil (`rgba` ou classe equivalente) no estado selecionado.

### GREEN

Implementar o mínimo para os testes passarem, preservando a funcionalidade dos formulários e do collapse Bootstrap.

### REFACTOR

- Remover classes `alert alert-info` apenas dessas ajudas permanentes.
- Manter semântica e acessibilidade: `aria-expanded`, `aria-controls`, `type="button"` em botões.
- Garantir que textos longos fiquem fora do fluxo principal até o usuário tocar/clicar.
- Manter inputs radio acessíveis no DOM, mas sem aparecer visualmente como bolinha protagonista.
- Reforçar `.decision-option.is-selected` com borda mais grossa, fundo sutil, título colorido e badge/ícone.
- Não criar CSS para os textos de ajuda se Bootstrap resolver; para cards, limitar CSS ao bloco já existente de decisão.

## Critérios de aceitação

- [ ] Ajuda da `Comunicação operacional` vira acionador discreto `Como usar?` com conteúdo colapsável.
- [ ] Texto completo da ajuda operacional continua disponível.
- [ ] Orientação `Faltam informações?` fica abaixo dos botões `Confirmar decisão` e `Voltar sem decidir`.
- [ ] Texto detalhado `Não use negativa apenas para solicitar complemento` continua disponível via click/tap em `Detalhes`.
- [ ] Não há dependência de hover.
- [ ] Radio buttons continuam no HTML, mas são visualmente ocultos com `visually-hidden` ou equivalente acessível.
- [ ] Cards `Aceitar`/`Negar` selecionados têm borda mais grossa, fundo sutil, título colorido e indicador `Selecionado`.
- [ ] Não há JS customizado novo, salvo justificativa no relatório.
- [ ] CSS customizado novo é zero ou mínimo e escopado.
- [ ] Sem models/migrations/FSM.
- [ ] Fluxos dos Slices 001 e 002 continuam funcionando.

## Gates de autoavaliação

Antes de encerrar o slice, o implementador deve verificar:

- [ ] `uv run ruff check .` passou.
- [ ] `uv run ruff format --check .` passou.
- [ ] `uv run mypy .` passou.
- [ ] `uv run pytest` passou.
- [ ] Testei manualmente no mobile/DevTools o abre/fecha de `Como usar?`.
- [ ] Testei manualmente no mobile/DevTools o abre/fecha de `Detalhes` abaixo dos botões.
- [ ] Testei manualmente no mobile/DevTools que tocar em qualquer área dos cards `Aceitar`/`Negar` seleciona a opção.
- [ ] Conferi que o radio visual não rouba atenção e que o card selecionado fica inequívoco.
- [ ] Conferi que a página ficou visualmente mais curta antes de expandir as ajudas.
- [ ] Atualizei `openspec/changes/doctor-decision-mobile-ux/tasks.md` marcando este slice.
- [ ] Criei relatório markdown temporário com antes/depois e evidências.

## Relatório obrigatório para terceiro LLM

Criar um arquivo markdown temporário, por exemplo:

```text
tmp/doctor-decision-mobile-ux-slice-003-report.md
```

O relatório deve conter:

- resumo do objetivo;
- arquivos alterados;
- snippets antes/depois dos dois textos de ajuda;
- snippets antes/depois dos cards `Aceitar`/`Negar` e CSS de seleção;
- evidência de que `Faltam informações?` ficou abaixo dos botões;
- testes adicionados/alterados;
- resultado dos quality gates;
- checklist manual mobile;
- riscos remanescentes.

A resposta final do implementador deve incluir:

```text
REPORT_PATH=tmp/doctor-decision-mobile-ux-slice-003-report.md
```

Depois disso, parar e pedir confirmação explícita antes de qualquer follow-up.

## Commit sugerido

```text
style(doctor): compact decision help texts
```
