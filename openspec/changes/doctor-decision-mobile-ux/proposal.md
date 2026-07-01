# Proposal: UX mobile da decisão médica

**Change ID**: `doctor-decision-mobile-ux`
**Risco**: MÉDIO (template/JS/CSS da decisão médica; sem models, migrations ou FSM)
**Dependências**: nenhuma direta

## Problema

Na página mobile de decisão médica (`templates/doctor/decision.html`), o fluxo decisório ainda permite ambiguidade operacional:

- o card de decisão aparece muito cedo, logo após os dados do paciente, competindo com a leitura clínica;
- os cards `Aceitar`/`Negar` têm área de toque boa, mas o estado selecionado é discreto demais;
- o médico pode clicar em `Enviar Decisão` sem decisão/campos completos e receber apenas feedback inline, o que no mobile pode parecer lentidão ou bug;
- o UUID técnico do caso é mostrado ao médico, sem utilidade clínica;
- já existe modal de confirmação final (`#confirm-modal`), mas ele só aparece quando o formulário está completo; não há feedback global para pendências.

## Objetivo

Melhorar a condução da decisão médica no mobile mantendo o estilo atual do aplicativo:

- Bootstrap 5.3 como base;
- paleta hospitalar existente em `static/css/app.css` (`--hospital-*`);
- Vanilla JS;
- SSR Django;
- mínimo CSS customizado, preferindo classes Bootstrap e pequenos seletores escopados à tela médica.

## Escopo

### Dentro

- Reforçar o feedback visual dos cards `Aceitar` e `Negar` quando selecionados.
- Manter/reaproveitar a revelação progressiva de campos após decisão inicial (`accept-section` / `deny-section`), melhorando copy e clareza.
- Remover o UUID técnico visível do formulário médico.
- Trocar o rótulo `Enviar Decisão` por `Confirmar decisão`.
- Reaproveitar o modal existente de confirmação final.
- Adicionar feedback global de pendências quando o médico clicar em confirmar com itens incompletos.
- Reposicionar o formulário de decisão como desfecho natural da análise clínica, com atalho mobile/desktop para chegar à decisão sem bloquear usuários experientes.
- Testes de regressão HTML/JS/CSS suficientes para proteger a UX proposta.

### Fora

- Alterações de models, migrations, FSM, permissões, locks ou auditoria.
- Mudanças no contrato backend de submissão (`DoctorDecisionForm` continua validando no servidor).
- Framework JS, HTMX, AJAX, SPA ou nova dependência frontend.
- Redesign global do tema hospitalar.
- Mudanças na fila médica, dashboards ou fluxo do agendador.

## Decisões

- **D1. Dois slices verticais e enxutos.** A melhoria imediata de decisão/feedback vem primeiro; a reorganização da ordem de leitura vem depois. Isso reduz risco e evita mover blocos grandes antes de resolver o bug perceptivo principal.
- **D2. Reutilizar o modal atual.** O modal `#confirm-modal` continuará sendo a confirmação final. O mesmo componente pode apresentar estado de pendências com título/corpo/botões diferentes, sem criar infraestrutura duplicada.
- **D3. Botão de confirmação não deve ser desabilitado por validação incompleta.** O botão pode ser desabilitado apenas por motivos operacionais reais, como lock inválido (`work_lock.js`) ou após confirmação final. Pendências de formulário devem gerar feedback explicativo.
- **D4. CSS mínimo e escopado.** Usar classes Bootstrap (`alert`, `badge`, `border`, `bg-*-subtle` quando apropriado) e poucas regras customizadas sob `.doctor-decision-form-card` / `.decision-radio-group`.
- **D5. UUID oculto para o médico.** O identificador humano continua sendo `Registro`/número do caso; UUID técnico não aparece no formulário. Se no futuro for necessário, deve ir para área técnica colapsável fora deste change.
- **D6. Decisão como desfecho, não barreira.** O formulário deve ficar após o conteúdo clínico, mas com atalho `Ir para decisão` para não forçar rolagem excessiva em casos simples.

## Recomendação de branch

Implementar este change em branch separado, por exemplo `change/doctor-decision-mobile-ux`, mantendo commits e pushes dos slices nesse branch dedicado.

## Critérios de sucesso

- Médico consegue perceber inequivocamente quando `Aceitar` ou `Negar` está selecionado.
- Clique em `Confirmar decisão` com pendências abre feedback global claro, com opções para voltar ao formulário ou sair sem decidir.
- Clique em `Confirmar decisão` com formulário completo continua abrindo o modal final já existente.
- UUID técnico (`case.case_id`) não aparece como campo visível no formulário médico.
- Campos condicionais continuam aparecendo apenas após `Aceitar` ou `Negar`.
- O formulário de decisão fica depois do conteúdo clínico principal, com atalho para decisão.
- Sem regressão no backend: validação server-side continua soberana.
- Sem alterações em models/migrations/FSM.
- Quality gate do projeto passa: `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest`.
- Cada slice gera relatório markdown temporário com antes/depois, evidências e `REPORT_PATH` para revisão de terceiro LLM.
