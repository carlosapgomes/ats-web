# Slice 006 — Prompt LLM1 v4 reconhece seções do corpo como fonte de solicitação

## Objetivo

O prompt do LLM1 passa a instruir que `Justificativa da Transferência` e
`Complemento da Solicitação` são fontes legítimas de evidência de solicitação
atual (o `Motivo da Solicitação` costuma registrar apenas o exame base porque
a central de regulação não oferece subtipos), com recomendação de `field_path`
canônicos nos `evidence_spans`. O guidance vive em DUAS camadas: no conteúdo
canônico semeado (nova versão de prompt, auditável por evento) e no sufixo
sempre anexado pelo renderizador (garantia mesmo com template de banco
desatualizado). Guardrails inalterados. Nenhuma mudança de schema, FSM,
persistência ou detecção determinística.

Emenda aprovada pelo usuário; fecha o modo de falha residual do change
(redação fora da rede determinística + LLM sub-reportando → proceed
silencioso). O gate do Slice 004 já garante que falsos positivos do LLM
caminhem para revisão NIR, nunca para proceed.

## Contexto necessário

- `apps/pipeline/llm1_service_v4.py` — ler antes:
  - `LLM1_V4_DEFAULT_SYSTEM_PROMPT` (~33-49): persona + regra atual
    "Liste em requested_procedures SOMENTE os procedimentos sustentados por
    evidencia textual explicita da solicitacao atual" — não nomeia nenhuma
    seção do relatório;
  - `LLM1_V4_REQUIRED_SCHEMA_INSTRUCTIONS` (~51-137) e
    `LLM1_V4_DEFAULT_USER_PROMPT` (~139+): contrato JSON + instruções do user
    prompt canônico;
  - `_render_user_prompt` (~224-249): anexa SEMPRE, após qualquer template
    (do banco ou fallback), as linhas de guardrail ("Historico/negacao nunca
    criam solicitacao atual...", "Cada procedimento de
    requested_procedures exige evidence_spans...") — é onde entra a linha de
    garantia (b);
  - **Convenção de estilo: o texto do prompt é SEM ACENTOS** ("Voce e um
    assistente clinico..."). Novo texto deve seguir a mesma convenção
    (ex.: "Justificativa da Transferencia", "solicitacao atual").
- `apps/llm/management/commands/seed_prompts.py` — idempotente por conteúdo
  exato (`active.content == content`, ~76-77): constants novos + re-execução
  → nova versão ativa (max+1), anterior desativada, histórico preservado.
  `DEFAULT_CONTENTS` importa os constants — nenhuma mudança de código no
  comando é esperada.
- `apps/llm/tests/test_seed_prompts.py` — `test_seeded_content_matches_the_
  v4_defaults` (~99) compara seed com os constants (fica verde
  automaticamente); verificar se há teste de bump de versão por mudança de
  conteúdo (se não houver, adicionar — R4).
- `apps/pipeline/tests/test_llm_v4_contracts.py` — contratos de
  schema/prompt do LLM1 (padrão para os testes novos).
- `design.md` deste change: decisão D8.
- Atribuição de versão: `orchestrator._resolve_prompt` devolve
  `(content, version)` do banco (fallback: constants, versão 0) e os eventos
  registram `prompt_{system,user}_version` — sem mudanças necessárias.

## Requisitos verificáveis

- **R1** — `LLM1_V4_DEFAULT_SYSTEM_PROMPT` ganha instrução de que o
  `Motivo da Solicitacao` frequentemente registra apenas o exame base (a
  central de regulação não oferece subtipos) e que `Justificativa da
  Transferencia` e `Complemento da Solicitacao` são fontes legítimas de
  solicitação atual quando o texto sustenta. Guardrails atuais preservados
  (histórico/negação; evidence_spans com excerpt real; sem inventar).
- **R2** — As instruções canônicas do user prompt (constants ou schema
  instructions) passam a RECOMENDAR `field_path` canônicos para
  `evidence_spans`: `motivo_da_solicitacao`, `justificativa_da_transferencia`,
  `complemento_da_solicitacao`, `resumo_clinico`, `relatorio_medico` —
  recomendação textual, sem enum/schema (campo permanece string livre
  1-120).
- **R3** — `_render_user_prompt` anexa UMA linha de garantia nomeando
  Justificativa/Complemento como fontes legítimas de solicitação atual —
  presente no render com QUALQUER template (inclusive um template mínimo
  arbitrário simulando banco desatualizado).
- **R4** — Teste do seed: com versão ativa de conteúdo ANTERIOR, executar
  `seed_prompts` cria nova versão ativa com o conteúdo novo, desativa a
  anterior e preserva exatamente uma ativa por nome (estender
  `apps/llm/tests/test_seed_prompts.py` se o caso não existir).
- **R5** — Contratos de texto: testes novos afirmam que (i) o system prompt
  canônico contém a instrução (palavras-chave: "justificativa da
  transferencia" e "solicitacao atual" no mesmo trecho instrutivo);
  (ii) o user prompt canônico contém os `field_path` canônicos recomendados;
  (iii) o render com template arbitrário contém a linha de garantia do R3 E
  os guardrails existentes ("Historico/negacao nunca criam solicitacao
  atual"); (iv) o texto novo segue o estilo sem acentos (assert negativo:
  nenhum dos novos trechos contém "ç", "ã", "é" etc. — ou equivalente
  pragmático: as strings literais adicionadas são sem acento por construção).
- **R6** — Não-regressão: `test_llm_v4_contracts.py`,
  `test_seed_prompts.py` e `test_llm1_service.py` verdes; contratos strict
  (schema binds) sem edição; suíte existente de prompts sem surpresa.

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/pipeline/llm1_service_v4.py
  - apps/pipeline/tests/test_llm_v4_contracts.py   # contratos de texto novos
  - apps/llm/tests/test_seed_prompts.py            # teste de bump de versão (R4), se ausente

allowed_incidental_files: []

out_of_scope:
  - schema 4.0 (evidence_spans.field_path permanece string livre)
  - prompts do LLM2
  - detecção determinística, reconciliação, orchestrator, intake/UI
  - comportamento do modelo (validação é do rc; unit testa só contrato de texto)
  - migration/FSM/persistência (PromptTemplate já versiona por conteúdo)
```

Nota: 3 arquivos. Mudança de texto de prompt afeta todo caso novo pós-deploy —
por isso o guidance é duplicado em conteúdo canônico (auditável) + sufixo
(garantido); o deploy exige re-rodar `seed_prompts` (runbook/release notes).

Escalar ao parent se: precisar mudar schema, seed command, orchestrator, ou se
os testes existentes de prompt pinarem texto de forma incompatível com a
emenda aprovada.

## Matriz requisito -> arquivo -> teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `apps/pipeline/llm1_service_v4.py` | `test_llm_v4_contracts.py::test_system_prompt_names_body_sections_as_request_source` |
| R2 | `apps/pipeline/llm1_service_v4.py` | `test_llm_v4_contracts.py::test_user_prompt_recommends_canonical_field_paths` |
| R3 | `apps/pipeline/llm1_service_v4.py` | `test_llm_v4_contracts.py::test_rendered_prompt_keeps_body_section_guarantee_with_stale_template` |
| R4 | `apps/llm/management/commands/seed_prompts.py` (sem mudança esperada) | `test_seed_prompts.py::test_seed_creates_new_version_when_content_changes` |
| R5 | — | os testes novos (i)-(iv) |
| R6 | — | suítes de regressão do plano |

## Plano de testes do slice

### RED (escreva os testes primeiro; confirme a falha pelo motivo esperado)

1. `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/pipeline/tests/test_llm_v4_contracts.py -q`
   — falha esperada: os testes novos de contrato de texto falham porque o
   system prompt não nomeia a Justificativa, o user prompt não recomenda
   field_path canônicos e o render não tem a linha de garantia.
2. `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/llm/tests/test_seed_prompts.py -q`
   — falha esperada (se o teste de bump for novo): falha porque ainda não
   existe; após stub mínimo de conteúdo antigo ativo, o seed cria a nova
   versão — o teste é sobre comportamento do comando com os constants NOVOS
   (deve ser escrito junto com a implementação; RED via teste de contrato
   dos constants no passo 1 é suficiente para o ciclo).

### GREEN

3. Implementar R1-R3 em `apps/pipeline/llm1_service_v4.py` (texto sem
   acentos, guardrails preservados).
4. Repetir os comandos dos passos 1-2 — resultado esperado: exit code 0.

### Verificação do slice

5. `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/pipeline/tests/test_llm_v4_contracts.py apps/llm/tests/test_seed_prompts.py apps/pipeline/tests/test_llm1_service.py apps/pipeline/tests/test_report_body_clues.py -q`
   — esperado: exit 0 (contratos de schema/prompt e detecção intactos).
6. `uv run ruff check apps/pipeline/llm1_service_v4.py apps/pipeline/tests/test_llm_v4_contracts.py apps/llm/tests/test_seed_prompts.py && uv run ruff format --check apps/pipeline/llm1_service_v4.py apps/pipeline/tests/test_llm_v4_contracts.py apps/llm/tests/test_seed_prompts.py`
7. `uv run mypy apps/pipeline apps/llm`

## Critérios de aceitação

- [ ] R1-R6 provados (testes novos verdes; suítes de regressão verdes sem edição).
- [ ] Guardrails preservados literalmente (histórico/negação; evidence_spans
      com excerpt real) e presentes no render com template arbitrário (R3/R5-iii).
- [ ] Texto novo sem acentos (convenção dos prompts atuais) (R5-iv).
- [ ] Nenhuma mudança de schema/seed command/orchestrator (se o teste de bump
      R4 exigir mudança no comando, escalar antes).
- [ ] Nenhum arquivo fora de `expected_files` alterado.
