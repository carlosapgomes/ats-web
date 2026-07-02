# Slice 004: Compactar ajuda do campo de orientações do aceite

## Objetivo

Reduzir mais um texto de ajuda longo que ocupa espaço vertical no formulário de decisão médica, mantendo a orientação essencial disponível.

Campo alvo no formulário de aceite:

```html
<div class="form-text">Opcional. Use para orientações que devem acompanhar o aceite, como suporte, preparo, prioridade ou cuidados no agendamento/execução. Para pedir documentos ou avisar outra equipe, use a comunicação operacional. Máx. 500 caracteres.</div>
```

Esse texto é útil, mas longo demais para ficar permanentemente expandido no mobile.

## Pré-requisito

Implementar após o Slice 003 concluído. Este é um follow-up pequeno, ideal para o mesmo LLM implementador se ele ainda estiver com o contexto do Slice 003.

## Valor entregue

O formulário de decisão fica mais compacto sem perder a orientação operacional importante:

- o médico continua vendo que o campo é opcional e limitado a 500 caracteres;
- o médico continua sendo alertado, em texto curto visível, de que pedidos de documentos devem ir para Comunicação operacional;
- exemplos detalhados ficam disponíveis por click/tap em `Detalhes`.

## Arquivos esperados

Tocar o mínimo necessário:

- `templates/doctor/decision.html`
- opcionalmente `apps/doctor/forms.py`, se optar por encurtar `form.observation.help_text` na fonte
- teste novo/ajustado em `apps/doctor/tests/test_views.py` ou teste estático equivalente

Evitar tocar:

- `static/css/app.css`;
- `static/js/decision.js`;
- models/migrations/FSM;
- views/services.

Preferir Bootstrap collapse ou `<details>/<summary>`. Não usar tooltip/hover como solução principal, porque a tela alvo é mobile.

## Handoff / prompt para implementador LLM com contexto zero

> Leia `AGENTS.md`, `PROJECT_CONTEXT.md`, `openspec/changes/doctor-decision-mobile-ux/design.md` e este arquivo.
>
> Antes de codar, confirme que está no branch dedicado do change, por exemplo `change/doctor-decision-mobile-ux`. Faça commit e push deste slice nesse branch separado.
>
> Contexto: o Slice 003 compactou outros textos de ajuda e reforçou os cards `Aceitar`/`Negar`. Agora faça um follow-up pequeno no campo `Orientações para agendamento/execução`, dentro da seção de aceite em `templates/doctor/decision.html`.
>
> Hoje o template renderiza:
>
> ```html
> <div class="form-text">{{ form.observation.help_text }}</div>
> ```
>
> E `apps/doctor/forms.py` define um `help_text` longo:
>
> ```text
> Opcional. Use para orientações que devem acompanhar o aceite, como suporte, preparo, prioridade ou cuidados no agendamento/execução. Para pedir documentos ou avisar outra equipe, use a comunicação operacional. Máx. 500 caracteres.
> ```
>
> Requisito de UX:
>
> 1. Trocar o texto permanentemente visível por uma versão curta:
>
> ```text
> Opcional · Máx. 500 caracteres. Para pedir documentos, use Comunicação operacional.
> ```
>
> 2. Adicionar link/botão `Detalhes` por click/tap, abrindo conteúdo colapsável com exemplos:
>
> ```text
> Exemplos de uso: suporte, preparo, prioridade ou cuidados no agendamento/execução. Este campo acompanha o aceite. Para pedir documentos ou avisar outra equipe, use Comunicação operacional.
> ```
>
> 3. Não depender de hover.
> 4. Não criar JS customizado; Bootstrap collapse já está disponível.
> 5. Não criar CSS customizado salvo necessidade real.
>
> Implementação sugerida no template:
>
> ```html
> <div class="form-text">
>   Opcional · Máx. 500 caracteres. Para pedir documentos, use Comunicação operacional.
>   <a data-bs-toggle="collapse" href="#doctor-observation-help" role="button"
>      aria-expanded="false" aria-controls="doctor-observation-help">
>     Detalhes
>   </a>
>   <div class="collapse mt-1" id="doctor-observation-help">
>     Exemplos de uso: suporte, preparo, prioridade ou cuidados no agendamento/execução.
>     Este campo acompanha o aceite. Para pedir documentos ou avisar outra equipe,
>     use Comunicação operacional.
>   </div>
> </div>
> ```
>
> Opção aceitável: encurtar `help_text` em `apps/doctor/forms.py` para a versão curta e usar `{{ form.observation.help_text }}` no template, adicionando só o collapse de detalhes hardcoded. Mantenha DRY de forma pragmática; não crie abstração nova só para esta copy.
>
> Princípios: Clean Code, DRY, You Aren't Gonna Need It. Este é um refinamento pequeno; não amplie escopo.

## TDD obrigatório

### RED

Antes da implementação, adicione testes que falhem. Sugestões mínimas:

1. Renderizar a página médica.
2. Afirmar que existe a copy curta:

```text
Opcional · Máx. 500 caracteres. Para pedir documentos, use Comunicação operacional.
```

3. Afirmar que existe `Detalhes` e `doctor-observation-help` ou id equivalente.
4. Afirmar que o texto detalhado com `suporte, preparo, prioridade ou cuidados` continua presente, mas em área colapsável.
5. Afirmar que o texto longo antigo não aparece como uma única `form-text` permanente antes do collapse.
6. Afirmar que o label `Orientações para agendamento/execução` continua presente.

### GREEN

Implementar o mínimo para os testes passarem.

### REFACTOR

- Manter markup simples e acessível (`aria-expanded`, `aria-controls`).
- Não criar CSS/JS desnecessário.
- Manter o campo dentro da seção de aceite.
- Preservar `maxlength="500"`, placeholder e validação existentes.

## Critérios de aceitação

- [ ] Texto visível do campo é curto e ocupa pouco espaço vertical.
- [ ] `Detalhes` mostra exemplos de uso por click/tap.
- [ ] A frase sobre pedidos de documentos irem para Comunicação operacional permanece visível de forma resumida.
- [ ] Não há dependência de hover.
- [ ] Sem JS customizado novo.
- [ ] Sem CSS customizado novo, salvo justificativa no relatório.
- [ ] Sem models/migrations/FSM.
- [ ] Fluxos dos Slices 001–003 continuam funcionando.

## Gates de autoavaliação

Antes de encerrar o slice, o implementador deve verificar:

- [ ] `uv run ruff check .` passou.
- [ ] `uv run ruff format --check .` passou.
- [ ] `uv run mypy .` passou.
- [ ] `uv run pytest` passou.
- [ ] Testei manualmente no mobile/DevTools o abre/fecha de `Detalhes` do campo de orientações.
- [ ] Conferi que o campo de orientações ocupa menos altura antes de expandir.
- [ ] Atualizei `openspec/changes/doctor-decision-mobile-ux/tasks.md` marcando este slice.
- [ ] Criei relatório markdown temporário com antes/depois e evidências.

## Relatório obrigatório para terceiro LLM

Criar um arquivo markdown temporário, por exemplo:

```text
tmp/doctor-decision-mobile-ux-slice-004-report.md
```

O relatório deve conter:

- resumo do objetivo;
- arquivos alterados;
- snippets antes/depois do help text do campo de orientações;
- testes adicionados/alterados;
- resultado dos quality gates;
- checklist manual mobile;
- riscos remanescentes.

A resposta final do implementador deve incluir:

```text
REPORT_PATH=tmp/doctor-decision-mobile-ux-slice-004-report.md
```

Depois disso, parar e pedir confirmação explícita antes de qualquer follow-up.

## Commit sugerido

```text
style(doctor): compact acceptance orientation help text
```
