# Slice 002: Visibilidade NIR/médico da relação entre casos

## Contexto zero para implementador

O Slice 001 deste change deve ter criado o fluxo explícito de reenvio corrigido:

```text
Case novo.corrects_case → Case anterior
Case novo.correction_reason
Case novo.correction_created_by
Case novo.correction_created_at
Eventos CASE_CORRECTION_CREATED / CASE_MARKED_SUPERSEDED
```

Este slice torna essa relação visível e segura para NIR e médico.

Importante: o prior-case lookup automático continua existindo. Ele detecta negativa recente por `agency_record_number`, mas não é o mesmo que vínculo explícito. Quando houver `case.corrects_case`, a UI deve destacar o vínculo explícito e evitar confusão/duplicidade com o card genérico de prior case.

## Objetivo do slice

Entregar verticalmente:

```text
NIR vê no caso novo que ele corrige o anterior
NIR vê no caso anterior/listagem que há caso corrigido relacionado
Médico abre o novo caso na decisão e vê card claro de reenvio corrigido
Médico é avisado de que documentos/anexos do caso anterior não foram herdados
```

Não implementar chat/comunicação por caso. Não embutir documentos do caso anterior.

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/intake/views.py`
2. `templates/intake/case_detail.html`
3. `templates/intake/closed_cases_search.html`
4. `apps/doctor/views.py`
5. `templates/doctor/decision.html`
6. testes em `apps/intake/tests/...` e `apps/doctor/tests/...`
7. `openspec/changes/corrected-case-resubmission-linkage/tasks.md` ao concluir

Se eventos/timeline precisarem de labels, adicionar no mesmo arquivo onde os mapas já existem (`apps/intake/views.py` e imports compartilhados no doctor). Não criar novos modelos/migrations neste slice, salvo correção inevitável do Slice 001 justificada no relatório.

## Requisitos funcionais

### R1. Detalhe NIR do caso novo

Em `templates/intake/case_detail.html`, se `case.corrects_case` existir, mostrar card:

```text
↻ Reenvio corrigido

Este caso corrige o caso anterior <registro / id curto>.
Motivo do reenvio: <correction_reason>
Criado por: <correction_created_by>
Criado em: <correction_created_at>

Atenção: documentos e anexos do caso anterior não foram herdados.
```

Informações úteis do caso anterior:

- `agency_record_number` ou ID curto;
- paciente, se disponível;
- status atual com label amigável;
- data de envio;
- decisão médica anterior, se houver;
- negativa de agendamento anterior, se houver.

Não mostrar PDF/anexos/timeline completa do caso anterior embutidos.

### R2. Detalhe NIR do caso anterior

Se o caso atual tiver `corrected_by_cases`, mostrar card:

```text
↻ Caso corrigido por novo envio

Este caso foi corrigido pelo(s) caso(s): <registro / id curto>.
```

Se houver múltiplos casos corrigidos, listar de forma compacta, ordenando por `created_at desc` ou `correction_created_at desc`.

Para manter slice enxuto, não é obrigatório criar detalhe read-only de caso `CLEANED`; esse card vale para casos anteriores ainda acessíveis pela rota operacional.

### R3. Busca de casos encerrados

Em `templates/intake/closed_cases_search.html`, para cada resultado:

- oferecer botão/link `Reenviar caso corrigido` apontando para `intake:corrected_resubmission`;
- se o caso já tiver correções, mostrar badge/linha resumida:

```text
Corrigido por novo envio
```

Não remover a ação de intercorrência pós-agendamento existente. Se ambas existirem, os botões devem coexistir de forma clara.

### R4. Labels de eventos/timeline

Adicionar labels e dots para:

```text
CASE_CORRECTION_CREATED → Reenvio corrigido criado
CASE_MARKED_SUPERSEDED  → Caso corrigido por novo envio
```

Onde aplicar:

- `EVENT_LABELS` em `apps/intake/views.py`;
- `EVENT_DOT_CSS` em `apps/intake/views.py`;
- doctor importa esses mapas de intake, então evite duplicar se possível.

### R5. Card médico no novo caso

Em `apps/doctor/views.py::_build_decision_context`, preparar contexto para `case.corrects_case`, por exemplo:

```python
correction_context = {
    "original_case_id": ...,
    "original_case_short_id": ...,
    "original_agency_record_number": ...,
    "original_patient_name": ...,
    "original_created_at": ...,
    "original_status_label": ...,
    "correction_reason": ...,
    "correction_created_by": ...,
    "correction_created_at": ...,
    "doctor_decision": ...,
    "doctor_decided_at": ...,
    "doctor_display": ...,
    "doctor_reason": ...,
    "appointment_status": ...,
    "appointment_decided_at": ...,
    "scheduler_display": ...,
    "appointment_reason": ...,
}
```

Em `templates/doctor/decision.html`, mostrar card claro:

```text
↻ Reenvio corrigido

Este caso foi reenviado pelo NIR para corrigir o caso anterior <registro / id curto>.

Motivo informado pelo NIR:
"..."

Desfecho do caso anterior:
<resumo seguro>

Atenção:
Os documentos e anexos do caso anterior não foram herdados. Avalie apenas o relatório e os anexos deste caso atual.
```

### R6. Não embutir documentos do caso anterior na tela médica

O card médico não deve conter:

- `<embed>` do PDF anterior;
- `<img>` de anexo anterior;
- links diretos para servir anexos do caso anterior;
- timeline completa do caso anterior.

Se houver link para o caso anterior, deve ser read-only e seguro. Para manter o slice enxuto, preferir não adicionar link no MVP.

### R7. Evitar duplicidade com prior-case lookup genérico

Se `case.corrects_case` existir e o prior-case lookup genérico apontar para o mesmo caso, a UI médica não deve mostrar dois cards semelhantes.

Regra simples:

```text
Se prior_context.prior_case.prior_case_id == str(case.corrects_case_id),
não renderizar o card genérico “Caso Anterior — Negação Recente”.
```

O presenter/relatório técnico pode continuar recebendo contexto de negativa recente. O requisito é evitar duplicidade visual de cards.

### R8. Semântica dos campos textuais preservada

Não alterar/remover:

- `doctor_reason`;
- `doctor_observation`;
- fluxo de decisão médica.

`correction_reason` é motivo do NIR para criar novo caso corrigido, não conversa operacional e não substitui o motivo formal da negativa.

## TDD obrigatório

Antes da implementação, criar testes falhando.

### Testes mínimos NIR

1. `test_case_detail_shows_corrects_case_card_for_corrected_case`
   - novo caso com `corrects_case`;
   - GET detalhe NIR;
   - mostra “Reenvio corrigido”, registro/id do caso anterior e `correction_reason`.

2. `test_case_detail_shows_corrected_by_card_for_original_case`
   - caso original com um `corrected_by_cases`;
   - GET detalhe NIR do original operacional;
   - mostra que foi corrigido pelo novo caso.

3. `test_closed_cases_search_shows_corrected_resubmission_action`
   - caso `CLEANED` aparece na busca;
   - resultado contém link `Reenviar caso corrigido`.

4. `test_closed_cases_search_shows_corrected_by_badge_when_applicable`
   - caso encerrado com correção;
   - busca mostra badge/linha de correção.

5. `test_correction_events_have_human_labels_in_timeline`
   - criar eventos de correção;
   - detalhe NIR mostra labels amigáveis.

### Testes mínimos médico

6. `test_doctor_decision_shows_corrected_resubmission_card`
   - caso em `WAIT_DOCTOR` com `corrects_case`;
   - GET decisão como médico;
   - mostra “Reenvio corrigido”, motivo do NIR e resumo do caso anterior.

7. `test_doctor_decision_card_warns_previous_documents_not_inherited`
   - card contém aviso explícito de não herança de documentos/anexos.

8. `test_doctor_decision_does_not_embed_previous_case_documents`
   - original tem PDF/anexo;
   - tela do novo caso não contém URL/filename/embed do PDF/anexo anterior.

9. `test_doctor_decision_hides_duplicate_prior_case_card_when_same_original`
   - case corrigido aponta para original;
   - prior lookup também detectaria o original;
   - tela mostra card de reenvio corrigido, mas não mostra card genérico duplicado “Caso Anterior — Negação Recente”.

10. `test_doctor_decision_without_correction_keeps_prior_case_card`
    - upload normal sem `corrects_case` mas com prior-case lookup;
    - card genérico de negativa recente continua aparecendo.

### RED esperado

Antes da implementação, os testes devem falhar por ausência de cards/contexto/links.

Registrar no relatório:

- comando executado para RED;
- nomes dos testes falhando;
- resumo da falha.

## Orientações de implementação

### Clean code

- Criar helpers pequenos para montar contexto de correção, se necessário.
- Evitar lógica pesada no template.
- Usar nomes claros: `correction_context`, `corrected_by_cases`, `original_case`.
- Preferir contexto pré-formatado em views para templates simples.

### DRY

- Reusar `STATUS_LABELS`, `STATUS_CSS_CLASS`, `DOCTOR_DECISION_MAP`, `SUPPORT_FLAG_MAP` quando possível.
- Não duplicar regras complexas de desfecho; criar helper local se necessário.

### YAGNI

Não implementar neste slice:

- chat/comunicação por caso;
- menções/notificações;
- link com detalhe completo do caso anterior para médico;
- incorporação de PDF/anexos do caso anterior;
- fechamento administrativo automático;
- novas migrations, salvo correção de bug do Slice 001;
- mudanças no pipeline LLM.

## Critérios de sucesso

- [ ] NIR vê card no novo caso com motivo do reenvio e caso anterior.
- [ ] NIR vê indicação de caso corrigido no caso anterior quando acessível.
- [ ] Busca de encerrados oferece caminho de reenvio corrigido.
- [ ] Eventos de correção têm labels amigáveis na timeline.
- [ ] Médico vê card “Reenvio corrigido” no novo caso.
- [ ] Card médico mostra resumo seguro do caso anterior.
- [ ] Card médico alerta que documentos/anexos anteriores não foram herdados.
- [ ] Tela médica não embute PDF/anexos/timeline do caso anterior.
- [ ] Card genérico de prior-case lookup não duplica visualmente o mesmo caso quando há vínculo explícito.
- [ ] Upload normal sem vínculo explícito mantém card genérico de prior-case lookup quando aplicável.
- [ ] Quality gate completo passa.

## Gates de autoavaliação

Responder no relatório:

1. Onde o NIR vê que o novo caso corrige o anterior?
2. Onde o NIR vê que o caso anterior foi corrigido por novo envio?
3. Onde o médico vê o motivo do reenvio corrigido?
4. Qual teste prova que documentos/anexos do caso anterior não são embutidos na tela médica?
5. Qual teste prova que o card genérico de prior case não duplica o mesmo caso anterior?
6. Qual teste prova que upload normal sem vínculo explícito continua mostrando prior-case lookup quando aplicável?
7. Alguma semântica de `doctor_reason`/`doctor_observation` foi alterada? Se sim, justificar; idealmente não.

## Relatório obrigatório

Criar relatório temporário, por exemplo:

```text
/tmp/corrected-case-resubmission-linkage-slice-002-report.md
```

O relatório deve conter:

- resumo da implementação;
- arquivos alterados;
- evidência do RED;
- evidência do GREEN;
- snippets antes/depois;
- screenshots textuais/snippets dos cards renderizados, se útil;
- resultados do quality gate;
- respostas aos gates de autoavaliação;
- justificativa para qualquer arquivo extra tocado.

Responder ao final com:

```text
REPORT_PATH=/tmp/corrected-case-resubmission-linkage-slice-002-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/corrected-case-resubmission-linkage/proposal.md, design.md, tasks.md and slices/slice-002-correction-relationship-visibility.md.
Implement ONLY Slice 002. Assume Slice 001 is already complete.
Use TDD: first add failing tests for NIR/detail/closed-search and doctor decision visibility, then implement minimal code.
Make the explicit corrected-resubmission relationship visible: NIR should see that a new case corrects an old one and that an old case has corrected submissions; closed case search should offer Reenviar caso corrigido; doctor decision should show a clear Reenvio corrigido card with correction_reason and safe prior-case summary.
Do not embed prior-case PDF, attachments or full timeline in the doctor screen. Do not implement chat, notifications, administrative closure, new FSM states or OCR/LLM changes. Do not alter doctor_reason/doctor_observation semantics.
Avoid duplicate UI: if case.corrects_case points to the same case as prior_context.prior_case, hide the generic prior-case card and show only the explicit correction card. Uploads without explicit correction must keep the generic prior-case lookup card.
Apply clean code, DRY and YAGNI. Keep templates simple by preparing context in views/helpers.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/corrected-case-resubmission-linkage/tasks.md when complete.
Create /tmp/corrected-case-resubmission-linkage-slice-002-report.md with RED/GREEN evidence, snippets, quality gate results and self-evaluation answers.
Commit and push.
Return REPORT_PATH=<path> and stop.
```
