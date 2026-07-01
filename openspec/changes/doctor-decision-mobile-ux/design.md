# Design: UX mobile da decisão médica

**Change ID**: `doctor-decision-mobile-ux`

## Contexto atual

Arquivos relevantes observados:

- `templates/doctor/decision.html`
  - O formulário de decisão aparece no topo, ao lado dos dados do paciente.
  - `accept-section` e `deny-section` já usam revelação progressiva via classe `decision-section active`.
  - O UUID técnico aparece em campo readonly `ID do Caso`.
  - O botão principal é `Enviar Decisão`.
  - Já existe modal Bootstrap `#confirm-modal` com botões `Revisar` e `Confirmar Decisão`.
- `static/js/decision.js`
  - Intercepta submit.
  - Se faltam decisão/campos, mostra erro inline e retorna sem modal.
  - Se completo, popula `#confirm-body` e abre `confirmModal.show()`.
  - Após confirmação final, usa `form.requestSubmit()` preservando o fluxo normal.
- `static/css/app.css`
  - `.decision-section` esconde/mostra campos condicionais.
  - `.decision-radio-group .form-check` cria cards clicáveis básicos.
  - O estado selecionado só muda label via `input:checked + label`, sem destacar o card inteiro.

## Estratégia

Implementar em 2 slices para manter verticalidade e baixo risco:

1. **Slice 001 — Clareza imediata do ato decisório.**
   - Reforça feedback visual dos cards.
   - Usa feedback global para pendências.
   - Remove UUID visível.
   - Renomeia botão para `Confirmar decisão`.
   - Mantém o formulário onde está, para entregar valor sem mover grandes blocos.

2. **Slice 002 — Ordem de leitura clínica.**
   - Move o formulário para o final do conteúdo clínico/operacional.
   - Adiciona atalho para decisão.
   - Mantém a implementação funcional do Slice 001.

## Design visual

### Cards `Aceitar`/`Negar`

Usar o markup atual de radio + label por acessibilidade e simplicidade, mas fazer o card inteiro expressar seleção.

Preferência técnica:

- adicionar classes/atributos mínimos ao wrapper `.form-check`, por exemplo:
  - `decision-option decision-option--accept`
  - `decision-option decision-option--deny`
- no JS, ao alternar decisão, adicionar/remover `.is-selected` no wrapper;
- alternativa aceitável: CSS com `:has(input:checked)` caso o projeto já use `:has()`; ainda assim preferir classe via JS se os testes ficarem mais simples e o suporte a navegador for preocupação.

Estado sugerido:

- `Aceitar` selecionado:
  - `border-color: var(--hospital-success)`;
  - fundo verde muito claro (`rgba(27, 122, 74, 0.08)` ou classe Bootstrap compatível);
  - título em `var(--hospital-success)`;
  - badge pequeno `Selecionado` ou ícone `✓` no canto direito.
- `Negar` selecionado:
  - `border-color: var(--hospital-danger)`;
  - fundo vermelho muito claro (`rgba(181, 53, 53, 0.08)`);
  - título em `var(--hospital-danger)`;
  - badge pequeno `Selecionado` ou ícone `✕` no canto direito.

CSS deve ser curto e escopado:

```css
.decision-radio-group .decision-option { ... }
.decision-radio-group .decision-option.is-selected { ... }
.decision-radio-group .decision-option--accept.is-selected { ... }
.decision-radio-group .decision-option--deny.is-selected { ... }
```

### Revelação progressiva

A estrutura atual já cumpre a regra principal:

- antes da decisão: `accept-section` e `deny-section` escondidos;
- após `Aceitar`: campos de suporte/fluxo/orientação aparecem;
- após `Negar`: motivo da negativa aparece.

Melhoria de copy recomendada:

- antes da decisão: texto curto `Escolha Aceitar ou Negar para revelar os campos necessários.`;
- seção aceitar: título pequeno `Dados para aceite`;
- seção negar: título pequeno `Motivo da negativa`.

Não adicionar wizard, stepper complexo ou dependências.

### Modal de pendências vs. modal final

Reutilizar `#confirm-modal`.

Estados:

1. **Pendências**
   - Título: `Decisão incompleta`.
   - Corpo: lista do que falta.
   - Botões:
     - `Voltar ao formulário` (`data-bs-dismiss="modal"`, com foco/scroll para o primeiro campo pendente se simples);
     - `Sair sem decidir` (link para `doctor:queue`).
   - Não submete formulário.

2. **Confirmação final**
   - Título: `Confirmar decisão`.
   - Corpo atual com resumo `ACEITAR` ou `NEGAR`.
   - Botões atuais:
     - `Revisar`;
     - `Confirmar Decisão`.
   - Submete após confirmação final, como hoje.

Evitar criar segundo modal, a menos que a implementação com um modal cause acoplamento maior. Se criar helper JS, mantê-lo pequeno e local a `decision.js`.

### Botão principal

Trocar rótulo:

```text
Enviar Decisão -> Confirmar decisão
```

O botão deve permanecer habilitado quando faltam campos, exceto:

- lock inválido/falha operacional via `work_lock.js`;
- após clique final em `Confirmar Decisão`, como já ocorre.

### UUID

Remover do template médico o bloco visível:

```html
<label for="case-id-display">ID do Caso</label>
<input ... value="{{ case.case_id }}" readonly>
```

Não remover `case.case_id` de URLs, hidden fields ou lógica interna. O page title já usa fallback truncado para `case.case_id`; isso é aceitável apenas se não houver registro humano, mas o formulário não deve expor o UUID como campo técnico.

## Reposicionamento do formulário

Após Slice 001, mover o bloco `.doctor-decision-form-card` para depois do conteúdo de avaliação clínica e comunicação operacional.

Ordem alvo:

1. Dados do Paciente.
2. Cards de contexto especial, se houver:
   - reenvio corrigido;
   - caso anterior/negação recente.
3. Relatório Automático da Regulação.
4. Texto Extraído do PDF.
5. PDF original.
6. Anexos clínicos, se houver.
7. Comunicação operacional.
8. Formulário de decisão.

Adicionar atalho próximo ao topo, preferencialmente após dados do paciente:

```html
<a href="#doctor-decision-form" class="btn btn-hospital-outline btn-sm w-100 w-md-auto">
  Decisão pendente · Ir para decisão
</a>
```

Usar âncora local, sem JS obrigatório.

## Testabilidade

### Testes sugeridos para Slice 001

- Template não contém label/campo `ID do Caso` visível no formulário médico.
- Template contém `Confirmar decisão` no botão principal.
- Template mantém `confirm-modal`.
- JS contém fluxo de pendências (ex.: texto `Decisão incompleta`, `Voltar ao formulário`, `Sair sem decidir`).
- CSS contém seletores de estado selecionado (`decision-option`, `is-selected`) e tokens `--hospital-success`/`--hospital-danger`.

### Testes sugeridos para Slice 002

- No HTML renderizado, `Relatório Automático da Regulação` aparece antes de `Formulário de Decisão`.
- Existe âncora `id="doctor-decision-form"`.
- Existe link/atalho `href="#doctor-decision-form"` com texto `Ir para decisão`.

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Regressão na submissão final | Manter `finalSubmitConfirmed` e `requestSubmit()` como hoje; testes existentes já protegem esse comportamento. |
| Modal único ficar confuso | Criar funções pequenas: `showPendingModal(missingItems)` e `showFinalConfirmModal(...)`. |
| CSS customizado crescer demais | Usar Bootstrap para layout e limitar CSS a seleção dos cards. |
| Mover formulário quebrar lock config | Ao mover, levar junto `#work-lock-config`, `#work-lock-warning`, `<form>` e modal permanece fora do layout. |
| Atalho parecer obrigação de decidir | Copy deve ser discreta: `Decisão pendente · Ir para decisão`, não bloqueante. |

## Não objetivos

- Campo técnico colapsável para UUID.
- Sticky bottom action bar.
- Scroll obrigatório até o final.
- Auto-scroll após seleção.
- Persistência parcial da decisão via AJAX.
