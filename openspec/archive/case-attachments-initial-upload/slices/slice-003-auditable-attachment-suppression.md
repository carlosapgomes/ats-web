# Slice 003: Supressão auditável de anexo enviado incorretamente

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`, monolito Django SSR. Este slice continua o change `case-attachments-initial-upload` após os Slices 001 e 002.

Leia, nesta ordem:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/case-attachments-initial-upload/proposal.md`
4. `openspec/changes/case-attachments-initial-upload/design.md`
5. `openspec/changes/case-attachments-initial-upload/tasks.md`
6. `openspec/changes/case-attachments-initial-upload/slices/slice-001-attachment-upload-doctor-view.md`
7. `openspec/changes/case-attachments-initial-upload/slices/slice-002-attachment-ux-shared-detail-hardening.md`
8. Este arquivo
9. Arquivos de anexos criados nos slices anteriores
10. `apps/intake/views.py`
11. `apps/intake/urls.py`
12. `apps/cases/models.py`
13. `apps/cases/services.py`, se existir serviço de anexos
14. `templates/intake/case_detail.html`
15. Testes existentes de anexos

Implemente **somente este slice** com TDD: RED → GREEN → REFACTOR.

## Contexto e problema

Edge case previsível: o NIR pode enviar por engano anexo de outro paciente.

Não devemos apagar silenciosamente um artefato clínico. A mitigação deve ser:

```text
NIR percebe anexo errado
→ suprime anexo com motivo obrigatório
→ anexo deixa de aparecer nas telas clínicas
→ rotas operacionais deixam de servir o arquivo
→ evento auditável registra a ação
```

Este slice implementa a ação operacional de supressão. Não implementa reabertura/reconsideração de casos decididos.

## Objetivo do slice

Entrega vertical:

```text
NIR abre detalhe de caso operacional com anexo ativo
→ clica Suprimir anexo
→ informa motivo obrigatório
→ anexo desaparece da UI clínica e não é mais servido
→ timeline mostra evento de supressão
```

## Pré-condições

O Slice 001 deve ter criado campos de supressão em `CaseAttachment`:

```python
is_suppressed
suppressed_at
suppressed_by
suppression_reason
```

Se os campos não existirem, adicione-os neste slice com migration, mas registre no relatório que a pré-condição não estava satisfeita.

## Escopo funcional

### R1. Serviço/helper transacional de supressão

Criar ou usar helper pequeno, preferencialmente em `apps/cases/services.py` ou módulo coeso:

```python
def suppress_case_attachment(*, attachment: CaseAttachment, user: User, reason: str) -> CaseAttachment: ...
```

Regras:

- motivo obrigatório, não vazio;
- anexo já suprimido não pode ser suprimido novamente;
- operação transacional com `select_for_update()`;
- setar `is_suppressed=True`, `suppressed_at`, `suppressed_by`, `suppression_reason`;
- registrar `CASE_ATTACHMENT_SUPPRESSED` em `CaseEvent`.

Payload sugerido:

```json
{
  "attachment_id": "...",
  "original_filename": "...",
  "content_type": "...",
  "size_bytes": 123,
  "sha256": "...",
  "reason": "..."
}
```

Não registrar conteúdo clínico integral.

### R2. Autorização NIR para suprimir

Adicionar rota POST no app intake, por exemplo:

```text
/cases/<case_id>/attachments/<attachment_id>/suppress/
```

Regras:

- login e papel ativo `nir`;
- caso deve estar operacional, isto é, `status != CLEANED`;
- anexo deve pertencer ao caso;
- anexo deve estar ativo;
- motivo obrigatório no POST;
- após sucesso, redirecionar para detalhe do caso com mensagem de sucesso.

Não permitir supressão operacional em caso `CLEANED` neste slice. Para caso já decidido/encerrado, recomendação é fluxo administrativo/futuro.

### R3. UI no detalhe NIR

Em `templates/intake/case_detail.html`, para cada anexo ativo em caso operacional, mostrar ação discreta:

```text
Suprimir anexo enviado incorretamente
```

Ao acionar, exigir motivo obrigatório. Pode ser formulário inline simples dentro do collapsible do anexo.

Texto de ajuda recomendado:

```text
Use apenas se este anexo foi enviado por engano, por exemplo por pertencer a outro paciente. A ação será auditada e o anexo deixará de aparecer para o médico.
```

### R4. Efeito nas telas clínicas e rotas

Garantir que anexos suprimidos:

- não aparecem na tela médica;
- não aparecem no detalhe NIR como anexos ativos;
- não são servidos pela rota médica;
- não são servidos pela rota NIR operacional;
- podem aparecer apenas como evento de timeline, com texto genérico.

A timeline deve ter label para `CASE_ATTACHMENT_SUPPRESSED`, por exemplo:

```text
Anexo suprimido pelo NIR
```

### R5. Mensagem para médico se supressão ocorreu

Se simples, exibir no detalhe/timeline médico apenas evento genérico:

```text
Um anexo foi removido pelo NIR por envio incorreto.
```

Evitar expor nome do arquivo removido em telas clínicas se houver risco de PHI de outro paciente. O payload auditável pode conter metadados para admin/auditoria futura.

## Fora de escopo

- Deleção física do arquivo.
- Restaurar anexo suprimido.
- Permitir supressão em caso `CLEANED` pela rota NIR operacional.
- Envio de novos anexos após o upload inicial.
- Encerramento administrativo automático.
- Notificação ativa/push para médico com tela já aberta.
- Reabertura/reconsideração de caso decidido.
- Relação formal entre caso original e caso reenviado/corrigido.
- OCR/LLM/classificação de anexos.

## Observações para abordagem futura de reinserção/reabertura

Se o anexo errado já pode ter contaminado uma decisão médica, a correção segura não deve ser editar silenciosamente o mesmo caso.

Abordagem futura recomendada:

```text
Case A original
  - anexo errado suprimido
  - decisão potencialmente contaminada
  - encerramento administrativo se necessário

Case B corrigido/reenvio
  - novo Case
  - seus próprios anexos corretos
  - referência explícita a Case A como caso corrigido/superseded
```

Importante:

- anexos não devem ser herdados/copiados automaticamente entre reenvios;
- cada `Case` mantém sua própria lista de anexos;
- a referência entre casos deve ser auditável;
- prior-case lookup/reinserção deve usar campos imutáveis de decisão, não status FSM transitório.

## Arquivos prováveis

Idealmente tocar apenas:

1. `apps/cases/services.py` ou módulo de serviços de anexos existente
2. `apps/intake/views.py`
3. `apps/intake/urls.py`
4. `templates/intake/case_detail.html`
5. `apps/intake/tests/test_case_detail.py`
6. `apps/cases/tests/` se testes de serviço ficarem melhor no domínio
7. `apps/doctor/tests/test_views.py` para regressão de ocultação médica
8. `openspec/changes/case-attachments-initial-upload/tasks.md` ao final

Se precisar criar migration porque campos de supressão não existem, justificar no relatório.

## TDD obrigatório

Antes de implementar, adicionar testes falhando.

### Testes mínimos de serviço/domínio

1. `test_suppress_attachment_sets_suppression_fields`
   - chama serviço;
   - verifica `is_suppressed=True`, `suppressed_at`, `suppressed_by`, `suppression_reason`.

2. `test_suppress_attachment_requires_reason`
   - motivo vazio falha.

3. `test_suppress_attachment_is_idempotency_guarded`
   - segunda supressão falha de forma controlada.

4. `test_suppress_attachment_records_case_event`
   - evento `CASE_ATTACHMENT_SUPPRESSED` com payload mínimo.

### Testes mínimos de view NIR

5. `test_intake_case_detail_shows_suppress_action_for_active_attachment`
   - detalhe operacional mostra botão/form de supressão.

6. `test_nir_can_suppress_attachment_from_operational_case`
   - POST suprime e redireciona com mensagem.

7. `test_nir_cannot_suppress_attachment_from_cleaned_case`
   - caso `CLEANED` retorna 404/erro e não altera anexo.

8. `test_suppressed_attachment_not_rendered_as_active_in_intake_detail`
   - após supressão, anexo ativo desaparece; timeline mostra evento.

9. `test_intake_attachment_view_does_not_serve_suppressed_attachment`
   - rota operacional NIR retorna 404/403.

### Testes mínimos médicos/regressão

10. `test_doctor_decision_does_not_render_suppressed_attachment`
    - anexo suprimido não aparece para médico.

11. `test_doctor_attachment_view_does_not_serve_suppressed_attachment`
    - rota médica retorna 404/403.

12. `test_attachment_suppressed_event_has_timeline_label`
    - label `Anexo suprimido pelo NIR` aparece na timeline.

## Clean code / DRY / YAGNI

- Não criar workflow genérico de documentos.
- Não criar hard delete.
- Não criar restore.
- Não acoplar regra de negócio no template.
- Validação de motivo/autorização deve ficar em view/serviço, não só no HTML.
- Reutilizar filtros de anexos ativos já existentes.
- Não tocar pipeline LLM/FSM.

## Critérios de aceitação

- [ ] TDD seguido: testes novos falham antes da implementação e passam após.
- [ ] NIR consegue suprimir anexo ativo de caso operacional com motivo obrigatório.
- [ ] Supressão registra campos no `CaseAttachment`.
- [ ] Supressão registra `CASE_ATTACHMENT_SUPPRESSED`.
- [ ] Anexo suprimido não aparece nas telas clínicas.
- [ ] Anexo suprimido não é servido por rotas operacionais/médicas.
- [ ] Timeline exibe evento genérico de supressão.
- [ ] Caso `CLEANED` não permite supressão pela rota operacional NIR.
- [ ] Não há deleção física silenciosa.
- [ ] Nenhum estado FSM novo foi criado.
- [ ] Nenhum processamento LLM/OCR foi implementado.
- [ ] Quality gate do AGENTS.md passa.

## Gates de autoavaliação

Responder no relatório do slice:

1. Por que supressão foi usada em vez de deleção física?
2. Onde o motivo obrigatório é validado?
3. Qual teste prova que anexo suprimido não aparece para o médico?
4. Qual teste prova que a rota não serve anexo suprimido?
5. Como o evento evita expor PHI desnecessária na timeline clínica?
6. O que acontece se o médico já tiver visto o anexo antes da supressão?
7. Há alguma alteração em FSM/pipeline/LLM? Se sim, está errado para este slice.
8. Como reenvio/reabertura deve ser tratado futuramente, sem misturar anexos entre casos?

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
/tmp/ats-web-slice-003-case-attachments-suppression-report.md
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
REPORT_PATH=/tmp/ats-web-slice-003-case-attachments-suppression-report.md
```

Depois de responder, **parar** e pedir confirmação explícita antes de qualquer próximo slice.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/case-attachments-initial-upload/proposal.md, design.md, tasks.md, Slices 001-002, and slices/slice-003-auditable-attachment-suppression.md. Implement ONLY Slice 003 using TDD (RED → GREEN → REFACTOR). Keep code clean, DRY and YAGNI.

Goal: NIR can suppress an active incorrectly uploaded attachment from an operational non-CLEANED case with mandatory reason. Suppressed attachments must stop appearing in clinical UIs and stop being served by protected routes. Record CASE_ATTACHMENT_SUPPRESSED. Do not physically delete files, do not restore, do not add post-upload attachments, do not implement reabertura/reconsideração, do not alter FSM/LLM/OCR.

Add failing tests first for service fields, mandatory reason, event, NIR POST suppression, blocked CLEANED case, hidden suppressed attachments in NIR/doctor UI, protected routes not serving suppressed attachments, and timeline label. Then implement minimal code.

Run the full quality gate: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/case-attachments-initial-upload/tasks.md when complete. Create /tmp/ats-web-slice-003-case-attachments-suppression-report.md with before/after snippets and validation evidence. Commit and push. Reply REPORT_PATH=<path> and stop.
```
