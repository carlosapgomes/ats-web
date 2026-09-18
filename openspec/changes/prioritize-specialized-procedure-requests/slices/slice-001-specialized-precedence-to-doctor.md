# Slice 001 — Procedimento especializado predominante até avaliação médica

## Objetivo

Quando o NIR declarou Ecoendoscopia ou CPRE e o relatório produz uma solicitação atual desse especializado junto de EDA e/ou Colonoscopia, reconciliar somente o especializado, preservar a evidência bruta, avançar o caso a `WAIT_DOCTOR` e informar ao médico, sem bloqueio, que a precedência foi aplicada.

## Contexto necessário

Leia antes de editar:

1. `AGENTS.md` e `PROJECT_CONTEXT.md`;
2. `docs/adr/ADR-0006-ecoendoscopia-e-cpre-como-procedimentos-independentes.md` e `docs/adr/ADR-0008-precedencia-procedimentos-especializados-reconciliacao.md`;
3. `proposal.md`, `design.md` (D1–D6), `tasks.md` e o delta `specs/procedure-combination-policy/spec.md` deste change;
4. `openspec/specs/procedure-combination-policy/spec.md`;
5. `apps/pipeline/procedure_reconciliation.py`, especialmente `_collapse_linked_specialized()` e `reconcile_detected_procedures()`;
6. `apps/pipeline/orchestrator.py`, da detecção até `CASE_PROCEDURES_DETECTED`, montagem de `suggested_action` e `_build_llm2_structured_data_view()`;
7. `apps/doctor/presenters.py::DoctorReportPresenter._build_notices`;
8. `apps/pipeline/tests/test_echoendoscopy_pipeline_v3.py` e `apps/pipeline/tests/test_cpre_pipeline_v3.py`.

Premissas que não devem ser reabertas neste slice:

- o detector atual já decide `current_request|historical|negated|mention`;
- a declaração NIR continua separada da detecção;
- Ecoendoscopia + CPRE continua incompatível;
- EDA + Colonoscopia continua sendo a única combinação válida;
- médico pode ajustar o procedimento pela decisão existente.

## Requisitos verificáveis

- **R1:** exatamente um tipo especializado detectado como solicitação atual elimina EDA e/ou Colonoscopia do conjunto reconciliado, com ou sem vínculo textual `com/e`.
- **R2:** dois tipos especializados, valor desconhecido ou duplicata continuam fail-closed em revisão NIR; nenhum especializado é escolhido arbitrariamente.
- **R3:** sem especializado atual, EDA-only, Colonoscopia-only e EDA + Colonoscopia preservam o comportamento existente; histórico/negação/mera menção especializada não acionam a regra.
- **R4:** a precedência não altera a declaração NIR: declarado=especializado prossegue; declarado divergente continua mismatch, sem auto-upgrade especializado.
- **R5:** quando aplicada, a regra projeta somente o especializado, envia somente ele ao LLM2, mantém `Case.structured_data` original e registra `procedure_precedence` enxuto em `CASE_PROCEDURES_DETECTED` e `suggested_action`.
- **R6:** o caso coincidente chega a `WAIT_DOCTOR`; o presenter acrescenta aviso não bloqueante com labels canônicos apenas quando houve supressão. Singleton especializado normal não recebe esse aviso.
- **R7:** detector/regex, prompts, schemas, policy clínica, models, migrations, FSM, flags, forms e templates permanecem inalterados.

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/pipeline/procedure_reconciliation.py
  - apps/pipeline/orchestrator.py
  - apps/doctor/presenters.py
  - apps/pipeline/tests/test_echoendoscopy_pipeline_v3.py
  - apps/pipeline/tests/test_cpre_pipeline_v3.py
allowed_incidental_files: []
file_cap: 5
out_of_scope:
  - alterar qualificação de ocorrência, aliases ou regex
  - alterar prompts ou schemas LLM 3.0
  - aceitar combinação com procedimento especializado
  - auto-corrigir a declaração do NIR
  - alterar policy pré-operatória ou requisitos de imagem
  - criar model, migration, evento novo, notificação ou estado FSM
  - editar template ou formulário médico
  - reprocessar casos antigos/FAILED ou operar produção
```

Pare e escale antes de tocar qualquer arquivo funcional fora da lista, mesmo que pareça uma melhoria relacionada. Se a implementação exigir detector, schema, persistência ou template, entregue `INCOMPLETE/BLOQUEADO` com a causa em vez de ampliar o slice.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1/R2/R4 | `procedure_reconciliation.py`, dois testes especializados | unitários para conjuntos convencional+Eco, convencional+CPRE, Eco+CPRE, mismatch declarado |
| R3 | `procedure_reconciliation.py`, dois testes especializados | EDA+Colon preservado; Eco/CPRE histórica/negada não domina |
| R5 | `orchestrator.py`, dois testes especializados | E2E: rows detectadas, prompt LLM2, `structured_data`, evento e `suggested_action` |
| R6 | `presenters.py`, teste de Ecoendoscopia | `WAIT_DOCTOR`; notice com precedência e ausência no singleton normal |
| R7 | nenhum produto adicional | inspeção Git contra `BASE_REF` e `git diff --check` |

## Plano TDD

### RED

Edite primeiro somente os dois arquivos de teste esperados e adicione fixtures sintéticas, sem dados pessoais/reais. Cubra ao menos estes cenários com nomes equivalentes:

- `test_independent_eda_and_echo_requests_prioritize_echoendoscopy`;
- `test_independent_eda_and_cpre_requests_prioritize_cpre`;
- `test_unique_specialized_suppresses_all_conventional_types`;
- `test_both_specialized_still_require_nir_review`;
- `test_eda_colonoscopy_remains_combined`;
- `test_specialized_precedence_reaches_doctor_with_audit_metadata`;
- `test_doctor_notice_exists_only_when_precedence_was_applied`.

Comando:

```bash
uv run pytest \
  apps/pipeline/tests/test_echoendoscopy_pipeline_v3.py \
  apps/pipeline/tests/test_cpre_pipeline_v3.py \
  -v -k 'prioritize or precedence or both_specialized or remains_combined'
```

RED válido: falha de assertion mostrando que solicitações independentes ainda retornam `nir_review`, que os metadados/notice não existem ou que o conjunto bruto não é reduzido. Erro de sintaxe, import, fixture, banco, collection ou respostas fake insuficientes não vale como RED.

### GREEN

Implemente o mínimo em:

1. `procedure_reconciliation.py`: precedência por exatamente um especializado e metadados imutáveis;
2. `orchestrator.py`: propagar metadados ao evento/sugestão sem mutar LLM1;
3. `presenters.py`: notice informativo via `report.notices`.

Rode o mesmo comando RED até exit code 0.

### REFACTOR e verificação local

- Remova ou renomeie a semântica antiga de “linked-only” no reconciler; não remova o contrato de ocorrências do detector.
- Centralize a serialização de `procedure_precedence` em helper pequeno se isso evitar duplicação entre evento e sugestão.
- Não crie abstração genérica, novo módulo ou enum persistido.
- Rode:

```bash
uv run pytest \
  apps/pipeline/tests/test_echoendoscopy_pipeline_v3.py \
  apps/pipeline/tests/test_cpre_pipeline_v3.py -q
uv run pytest \
  apps/doctor/tests/test_echoendoscopy_workflow.py \
  apps/doctor/tests/test_presenter.py -q
uv run ruff check \
  apps/pipeline/procedure_reconciliation.py \
  apps/pipeline/orchestrator.py \
  apps/doctor/presenters.py \
  apps/pipeline/tests/test_echoendoscopy_pipeline_v3.py \
  apps/pipeline/tests/test_cpre_pipeline_v3.py
uv run ruff format --check \
  apps/pipeline/procedure_reconciliation.py \
  apps/pipeline/orchestrator.py \
  apps/doctor/presenters.py \
  apps/pipeline/tests/test_echoendoscopy_pipeline_v3.py \
  apps/pipeline/tests/test_cpre_pipeline_v3.py
git diff --check
```

A suíte completa pertence ao gate final do change, não deve ser repetida durante o slice.

## Checks objetivos de escopo e contrato

```bash
# Somente os cinco arquivos funcionais esperados podem mudar no slice.
git diff --name-only "$BASE_REF" -- | sort

# Áreas protegidas devem permanecer sem diff.
git diff --exit-code "$BASE_REF" -- \
  apps/pipeline/scope_detection.py \
  apps/pipeline/llm1_service_v3.py \
  apps/pipeline/llm2_service_v3.py \
  apps/pipeline/schemas \
  apps/pipeline/policy \
  apps/cases/models.py \
  apps/cases/migrations \
  templates/doctor/decision.html

# O contrato novo deve estar identificável sem matching de texto clínico.
rg -n 'procedure_precedence|specialized_over_conventional|suppressed|precedence_applied' \
  apps/pipeline/procedure_reconciliation.py \
  apps/pipeline/orchestrator.py \
  apps/doctor/presenters.py \
  apps/pipeline/tests/test_echoendoscopy_pipeline_v3.py \
  apps/pipeline/tests/test_cpre_pipeline_v3.py
```

## Critérios de aceitação

- [ ] R1–R7 comprovados por testes/checks mapeados.
- [ ] Caso sintético equivalente ao incidente — cabeçalho EDA, EDA anterior e solicitação repetida de Ecoendoscopia — chega a `WAIT_DOCTOR` como singleton Ecoendoscopia quando o NIR declarou Ecoendoscopia.
- [ ] Cenário equivalente de CPRE também chega a `WAIT_DOCTOR`.
- [ ] Ecoendoscopia + CPRE continua em revisão NIR.
- [ ] Mismatch da declaração NIR continua em revisão, sem swap silencioso.
- [ ] `structured_data` original contém os itens extraídos; LLM2 e rows detectadas contêm somente o especializado.
- [ ] Evento e `suggested_action` contêm regra/selecionado/suprimidos e nenhum trecho clínico integral.
- [ ] Aviso médico aparece somente quando a precedência foi aplicada e não bloqueia a decisão.
- [ ] Nenhum arquivo/área fora do blast radius mudou.

## Gates de autoavaliação

Responda no relatório com teste, linha ou comando:

1. Em que ponto a regra recebe somente solicitações já qualificadas como atuais?
2. Quais conjuntos brutos são reduzidos e qual condição impede escolher entre Ecoendoscopia e CPRE?
3. Qual teste prova que `EDA + Colonoscopia` não mudou?
4. Qual teste prova que histórico/negação especializada não domina?
5. Qual teste prova que declaração EDA + detecção Eco continua mismatch?
6. O que permanece em `Case.structured_data` e o que chega ao LLM2?
7. Quais chaves exatas são gravadas no evento e na sugestão? Há texto clínico/PII nelas?
8. Como o presenter evita aviso em singleton normal e conflito fail-closed?
9. Algum detector, prompt, schema, policy, model, migration, FSM, form ou template mudou? A resposta esperada é não, com diff.
10. Qual risco residual permanece? Cite que uma classificação incorreta do detector como solicitação atual pode acionar precedência; este slice não muda essa classificação.

## Handoff

Gerar:

```text
REPORT_PATH=/tmp/prioritize-specialized-procedure-requests-slice-001-report.md
```

O relatório deve conter: branch/`BASE_REF`, matriz requisito→evidência, RED semântico, GREEN, arquivos alterados, snippets antes/depois, conjuntos testados, prova de imutabilidade LLM1 vs visão LLM2, payloads saneados de auditoria, notice médico, comandos/exit codes, riscos residuais e handoff para reviewer.

O worker não altera `tasks.md`, não faz commit/push e para após entregar o relatório.

## Prompt pronto para implementador LLM com contexto zero

```text
Leia AGENTS.md, PROJECT_CONTEXT.md, ADR-0006, ADR-0008 e todos os artefatos de openspec/changes/prioritize-specialized-procedure-requests, depois leia os arquivos fonte/teste listados no Slice 001. Implemente SOMENTE o Slice 001 em RED → GREEN → REFACTOR.

Aplique precedência após a qualificação atual existente: quando o conjunto detectado contém exatamente um especializado (echoendoscopy ou cpre), remova EDA/Colonoscopia do conjunto reconciliado mesmo em trechos independentes. Não escolha quando ambos os especializados estão presentes. Preserve EDA+Colonoscopia, unknown/duplicata fail-closed, mismatch da declaração NIR e ausência de auto-upgrade especializado.

Preserve Case.structured_data original; use somente o singleton reconciliado nas rows/policy/LLM2. Registre metadado procedure_precedence enxuto no CASE_PROCEDURES_DETECTED e suggested_action e exponha aviso não bloqueante pelo report.notices existente. Não altere detector/regex, prompts, schemas, policy clínica, models, migrations, FSM, flags, forms ou templates.

Escreva primeiro os testes e capture RED semântico com o comando do slice. Execute GREEN, regressões locais, Ruff focado, git diff --check e inspeções de áreas protegidas. Se precisar de arquivo fora dos cinco permitidos, pare como INCOMPLETE/BLOQUEADO. Gere /tmp/prioritize-specialized-procedure-requests-slice-001-report.md, não altere tasks.md, não faça commit/push e pare para review.
```
