# Slice 002: Ordem de leitura clínica e atalho para decisão

## Objetivo

Reposicionar o `Formulário de Decisão` como desfecho natural da análise clínica, sem impedir o médico experiente de decidir rapidamente.

A tela deve conduzir o fluxo mental:

1. Dados do paciente.
2. Contextos especiais, se houver.
3. Relatório automático da regulação.
4. Texto/PDF/anexos.
5. Comunicação operacional.
6. Decisão médica.

## Pré-requisito

Implementar somente depois do Slice 001 concluído e revisado.

## Valor entregue

A decisão deixa de competir visualmente com o conteúdo clínico no topo. O médico lê primeiro e decide depois, mas tem um atalho explícito `Ir para decisão` para casos simples.

## Arquivos esperados

Tocar o mínimo necessário:

- `templates/doctor/decision.html`
- `static/css/app.css` somente se necessário para espaçamento/âncora/atalho
- teste novo ou existente em `apps/doctor/tests/test_views.py` ou `tests/`

Não tocar:

- `static/js/decision.js`, salvo ajuste estritamente necessário causado pelo novo posicionamento;
- models/migrations/FSM;
- views backend, salvo se absolutamente necessário para teste.

## Handoff / prompt para implementador LLM com contexto zero

> Leia `AGENTS.md`, `PROJECT_CONTEXT.md`, `openspec/changes/doctor-decision-mobile-ux/design.md` e este arquivo.
>
> Antes de codar, confirme que está no branch dedicado do change, por exemplo `change/doctor-decision-mobile-ux`. Faça commit e push deste slice nesse branch separado.
>
> Contexto: o Slice 001 já melhorou o formulário de decisão em `templates/doctor/decision.html`. Agora a tarefa é mover esse formulário para o final da página, mantendo todo o seu comportamento. O formulário contém `#work-lock-config`, `#work-lock-warning`, `<form id="decision-form">`, radios de decisão, seções condicionais, hidden `lock_token` e botão `#btn-submit`. Leve esse bloco inteiro junto; não perca o lock config.
>
> Ordem alvo da página:
>
> 1. Dados do Paciente no topo.
> 2. Card `Reenvio corrigido`, se existir.
> 3. Card `Caso Anterior — Negação Recente`, se existir.
> 4. `Relatório Automático da Regulação`.
> 5. `Texto Extraído do PDF`.
> 6. `Visualizar PDF Original`.
> 7. `Anexos Clínicos`, se houver.
> 8. `Comunicação operacional`.
> 9. `Formulário de Decisão`.
>
> Adicione uma âncora ao card do formulário, por exemplo `id="doctor-decision-form"`.
>
> Adicione um atalho não bloqueante perto do topo, logo após `Dados do Paciente`:
>
> ```html
> <a href="#doctor-decision-form" class="btn btn-hospital-outline btn-sm w-100 w-md-auto">
>   Decisão pendente · Ir para decisão
> </a>
> ```
>
> O atalho deve usar Bootstrap e estilo já existente (`btn-hospital-outline`). Não criar JS de scroll. Não criar sticky footer neste slice.
>
> Preserve o modal `#confirm-modal` no final do template, fora do layout principal, como está. Preserve também os scripts `decision.js` e `work_lock.js`.
>
> Princípios: Clean Code, DRY, You Aren't Gonna Need It. Faça uma movimentação cuidadosa no template, sem alterar regras de negócio.

## TDD obrigatório

### RED

Antes da implementação, adicione testes que falhem. Sugestões mínimas:

1. Renderizar a página médica e verificar a ordem textual no HTML:
   - posição de `Relatório Automático da Regulação` deve ser menor que posição de `Formulário de Decisão`;
   - posição de `Comunicação operacional` deve ser menor que posição de `Formulário de Decisão`.

2. Verificar âncora e atalho:
   - HTML contém `id="doctor-decision-form"`;
   - HTML contém `href="#doctor-decision-form"`;
   - HTML contém texto `Ir para decisão`.

3. Verificar preservação funcional básica:
   - HTML ainda contém `id="decision-form"`;
   - HTML ainda contém `id="work-lock-config"`;
   - HTML ainda contém `id="confirm-modal"`.

### GREEN

Mover o bloco do formulário inteiro para depois de `{% include "cases/_communication_thread.html" %}` ou imediatamente após ele, mantendo o modal fora de `.doctor-decision-layout` se essa for a estrutura atual.

### REFACTOR

- Remover comentários obsoletos como `Top: patient context + decision form`.
- Garantir espaçamento coerente com cards existentes (`mb-4`, `p-4`, `row g-4` só se ainda fizer sentido).
- Evitar duplicar o formulário.
- Manter indentação legível.

## Critérios de aceitação

- [ ] `Formulário de Decisão` aparece depois de `Relatório Automático da Regulação`.
- [ ] `Formulário de Decisão` aparece depois de `Comunicação operacional`.
- [ ] Existe atalho visível `Decisão pendente · Ir para decisão` perto do topo.
- [ ] Atalho aponta para `#doctor-decision-form`.
- [ ] O card do formulário tem `id="doctor-decision-form"`.
- [ ] `#work-lock-config`, `#work-lock-warning`, `#decision-form`, `#btn-submit` e `#confirm-modal` continuam presentes.
- [ ] Fluxos do Slice 001 continuam funcionando.
- [ ] Sem alteração em models/migrations/FSM.
- [ ] Sem JS novo desnecessário.

## Gates de autoavaliação

Antes de encerrar o slice, o implementador deve verificar:

- [ ] `uv run ruff check .` passou.
- [ ] `uv run ruff format --check .` passou.
- [ ] `uv run mypy .` passou.
- [ ] `uv run pytest` passou.
- [ ] Testei manualmente o atalho `Ir para decisão` em mobile/DevTools.
- [ ] Testei manualmente que o formulário ainda abre modal de pendências e modal final.
- [ ] Conferi que o card de dados do paciente continua no topo.
- [ ] Conferi que a página não cria obrigação rígida de rolar; o atalho resolve casos simples.
- [ ] Atualizei `openspec/changes/doctor-decision-mobile-ux/tasks.md` marcando este slice.
- [ ] Criei relatório markdown temporário com antes/depois e evidências.

## Relatório obrigatório para terceiro LLM

Criar um arquivo markdown temporário, por exemplo:

```text
tmp/doctor-decision-mobile-ux-slice-002-report.md
```

O relatório deve conter:

- resumo do objetivo;
- arquivos alterados;
- snippets antes/depois mostrando a posição do formulário;
- evidência da âncora/atalho;
- testes adicionados/alterados;
- resultado dos quality gates;
- checklist manual mobile;
- riscos remanescentes.

A resposta final do implementador deve incluir:

```text
REPORT_PATH=tmp/doctor-decision-mobile-ux-slice-002-report.md
```

Depois disso, parar e pedir confirmação explícita antes de qualquer follow-up.

## Commit sugerido

```text
style(doctor): move decision form after clinical review
```
