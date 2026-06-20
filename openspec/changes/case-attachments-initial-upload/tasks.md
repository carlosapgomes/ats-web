# Tasks: Anexos clínicos no upload inicial NIR

## Slices verticais

- [x] Slice 001 — MVP end-to-end de anexos no upload único e tela médica (`slices/slice-001-attachment-upload-doctor-view.md`)
- [x] Slice 002 — UX condicional, detalhe compartilhado e hardening operacional (`slices/slice-002-attachment-ux-shared-detail-hardening.md`)
- [x] Slice 003 — Supressão auditável de anexo enviado incorretamente (`slices/slice-003-auditable-attachment-suppression.md`)
- [x] Slice 004 — Anexos complementares antes da decisão médica (`slices/slice-004-supplemental-attachments-before-doctor-decision.md`)

## Definition of Done do change

- [x] Upload múltiplo de PDFs principais continua funcionando sem regressão.
- [x] Upload com exatamente 1 PDF principal permite anexos opcionais.
- [x] Upload com múltiplos PDFs principais não aceita anexos e exibe mensagem clara se enviados.
- [x] Formatos aceitos: PDF, JPEG/JPG e PNG.
- [x] Máximo de 10 anexos por caso.
- [x] Máximo de 20 MB por anexo.
- [x] Anexos são salvos com caminho/nome baseado em UUID, sem colisão por nome original.
- [x] Nome original é preservado como metadado para exibição/auditoria.
- [x] `CaseEvent` registra `CASE_ATTACHMENT_ADDED` para cada anexo aceito.
- [x] Anexos são servidos por views protegidas, não por URL pública de media.
- [x] Anexos possuem status/supressão auditável para mitigar envio incorreto.
- [x] Anexos suprimidos deixam de aparecer nas telas clínicas e deixam de ser servidos pelas rotas operacionais.
- [x] Médico vê anexos ativos inline na tela de decisão, em collapsibles por anexo.
- [x] PDF principal continua sendo o único documento processado pela barreira de regulação e pipeline LLM neste change.
- [x] UI de upload mostra/habilita anexos somente quando há exatamente 1 PDF principal selecionado.
- [x] Detalhe NIR/read-only exibe anexos em ordem consistente: texto extraído, PDF principal, anexos, timeline.
- [x] NIR consegue pré-visualizar anexos antes de enviar e remover anexos selecionados antes do submit.
- [x] NIR confirma explicitamente que revisou anexos e que pertencem ao mesmo paciente/caso antes de enviar anexos.
- [x] NIR consegue suprimir anexo ativo enviado incorretamente, com motivo obrigatório e evento auditável.
- [x] NIR consegue adicionar anexos complementares ao mesmo caso antes da decisão médica, com justificativa obrigatória.
- [x] Se o caso estiver reservado por médico em `WAIT_DOCTOR`, o NIR recebe mensagem para aguardar liberação ou comunicar o médico.
- [x] Após decisão médica, anexos complementares não são adicionados ao mesmo caso; reenvio/caso corrigido fica para change futuro.
- [x] Anexos complementares registram evento específico `CASE_ATTACHMENT_SUPPLEMENT_ADDED`.
- [x] Testes relevantes foram escritos antes da implementação passar (TDD RED → GREEN → REFACTOR).
- [x] Clean code aplicado: funções pequenas, nomes claros, sem lógica de negócio pesada em views/templates, DRY, YAGNI.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatório markdown temporário criado por cada slice com snippets antes/depois e evidências.
- [x] Cada slice atualiza este `tasks.md` ao concluir.
- [x] Commit e push realizados após cada slice.

## Limitação aceita (ver design.md § "Limitações aceitas")

- L1. Lote de anexos complementares sem atomicidade transacional de batch (race condition de janela de milissegundos, mitigado por validações pré-loop e por-inserção; não há corrupção de dados).

## Notas para implementadores

- Não alterar FSM neste change.
- Não implementar OCR/LLM para anexos neste change.
- Não criar storage externo/S3.
- Não expor arquivos clínicos via `MEDIA_URL` público.
- Se um slice precisar tocar mais arquivos que o previsto, justificar no relatório do slice antes de ampliar escopo.
