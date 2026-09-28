# Slice 001: Echo mismatch observável (`got` + metadados do raw)

## 1. Objetivo

Quando o LLM2 v4 ecoar `case_id` ou `agency_record_number` divergentes, o erro levantado
passa a conter os valores `expected` **e** `got` integrais, mais `raw_len` e `raw_sha256`
(12 hex) do `raw_response` — sem vazar conteúdo clínico. O tipo passa a ser
`Llm2V4EchoMismatchError` (subclasse de `Llm2V4ValidationError`) com atributos
`field`/`expected`/`got`, permitindo o retry do slice 002. Nenhum retry neste slice:
1 chamada com IDs errados = 1 erro imediato, porém diagnóstico.

## 2. Contexto necessário

Ler antes de editar (mínimo suficiente):

- `apps/pipeline/llm2_service_v4.py` — inteiro (foco: `Llm2V4ValidationError`,
  `Llm2V4ProcedureSetMismatchError`, `Llm2ServiceV4.run`, `_decode_and_validate`,
  `_render_user_prompt`). Estado atual relevante:
  ```python
  if validated.case_id != str(case_id):
      raise Llm2V4ValidationError(f"LLM2 v4 case_id mismatch: expected {case_id!r}")
  if validated.agency_record_number != str(agency_record_number):
      raise Llm2V4ValidationError(f"LLM2 v4 agency_record_number mismatch: expected {agency_record_number!r}")
  ```
- `apps/pipeline/schemas/llm2_v4.py` — `Llm2ResponseV4` (`case_id: str`,
  `agency_record_number: str` com pattern `^[0-9]{5,}$`, `procedure_recommendations` 1–10).
- `apps/pipeline/llm.py` — `RecordingLlmClient` / `StaticLlmClient` (construtores e `complete`).
- `apps/pipeline/tests/test_llm_v4_contracts.py` — builders `_recommendation()` e
  `_llm2_v4_payload()` (linhas ~118–150) como referência de payload válido; **não** importar
  de testes — copiar o mínimo necessário para o novo arquivo de teste.
- `apps/pipeline/orchestrator.py` — somente `run_pipeline` (linhas ~236–260) para confirmar
  que `str(exc)` flui para `PIPELINE_FAILED` sem mudança. **Não alterar este arquivo.**
- Restrições: `AGENTS.md` (TDD RED→GREEN→REFACTOR, `uv`, `ruff`, `mypy`, `pytest`).

## 3. Requisitos verificáveis

- **R1.** `case_id` divergente levanta `Llm2V4EchoMismatchError` (subclasse de
  `Llm2V4ValidationError`) com `field == "case_id"`, `expected == <case_id>`, `got == <valor retornado>`,
  e `str(exc)` contendo `case_id mismatch`, `expected '<case_id>'` e `got '<valor>'`.
- **R2.** `agency_record_number` divergente: idem com `field == "agency_record_number"`.
- **R3.** `str(exc)` contém `raw_len=<len(raw_response)>` e `raw_sha256=<12 hex de sha256(raw_response)>`,
  e **não** contém texto de `rationale` (ex.: o `short_reason` do payload deve estar ausente da mensagem).
- **R4.** Compat grep: mensagens contêm as substrings `case_id mismatch` / `agency_record_number mismatch`.
- **R5.** Sem retry neste slice: 1 resposta com IDs errados → exatamente 1 chamada (`len(client.calls) == 1`).
- **R6.** `orchestrator.py`, schemas, prompts e serviços legados inalterados
  (fluxo `PIPELINE_FAILED` reaproveitado via `str(exc)`).

## 4. Escopo e expected blast radius

```yaml
expected_files:
  - apps/pipeline/llm2_service_v4.py
  - apps/pipeline/tests/test_llm2_service_v4.py  # NOVO

allowed_incidental_files: []

out_of_scope:
  - retry para echo mismatch (slice 002)
  - qualquer mudança em orchestrator.py, llm.py, schemas/, prompts, LLM1, serviços v1.1/v2/v3
  - logging do raw integral ou de campos clínicos
  - migrations, FSM, templates, views
```

Escalar (parar e pedir decisão) em vez de ampliar se:

- precisar mudar assinatura de `run()` / `_decode_and_validate` além de carregar `got`/metadados;
- precisar tocar `orchestrator.py` ou schemas para fazer o teste passar;
- o `raw_sha256`/`raw_len` exigir helper compartilhado fora do módulo;
- qualquer teste existente quebrar por causa da nova mensagem/tipo.

## 5. Plano de testes do slice

### Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
|---|---|---|
| R1 | `apps/pipeline/llm2_service_v4.py`, `apps/pipeline/tests/test_llm2_service_v4.py` | `test_case_id_mismatch_reports_expected_and_got` |
| R2 | mesmos | `test_agency_record_number_mismatch_reports_expected_and_got` |
| R3 | mesmos | `test_mismatch_message_carries_raw_metadata_without_clinical_text` |
| R4 | mesmos | coberto pelos asserts de substring em R1/R2 |
| R5 | mesmos | `assert len(client.calls) == 1` nos testes R1/R2 |
| R6 | — | `git diff --name-only` mostra só os 2 arquivos |

### RED

- Comando: `uv run pytest apps/pipeline/tests/test_llm2_service_v4.py -x -q`
- Falha esperada: arquivo inexistente (collection error) OU testes falhando porque o código atual
  levanta `Llm2V4ValidationError` genérico sem `got`/`raw_len`/`raw_sha256` e sem o tipo `Llm2V4EchoMismatchError`.
- O worker deve escrever primeiro o novo teste com builders mínimos:
  ```python
  # payload v4 válido mínimo: schema_version "4.0", language "pt-BR",
  # case_id, agency_record_number "12345", 1 recommendation "cpre",
  # global_support_recommendation "none", summary None
  # recommendation: procedure_type/suggestion/support_recommendation/rationale/policy_alignment/confidence
  # (ver _recommendation/_llm2_v4_payload em test_llm_v4_contracts.py)
  # run via RecordingLlmClient(responses=[json.dumps(payload_errado)]) com:
  #   Llm2ServiceV4(client).run(case_id="c1", agency_record_number="12345",
  #     llm1_structured_data={}, detected_procedure_types=("cpre",),
  #     policy_results={"cpre": {"decision": "deny"}}, prior_contexts={"cpre": {"prior_case": None, ...}},
  #     system_prompt="sp", user_prompt_template="ut")
  ```
  Notas: `policy_results`/`prior_contexts` são serializados para o prompt mas não validados
  pelo serviço — dicionários mínimos bastam. `agency_record_number` do payload precisa casar
  `^[0-9]{5,}$` para passar no schema e chegar à checagem de eco (use `"99999"` para o caso R2).

### GREEN

- Mesmo comando deve passar: `uv run pytest apps/pipeline/tests/test_llm2_service_v4.py -x -q` → exit 0.
- Implementação mínima: novo tipo + `_decode_and_validate` calcula
  `hashlib.sha256(raw_response.encode("utf-8")).hexdigest()[:12]` e inclui `got`/metadados na mensagem.
  Sugestão de formato (worker pode ajustar desde que R1–R4 passem):
  `LLM2 v4 case_id mismatch: expected 'c1' got 'outro' (raw_len=1234 raw_sha256=abcdef123456)`.

### Verificação do slice (após GREEN, sem suíte completa)

- `uv run pytest apps/pipeline/tests/test_llm_v4_contracts.py -k TestLlm2V4Schema -q` → exit 0
  (schema v4 intacto; sem DB).
- `uv run ruff check apps/pipeline/llm2_service_v4.py apps/pipeline/tests/test_llm2_service_v4.py` → exit 0
- `uv run ruff format --check apps/pipeline/llm2_service_v4.py apps/pipeline/tests/test_llm2_service_v4.py` → exit 0
- `uv run mypy apps/pipeline/llm2_service_v4.py` → exit 0
- `git diff --name-only` → exatamente os 2 arquivos previstos.

## 6. Critérios de aceitação

- [ ] R1: `case_id` errado → `Llm2V4EchoMismatchError` com `field`/`expected`/`got` e mensagem com ambos.
- [ ] R2: `agency_record_number` errado → idem.
- [ ] R3: mensagem com `raw_len` + `raw_sha256` (12 hex), sem texto de `rationale`.
- [ ] R4: substrings legadas preservadas.
- [ ] R5: 1 chamada por mismatch (sem retry).
- [ ] R6: diff restrito aos 2 arquivos; verificações do slice verdes.

## 7. Contrato de handoff

Worker com contexto fresco implementa só este slice via `/slice-loop`. Não implementar retry
(slice 002), não atualizar `tasks.md`, não commitar. Reviewer verifica BEHAVIOR/TESTS/SCOPE/DESIGN
com veredito `OK`/`BLOCK`.
