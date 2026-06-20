# Slice 004: Anexos complementares antes da decisão médica

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`, monolito Django SSR. Este slice continua o change `case-attachments-initial-upload` após os Slices 001–003.

Leia, nesta ordem:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/case-attachments-initial-upload/proposal.md`
4. `openspec/changes/case-attachments-initial-upload/design.md`
5. `openspec/changes/case-attachments-initial-upload/tasks.md`
6. Slices 001, 002 e 003 deste change
7. Este arquivo
8. `apps/cases/models.py`
9. `apps/cases/services.py` ou serviço de anexos existente
10. `apps/intake/views.py`
11. `apps/intake/urls.py`
12. `templates/intake/case_detail.html`
13. `apps/doctor/views.py`
14. `templates/doctor/decision.html`
15. Testes existentes de anexos/locks/case detail

Implemente **somente este slice** com TDD: RED → GREEN → REFACTOR.

## Contexto e problema

Dois cenários previsíveis precisam ser cobertos:

1. o caso foi aberto sem anexos, mas deveria ter anexos;
2. o caso foi aberto com anexos, mas faltou um ou mais anexos.

Se o médico ainda não decidiu, o caminho mais seguro e enxuto é adicionar os anexos faltantes ao **mesmo `Case`**, como complementação documental.

Se o médico já decidiu, não adicionar ao mesmo caso. A conduta futura deve ser novo caso corrigido/reconsideração vinculada ao caso anterior, sem misturar anexos entre envios.

## Objetivo do slice

Entrega vertical:

```text
NIR abre detalhe operacional de caso ainda sem decisão médica
→ clica Adicionar anexo complementar
→ envia PDF/JPEG/PNG com justificativa obrigatória
→ sistema valida elegibilidade e lock médico
→ anexo fica vinculado ao mesmo Case como supplemental
→ médico vê anexo complementar sinalizado
→ evento CASE_ATTACHMENT_SUPPLEMENT_ADDED registra ação
```

## Pré-condições

O modelo `CaseAttachment` deve ter campos:

```python
upload_phase
uploaded_when_case_status
note
is_suppressed
```

Se esses campos não existirem, adicione-os com migration e registre no relatório que a pré-condição do Slice 001 não estava satisfeita.

## Escopo funcional

### R1. Elegibilidade para anexo complementar

Permitir adicionar anexo complementar somente se:

```text
doctor_decision vazio
case.status em estado antes/dependente da avaliação médica
case.status != CLEANED
```

Estados elegíveis sugeridos:

```text
R1_ACK_PROCESSING
EXTRACTING
LLM_STRUCT
LLM_SUGGEST
R2_POST_WIDGET
WAIT_DOCTOR
```

Não permitir se:

- `doctor_decision` preenchido;
- status posterior à decisão médica;
- caso `CLEANED`;
- caso administrativamente encerrado, se houver sinalização por evento/estado;
- anexo inválido.

### R2. Lock médico em `WAIT_DOCTOR`

Se `case.status == WAIT_DOCTOR` e existir lock ativo com contexto médico/decisão de outro usuário, bloquear inclusão e mostrar ao NIR:

```text
Este caso está reservado por Dr(a). X. Aguarde a liberação ou comunique o médico.
```

Motivo: evitar que o médico decida com tela aberta sem perceber novo documento.

Se não houver lock ativo, permitir.

Se o lock estiver expirado, usar helper existente de expiração/compute se aplicável; não criar novo sistema de lock.

### R3. Serviço/helper transacional

Criar helper pequeno, preferencialmente em `apps/cases/services.py` ou serviço de anexos existente:

```python
def add_supplemental_case_attachment(
    *,
    case: Case,
    uploaded_file: UploadedFile,
    user: User,
    note: str,
) -> CaseAttachment: ...
```

Regras:

- `note` obrigatório, não vazio;
- reusar validação de tipo/tamanho/quantidade quando possível;
- `upload_phase="supplemental"`;
- `uploaded_when_case_status = case.status`;
- `note = note.strip()`;
- registrar `CASE_ATTACHMENT_SUPPLEMENT_ADDED`;
- operação transacional com `select_for_update()` no `Case`.

Payload sugerido do evento:

```json
{
  "attachment_id": "...",
  "original_filename": "...",
  "content_type": "...",
  "size_bytes": 123,
  "sha256": "...",
  "note": "Laudo de USG enviado posteriormente pela unidade de origem.",
  "case_status_at_upload": "WAIT_DOCTOR"
}
```

### R4. View/form NIR

Adicionar rota POST no app intake, por exemplo:

```text
/cases/<case_id>/attachments/supplemental/add/
```

A view deve:

- exigir login e papel ativo `nir`;
- buscar caso operacional;
- validar elegibilidade;
- validar lock médico ativo;
- aceitar 1 ou mais anexos complementares, respeitando limites existentes;
- exigir justificativa obrigatória única para o lote;
- após sucesso, redirecionar para detalhe do caso com mensagem.

Se preferir MVP mais enxuto, aceitar apenas um arquivo por POST, mas documentar no relatório. Idealmente permitir múltiplos anexos complementares em um lote respeitando os mesmos limites.

### R5. UI no detalhe NIR

Em `templates/intake/case_detail.html`, mostrar seção/form:

```text
Adicionar anexo complementar
```

Somente quando caso for elegível.

Campos:

- arquivos PDF/JPEG/PNG;
- justificativa obrigatória;
- texto de ajuda:

```text
Use para enviar laudo/documento que faltou no upload inicial. Permitido apenas antes da decisão médica.
```

Se caso estiver bloqueado por médico, mostrar mensagem com nome do médico em vez do formulário.

### R6. Exibição médica/read-only

Anexos complementares devem aparecer junto dos anexos ativos, com badge/aviso:

```text
Adicionado após upload inicial — não analisado automaticamente pela IA
```

Exibir a justificativa (`note`) de forma clara.

Anexos iniciais podem continuar sem badge ou com label `Anexo inicial` se já houver UI para isso.

### R7. Timeline/event labels

Adicionar label para:

```text
CASE_ATTACHMENT_SUPPLEMENT_ADDED → Anexo complementar adicionado
```

Dot sugerido: `nir`.

## Fora de escopo

- Adicionar anexo após decisão médica.
- Criar novo caso corrigido automaticamente.
- Relação formal `supersedes_case`.
- Reabrir caso negado.
- OCR/LLM de anexos.
- Notificação ativa/push ao médico.
- Alterar FSM.
- Criar novo lock.

## Observação importante sobre caso já decidido

Se o médico já decidiu e o NIR percebe que faltou anexo, não adicionar ao mesmo `Case`.

Conduta futura recomendada:

```text
Case A original decidido
→ se decisão potencialmente prejudicada, encerramento administrativo/reconsideração conforme política futura
→ Case B corrigido/reenvio, com seus próprios anexos
→ Case B referencia Case A em campo futuro/superseded
```

Até esse change futuro existir, o sistema deve bloquear anexo complementar após decisão e orientar a correção operacional fora deste fluxo.

## Arquivos prováveis

Idealmente tocar apenas:

1. `apps/cases/services.py` ou serviço de anexos existente
2. `apps/intake/views.py`
3. `apps/intake/urls.py`
4. `templates/intake/case_detail.html`
5. `apps/intake/tests/test_case_detail.py`
6. `apps/doctor/tests/test_views.py` para visualização médica
7. `apps/cases/tests/` se testes de serviço ficarem melhor no domínio
8. `openspec/changes/case-attachments-initial-upload/tasks.md` ao final

Se precisar criar migration por campos ausentes, justificar no relatório.

## TDD obrigatório

Antes de implementar, adicionar testes falhando.

### Testes mínimos de serviço/elegibilidade

1. `test_add_supplemental_attachment_requires_note`
   - nota vazia falha.

2. `test_add_supplemental_attachment_allowed_before_doctor_decision`
   - caso em estado elegível e sem `doctor_decision` aceita anexo.

3. `test_add_supplemental_attachment_sets_phase_status_and_note`
   - `upload_phase="supplemental"`, `uploaded_when_case_status`, `note`.

4. `test_add_supplemental_attachment_records_specific_event`
   - `CASE_ATTACHMENT_SUPPLEMENT_ADDED` registrado.

5. `test_add_supplemental_attachment_rejects_after_doctor_decision`
   - `doctor_decision="accept"` ou `deny` falha.

6. `test_add_supplemental_attachment_rejects_cleaned_case`
   - caso `CLEANED` falha.

### Testes mínimos de lock médico

7. `test_nir_supplemental_attachment_blocked_when_doctor_lock_active`
   - caso `WAIT_DOCTOR` com lock ativo de outro usuário;
   - POST retorna mensagem `Este caso está reservado por Dr(a). X...`;
   - nenhum anexo criado.

8. `test_nir_supplemental_attachment_allowed_when_wait_doctor_without_lock`
   - mesmo estado sem lock ativo permite.

### Testes mínimos de view/UI NIR

9. `test_intake_case_detail_shows_supplemental_attachment_form_when_eligible`
   - detalhe operacional mostra formulário.

10. `test_intake_case_detail_hides_supplemental_form_after_doctor_decision`
    - caso decidido não mostra formulário.

11. `test_nir_can_post_supplemental_attachment`
    - POST cria anexo e redireciona com mensagem.

12. `test_supplemental_attachment_form_requires_note_in_view`
    - POST sem nota falha com mensagem.

### Testes mínimos de visualização médica/read-only

13. `test_doctor_decision_marks_supplemental_attachment`
    - tela médica mostra badge `Adicionado após upload inicial` e nota.

14. `test_intake_case_detail_marks_supplemental_attachment`
    - detalhe NIR/read-only mostra badge/nota.

15. `test_attachment_supplement_event_has_timeline_label`
    - timeline mostra `Anexo complementar adicionado`.

## Clean code / DRY / YAGNI

- Reusar validação de anexo do upload inicial.
- Não duplicar cálculo de lock ativo se helper existir.
- Não colocar regra de elegibilidade apenas no template.
- Não criar novo workflow engine.
- Não alterar FSM.
- Não implementar reenvio/reabertura neste slice.
- Não implementar OCR/LLM.
- Não criar notificação/chat.

## Critérios de aceitação

- [ ] TDD seguido: testes novos falham antes da implementação e passam após.
- [ ] NIR consegue adicionar anexo complementar ao mesmo caso antes da decisão médica.
- [ ] Justificativa é obrigatória.
- [ ] `CASE_ATTACHMENT_SUPPLEMENT_ADDED` é registrado.
- [ ] Anexo complementar tem `upload_phase="supplemental"`, status do caso e nota.
- [ ] Caso com lock médico ativo bloqueia inclusão com mensagem clara.
- [ ] Caso já decidido bloqueia inclusão no mesmo `Case`.
- [ ] Médico vê anexo complementar sinalizado e nota.
- [ ] Nenhum estado FSM novo foi criado.
- [ ] Nenhum processamento LLM/OCR foi implementado.
- [ ] Quality gate do AGENTS.md passa.

## Gates de autoavaliação

Responder no relatório do slice:

1. Quais estados são elegíveis para anexo complementar e por quê?
2. Onde `doctor_decision` bloqueia anexos após decisão?
3. Como o código detecta lock médico ativo e qual teste prova a mensagem ao NIR?
4. Qual teste prova o evento `CASE_ATTACHMENT_SUPPLEMENT_ADDED`?
5. Como a UI diferencia anexo inicial de complementar?
6. O que acontece quando faltou anexo após decisão médica?
7. Há alguma alteração em FSM/pipeline/LLM? Se sim, está errado para este slice.
8. Como o desenho evita misturar anexos entre caso original e reenvio futuro?

## Comandos de validação mínimos

Durante desenvolvimento:

```bash
uv run pytest apps/intake/tests/test_case_detail.py apps/doctor/tests/test_views.py apps/cases/tests -q
uv run ruff check apps/cases apps/intake apps/doctor
uv run ruff format --check apps/cases apps/intake apps/doctor
uv run mypy apps/cases apps/intake apps/doctor
```

Antes de finalizar:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório final obrigatório

Criar um relatório temporário em markdown, por exemplo:

```text
/tmp/ats-web-slice-004-case-attachments-supplemental-report.md
```

O relatório deve conter:

- resumo da entrega;
- arquivos tocados;
- snippets antes/depois dos pontos críticos;
- evidências RED/GREEN dos testes;
- validações executadas e resultados;
- riscos/limitações;
- confirmação de que `tasks.md` foi atualizado;
- commit hash e confirmação de push.

Resposta final obrigatória:

```text
REPORT_PATH=/tmp/ats-web-slice-004-case-attachments-supplemental-report.md
```

Depois de responder, **parar** e pedir confirmação explícita antes de qualquer próximo slice.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/case-attachments-initial-upload/proposal.md, design.md, tasks.md, Slices 001-003, and slices/slice-004-supplemental-attachments-before-doctor-decision.md. Implement ONLY Slice 004 using TDD (RED → GREEN → REFACTOR). Keep code clean, DRY and YAGNI.

Goal: NIR can add supplemental PDF/JPEG/PNG attachments to the same Case before doctor decision, with mandatory note and event CASE_ATTACHMENT_SUPPLEMENT_ADDED. Block if doctor_decision is already set, if case is CLEANED/post-decision, or if WAIT_DOCTOR has active doctor lock; show message: “Este caso está reservado por Dr(a). X. Aguarde a liberação ou comunique o médico.” Mark supplemental attachments in doctor/NIR UI with “Adicionado após upload inicial — não analisado automaticamente pela IA”. Do not create corrected cases, do not implement reabertura, do not alter FSM, do not process attachments via LLM/OCR.

Add failing tests first for eligibility, mandatory note, event, lock blocking, NIR POST/view, doctor display badge/note, and rejection after doctor decision. Then implement minimal code.

Run the full quality gate: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/case-attachments-initial-upload/tasks.md when complete. Create /tmp/ats-web-slice-004-case-attachments-supplemental-report.md with before/after snippets and validation evidence. Commit and push. Reply REPORT_PATH=<path> and stop.
```
