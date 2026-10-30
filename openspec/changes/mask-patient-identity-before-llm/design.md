# Design: Mascaramento de identidade do paciente antes do LLM

**Change ID:** `mask-patient-identity-before-llm`
**Branch:** `feature/pii-mask-patient-identity` (a partir de `main`)
**Origem:** relatório de avaliação PII (sessão 2026-10-30) + requisitos
PI-01–PI-15 em `docs/requirements/requisitos-funcionais-independentes-de-stack.md` §13.
**Amostras locais de verificação:** `tmp/sample-pdfs/` (5 PDFs; nome do
paciente no nome do arquivo — nunca reproduzir identidades em código,
testes, relatórios ou logs; PI-13).

## 1. Problema (evidência)

1. `extract_pdf_text` → `strip_watermark_and_extract_record` →
   `Case.extracted_text`: só remove nº de ocorrência e watermark numérico.
   O nome permanece (`test_pdf_utils.py` exige `"João" in cleaned`).
2. `orchestrator._run_v4_pipeline` passa `case.extracted_text` verbatim ao
   LLM1 v4 (`Texto clinico do relatorio:\n{clean_text}`), cujo contrato
   `Llm1Patient {name, age, sex, document_id}` pede a identidade de volta.
3. O JSON do LLM1 (com `patient.name`/`document_id`) é dumpado no prompt do
   LLM2 v4, junto de `prior_contexts` (reason/decided_by em texto livre).
   Retries reenviam o mesmo prompt (LLM1 ≤2 envios; LLM2 ≤3 envios).
4. Exibição/busca leem `structured_data.patient.name` — identidade depende
   da resposta do modelo, não de fonte local.
5. `CNS`/`Nome Social` não existem em código algum.

Formato real (probe somente-leitura em `tmp/sample-pdfs/`, 5/5):

- Linha anterior a `Paciente:` = `<NOME> - Idade: Na. - Sexo ... [- Raça/Cor ...]`;
  nome do arquivo confere com o cabeçalho em 5/5.
- Cabeçalho repete em **toda** página (ocorrências do nome = nº de páginas).
- `CNS:` inline: `não cadastrado` (2/5) ou 15 dígitos iniciando por 7 (3/5).
- `Nome Social:` sem valor inline; linha seguinte é token de watermark
  (5/5) — **forma preenchida não observada** nas amostras.

## 2. Decisões

- **D1 — Módulo puro novo** `apps/intake/patient_identity.py`, sem Django/DB:
  `extract_patient_identity(cleaned_text) -> PatientIdentity` e
  `mask_patient_identity(text, identity) -> str`, mais
  `mask_identity_in_value` para scrub recursivo em dict/list/str.
  Sem Presidio/NER/LLM desidentificador (PI §13.3).
- **D2 — Extração ancorada no primeiro bloco de cabeçalho.** Nome: linha
  anterior a `Paciente:` cortada em ` - Idade:` (ou valor após `Paciente:`
  nos formatos sintéticos). CNS: `CNS:` inline com 15 dígitos e fronteiras
  (`(?<!\d)…(?!\d)`); `não cadastrado`/vazio = ausente legítimo. Nome
  Social: inline após `Nome Social:` ou linha seguinte **validada**
  (rejeita labels conhecidos, token numérico de watermark e valores que
  contenham `:` de campo vizinho); ambíguo → `status="ambiguous"`.
  Repetição de cabeçalho divergente (nomes diferentes) → `ambiguous`.
- **D3 — Máscara por valor completo normalizado.** Substitui nome, nome
  social e CNS em todo o texto (todas as páginas e repetições narrativas),
  casando variações de caixa/acentos/espaços, com fronteiras de palavra;
  nunca tokens isolados do nome. Placeholders fixos:
  `[NOME_REMOVIDO]`, `[NOME_SOCIAL_REMOVIDO]`, `[CNS_REMOVIDO]`.
- **D4 — Identidade persistida localmente, texto original intacto.**
  Campos novos em `Case`: `patient_identity_name`,
  `patient_identity_social_name`, `patient_identity_cns`,
  `patient_identity_status` (`extracted|absent|ambiguous|failed`),
  preenchidos em `_do_extraction`. `Case.extracted_text` e o PDF não
  mudam (PI-02). `Case.patient_name` prefere a fonte local e cai para
  `structured_data` (histórico).
- **D5 — Fronteira única no orchestrator.** `_run_v4_pipeline` deriva a
  identidade (persistida ou extraída sob demanda do `extracted_text` —
  cobre históricos sem backfill), constrói `llm_text` mascarado uma vez e
  usa **só ele** em LLM1, detecção, policy anchors, imaging/infection/
  dilation/priority signals. Verificadores ancoram contra o texto enviado
  (PI-11). Leiame: nenhum outro chamador envia `extracted_text` a LLM.
- **D6 — Fail-closed (PI-09).** `status in {ambiguous}` ou exceção do
  parser, ou guarda final encontrando identificador conhecido no prompt
  montado → `PatientIdentityMaskingError` → pipeline falha auditável
  (`PIPELINE_FAILED` via `_record_pipeline_failure`), sem chamar o LLM e
  sem fallback ao texto original. `absent` legítimo não bloqueia.
- **D7 — Contrato LLM sem identidade (PI-07).** Instrução do LLM1 v4 fixa
  `patient.name = null` e `patient.document_id = null`; após validar, o
  serviço força ambos para `None` no dict persistido. O orchestrator
  injeta o nome **local** em `structured_data.patient.name` antes de
  persistir (display/busca inalterados, proveniência local — PI-02).
  View do LLM2 recebe scrub recursivo do JSON do LLM1 (nome/document_id
  removidos; qualquer ocorrência textual da identidade mascarada) e
  `prior_contexts` com `reason` mascarado; `decided_by` profissional é
  preservado (PI-08).
- **D8 — Sem log de identidade (PI-10/PI-12).** Eventos/logs só com
  `status` e contagens (nº de substituições por tipo), nunca valores.
- **D9 — `agency_record_number` permanece em claro** (correlacionador
  operacional; decisão PI-D1 em aberto, fora deste escopo).

## 3. Slices (verticais, TDD RED→GREEN→REFACTOR)

- **Slice 1 — parser + máscara:** `patient_identity.py` +
  `apps/intake/tests/test_patient_identity.py` (puros, sem DB).
- **Slice 2 — persistência:** campos + migration `0022` em
  `apps/cases/models.py`, preenchimento em `apps/intake/tasks.py`,
  `patient_name` com precedência local; testes em
  `test_pdf_extraction_task.py`/`test_models.py`.
- **Slice 3 — fronteira LLM:** `orchestrator.py` (texto mascarado, guarda,
  injeção local, scrub LLM2/prior), `llm1_service_v4.py` (prompt + força
  null); testes em `test_orchestrator.py` com `RecordingLlmClient`
  assertando prompts sem identificadores sintéticos.
- **Slice 4 — verificação:** probe read-only nas amostras
  `tmp/sample-pdfs/` (arquivo→cabeçalho→máscara, só booleans/contagens),
  gate completo, relatório do slice.

## 4. Critérios de sucesso / autoavaliação

- [ ] Nenhum prompt capturado (LLM1/LLM2/retries) contém nome/social/CNS sintéticos.
- [ ] Máscara cobre cabeçalhos repetidos e repetição narrativa; idade/sexo/clínica intactos.
- [ ] Nome curto não corrompe palavra maior; CNS não consome prefixo de outro número.
- [ ] Ambiguidade/falha → zero chamadas LLM + `PIPELINE_FAILED` auditável.
- [ ] `patient_name`, telas e busca seguem funcionando com fonte local.
- [ ] Gate: `ruff check` + `ruff format --check` + `mypy` + `pytest` verdes.

## 5. Riscos

- Layout de `Nome Social` preenchido não observado: parser aceita inline
  ou próxima linha validada e falha fechado no ambíguo; confirmar com
  exemplar anonimizado quando surgir.
- Excerpts do LLM1 passam a conter placeholders: ancoragem usa o texto
  mascarado enviado (D5), nunca o original.
- Busca trigram por nome continua sobre `structured_data.patient.name`,
  agora de proveniência local (D7) — sem mudança de índice nesta change.
