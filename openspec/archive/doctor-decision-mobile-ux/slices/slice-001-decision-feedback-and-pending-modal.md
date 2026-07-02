# Slice 001: Clareza imediata da decisão médica

## Objetivo

Resolver a confusão principal no mobile sem mover grandes blocos da página:

1. deixar inequívoco quando `Aceitar` ou `Negar` foi selecionado;
2. manter/revelar campos condicionais somente após decisão inicial;
3. trocar `Enviar Decisão` por `Confirmar decisão`;
4. remover o UUID técnico visível do formulário médico;
5. ao clicar em `Confirmar decisão` com pendências, abrir feedback global em modal, em vez de depender apenas de erro inline discreto;
6. preservar o modal final de confirmação já existente para o caso completo.

## Valor entregue

O médico não deve mais ficar em dúvida se clicou ou não em `Aceitar`/`Negar`, nem interpretar ausência de submissão como lentidão/bug quando há pendências de formulário.

## Arquivos esperados

Tocar o mínimo necessário:

- `templates/doctor/decision.html`
- `static/js/decision.js`
- `static/css/app.css`
- teste novo ou existente em `apps/doctor/tests/test_views.py` ou `tests/` para proteger HTML/JS/CSS

Não tocar:

- models/migrations/FSM;
- views backend, salvo se absolutamente necessário para teste de contexto;
- forms backend, exceto se aparecer bug real já coberto por teste.

## Handoff / prompt para implementador LLM com contexto zero

> Leia `AGENTS.md`, `PROJECT_CONTEXT.md` e este arquivo antes de implementar.
>
> Antes de codar, trabalhe em branch separado para este change, por exemplo `change/doctor-decision-mobile-ux` (`git checkout -b change/doctor-decision-mobile-ux` se ainda não existir). Faça commit e push do slice nesse branch dedicado.
>
> Contexto: a tela médica está em `templates/doctor/decision.html`. O formulário atual tem radios `#decision-accept` e `#decision-deny`, seções condicionais `#accept-section` e `#deny-section`, botão `#btn-submit` com texto `Enviar Decisão`, campo visível `ID do Caso` com `{{ case.case_id }}`, e modal Bootstrap `#confirm-modal`. O JS em `static/js/decision.js` intercepta submit, valida campos e só abre o modal se estiver tudo completo. Se faltar decisão/campo, hoje ele apenas mostra erro inline e retorna.
>
> Implemente uma melhoria enxuta, mobile-first e coerente com Bootstrap 5.3 + paleta hospitalar existente. Não adicione framework JS nem dependência.
>
> Requisitos:
>
> 1. No template, transforme os wrappers dos radios em cards selecionáveis com classes escopadas, por exemplo `decision-option decision-option--accept` e `decision-option decision-option--deny`. Mantenha os inputs radio reais por acessibilidade e submissão normal.
> 2. Quando uma opção estiver selecionada, o card inteiro deve ficar visualmente destacado. Pode usar JS para aplicar `.is-selected` no wrapper. Use cores existentes: `--hospital-success` para aceitar e `--hospital-danger` para negar, com fundo muito claro. Evite CSS extenso.
> 3. Adicione texto curto antes das opções: `Escolha Aceitar ou Negar para revelar os campos necessários.`
> 4. Mantenha a revelação progressiva atual: `accept-section` aparece só para aceite; `deny-section` só para negativa. Opcionalmente adicione subtítulos pequenos (`Dados para aceite`, `Motivo da negativa`) dentro das seções.
> 5. Remova do formulário o bloco visível `ID do Caso`/UUID. Não remova o uso interno de `case.case_id` em URLs, locks ou hidden fields.
> 6. Troque o texto do botão principal para `Confirmar decisão`.
> 7. Reutilize o modal existente `#confirm-modal` para dois estados:
>    - pendências: título `Decisão incompleta`, corpo com lista do que falta, botões `Voltar ao formulário` e `Sair sem decidir`;
>    - confirmação final: comportamento atual, com resumo da decisão e botões `Revisar`/`Confirmar Decisão`.
> 8. Clique em `Confirmar decisão` com pendências deve abrir o modal de pendências. Não deve submeter.
> 9. Clique em `Confirmar decisão` com formulário completo deve continuar abrindo o modal final e, após `Confirmar Decisão`, preservar `form.requestSubmit()` e `finalSubmitConfirmed`.
> 10. O botão pode ser desabilitado por lock operacional (`work_lock.js`) ou após envio final, mas não por simples ausência de decisão/campos.
>
> Princípios: Clean Code, DRY, You Aren't Gonna Need It. Prefira funções pequenas em `decision.js`, como `collectMissingItems()`, `showPendingModal(items)` e `showFinalConfirmModal(...)`. Não implemente wizard, sticky footer, AJAX ou autosave.

## TDD obrigatório

### RED

Antes da implementação, adicione testes que falhem. Sugestões mínimas:

1. Teste de template/HTML:
   - renderizar a página de decisão médica;
   - afirmar que contém `Confirmar decisão`;
   - afirmar que não contém o label visível `ID do Caso`;
   - afirmar que contém `decision-option--accept` e `decision-option--deny`.

2. Teste estático de JS:
   - ler `static/js/decision.js`;
   - afirmar presença de `Decisão incompleta`;
   - afirmar presença de `Sair sem decidir`;
   - afirmar que `form.requestSubmit()` continua presente.

3. Teste estático de CSS:
   - ler `static/css/app.css`;
   - afirmar presença de `.decision-option` / `.is-selected`;
   - afirmar uso de `--hospital-success` e `--hospital-danger` no bloco de decisão.

### GREEN

Implementar o mínimo para os testes passarem e validar manualmente o fluxo básico:

- sem decisão → modal de pendências lista `Escolha Aceitar ou Negar`;
- aceitar sem suporte/fluxo → modal lista campos pendentes;
- negar sem motivo → modal lista motivo pendente;
- formulário completo → modal final de confirmação.

### REFACTOR

- Remover duplicação no JS.
- Manter seletores escopados.
- Não aumentar complexidade do template além do necessário.
- Garantir que nomes de funções e classes sejam claros.

## Critérios de aceitação

- [ ] `Aceitar` selecionado é visualmente inequívoco no card inteiro.
- [ ] `Negar` selecionado é visualmente inequívoco no card inteiro.
- [ ] `accept-section` e `deny-section` continuam ocultas até decisão inicial.
- [ ] `Confirmar decisão` substitui `Enviar Decisão` no botão principal.
- [ ] UUID técnico não aparece como campo visível no formulário.
- [ ] Pendências de decisão/campos aparecem em modal global com lista objetiva.
- [ ] Modal final de confirmação continua funcionando quando o formulário está completo.
- [ ] `requestSubmit()` permanece no fluxo final.
- [ ] CSS customizado é mínimo, escopado e usa tokens da paleta hospitalar.
- [ ] Sem models/migrations/FSM.

## Gates de autoavaliação

Antes de encerrar o slice, o implementador deve verificar:

- [ ] `uv run ruff check .` passou.
- [ ] `uv run ruff format --check .` passou.
- [ ] `uv run mypy .` passou.
- [ ] `uv run pytest` passou.
- [ ] Testei manualmente no mobile/DevTools: clicar no card inteiro seleciona a decisão.
- [ ] Testei manualmente os 4 cenários: sem decisão, aceite incompleto, negativa incompleta, decisão completa.
- [ ] Não criei dependência nova nem framework JS.
- [ ] Não toquei em models/migrations/FSM.
- [ ] Atualizei `openspec/changes/doctor-decision-mobile-ux/tasks.md` marcando este slice.
- [ ] Criei relatório markdown temporário com antes/depois e evidências.

## Relatório obrigatório para terceiro LLM

Criar um arquivo markdown temporário, por exemplo:

```text
tmp/doctor-decision-mobile-ux-slice-001-report.md
```

O relatório deve conter:

- resumo do problema;
- arquivos alterados;
- snippets antes/depois do template, JS e CSS;
- testes adicionados/alterados;
- resultado dos quality gates;
- checklist manual mobile;
- riscos remanescentes.

A resposta final do implementador deve incluir:

```text
REPORT_PATH=tmp/doctor-decision-mobile-ux-slice-001-report.md
```

Depois disso, parar e pedir confirmação explícita antes de iniciar o Slice 002.

## Commit sugerido

```text
fix(doctor): clarify decision selection and pending feedback
```
