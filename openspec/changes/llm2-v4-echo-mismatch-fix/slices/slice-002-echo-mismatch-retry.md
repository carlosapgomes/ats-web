# Slice 002: Retry one-shot para echo mismatch

## 1. Objetivo

A primeira resposta LLM2 v4 com `case_id`/`agency_record_number` divergentes dispara
automaticamente **uma única** nova chamada com instrução corretiva contendo os IDs exatos
esperados (e o `got` recebido). Segunda resposta correta → sucesso; segundo mismatch →
aborta com a mensagem observável do slice 001. O retry de eco coexiste com os retries
existentes de procedure-set e idioma (cada um no máximo 1 vez; máximo físico 4 chamadas).

Pré-requisito: slice 001 entregue (`Llm2V4EchoMismatchError` com `field`/`expected`/`got`).

## 2. Contexto necessário

Ler antes de editar (mínimo suficiente):

- `apps/pipeline/llm2_service_v4.py` — estado pós-slice-001 (foco: `Llm2V4EchoMismatchError`,
  loop `while True` em `run()` com flags `procedure_set_retry_used`/`language_retry_used`,
  helpers `_procedure_set_retry_instruction`, `_closed_list_declaration`).
  Padrão a seguir (já existente para procedure-set):
  ```python
  except Llm2V4ProcedureSetMismatchError:
      if procedure_set_retry_used:
          raise
      procedure_set_retry_used = True
      raw_response = self._client.complete(
          system_prompt=system_prompt,
          user_prompt=f"{user_prompt}\n\n{_procedure_set_retry_instruction(detected_procedure_types)}",
      )
      continue
  ```
- `apps/pipeline/tests/test_llm2_service_v4.py` — testes do slice 001 (builders e estilo);
  estender o mesmo arquivo.
- `apps/pipeline/llm.py` — `RecordingLlmClient` (para contar `client.calls` e inspecionar
  `client.calls[i]["user_prompt"]`).
- Restrições: `AGENTS.md` (TDD, `uv`, `ruff`, `mypy`, `pytest`). Sem DB nestes testes.

## 3. Requisitos verificáveis

- **R1.** Echo mismatch na 1ª resposta → 2ª chamada automática; `user_prompt` do retry contém
  o `case_id` esperado, o `agency_record_number` esperado e o `got` recebido
  (para guiar a correção), mais a lista fechada de procedimentos (reaproveitar o apêndice
  sobre o `user_prompt` original, como o retry de procedure-set faz).
- **R2.** Retry com resposta correta (IDs + conjunto + pt-BR) → sucesso:
  `procedure_recommendations` retornadas, `len(client.calls) == 2`.
- **R3.** Segundo echo mismatch → levanta `Llm2V4EchoMismatchError` com o `got` da **2ª**
  tentativa, `len(client.calls) == 2`, sem 3ª tentativa.
- **R4.** Coexistência: echo retry não consome nem bloqueia o procedure-set retry.
  Cenário: 1ª resposta IDs errados → 2ª resposta IDs certos mas conjunto errado →
  3ª resposta totalmente correta → sucesso com `len(client.calls) == 3`.
- **R5.** Orçamento documentado: docstring do módulo/`run` atualizada para
  "1 echo + 1 procedure-set + 1 idioma, máximo físico 4 chamadas" (antes: 3).
- **R6.** Sem mudança em `_decode_and_validate` além do já entregue no slice 001;
  `orchestrator.py`, schemas, prompts e serviços legados inalterados.

## 4. Escopo e expected blast radius

```yaml
expected_files:
  - apps/pipeline/llm2_service_v4.py
  - apps/pipeline/tests/test_llm2_service_v4.py  # estender

allowed_incidental_files: []

out_of_scope:
  - mudança no formato da mensagem de erro (slice 001; só reaproveitar)
  - retry para non-JSON / schema validation failed
  - qualquer mudança em orchestrator.py, llm.py, schemas/, prompts, LLM1, v1.1/v2/v3
  - migrations, FSM, templates, views
```

Escalar em vez de ampliar se:

- o retry exigir mudar a ordem de validação (IDs → conjunto → idioma deve permanecer);
- o retry exigir reconstruir o `user_prompt` base em vez de apêndice;
- qualquer teste do slice 001 precisar mudar de significado (só R5 do slice 001 muda de
  "1 chamada" para "até 2 chamadas em mismatch" — **atualizar esse assert é esperado e permitido**);
- descobrir que `language_retry` interage mal com o novo `except` (ordem dos `except`s).

Nota explícita: o assert `len(client.calls) == 1` do slice 001 (R5) **deve** ser atualizado
neste slice para o novo comportamento (1ª tentativa falha → retry). Isso não é regressão,
é a entrega deste slice. Registrar a atualização no relatório.

## 5. Plano de testes do slice

### Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
|---|---|---|
| R1 | `llm2_service_v4.py`, `test_llm2_service_v4.py` | `test_echo_mismatch_triggers_single_retry_with_exact_ids` (assert IDs+got+lista fechada no `calls[1]`) |
| R2 | mesmos | mesmo teste: sucesso com `len(calls) == 2` e recommendations retornadas |
| R3 | mesmos | `test_second_echo_mismatch_aborts_without_third_call` (`got` da 2ª, `len == 2`) |
| R4 | mesmos | `test_echo_retry_then_procedure_set_retry_coexist` (`len == 3`, sucesso) |
| R5 | `llm2_service_v4.py` | `rg -n "máximo físico de (três|3|quatro|4)"` mostra novo texto; ou inspeção do diff da docstring |
| R6 | — | `git diff --name-only` mostra só os 2 arquivos |

### RED

- Comando: `uv run pytest apps/pipeline/tests/test_llm2_service_v4.py -x -q -k "retry or second_echo or coexist"`
- Falha esperada: novos testes falham porque o código do slice 001 levanta na 1ª tentativa
  sem refazer a chamada (`len(calls) == 1`, `RecordingLlmClient` sem 2ª resposta consumida).
- Builders: reaproveitar os do slice 001. Para R4, montar 3 payloads:
  1. `case_id="errado"` (IDs errados, conjunto certo);
  2. `case_id="c1"`, `agency_record_number="12345"`, mas `procedure_recommendations` com
     procedimento fora do `detected_procedure_types` (ex.: pedir `("cpre",)` e devolver `("eda",)`);
  3. totalmente correto. `detected_procedure_types=("cpre",)` em todos.

### GREEN

- `uv run pytest apps/pipeline/tests/test_llm2_service_v4.py -x -q` → exit 0 (inclui testes do
  slice 001, com o assert R5 atualizado para o novo comportamento).
- Implementação mínima: novo `except Llm2V4EchoMismatchError` + flag `echo_retry_used` +
  helper `_echo_retry_instruction(*, case_id, agency_record_number, field, got)` (nome/wording
  livres; o teste deve pinar presença dos IDs+got, não a frase exata). Atualizar docstring do orçamento.

### Verificação do slice (após GREEN, sem suíte completa)

- `uv run pytest apps/pipeline/tests/test_llm_v4_contracts.py -k TestLlm2V4Schema -q` → exit 0
- `uv run pytest apps/pipeline/tests/test_orchestrator.py -q` → exit 0 (**exige banco de teste**;
  subir `docker compose -f docker-compose.yml -f docker-compose.test.yml up -d` se necessário.
  Se o banco não estiver disponível, registrar no relatório e pular — o slice não toca o orchestrator,
  mas o módulo importa o serviço alterado).
- `uv run ruff check apps/pipeline/llm2_service_v4.py apps/pipeline/tests/test_llm2_service_v4.py` → exit 0
- `uv run ruff format --check apps/pipeline/llm2_service_v4.py apps/pipeline/tests/test_llm2_service_v4.py` → exit 0
- `uv run mypy apps/pipeline/llm2_service_v4.py` → exit 0
- `git diff --name-only` → exatamente os 2 arquivos previstos.

## 6. Critérios de aceitação

- [ ] R1: 1º mismatch → retry cujo prompt contém IDs esperados + `got` + lista fechada.
- [ ] R2: retry correto → sucesso com 2 chamadas.
- [ ] R3: 2º mismatch → aborta com `got` da 2ª, sem 3ª chamada.
- [ ] R4: echo + procedure-set coexistem (cenário de 3 chamadas passa).
- [ ] R5: docstring do orçamento atualizada (máx 4).
- [ ] R6: diff restrito aos 2 arquivos; testes do slice 001 atualizados onde esperado; verificações verdes.

## 7. Contrato de handoff

Worker com contexto fresco implementa só este slice via `/slice-loop` após o slice 001.
Não atualizar `tasks.md`, não commitar. Reviewer verifica BEHAVIOR/TESTS/SCOPE/DESIGN;
atenção a: `except` preciso (só echo), flag único, sem loop infinito, sem vazar PHI no retry prompt
além dos IDs (o prompt já contém dados do caso por construção — não adicionar campos clínicos novos).
