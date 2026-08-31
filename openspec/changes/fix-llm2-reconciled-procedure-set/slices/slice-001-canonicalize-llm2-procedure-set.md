<!-- markdownlint-disable MD013 -->

# Slice 001: Canonicalizar o conjunto do LLM2 e limitar retry de mismatch

## Handoff para implementador LLM com contexto zero

Você está no monolito Django SSR em `/projects/dev/ats-web`. Este é o **único slice de implementação** do change `fix-llm2-reconciled-procedure-set`. Não existe slice futuro a antecipar e você não deve operar produção.

Leia integralmente, nesta ordem, antes de planejar ou editar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/fix-llm2-reconciled-procedure-set/proposal.md`
4. `openspec/changes/fix-llm2-reconciled-procedure-set/design.md`
5. `openspec/changes/fix-llm2-reconciled-procedure-set/specs/procedure-neutral-analysis/spec.md`
6. `openspec/changes/fix-llm2-reconciled-procedure-set/tasks.md`
7. este arquivo
8. `openspec/specs/procedure-neutral-analysis/spec.md`
9. `docs/adr/ADR-0004-procedimentos-multiplos-e-contrato-llm-neutro.md`
10. `apps/pipeline/orchestrator.py` — `run_pipeline()`, `_run_v2_pipeline()` e chamada de `Llm2ServiceV2.run()`
11. `apps/pipeline/llm2_service_v2.py` — `run()`, `_render_user_prompt()`, `_decode_and_validate()` e retry pt-BR
12. `apps/pipeline/procedure_reconciliation.py` — leitura apenas; confirme `detected_procedure_types`
13. `apps/pipeline/scope_detection.py::detect_requested_procedures_v2` — leitura apenas; não altere regex
14. `apps/pipeline/schemas/llm2_v2.py` — leitura apenas; confirme validator de duplicatas
15. `apps/pipeline/tests/test_slice_002_contracts.py` — `TestLlm2ServiceV2` e builders v2
16. `apps/pipeline/tests/test_slice_002_pipeline.py` — `TestCombinedHappyPath`, `TestSimpleAndFailurePaths` e builders do pipeline
17. `apps/pipeline/llm.py::RecordingLlmClient` — sem editar

### Incidente e causa confirmada

Nos casos de produção afetados, o LLM1 listou EDA e Colonoscopia, mas a detecção/reconciliação conservadora manteve somente um procedimento atual. O orchestrator enviou ao LLM2 o `structured_data` bruto com ambos, enquanto `_decode_and_validate()` recebeu o conjunto reconciliado singular. A saída seguiu o contexto bruto e falhou corretamente:

```text
LLM2 v2 procedure set mismatch: expected ['eda'], got ['colonoscopy', 'eda']
LLM2 v2 procedure set mismatch: expected ['colonoscopy'], got ['colonoscopy', 'eda']
```

Não corrija o validator nem a reconciliação. Corrija a visão enviada ao LLM2 e dê uma única chance corretiva ao modelo.

### Estado atual esperado

- `case.structured_data = result1.structured_data` preserva o artefato LLM1.
- Policy e prior contexts iteram `reconciliation.detected_procedure_types`.
- `Llm2ServiceV2.run()` recebe hoje o `result1.structured_data` original.
- `_render_user_prompt()` serializa o objeto inteiro e não lista explicitamente `detected_procedure_types`.
- `_decode_and_validate()` levanta a mesma classe base para mismatch de conjunto e outros erros.
- Mismatch de conjunto não recebe retry.
- Termos narrativos não pt-BR recebem um retry já existente.
- `run_pipeline()` captura falha, registra `PIPELINE_FAILED`, tenta transicionar para `FAILED` e não relança.
- Não existe recuperação automática de casos `FAILED`.

Se qualquer premissa divergir, registre no relatório. Se houver conflito funcional, worktree sujo, baseline vermelho ou necessidade de tocar detector/reconciliação/schema/model/migration, reporte **INCOMPLETE/BLOQUEADO** e pare em vez de improvisar.

### Fluxo vertical a entregar

```text
LLM1 original contém EDA + Colonoscopia
→ detector/reconciliação escolhe conjunto canônico
→ orchestrator cria cópia profunda e filtra requested_procedures
→ serviço anexa lista JSON fechada ao prompt
→ primeira resposta exata segue normalmente
   OU primeiro set mismatch recebe uma correção
→ resposta integralmente válida chega a WAIT_DOCTOR
   OU segundo mismatch mantém FAILED sem sugestão parcial
→ structured_data original permanece intacto
```

## Protocolo obrigatório para implementador DeepSeek4-Flash

Este slice será implementado por um modelo rápido e com tendência a concluir cedo demais. Siga este protocolo literalmente. **Se qualquer item falhar, o slice está INCOMPLETE**: não marque `tasks.md`, não faça commit/push e responda com bloqueio + evidência.

1. **Plano antes de editar**: escreva no relatório uma matriz `Requisito → arquivo(s) → teste(s)/inspeção`. Não implemente requisito sem teste ou justificativa explícita.
2. **Worktree e baseline antes de editar**:
   - confirme `git status --short` limpo;
   - confirme a branch `feature/fix-llm2-reconciled-procedure-set` ou outra branch explicitamente atribuída; não implemente em `main`;
   - use somente o PostgreSQL de testes dedicado conforme `AGENTS.md`;
   - registre `BASE_REF=$(git rev-parse HEAD)`;
   - rode `uv run pytest` no estado inicial limpo;
   - cole exit code e resumo explícito com `passed`, `failed=0` e `errors=0`.
   Baseline com falha/erro bloqueia antes de qualquer edição.
3. **RED real**: edite primeiro somente os dois arquivos de teste permitidos. Rode o subconjunto alvo. Pelo menos um teste novo deve falhar porque o prompt ainda contém o conjunto bruto ou porque mismatch ainda não recebe retry. RED por sintaxe, import, fixture, banco ou resposta fake esgotada não conta.
4. **GREEN mínimo**: altere somente `orchestrator.py` e `llm2_service_v2.py`. Não altere detector, matriz, schema, policy, prompts versionados, models ou FSM.
5. **REFACTOR seguro**: aplique clean code, DRY e YAGNI apenas nos trechos tocados. Use helper privado coeso para projeção e erro tipado para controle; não crie módulo, framework de retries ou abstração genérica.
6. **Verificação por inspeção**: execute todos os comandos `rg`, testes, escopo Git, OpenSpec e `git diff --check` descritos neste slice. Cole resultado/resumo e interpretação no relatório.
7. **Quality gate completo e comparação pytest**: execute exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` e `uv run pytest`. O pytest final deve ter exit code 0, zero failures/errors e `passed_final >= passed_baseline`.
8. **Relatório com evidência, não opinião**: inclua baseline, RED/GREEN, snippets antes/depois, prompts capturados sem dados pessoais, inspeções, call counts, quality gate e respostas aos gates. Inclua `Handoff para verificador` com arquivos alterados, comandos exatos de rerun, riscos/limitações e checklist R1–R8. Só escreva `Status: COMPLETE` quando tudo estiver comprovado.
9. **Conclusão controlada**: somente após todos os gates passarem, marque o Slice 001 e os itens comprovados da Definition of Done de implementação. Não marque os itens operacionais. Faça commit rastreável, push, atualize o relatório com commit/push, responda com `REPORT_PATH` e pare.

## Objetivo do slice

Entregar de ponta a ponta uma chamada LLM2 coerente com a reconciliação, mantendo o artefato LLM1 original para auditoria e um único retry fail-closed para divergência de conjunto.

É um slice único porque a projeção isolada reduz o estímulo contraditório, mas só prompt + erro tipado + retry + persistência comprovam o fluxo completo. Dividir por arquivo/camada seria horizontal e deixaria um hotfix parcialmente seguro.

## Contexto técnico e limites

- O conjunto canônico é `reconciliation.detected_procedure_types`, já ordenado como `eda`, `colonoscopy`.
- `requested_procedures` vem de um schema LLM1 v2 validado, com itens tipados e sem duplicatas.
- `Case.structured_data` deve continuar mostrando o que o LLM1 afirmou, mesmo quando a reconciliação descartou um item.
- Summary e campos comuns podem mencionar outro procedimento; por isso o prompt precisa declarar a lista fechada além de filtrar a coleção.
- `procedure_recommendations` continua validado por igualdade exata; não aceite subconjunto, superset ou fallback.
- O retry novo é físico, não uma segunda análise por procedimento. Nunca divida EDA e Colonoscopia em chamadas separadas.
- O retry de idioma existente é independente. Dois orçamentos one-shot implicam máximo de três chamadas LLM2 quando ambos são acionados em sequência.
- O slice não muda jobs django-q, captura de `run_pipeline()`, eventos ou recuperação de `FAILED`.

## Escopo funcional

### R1. Criar visão efêmera canônica sem mutar auditoria

Em `apps/pipeline/orchestrator.py`:

- adicionar um helper privado com nome claro para projetar dados LLM1 ao contexto LLM2;
- usar `copy.deepcopy()` ou garantia equivalente explícita de cópia profunda;
- reconstruir `requested_procedures` na ordem de `reconciliation.detected_procedure_types`;
- reutilizar somente os itens originais correspondentes;
- remover da cópia itens não reconciliados;
- não sintetizar item ausente nem editar nested fields;
- passar a cópia apenas no argumento `llm1_structured_data` de `Llm2ServiceV2.run()`;
- manter policy, priority signals, eventos, presenter e `case.structured_data` usando `result1.structured_data` original.

Teste a igualdade do artefato persistido antes/depois e o conteúdo real capturado no prompt, não apenas o retorno do helper.

### R2. Tornar a lista reconciliada explícita em toda tentativa

Em `apps/pipeline/llm2_service_v2.py`:

- passar `detected_procedure_types` para `_render_user_prompt()`;
- serializar `list(detected_procedure_types)` com `json.dumps(..., ensure_ascii=False)` ou equivalente JSON determinístico;
- anexar texto inequívoco de lista fechada ao envelope do usuário;
- exigir exatamente um item em `procedure_recommendations` por item da lista e nenhum outro;
- repetir a mesma lista na instrução específica de retry;
- preservar `system_prompt`, template gerenciado/injetado, policy results, prior contexts e instruções pt-BR;
- não alterar seed/admin/DB de prompts.

Os testes devem extrair e fazer parse do bloco “Dados extraídos” do prompt, evitando asserts frágeis sobre o JSON inteiro.

### R3. Diferenciar mismatch por tipo, nunca por mensagem

- criar `Llm2V2ProcedureSetMismatchError` como subclasse de `Llm2V2ValidationError`;
- levantar essa subclasse somente na comparação final `returned != expected`;
- preservar a mensagem atual com expected/got para diagnóstico;
- manter parse, schema, duplicata, IDs e idioma na classe/fluxo apropriado atual;
- capturar explicitamente a subclasse no controle de retry;
- proibir `if "procedure set mismatch" in str(error)` ou matching equivalente.

Esse tipo pode permanecer no mesmo módulo; não criar hierarquia ou módulo genérico de erros.

### R4. Aplicar exatamente um retry corretivo de conjunto

- toda execução começa com orçamento de conjunto não consumido;
- ao receber `Llm2V2ProcedureSetMismatchError`, fazer uma nova chamada com instrução corretiva que repete a lista canônica;
- marcar o orçamento antes da nova chamada;
- se qualquer resposta posterior apresentar novo mismatch, propagar imediatamente;
- revalidar integralmente parse, schema, IDs, conjunto e idioma em cada resposta;
- caminho exato não faz retry;
- erro que não é mismatch de conjunto não dispara esse retry;
- não retornar a primeira resposta parcialmente válida;
- não capturar/engolir a exceção final dentro do serviço.

Teste call counts exatos com `RecordingLlmClient`: uma chamada no happy path, duas na recuperação/falha persistente do serviço.

### R5. Preservar retry de idioma com limite global finito

Refatore o mínimo necessário para que:

- uma resposta com conjunto correto e termo narrativo proibido ainda receba uma instrução pt-BR;
- cada orçamento (conjunto e idioma) seja usado no máximo uma vez;
- uma resposta de retry volte a passar por todas as validações;
- combinação dos dois motivos nunca ultrapasse três chamadas LLM2;
- segundo erro da mesma dimensão falhe;
- não haja recursão sem bound, decorator de retry, sleep/backoff ou dependência nova.

Adicione pelo menos uma regressão do retry de idioma; ela não precisa ser o teste RED principal.

### R6. Cobrir as três projeções reconciliadas no pipeline

Em `apps/pipeline/tests/test_slice_002_pipeline.py`, adicionar cenários semanticamente reais:

1. **EDA-only**: caso declarado EDA; LLM1 lista ambos; texto solicita EDA e contém Colonoscopia apenas histórica/negada; LLM2 responde somente EDA.
2. **Colonoscopia-only**: caso declarado Colonoscopia; LLM1 lista ambos; texto solicita Colonoscopia e contém EDA apenas histórica/negada; LLM2 responde somente Colonoscopia.
3. **Combinado**: declaração/texto/LLM1/reconciliação mantêm ambos; LLM2 responde ambos.

Para cada cenário relevante, provar:

- status final `WAIT_DOCTOR`;
- bloco LLM1 do prompt contém exatamente os tipos esperados em `requested_procedures`;
- lista canônica explícita corresponde ao reconciliado;
- recomendações finais correspondem ao mesmo conjunto;
- sem mismatch, o total é duas chamadas no cliente compartilhado (LLM1 + uma LLM2);
- nos cenários single, `case.structured_data` persistido ainda contém ambos.

Reutilize builders existentes e textos já suportados. Não adicione `colonospia`, `colonoscópica` ou outro alias ao detector/testes.

### R7. Preservar falha controlada e contratos existentes

Atualize a regressão de conjunto inválido para fornecer duas respostas LLM2 divergentes e provar:

- total de três chamadas no cliente compartilhado (LLM1 + tentativa LLM2 + retry LLM2);
- caso termina `FAILED` pelo tratamento existente;
- `suggested_action is None`;
- `PIPELINE_FAILED` contém `procedure set mismatch` referente à falha final;
- nenhum `LLM2_OK`/`CASE_READY_FOR_DOCTOR` é produzido após a falha.

Preserve, sem enfraquecer:

- rejeição de lista omitida/vazia;
- rejeição de duplicata;
- rejeição de item adicionado;
- validação de IDs;
- suporte global mais restritivo;
- EDA, Colonoscopia e combinado normais;
- nenhuma persistência parcial.

### R8. Manter o hotfix estritamente delimitado

Não alterar:

- `apps/pipeline/scope_detection.py` ou qualquer regex/alias;
- `apps/pipeline/procedure_reconciliation.py` ou matriz D7;
- `apps/pipeline/schemas/**`;
- policy, prior-case, LLM1, presenter ou apps fora de pipeline;
- models, migrations, FSM, eventos, settings, django-q ou dependências;
- prompts ativos/seed/admin;
- recuperação/reprocessamento de `FAILED`;
- casos ou infraestrutura de produção.

Se um teste revelar necessidade real fora dos quatro arquivos, pare e consulte o planner. Não basta justificar depois.

## Arquivos esperados e limite de escopo

Arquivos funcionais permitidos, máximo de quatro:

1. `apps/pipeline/orchestrator.py`
2. `apps/pipeline/llm2_service_v2.py`
3. `apps/pipeline/tests/test_slice_002_contracts.py`
4. `apps/pipeline/tests/test_slice_002_pipeline.py`

Após todos os gates, o único arquivo adicional permitido é:

- `openspec/changes/fix-llm2-reconciled-procedure-set/tasks.md`

Arquivos proibidos incluem detector, reconciliação, schemas, models, migrations, prompts/seed, settings, Docker, demais apps e demais specs. Qualquer arquivo funcional extra sem autorização explícita torna o slice INCOMPLETE/BLOQUEADO.

## TDD obrigatório: RED → GREEN → REFACTOR

### 1. Preparação e baseline

Antes de editar:

```bash
git status --short
git branch --show-current
BASE_REF=$(git rev-parse HEAD)
printf 'BASE_REF=%s\n' "$BASE_REF"
uv run pytest
```

Se necessário, suba somente o banco de teste conforme `AGENTS.md`. Não use produção nem mude settings para contornar infraestrutura.

Registre hash, exit code, resumo completo, `failed=0`, `errors=0` e `passed_baseline`.

### 2. RED real

Edite primeiro somente:

- `apps/pipeline/tests/test_slice_002_contracts.py`
- `apps/pipeline/tests/test_slice_002_pipeline.py`

Use nomes contendo os termos abaixo ou adapte o `-k` e registre o comando exato:

- `reconciled_procedure_context`
- `procedure_set_retry`
- `persistent_procedure_set_mismatch`

Rode:

```bash
uv run pytest \
  apps/pipeline/tests/test_slice_002_contracts.py \
  apps/pipeline/tests/test_slice_002_pipeline.py \
  -v -k 'reconciled_procedure_context or procedure_set_retry or persistent_procedure_set_mismatch'
```

Resultado obrigatório: exit code não zero e falha semântica esperada, por exemplo:

- prompt LLM2 ainda contém ambos quando reconciliado é singular;
- lista canônica explícita não existe;
- primeiro mismatch aborta sem segunda chamada;
- falha persistente usa apenas uma tentativa LLM2.

RED por `StopIteration`, resposta fake insuficiente, sintaxe, import, fixture ou banco não conta. Testes de regressão que já passam podem coexistir, mas não substituem o RED.

### 3. GREEN mínimo

Implemente R1–R5 apenas nos dois arquivos de produto. Rode:

```bash
uv run pytest \
  apps/pipeline/tests/test_slice_002_contracts.py \
  apps/pipeline/tests/test_slice_002_pipeline.py \
  -v -k 'reconciled_procedure_context or procedure_set_retry or persistent_procedure_set_mismatch'
uv run pytest apps/pipeline/tests/test_slice_002_contracts.py apps/pipeline/tests/test_slice_002_pipeline.py -q
```

Todos devem passar. Não enfraqueça asserts, não altere builders globais para esconder diferença e não faça o validator aceitar conjuntos diferentes.

### 4. REFACTOR seguro

Revise os quatro arquivos:

- helper de projeção pequeno, privado, determinístico e sem side effect;
- um único local serializa a lista canônica;
- erro tipado controla retry sem matching textual;
- budgets one-shot com fluxo legível e sem recursão;
- chamada/validação não duplicada desnecessariamente;
- comentários/docstrings não prometem mais uma única chamada física absoluta;
- nenhum código morto, abstração de retry genérica ou comportamento futuro;
- clean code, DRY, YAGNI, nomes claros, coesão e baixo acoplamento.

Rode novamente os testes alvo após qualquer refactor.

## Checks de inspeção obrigatórios antes de concluir

Execute todos e cole resultado + interpretação no relatório.

### I1. Projeção efêmera e boundary correto

```bash
rg -n 'deepcopy|requested_procedures|detected_procedure_types|Llm2ServiceV2|llm1_structured_data=' apps/pipeline/orchestrator.py
if rg -n 'llm1_structured_data=result1\.structured_data' apps/pipeline/orchestrator.py; then
  echo 'ERRO: LLM2 ainda recebe diretamente o artefato bruto do LLM1'
  exit 1
else
  echo 'OK: chamada LLM2 não recebe diretamente result1.structured_data'
fi
```

Confirme que somente a chamada LLM2 usa a cópia; policy/eventos/persistência continuam usando o original.

### I2. Lista canônica no prompt

```bash
rg -n 'detected_procedure_types|json\.dumps|reconciliad|lista fechada|exatamente um item|procedure_recommendations' apps/pipeline/llm2_service_v2.py
```

Confirme serialização JSON determinística, cardinalidade exata e repetição no retry. Texto equivalente é aceitável, desde que os testes capturem o contrato.

### I3. Erro tipado e retry restrito

```bash
rg -n 'Llm2V2ProcedureSetMismatchError|procedure set mismatch|procedure_set_retry|language.*retry|except ' apps/pipeline/llm2_service_v2.py
if rg -n 'procedure set mismatch.*str\(|str\([^)]*\).*procedure set mismatch' apps/pipeline/llm2_service_v2.py; then
  echo 'ERRO: controle de retry depende da mensagem da exceção'
  exit 1
else
  echo 'OK: nenhum matching textual aparente para controlar retry'
fi
```

Interprete onde a subclasse nasce, onde é capturada e como o segundo mismatch escapa. Call counts são provados por testes, não por `rg`.

### I4. Detector, reconciliação e schemas intocados

```bash
git diff --exit-code "$BASE_REF" -- \
  apps/pipeline/scope_detection.py \
  apps/pipeline/procedure_reconciliation.py \
  apps/pipeline/schemas \
  apps/cases/models.py
if rg -n -i 'colonospia|colonosc[oó]pica' apps/pipeline/scope_detection.py apps/pipeline/tests; then
  echo 'ERRO: variantes ortográficas fora de escopo foram adicionadas'
  exit 1
else
  echo 'OK: variantes ortográficas fora de escopo ausentes'
fi
```

Qualquer diff nos caminhos protegidos é bloqueio.

### I5. Testes cobrem conjuntos, retry e auditoria

```bash
rg -n 'reconciled_procedure_context|procedure_set_retry|persistent_procedure_set_mismatch|structured_data|WAIT_DOCTOR|FAILED|PIPELINE_FAILED|client\.calls' \
  apps/pipeline/tests/test_slice_002_contracts.py \
  apps/pipeline/tests/test_slice_002_pipeline.py
```

Adapte os padrões apenas se os nomes forem diferentes; no relatório mapeie cada cenário EDA-only, Colon-only, ambos, recovery e failure ao teste exato.

### I6. Escopo e higiene

```bash
git diff --check
git diff --name-only "$BASE_REF" -- | sort
git status --short
```

Antes de marcar tasks, somente os quatro arquivos funcionais podem aparecer. Depois, também pode aparecer `openspec/changes/fix-llm2-reconciled-procedure-set/tasks.md`.

### I7. Validação OpenSpec e testes alvo finais

```bash
openspec validate fix-llm2-reconciled-procedure-set --strict
uv run pytest \
  apps/pipeline/tests/test_slice_002_contracts.py \
  apps/pipeline/tests/test_slice_002_pipeline.py \
  -v -k 'reconciled_procedure_context or procedure_set_retry or persistent_procedure_set_mismatch'
uv run pytest apps/pipeline/tests/test_slice_002_contracts.py apps/pipeline/tests/test_slice_002_pipeline.py -q
```

Se os nomes diferirem, registre a expressão usada e prove que todos os testes novos foram selecionados.

## Critérios de sucesso binários

- [ ] S1. Worktree inicial limpo, branch autorizada, `BASE_REF` registrado e baseline completo verde.
- [ ] S2. Matriz requisito→arquivo→teste/inspeção foi escrita antes da implementação.
- [ ] S3. RED real foi capturado antes de código de produto por contexto bruto ou ausência de retry.
- [ ] S4. Helper cria cópia profunda e filtra somente `requested_procedures`.
- [ ] S5. Ordem da lista efêmera segue `detected_procedure_types` e nenhum item é inventado.
- [ ] S6. `case.structured_data` original permanece byte/logicamente equivalente ao payload validado do LLM1.
- [ ] S7. Prompt inicial declara lista JSON fechada e cardinalidade exata.
- [ ] S8. Retry de conjunto repete exatamente a mesma lista canônica.
- [ ] S9. EDA-only, Colonoscopia-only e combinado chegam a `WAIT_DOCTOR` com conjuntos corretos.
- [ ] S10. Happy path exato mantém uma chamada LLM2.
- [ ] S11. Primeiro mismatch corrigido usa exatamente duas chamadas LLM2 e retorna resultado válido.
- [ ] S12. Segundo mismatch falha sem terceira tentativa de conjunto.
- [ ] S13. Erro de conjunto possui subclasse e não há matching textual de mensagem.
- [ ] S14. JSON/schema/duplicata/IDs não disparam retry de conjunto.
- [ ] S15. Retry pt-BR permanece funcional, one-shot e validado novamente.
- [ ] S16. Combinação dos dois budgets é finita e não ultrapassa três chamadas LLM2.
- [ ] S17. Falha persistente produz `FAILED`/`PIPELINE_FAILED`, sem `suggested_action`, `LLM2_OK` ou chegada ao médico.
- [ ] S18. Validator de igualdade exata, suporte global e regressões existentes não foram enfraquecidos.
- [ ] S19. Detector, reconciliação, schemas, models, migrations, FSM, prompts e filas permaneceram intactos.
- [ ] S20. Nenhuma variante ortográfica, recuperação de `FAILED`, reprocessamento ou operação de produção foi adicionada.
- [ ] S21. Testes alvo e os dois arquivos completos de teste passam.
- [ ] S22. Inspeções I1–I7 foram executadas e interpretadas.
- [ ] S23. Somente quatro arquivos funcionais permitidos foram alterados.
- [ ] S24. Quality gate completo passou com pytest final exit 0, `failed=0`, `errors=0` e `passed_final >= passed_baseline`.
- [ ] S25. Relatório temporário contém matriz, baseline, RED/GREEN, snippets, prompts saneados, call counts, inspeções e handoff.
- [ ] S26. `tasks.md` foi atualizado somente após S1–S25; itens operacionais ficaram desmarcados; commit e push foram concluídos.

## Gates de autoavaliação

Responda objetivamente no relatório, citando teste, linha ou comando:

1. Qual objeto permanece persistido em `Case.structured_data` e qual objeto efêmero é enviado ao LLM2?
2. Qual teste prova que LLM1 com ambos + reconciliação EDA-only envia apenas EDA ao LLM2 sem apagar Colonoscopia do artefato original?
3. Qual teste prova o cenário espelho de Colonoscopia-only?
4. Qual teste prova que combinado continua com ambos e sem retry desnecessário?
5. Como a ordem canônica é determinada? Algum item clínico é sintetizado? A resposta correta é não.
6. Onde a lista fechada aparece no prompt? Mostre trecho saneado e parse JSON dos três conjuntos.
7. O template ativo no banco pode omitir essa lista? A resposta correta é não, pois o envelope do serviço a anexa.
8. Qual classe distingue mismatch de conjunto? Existe qualquer matching em `str(error)`?
9. Quantas chamadas LLM2 ocorrem no happy path, na recuperação do primeiro mismatch e em dois mismatches?
10. Qual teste prova que erro não relacionado ao conjunto não usa esse retry?
11. Como os budgets de conjunto e idioma impedem loop? Qual é o máximo físico de chamadas LLM2?
12. Toda resposta de retry repassa parse, schema, IDs, conjunto e idioma?
13. O que é persistido antes da validação final? A resposta deve confirmar que não há `suggested_action` parcial.
14. Qual teste prova `FAILED` + `PIPELINE_FAILED` e ausência de `LLM2_OK` no segundo mismatch?
15. Alguma regex, alias, matriz, schema, model, migration, FSM, prompt versionado ou tarefa django-q mudou? A resposta correta é não, com diff.
16. Foi criada recuperação de casos `FAILED` ou alteração em produção? A resposta correta é não.
17. Quais testes existentes de omissão, duplicata, adição, IDs, idioma e suporte foram preservados?
18. Qual teste falhou no RED e por que a falha era semanticamente correta?
19. Quais arquivos mudaram desde `BASE_REF`? Coincidem exatamente com o limite?
20. Qual foi a contagem pytest baseline/final? Final teve exit 0, zero failures/errors e `passed_final >= passed_baseline`?
21. Qual risco residual permanece? Cite que o LLM ainda pode divergir duas vezes, caso em que o desenho deliberadamente mantém fail-closed e exige reapresentação operacional posterior.

## Condições automáticas de INCOMPLETO

Marque **INCOMPLETO/BLOQUEADO (INCOMPLETE)**, não atualize `tasks.md` e não faça commit/push se ocorrer qualquer situação:

- worktree inicial sujo, branch não autorizada ou implementação em `main`;
- baseline completo ausente, não registrado ou com exit code diferente de 0/falha/erro;
- matriz requisito→arquivo→teste ausente;
- teste planejado não escrito/executado;
- ausência de RED real antes do produto;
- RED causado por sintaxe/import/fixture/infraestrutura/`StopIteration` em vez do contrato;
- teste enfraquecido/removido para obter GREEN;
- LLM2 continuar recebendo diretamente `result1.structured_data` bruto;
- filtro mutar `case.structured_data` ou nested data original;
- projeção inventar item clínico ou reescrever summary/evidence;
- prompt não declarar lista JSON fechada e cardinalidade exata;
- conjunto do prompt divergir do conjunto usado pelo validator;
- retry depender de substring da mensagem em vez de erro tipado;
- happy path executar retry desnecessário;
- primeiro mismatch não receber exatamente uma chance corretiva;
- segundo mismatch receber nova chance ou ser aceito;
- JSON/schema/duplicata/IDs consumirem retry de conjunto;
- qualquer retry deixar de repetir validação integral;
- retry de idioma ser removido, ficar ilimitado ou deixar de falhar após seu budget;
- combinação permitir mais de três chamadas LLM2 ou loop/recursão sem bound;
- resposta parcial ser persistida;
- caso com mismatch persistente chegar a `WAIT_DOCTOR` ou gerar `LLM2_OK`;
- regex/alias de detector, matriz de reconciliação, schema, policy, model, migration, FSM, evento, prompt versionado, fila ou dependência ser alterado;
- variante `colonospia`/`colonoscópica` ser adicionada;
- recuperação/reprocessamento de `FAILED` ou acesso/operação de produção ser implementado;
- qualquer arquivo funcional fora dos quatro permitidos mudar sem autorização prévia;
- qualquer check I1–I7 não ser executado ou revelar anti-pattern;
- `openspec validate --strict` ou `git diff --check` falhar;
- testes alvo ou arquivos completos de teste falharem;
- quality gate completo não ser executado;
- ruff, format, mypy ou pytest falhar;
- pytest final ter exit code != 0, `failed > 0` ou `errors > 0`;
- `passed_final < passed_baseline`;
- relatório registrar somente quantidade de passed sem exit code e zero failures/errors;
- relatório temporário não existir no caminho exigido ou não conter `Handoff para verificador`;
- itens operacionais de `tasks.md` serem marcados durante implementação;
- commit/push ocorrer apesar de gate faltante ou falho.

Em bloqueio ambiental, preserve evidências e reporte o motivo. Não remova gates nem amplie escopo para contornar.

## Quality gate obrigatório

Após GREEN, REFACTOR e inspeções, execute separadamente e registre cada exit code:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

Compare explicitamente:

```text
passed_final >= passed_baseline
failed_final = 0
errors_final = 0
exit_code_final = 0
```

Também execute:

```bash
openspec validate fix-llm2-reconciled-procedure-set --strict
git status --short
git diff --check
git diff --stat "$BASE_REF"
```

## Relatório markdown temporário obrigatório

Criar exatamente:

```text
/tmp/fix-llm2-reconciled-procedure-set-slice-001-report.md
```

O arquivo é temporário e não deve ser commitado. Estrutura mínima obrigatória:

```markdown
# Relatório — fix-llm2-reconciled-procedure-set — Slice 001

## Status
Status: COMPLETE | INCOMPLETE

## Identificação
- Branch:
- BASE_REF:
- Commit final:
- Push remoto:

## Matriz requisito → arquivo(s) → teste(s)/inspeção
| Requisito | Arquivos | Testes/inspeções | Resultado |
| --- | --- | --- | --- |

## Baseline antes de editar
- `git status --short`:
- `uv run pytest`:
- Exit code:
- Resumo: passed=?, failed=0, errors=0

## RED
- Arquivos de teste alterados primeiro:
- Comando:
- Exit code:
- Teste(s) falhando:
- Motivo semântico esperado:
- Trecho de output:

## GREEN
- Implementação mínima por requisito:
- Comandos alvo:
- Exit codes e resumos:

## REFACTOR
- Limpezas realizadas:
- Evidência clean code/DRY/YAGNI:
- Confirmação de nenhum escopo futuro:

## Snippets antes/depois
- Chamada LLM2 no orchestrator:
- Projeção de `requested_procedures`:
- Envelope com conjunto canônico:
- Erro tipado + budgets de retry:
- Persistência/falha controlada:

## Evidência dos três conjuntos
| Cenário | requested_procedures no prompt | lista fechada | artefato persistido | recomendações | chamadas |
| --- | --- | --- | --- | --- | --- |
| EDA-only | | | | | |
| Colonoscopia-only | | | | | |
| Combinado | | | | | |

## Evidência dos retries
| Cenário | Respostas | Chamadas LLM2 | Resultado final |
| --- | --- | --- | --- |
| Sem mismatch | | | |
| Primeiro mismatch corrigido | | | |
| Dois mismatches | | | |
| Erro não-set | | | |
| Idioma | | | |

## Checks de inspeção I1–I7
- Comandos:
- Outputs/resumos:
- Interpretação:

## Pytest baseline vs final
- BASE_REF:
- Baseline: exit code, passed, failed=0, errors=0
- Final: exit code, passed, failed=0, errors=0
- `passed_final >= passed_baseline`: Sim/Não

## Quality gate completo
- `uv run ruff check .`:
- `uv run ruff format --check .`:
- `uv run mypy .`:
- `uv run pytest`:
- `openspec validate ... --strict`:
- `git diff --check`:

## Gates de autoavaliação
1. ...

## Escopo
- Arquivos alterados desde BASE_REF:
- Arquivos extras: nenhum | justificativa/autorização
- Detector/reconciliação/schema/model/FSM/prompts/produção intactos: Sim/Não

## Handoff para verificador
- Arquivos alterados:
- Comandos exatos para rerun:
- Testes RED/GREEN relevantes:
- Riscos/limitações:
- Checklist R1–R8:
- Itens operacionais deliberadamente pendentes:
```

Não copie nomes, texto clínico integral, PDFs, chaves ou segredos de produção para o relatório. Use apenas fixtures sintéticas e identificadores técnicos necessários.

## Commit e push

Somente após todos os gates e o relatório:

```text
fix(pipeline): alinhar LLM2 ao conjunto reconciliado
```

Faça push para `feature/fix-llm2-reconciled-procedure-set` (ou branch explicitamente atribuída). Não crie tag, release, deploy nem reapresente casos neste slice.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, every artifact under openspec/changes/fix-llm2-reconciled-procedure-set, the canonical procedure-neutral-analysis spec, ADR-0004, and all implementation/test files listed in Slice 001. Implement ONLY this slice on feature/fix-llm2-reconciled-procedure-set; never implement directly on main.

Follow the DeepSeek4-Flash protocol literally: clean worktree, BASE_REF, full pytest baseline before edits, requirement matrix, tests first with a semantic RED, minimal GREEN, narrow clean-code/DRY/YAGNI refactor, every inspection I1–I7, full quality gate, OpenSpec strict validation, and baseline-vs-final comparison. Any missing/failing evidence, pytest failure/error, passed_final < baseline, forbidden file, or unbounded retry means INCOMPLETE: do not update tasks.md and do not commit/push.

Deliver one vertical flow: deep-copy the LLM1 structured data for LLM2, filter only requested_procedures by reconciliation.detected_procedure_types in canonical order, preserve the original persisted artifact, append the exact reconciled JSON list to every LLM2 prompt, distinguish procedure-set mismatch with a typed exception, and allow exactly one set-specific corrective retry while preserving the bounded pt-BR retry. Keep exact-set validation fail-closed. Prove EDA-only, Colonoscopy-only, combined, first-mismatch recovery, second-mismatch failure, non-set no-retry, language regression, call counts, and no partial suggestion.

Do not touch scope_detection regex/aliases (including colonospia/colonoscópica), procedure reconciliation, schemas, policy, models, migrations, FSM, managed prompts, queues, dependencies, or any app outside the four allowed files. Do not add FAILED recovery, reprocess jobs, deploy, access production, or re-present cases.

Create /tmp/fix-llm2-reconciled-procedure-set-slice-001-report.md with factual evidence and Handoff for verifier. If and only if every gate passes, mark only Slice 001 and implementation DoD items, leave operational items unchecked, commit, push, reply REPORT_PATH=/tmp/fix-llm2-reconciled-procedure-set-slice-001-report.md, and STOP for planner review.
```
