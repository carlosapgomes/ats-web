# Slice 001: Echo mismatch não-fatal (warning + overwrite, sem retry)

## 1. Identity

- Slice ID: `slice-001-echo-nonfatal-overwrite`
- Change ID: `llm2-v4-echo-nonfatal-overwrite`
- Task: `tasks.md` item 1 (Slice 001)

## 2. Objective

Resposta LLM2 v4 schema-válida com `case_id`/`agency_record_number` divergentes prossegue via overwrite com warning observável, sem retry e sem `FAILED`.

## 3. Read first

Read first:

- `AGENTS.md`
- `PROJECT_CONTEXT.md`
- `openspec/changes/llm2-v4-echo-nonfatal-overwrite/proposal.md`
- `openspec/changes/llm2-v4-echo-nonfatal-overwrite/specs/procedure-neutral-analysis/spec.md`
- `apps/pipeline/llm2_service_v4.py` — inteiro (foco: `Llm2V4EchoMismatchError`, `_ECHO_MISMATCH_LABELS`, `Llm2ServiceV4.run` loop com `echo_retry_used`, `_echo_retry_instruction`, `_decode_and_validate`, `_raw_metadata`)
- `apps/pipeline/schemas/llm2_v4.py` — `Llm2ResponseV4` (só para confirmar que o schema NÃO muda)
- `apps/pipeline/tests/test_llm2_service_v4.py` — builders e estilo (estender/atualizar o mesmo arquivo)
- `apps/pipeline/llm.py` — `RecordingLlmClient` (contagem `client.calls`)
- `apps/pipeline/tests/test_llm_v4_contracts.py` — builders `_llm2_v4_payload` como referência (não importar de testes)

Follow the repository engineering policy in `AGENTS.md` and preserve existing conventions. Prefer the smallest correct change; avoid speculative abstraction and unrelated refactoring.

## 4. Requirements

- **R1.** `case_id` divergente (ex.: `got="...-abec-..."`, `expected="...-abac-..."`) NÃO levanta, NÃO retry: retorna sucesso com `procedure_recommendations` válidas, `len(client.calls) == 1`, e IDs efetivos iguais aos esperados.
- **R2.** `agency_record_number` divergente: idem R1 (1 chamada, sucesso, overwrite).
- **R3.** Cada overwrite emite `logger.warning` contendo `case_id mismatch` ou `agency_record_number mismatch`, `expected '<id>'`, `got '<valor>'`, `raw_len=<len>` e `raw_sha256=<12 hex>`, e NÃO contém texto de `rationale`/`details` (ex.: `short_reason` ausente da mensagem). Verificável via `caplog`.
- **R4.** Compat grep: substrings legadas `case_id mismatch` / `agency_record_number mismatch` preservadas na mensagem de warning.
- **R5.** Sem chamada extra por eco: mismatch → exatamente 1 chamada total; caminho feliz inalterado (1 chamada); coexistência preservada — mismatch de eco + conjunto errado na mesma 1ª resposta ainda dispara o retry de conjunto existente (cenário: 1ª resposta IDs errados + conjunto errado → overwrite de IDs + retry de conjunto → 2ª correta → sucesso com `len(calls) == 2`).
- **R6.** Código morto do retry de eco removido (flag `echo_retry_used`, branch `except Llm2V4EchoMismatchError` com retry, helper `_echo_retry_instruction`); `Llm2V4EchoMismatchError`/`_ECHO_MISMATCH_LABELS` removidos ou mantidos só como formatador sem `raise` — remover é preferido; se mantiver, justificar no relatório. Docstring do módulo/`run` atualizada de “máx 4 chamadas (1 eco + 1 conjunto + 1 idioma)” para “máx 3 chamadas”.
- **R7.** `schemas/llm2_v4.py`, `orchestrator.py`, prompts, LLM1, serviços legados, migrations, FSM inalterados.

## 5. Expected blast radius

Provavelmente afetados:

- `apps/pipeline/llm2_service_v4.py`
- `apps/pipeline/tests/test_llm2_service_v4.py` (estender/atualizar)

Sensíveis / fora de escopo sem escalada:

- `apps/pipeline/schemas/llm2_v4.py` (contrato strict intacto)
- `apps/pipeline/orchestrator.py` (`PIPELINE_FAILED` inalterado)
- prompts (`PromptTemplate`, fallbacks), LLM1, serviços v1.1/v2/v3
- migrations, FSM, templates, views

Comportamento anterior que precisa permanecer: validação de conjunto (com retry), guarda pt-BR (com retry), `non-JSON`/`schema validation failed` ainda fatais, `PIPELINE_FAILED` para falhas reais.

## 6. Failing-before plan

Failing-before evidence:

- targeted test: `uv run pytest apps/pipeline/tests/test_llm2_service_v4.py -x -q`
- expected failure: testes novos/ajustados que esperam sucesso com overwrite falham no código atual porque `_decode_and_validate` levanta `Llm2V4EchoMismatchError` e `run()` faz retry (ou aborta na 2ª): `len(client.calls) == 2` em vez de 1, ou `pytest.raises` onde o novo teste espera retorno. Worker deve escrever primeiro o teste de overwrite (ex.: `_llm2_v4_payload(case_id="outro-id")` → esperar `result` + `len(calls)==1` + warning no `caplog`) e demonstrar RED antes de implementar.

Builders mínimos (copiar estilo do arquivo, não importar de outros testes):

```python
# payload v4 válido mínimo: schema_version "4.0", language "pt-BR",
# case_id, agency_record_number "12345", 1 recommendation "cpre",
# global_support_recommendation "none", summary None
# recommendation: procedure_type/suggestion/support_recommendation/rationale/policy_alignment/confidence
# run via RecordingLlmClient(responses=[json.dumps(payload)]) com:
#   Llm2ServiceV4(client).run(case_id="c1", agency_record_number="12345",
#     llm1_structured_data={}, detected_procedure_types=("cpre",),
#     policy_results={"cpre": {"decision": "deny"}}, prior_contexts={"cpre": {"prior_case": None}},
#     system_prompt="sp", user_prompt_template="ut")
```

## 7. Implementation constraints

- Preservar observabilidade sem PHI: reaproveitar `_raw_metadata`; nunca logar `rationale`/`details`/raw integral além dos IDs operacionais.
- Overwrite via `model_copy(update={"case_id": ..., "agency_record_number": ...})` (preferido) ou atribuição direta se o modelo permitir; não mutar `raw_response`.
- Adicionar `import logging; logger = logging.getLogger(__name__)` (módulo hoje sem logger).
- Não alterar ordem das demais validações (conjunto → idioma) nem seus retries.
- Não implementar remoção de campo do schema nem mudança de prompt (fora de escopo).
- Não atualizar `tasks.md`, não commitar.

## 8. Validation

Focused validation (worker):

- `uv run pytest apps/pipeline/tests/test_llm2_service_v4.py -q` → exit 0
- `uv run pytest apps/pipeline/tests/test_llm_v4_contracts.py -k TestLlm2V4Schema -q` → exit 0 (schema intacto; sem DB)
- `uv run ruff check apps/pipeline/llm2_service_v4.py apps/pipeline/tests/test_llm2_service_v4.py` → exit 0
- `uv run ruff format --check apps/pipeline/llm2_service_v4.py apps/pipeline/tests/test_llm2_service_v4.py` → exit 0
- `uv run mypy apps/pipeline/llm2_service_v4.py` → exit 0
- `git diff --name-only` → exatamente os 2 arquivos previstos (justificar qualquer adicional)

Project-required gates: referencie `AGENTS.md` (gate completo roda no gate final do change, não neste slice).

## 9. Acceptance criteria

- [ ] R1: `case_id` errado → sucesso, 1 chamada, IDs efetivos = esperados.
- [ ] R2: `agency_record_number` errado → idem.
- [ ] R3: warning com `expected`+`got`+`raw_len`+`raw_sha256`, sem texto clínico (assert via `caplog`).
- [ ] R4: substrings legadas preservadas.
- [ ] R5: nenhuma chamada extra por eco; coexistência com retry de conjunto demonstrada.
- [ ] R6: retry de eco removido; docstring de orçamento atualizada (máx 3).
- [ ] R7: diff restrito; verificações focadas verdes.

## 10. Escalation conditions

Stop with `BLOCKED_NEEDS_DECISION` se descobrir:

- contradição entre proposal/spec e comportamento necessário;
- necessidade de mudar schema, orchestrator, prompts, migração/FSM para fazer o teste passar;
- `Llm2ResponseV4` imutável impedindo overwrite sem trocar estratégia validada;
- qualquer teste existente que quebre por motivo além da mudança proposital de `raise`→overwrite;
- nova implicação de segurança, privacidade ou comportamento clínico (ex.: evidência de troca real de casos mascarada pelo overwrite).

## 11. Evidence report

Use o caminho canônico:

```text
/tmp/sirhosp-slice-<ID>-report.md
```

O relatório deve conter:

- status: `READY_FOR_REVIEW` ou `BLOCKED_NEEDS_DECISION`;
- requirements → evidence;
- arquivos alterados;
- failing-before evidence;
- passing-after evidence;
- comandos executados e exit status;
- expansão inesperada de blast radius e justificativa;
- riscos/limitações (ex.: risco residual de mascarar bug de montagem, aceito na proposal);
- decisões que precisam de humano, se houver.

## 12. Worker handoff

Implement only this approved slice.
Treat the slice and referenced OpenSpec artifacts as the implementation contract.
Reconstruct context from the listed files; do not rely on prior conversation.
Follow the repository engineering policy.
Produce failing-before evidence, implement the smallest correct change, run focused validation, and produce the required evidence report.
Do not update `tasks.md`, commit, push, merge, archive, or start another slice.
If a new decision is required, stop with `BLOCKED_NEEDS_DECISION` and evidence.
Otherwise finish with `READY_FOR_REVIEW` and `REPORT_PATH=<path>`.
