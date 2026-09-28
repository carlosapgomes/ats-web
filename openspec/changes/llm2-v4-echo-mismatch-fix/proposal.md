# Proposal: LLM2 v4 echo-mismatch observability + one-shot retry

**Change ID:** `llm2-v4-echo-mismatch-fix`

**Tipo:** mini fix (hardening pós-incidente, 2 slices, 2 arquivos)

**BASE_REF:** `e0f03aa2e7970a36a1adfbf07c0a5cffeab4a45f` (`main`, tree limpa em 2026-09-28)

## Why

Em 2026-09-28T15:08:28Z (12:08:28 Bahia), o caso `cab6a0a8-c7a9-4ffd-8f92-301a943a7d6a`
(ocorrência `5062149`, CPRE único, declarado=detectado) falhou no pipeline com:

```
Llm2V4ValidationError: LLM2 v4 case_id mismatch: expected 'cab6a0a8-...'
```

Investigação (somente leitura em `eon:/srv/apps/chd`):

- LLM1 OK (prompts v4/v4, 82s), policy `deny` (`abdominal_imaging_finding_absent`), sem prior case.
- LLM2 respondeu JSON **schema-válido** mas com `case_id` divergente → `PIPELINE_FAILED` → `LLM2_FAILED` → `FAILED` em 11s (1 chamada, sem retry).
- Falha **isolada**: 1 em 45 pipelines nas últimas 12h; 1 em 24h (vida do RC6); workers `restarts=0`.
- Sem UUID no texto do relatório para confundir o modelo (`TEXT_LEN=13415`, `HAS_UUID_LIKE=False`).

Dois gaps impediram diagnóstico completo e recuperação automática:

1. **Observabilidade:** `apps/pipeline/llm2_service_v4.py:234,236` loga só `expected`, nunca `got`,
   nem metadados do raw. O valor devolvido pelo modelo é irrecuperável post-hoc.
2. **Robustez:** `Llm2ServiceV4.run` tem retry one-shot para procedure-set mismatch e para
   guarda pt-BR, mas **não** para echo mismatch (`case_id`/`agency_record_number`) —
   erro esporádico de cópia falha direto, sem segunda chance.

## What Changes

**Slice 001 — observabilidade do echo mismatch:**
- Novo `Llm2V4EchoMismatchError(Llm2V4ValidationError)` com atributos `field` (`case_id` |
  `agency_record_number`), `expected`, `got`.
- Mensagem passa a conter `expected`, `got` (valores integrais — IDs operacionais, sem PHI),
  mais `raw_len` e `raw_sha256` (12 hex) do `raw_response`, sem despejar conteúdo clínico.
- Substrings legadas `case_id mismatch` / `agency_record_number mismatch` preservadas (grep-compat).
- `PIPELINE_FAILED` carrega a nova mensagem automaticamente via `str(exc)` — sem mudança no orchestrator.

**Slice 002 — retry one-shot para echo mismatch:**
- `run()` captura `Llm2V4EchoMismatchError` uma única vez e refaz a chamada com instrução
  corretiva contendo os IDs exatos esperados (e o `got` recebido, para guiar a correção).
- Sucesso no retry retorna resultado; segundo mismatch aborta com a mensagem observável do slice 001.
- Orçamento: 1 echo + 1 procedure-set + 1 linguagem, **máximo físico 4 chamadas** (docstring atualizada).

## Decisões de design (sem `design.md` separado — mini fix)

- **Sem PHI nos logs:** IDs (`case_id` UUID, `agency_record_number` numérico) são seguros para log
  integral. Conteúdo clínico (`rationale`, `details`, raw integral) **nunca** entra na mensagem;
  `raw_len` + `raw_sha256[:12]` permitem distinguir truncamento de alucinação e deduplicar ocorrências.
- **Exceção tipada em vez de match de string:** `Llm2V4EchoMismatchError` segue o padrão existente
  de `Llm2V4ProcedureSetMismatchError`, permitindo `except` preciso no loop de retry.
- **Retry compartilha o loop existente:** novo flag `echo_retry_used`, mesma estrutura
  `while True` + `continue`. Ordem de validação inalterada (IDs → conjunto → idioma).
- **Instrução de retry reaproveita o `user_prompt` original:** apêndice corretivo (IDs exatos +
  lista fechada já presente no prompt base), sem reconstruir o prompt.

## Non-goals

- Mudança em schema Pydantic, prompts ativos, catálogo de procedimentos, policy, FSM, migrations.
- Mudança no `orchestrator.py` (fluxo `PIPELINE_FAILED`/`_try_fail_case` inalterado).
- Mudança nos serviços legados (`llm2_service.py` v1.1, `llm2_service_v2/v3`) ou LLM1.
- Retry para `non-JSON` ou `schema validation failed` (falhas estruturais, não erro de cópia).
- Reprocessamento do caso `cab6a0a8` (decisão operacional fora deste change).
- Logging do raw integral em qualquer nível (vetado por PHI).

## Sucesso

- Echo mismatch futuro registra `expected` + `got` + `raw_len` + `raw_sha256` em `PIPELINE_FAILED` e no traceback do worker.
- Erro esporádico de cópia tem uma segunda chance automática antes de marcar `FAILED`.
- Zero regressão: suíte completa verde; `ruff`/`mypy` limpos; blast radius restrito aos 2 arquivos previstos.
