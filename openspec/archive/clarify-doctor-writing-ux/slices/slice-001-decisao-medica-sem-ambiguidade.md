# Slice 001: Decisão médica sem ambiguidade

## Contexto zero para implementador

Leia primeiro:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/clarify-doctor-writing-ux/proposal.md`
4. `openspec/changes/clarify-doctor-writing-ux/design.md`
5. `openspec/changes/clarify-doctor-writing-ux/tasks.md`
6. Este arquivo

O sistema é um monolito Django SSR. A tela médica permite decidir casos em `WAIT_DOCTOR`. Antes da comunicação operacional existir, foi criado o campo `Case.doctor_observation` como `Observação Médica` genérica. Agora existe `CaseCommunicationMessage` para mensagens operacionais entre NIR/médico/agendador.

Problema deste slice: na decisão médica há três lugares para escrever:

- motivo da negativa;
- observação médica genérica;
- comunicação operacional.

Isso confunde o médico. A regra de produto agora é:

- se vai **negar**, escrever no **Motivo da Negativa**;
- se vai **aceitar** e precisa orientar agendamento/execução, usar `doctor_observation`, com label novo;
- se faltam documentos/dados ou precisa avisar NIR/agendador, usar **Comunicação operacional** e voltar sem decidir.

## Objetivo do slice

Entregar uma mudança vertical na tela de decisão médica:

```text
Médico abre caso → entende que pendência documental vai para Comunicação operacional → se aceitar, pode preencher Orientações para agendamento/execução → se negar, preenche apenas Motivo da Negativa → volta sem decidir sem ambiguidade
```

## Arquivos esperados

Tocar idealmente apenas:

1. `apps/doctor/forms.py`
2. `templates/doctor/decision.html`
3. `apps/doctor/views.py`
4. `apps/doctor/tests/test_views.py`

Não criar migration. Não alterar modelo, FSM, comunicação operacional, notificações ou downstream neste slice.

Se precisar tocar outro arquivo, justificar no relatório temporário.

## Requisitos funcionais

### R1. Renomear o campo visual

Em `apps/doctor/forms.py`, alterar o campo `observation` para deixar de ser `Observação Médica` genérica.

Label recomendado:

```text
Orientações para agendamento/execução
```

Help text recomendado:

```text
Opcional. Use para orientações que devem acompanhar o aceite, como suporte, preparo, prioridade ou cuidados no agendamento/execução. Para pedir documentos ou avisar outra equipe, use a comunicação operacional. Máx. 500 caracteres.
```

Manter:

- `required=False`
- `max_length=500`
- textarea com `maxlength=500`

Pode adicionar placeholder no widget, desde que sem JavaScript novo obrigatório.

### R2. Campo associado ao aceite

Em `templates/doctor/decision.html`:

- mover/renderizar o campo `observation` dentro de `#accept-section`, abaixo de `support_flag` e `admission_flow`;
- remover o bloco genérico de observação que aparece depois do ID do caso;
- manter re-renderização com valor e erros quando formulário inválido;
- não mostrar `Observação Médica` como label em nenhum ponto da tela médica.

A seção de negativa deve conter apenas o motivo da negativa e textos auxiliares.

### R3. Microcopy sobre comunicação operacional

Adicionar texto discreto, preferencialmente um `alert alert-info` ou `form-text`, próximo ao formulário:

```text
Se faltam documentos ou dados para decidir, envie uma mensagem na Comunicação operacional marcando o NIR e volte sem decidir. Não use negativa apenas para solicitar complemento.
```

Não implementar autocomplete, modal, JS novo, nem mudança no serviço de comunicação.

### R4. Botão de saída sem ambiguidade

Alterar o link `Cancelar` da tela de decisão médica para:

```text
Voltar sem decidir
```

Não alterar rota nem comportamento.

### R5. Persistência somente em aceite

Em `apps/doctor/views.py::doctor_submit`, alterar a atribuição atual de `case.doctor_observation`.

Regra:

```python
if decision == "accept":
    case.doctor_observation = form.cleaned_data.get("observation", "").strip()
else:
    case.doctor_observation = ""
```

A negativa continua exigindo `reason` e persistindo `doctor_reason` normalmente.

Não criar erro de form se `deny` vier com `observation` no POST; apenas ignorar/limpar para evitar ambiguidade e manter compatibilidade.

## TDD obrigatório

Antes de implementar, adicionar/ajustar testes falhando em `apps/doctor/tests/test_views.py`.

### Testes mínimos

1. `test_decision_form_uses_acceptance_orientation_label`
   - Instanciar `DoctorDecisionForm` ou renderizar GET da tela.
   - Deve conter `Orientações para agendamento/execução`.
   - Não deve conter label `Observação Médica` na tela/form.

2. `test_decision_page_guides_missing_documents_to_operational_communication`
   - GET da tela de decisão como médico.
   - Deve conter texto essencial: `Comunicação operacional`, `NIR`, `volte sem decidir` ou equivalente.

3. `test_decision_page_cancel_link_says_back_without_deciding`
   - GET da tela de decisão.
   - Deve conter `Voltar sem decidir`.
   - Não deve conter o link/botão da decisão médica com texto `Cancelar`.

4. Atualizar `test_accept_with_empty_observation_is_valid`
   - Continua válido, mas pode atualizar nomenclatura se necessário.

5. Atualizar `test_accept_with_500_char_observation_is_valid`
   - Continua válido.

6. Atualizar `test_accept_with_501_char_observation_is_invalid`
   - Continua inválido.

7. Substituir o teste antigo `test_deny_with_observation_is_valid` se existir.
   - Novo comportamento esperado: o form pode continuar válido, mas a view não deve persistir a orientação na negativa.

8. Atualizar `test_submit_accept_with_observation_persists`
   - Deve provar que aceite persiste a orientação, preferencialmente já com texto no novo significado.

9. Substituir `test_submit_deny_with_observation_persists`
   - Novo nome sugerido: `test_submit_deny_with_observation_ignores_orientation`.
   - POST `deny` com `reason` e `observation` preenchidos.
   - Após submit, `case.doctor_reason` contém motivo.
   - `case.doctor_observation == ""`.

10. `test_submit_accept_strips_orientation_whitespace`
    - Opcional se couber; recomendado para cobrir `.strip()`.

## Critérios de sucesso

- [ ] TDD seguido: testes novos/alterados falham antes da implementação e passam após.
- [ ] Campo visual não usa mais `Observação Médica` na tela médica.
- [ ] Campo é apresentado como orientação vinculada ao aceite.
- [ ] Help text diferencia orientação de aceite vs comunicação operacional.
- [ ] UI orienta pendência documental para comunicação operacional com NIR.
- [ ] Botão/link de saída diz `Voltar sem decidir`.
- [ ] Aceite com orientação persiste `doctor_observation`.
- [ ] Aceite sem orientação continua válido.
- [ ] Orientação > 500 caracteres continua inválida.
- [ ] Negativa com motivo não persiste `doctor_observation`, mesmo se POST enviar `observation`.
- [ ] Nenhuma migration criada.
- [ ] Quality gate do AGENTS.md passa ou eventual falha externa é documentada.

## Gates de autoavaliação

Responder no relatório temporário:

1. A tela médica ainda mostra `Observação Médica`? Se sim, está errado.
2. O campo de orientação fica visualmente dentro/associado ao aceite? Onde?
3. A negativa consegue persistir `doctor_observation` via POST manual? Qual teste prova que não?
4. O médico recebe orientação clara para pedir documento via comunicação operacional? Onde?
5. O botão `Cancelar` da decisão médica foi substituído por `Voltar sem decidir` sem mudar comportamento?
6. Alguma migration foi criada? Se sim, justificar; o esperado é não criar.
7. Quais testes foram adicionados/alterados e quais comportamentos protegem?

## Relatório obrigatório

Ao concluir, criar um arquivo markdown temporário, por exemplo:

```text
/tmp/clarify-doctor-writing-ux-slice-001-report.md
```

O relatório deve conter:

- resumo do que mudou;
- lista de arquivos tocados;
- snippets antes/depois dos trechos principais;
- evidência TDD: quais testes falharam antes e passaram depois;
- respostas aos gates de autoavaliação;
- comandos de quality gate executados e resultados;
- riscos/observações para o próximo slice.

Responder ao usuário/planner com:

```text
REPORT_PATH=/tmp/clarify-doctor-writing-ux-slice-001-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/clarify-doctor-writing-ux/proposal.md, design.md, tasks.md and slices/slice-001-decisao-medica-sem-ambiguidade.md.
Implement ONLY Slice 001.
Use a vertical, lean slice. Touch only apps/doctor/forms.py, templates/doctor/decision.html, apps/doctor/views.py and apps/doctor/tests/test_views.py unless absolutely necessary.
Follow TDD: first add/adjust failing tests, then implement minimal code, then refactor safely.
Apply clean code, DRY, YAGNI. Do not create migrations. Do not alter FSM, model fields, communication services, notifications or downstream labels in this slice.
Change the doctor's generic Observação Médica into an acceptance-only UI field named Orientações para agendamento/execução, with help text explaining that document/data requests belong in Comunicação operacional.
Change the decision page return link from Cancelar to Voltar sem decidir.
In doctor_submit, persist doctor_observation only for decision == accept; for deny, clear/ignore posted observation and keep doctor_reason as the single negative rationale.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/clarify-doctor-writing-ux/tasks.md for Slice 001 when complete.
Create /tmp/clarify-doctor-writing-ux-slice-001-report.md with before/after snippets, TDD evidence, quality gate results and self-evaluation gate answers.
Commit and push.
Return REPORT_PATH=/tmp/clarify-doctor-writing-ux-slice-001-report.md and STOP.
```
