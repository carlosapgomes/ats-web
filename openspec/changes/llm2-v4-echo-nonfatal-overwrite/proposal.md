# Proposal: LLM2 v4 echo mismatch não-fatal (warning + overwrite)

**Change ID:** `llm2-v4-echo-nonfatal-overwrite`

**Tipo:** mini fix (hardening pós-incidente, 1 slice, 2 arquivos)

**BASE_REF:** `5661fea7425bfbb93898c377610612aa3c9be658` (`main`, tree limpa em 2026-10-05)

## Why

Dois incidentes com a mesma assinatura, antes e depois do hardening rc.7:

* 2026-09-28 — caso `cab6a0a8` (`5062149`, CPRE): `case_id mismatch` sem `got`, 1 chamada, 11s, sem retry.
* 2026-10-05 — caso `fbee1873-fd09-4085-abac-e418c3cbe8ce` (`5067824`, CPRE): `expected '...-abac-...' got '...-abec-...` (1 char, `raw_len=1329`), ~52s (inicial + retry), `PIPELINE_FAILED` → `FAILED` mesmo com o fix.

O change anterior (`llm2-v4-echo-mismatch-fix`, slices 001 observabilidade + 002 retry one-shot, release `v0.10.0-rc.7`, em prod via `rc.8`) funcionou como especificado — registrou `got` + `raw_len` + `raw_sha256` e deu segunda chance — mas o modelo errou a cópia **duas vezes seguidas**. Por design, o segundo mismatch aborta sem terceira chamada.

Causa estrutural: exigir que o LLM transcreva UUID de 36 chars de alta entropia é superfície de falha evitável. O client atual é stateless (`apps/pipeline/llm.py:104-120` — um `chat.completions.create` isolado por chamada, sem memória conversacional), logo a atribuição resposta→caso é garantida pelo HTTP isolado, não pelo eco. O precedente já existe no código: `Llm1ResponseV4` (`schemas/llm1_v4.py:275-277`) **não tem campo `case_id`** — o prompt manda `case_id` como contexto mas só valida `agency_record_number`. LLM1 opera sem eco de `case_id` sem incidentes desse tipo.

UUID (`case_id` v4 aleatório) e `agency_record_number` (numérico operacional) **não são PII/PHI** por si; o payload sensível real é `extracted_text` + `patient{name,age,sex,document_id}` — já enviado ao LLM por arquitetura. Remover o eco não é medida de privacidade, é medida de robustez.

## What Changes

**Slice único — echo mismatch vira warning + overwrite, sem retry, sem FAILED:**

* `_decode_and_validate` (`apps/pipeline/llm2_service_v4.py:286-313`) deixa de levantar `Llm2V4EchoMismatchError` como fatal. Em divergência de `case_id`/`agency_record_number`: emite `logger.warning` com o formato observável já existente (`expected`, `got`, `raw_len`, `raw_sha256`, sem conteúdo clínico), sobrescreve os IDs validados com os valores esperados (`model_copy(update=...)` ou atribuição) e retorna o objeto para o fluxo normal (conjunto → idioma → sucesso).
* Remove o retry de eco: flag `echo_retry_used`, branch `except Llm2V4EchoMismatchError`, helper `_echo_retry_instruction`, classe `Llm2V4EchoMismatchError` + `_ECHO_MISMATCH_LABELS` (ou mantém a classe só como formatador, sem `raise` — decisão do worker pela menor mudança correta; remover código morto é preferido). Orçamento cai de “máx 4 chamadas” para “máx 3 chamadas” (1 conjunto + 1 idioma + inicial). Docstring do módulo/`run` atualizada.
* Schema (`schemas/llm2_v4.py`), prompts ativos, orchestrator (`PIPELINE_FAILED`/`_try_fail_case`), serviços legados, FSM, migrations: inalterados. O modelo continua retornando os campos (strict schema intacto, sem transição `extra="forbid"`); só o tratamento da divergência muda de fatal para corretivo.
* Observabilidade preservada: todo overwrite gera warning logável com os mesmos metadados que hoje vão para `PIPELINE_FAILED` (para grep/dedup via `raw_sha256`), sem despejar `rationale`/`details`/raw.

## Decisões de design (sem `design.md` separado — mini fix)

* **Fail-open justificado:** atribuição é garantida pelo request HTTP isolado; eco divergente é erro de transcrição, não evidência de caso trocado. O risco residual (bug de montagem trocar texto do caso A com ID do caso B e o overwrite mascarar) é aceito porque: (a) nunca observado nos dois incidentes (texto e IDs do mesmo caso, só 1 char copiado errado); (b) `agency_record_number` + conjunto reconciliado + evidências ancoradas continuam validando coerência; (c) alternativa (FAILED) tem custo operacional certo (reenvio manual, caso preso) vs. risco teórico.
* **Sem retry de eco:** overwrite imediato na 1ª divergência elimina 1 chamada LLM (~30s + custo) e remove código de retry. Não manter “retry depois overwrite” — seria custo sem benefício diagnóstico adicional além do warning.
* **Sem PHI no warning:** reaproveitar `_raw_metadata` (`raw_len` + `sha256[:12]`); nunca logar `rationale`/`details`/raw integral.
* **Compat grep:** manter as substrings `case_id mismatch` / `agency_record_number mismatch` na mensagem de warning para continuidade operacional.

## Non-goals

* Remover `case_id`/`agency_record_number` do schema ou do prompt (contrato strict intacto).
* Mudar validação de conjunto, guarda pt-BR, policy, reconciliação, prompts ativos, LLM1, serviços v1.1/v2/v3.
* Mudar `orchestrator.py` (fluxo `PIPELINE_FAILED` permanece para as demais falhas).
* Exibir `payload.error` na timeline (problema real de observabilidade da UI, mas fora deste change).
* Reprocessar `fbee1873` (já supersedido por `315bc1d6`, `WAIT_DOCTOR`).
* Logging do raw integral.

## Sucesso

* Resposta schema-válida com IDs divergentes prossegue (overwrite) em vez de `FAILED`; pipeline chega a `LLM2_OK`/`WAIT_DOCTOR` quando o resto é válido.
* Todo overwrite emite warning com `expected` + `got` + `raw_len` + `raw_sha256`, sem texto clínico.
* Zero chamada extra por eco (máx físico 3).
* Zero regressão: suíte verde; `ruff`/`mypy` limpos; diff restrito aos 2 arquivos previstos.
