# Tasks: Anexos clínicos no upload inicial NIR

## Slices verticais

- [x] Slice 001 — MVP end-to-end de anexos no upload único e tela médica (`slices/slice-001-attachment-upload-doctor-view.md`)
- [x] Slice 002 — UX condicional, detalhe compartilhado e hardening operacional (`slices/slice-002-attachment-ux-shared-detail-hardening.md`)
- [ ] Slice 003 — Supressão auditável de anexo enviado incorretamente (`slices/slice-003-auditable-attachment-suppression.md`)
- [ ] Slice 004 — Anexos complementares antes da decisão médica (`slices/slice-004-supplemental-attachments-before-doctor-decision.md`)

## Definition of Done do change

- [ ] Upload múltiplo de PDFs principais continua funcionando sem regressão.
- [ ] Upload com exatamente 1 PDF principal permite anexos opcionais.
- [ ] Upload com múltiplos PDFs principais não aceita anexos e exibe mensagem clara se enviados.
- [ ] Formatos aceitos: PDF, JPEG/JPG e PNG.
- [ ] Máximo de 10 anexos por caso.
- [ ] Máximo de 20 MB por anexo.
- [ ] Anexos são salvos com caminho/nome baseado em UUID, sem colisão por nome original.
- [ ] Nome original é preservado como metadado para exibição/auditoria.
- [ ] `CaseEvent` registra `CASE_ATTACHMENT_ADDED` para cada anexo aceito.
- [ ] Anexos são servidos por views protegidas, não por URL pública de media.
- [ ] Anexos possuem status/supressão auditável para mitigar envio incorreto.
- [ ] Anexos suprimidos deixam de aparecer nas telas clínicas e deixam de ser servidos pelas rotas operacionais.
- [ ] Médico vê anexos ativos inline na tela de decisão, em collapsibles por anexo.
- [ ] PDF principal continua sendo o único documento processado pela barreira de regulação e pipeline LLM neste change.
- [ ] UI de upload mostra/habilita anexos somente quando há exatamente 1 PDF principal selecionado.
- [ ] Detalhe NIR/read-only exibe anexos em ordem consistente: texto extraído, PDF principal, anexos, timeline.
- [ ] NIR consegue pré-visualizar anexos antes de enviar e remover anexos selecionados antes do submit.
- [ ] NIR confirma explicitamente que revisou anexos e que pertencem ao mesmo paciente/caso antes de enviar anexos.
- [ ] NIR consegue suprimir anexo ativo enviado incorretamente, com motivo obrigatório e evento auditável.
- [ ] NIR consegue adicionar anexos complementares ao mesmo caso antes da decisão médica, com justificativa obrigatória.
- [ ] Se o caso estiver reservado por médico em `WAIT_DOCTOR`, o NIR recebe mensagem para aguardar liberação ou comunicar o médico.
- [ ] Após decisão médica, anexos complementares não são adicionados ao mesmo caso; reenvio/caso corrigido fica para change futuro.
- [ ] Anexos complementares registram evento específico `CASE_ATTACHMENT_SUPPLEMENT_ADDED`.
- [ ] Testes relevantes foram escritos antes da implementação passar (TDD RED → GREEN → REFACTOR).
- [ ] Clean code aplicado: funções pequenas, nomes claros, sem lógica de negócio pesada em views/templates, DRY, YAGNI.
- [ ] Quality gate do AGENTS.md executado:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Relatório markdown temporário criado por cada slice com snippets antes/depois e evidências.
- [ ] Cada slice atualiza este `tasks.md` ao concluir.
- [ ] Commit e push realizados após cada slice.

## Notas para implementadores

- Não alterar FSM neste change.
- Não implementar OCR/LLM para anexos neste change.
- Não criar storage externo/S3.
- Não expor arquivos clínicos via `MEDIA_URL` público.
- Se um slice precisar tocar mais arquivos que o previsto, justificar no relatório do slice antes de ampliar escopo.
