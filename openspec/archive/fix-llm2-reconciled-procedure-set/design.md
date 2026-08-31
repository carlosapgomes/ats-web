<!-- markdownlint-disable MD013 -->

# Design: Contexto canônico reconciliado e retry limitado do LLM2

## Estado atual confirmado

O caminho executável está em `apps/pipeline/orchestrator.py::_run_v2_pipeline()`:

```text
Llm1ServiceV2.run()
→ case.structured_data = result1.structured_data
→ detect_requested_procedures_v2()
→ reconcile_detected_procedures()
→ policy/prior context por reconciliation.detected_procedure_types
→ Llm2ServiceV2.run(
      llm1_structured_data=result1.structured_data,
      detected_procedure_types=reconciliation.detected_procedure_types,
  )
```

`apps/pipeline/llm2_service_v2.py` serializa integralmente `llm1_structured_data` no prompt. `_decode_and_validate()` compara a coleção devolvida com `detected_procedure_types` e levanta `Llm2V2ValidationError` quando os conjuntos divergem.

A validação está correta. A inconsistência está na entrada: policy, prior contexts e validator usam o conjunto reconciliado, enquanto a seção “Dados extraídos” ainda pode apresentar procedimentos descartados como históricos/negados pela reconciliação.

O serviço já possui um retry de idioma pt-BR. Portanto, a intenção arquitetural da ADR-0004 de “uma chamada LLM2” deve ser lida como **uma análise conjunta por caso, nunca uma chamada separada por procedimento**; tentativas corretivas limitadas de validação já fazem parte do comportamento do serviço.

## Invariantes

1. O conjunto reconciliado é a autoridade operacional downstream.
2. O `structured_data` validado do LLM1 é a autoridade auditável da extração original e não pode ser mutado.
3. O LLM2 recebe uma visão efêmera coerente, nunca um segundo artefato persistido.
4. Igualdade exata da resposta LLM2 continua obrigatória.
5. Retry é exceção limitada, não substitui validação nem cria loop.
6. Nenhum procedimento ou dado clínico pode ser sintetizado durante a projeção.

## D1. Projetar uma cópia efêmera no boundary do orchestrator

Adicionar um helper privado e coeso em `apps/pipeline/orchestrator.py` para construir a visão do LLM2. O helper recebe:

- `result1.structured_data`;
- `reconciliation.detected_procedure_types`.

Comportamento normativo:

1. realizar cópia profunda do dicionário JSON do LLM1;
2. indexar os itens originais de `requested_procedures` por `procedure_type`;
3. reconstruir a lista seguindo a ordem de `detected_procedure_types`;
4. incluir somente itens originais cujo tipo pertence ao conjunto reconciliado;
5. não criar item ausente, não alterar campos comuns, summary, evidence spans ou valores internos;
6. passar a cópia somente para `Llm2ServiceV2.run()`.

A cópia profunda torna a fronteira explícita e protege auditoria contra mutações futuras no serviço. `case.structured_data`, `result1.structured_data`, eventos e projeções de policy continuam usando o objeto original.

Não mover essa regra para `scope_detection.py` nem reescrever `structured_data`: reconciliar e projetar são responsabilidades distintas.

## D2. Declarar o conjunto reconciliado como lista fechada no prompt

`Llm2ServiceV2._render_user_prompt()` passa a receber `detected_procedure_types` e acrescenta uma seção dinâmica, independente do template versionado, equivalente a:

```text
Procedimentos canônicos reconciliados (lista fechada): ["eda"]
Produza exatamente um item em procedure_recommendations para cada item dessa lista e nenhum outro.
```

Regras:

- serializar o conjunto como lista JSON, não como representação Python de tuple/set;
- preservar a ordem canônica recebida do orchestrator;
- usar a mesma lista na tentativa inicial e em qualquer retry;
- manter policy results e prior contexts já separados pelos mesmos tipos;
- anexar a seção depois do template, de modo que prompts ativos no banco, fallbacks e templates injetados em testes recebam o mesmo contrato;
- não alterar `seed_prompts`, versões no banco ou admin.

A filtragem D1 remove o item contraditório da coleção clínica; a lista explícita D2 elimina ambiguidade residual em summary ou texto comum preservado.

## D3. Usar erro tipado para mismatch de conjunto

Criar em `llm2_service_v2.py` uma exceção específica, por exemplo `Llm2V2ProcedureSetMismatchError`, como subclasse de `Llm2V2ValidationError`.

`_decode_and_validate()` deve levantar essa subclasse somente quando a resposta já passou por:

- parse JSON;
- schema Pydantic;
- validação de `case_id`;
- validação de `agency_record_number`;

e então o conjunto de `procedure_recommendations` difere de `detected_procedure_types`.

Demais erros continuam usando `Llm2V2ValidationError`. O controle de retry não deve fazer matching de strings como `"procedure set mismatch" in str(error)`, pois isso acopla fluxo de controle à mensagem humana.

Duplicatas continuam sendo rejeitadas pelo schema/model validator e não se tornam motivo para retry de conjunto. Payload não JSON, schema inválido, IDs divergentes e demais erros também falham imediatamente.

## D4. Um orçamento de retry por dimensão de correção

O serviço mantém dois orçamentos booleanos e finitos:

- `procedure_set_retry_used`: novo, inicialmente falso;
- `language_retry_used`: comportamento pt-BR existente, inicialmente falso.

Fluxo:

```text
tentativa inicial
→ parse/schema/IDs
→ mismatch de conjunto?
   → orçamento disponível: acrescenta instrução corretiva + tenta uma vez
   → orçamento consumido: propaga erro
→ conjunto válido
→ termos narrativos proibidos?
   → orçamento de idioma disponível: acrescenta instrução pt-BR + tenta uma vez
   → orçamento consumido: falha
→ retorna resultado validado
```

Cada resposta, inclusive retries, percorre novamente parse, schema, IDs, conjunto e idioma. Cada orçamento pode ser consumido no máximo uma vez. Assim:

- caminho normal: 1 chamada LLM2;
- somente mismatch de conjunto: no máximo 2 chamadas;
- somente idioma: no máximo 2 chamadas, como hoje;
- ambas as dimensões em respostas sucessivas: no máximo 3 chamadas;
- segundo mismatch de conjunto: falha imediatamente, independentemente da etapa em que ocorra.

A instrução corretiva de conjunto deve repetir a lista JSON canônica e informar que a resposta anterior omitiu/adicionou procedimento. Não enviar a resposta inválida de volta ao modelo nem incluir dados novos.

## D5. Preservar fail-closed e auditoria

O validator de igualdade exata permanece após todos os retries. Somente um `Llm2V2Result` integralmente válido permite construir `case.suggested_action` e avançar a FSM.

Se o mismatch persistir:

- a exceção sobe para o tratamento já existente de `run_pipeline()`;
- `PIPELINE_FAILED` registra o erro;
- `_try_fail_case()` mantém o caso em `FAILED` conforme o fluxo atual;
- nenhuma recomendação parcial é persistida;
- django-q não ganha retry automático;
- nenhum caso antigo é reaberto.

Em recuperação no retry, o fluxo segue normalmente e registra o `LLM2_OK` existente. Não criar novo `CaseEvent`, campo ou modelo apenas para contar a tentativa neste hotfix.

A auditoria do contraste permanece disponível por duas fontes já existentes:

- `Case.structured_data`: afirmação original do LLM1, sem alteração;
- `CASE_PROCEDURES_DETECTED`/`LLM2_OK`: conjunto reconciliado operacional.

## D6. Cobertura em dois níveis

### Contrato do serviço

Em `apps/pipeline/tests/test_slice_002_contracts.py`:

1. prompt inicial contém a lista JSON reconciliada e cardinalidade exata;
2. primeira resposta com conjunto errado + segunda correta retorna sucesso e usa duas chamadas;
3. duas respostas com conjunto errado levantam erro e usam exatamente duas chamadas;
4. erro não relacionado a conjunto não recebe retry de conjunto;
5. caminho exato continua com uma chamada;
6. retry de idioma continua limitado e funcional;
7. cobertura existente de omissão, duplicata e adição não é removida nem enfraquecida.

### Pipeline integrado

Em `apps/pipeline/tests/test_slice_002_pipeline.py`:

1. LLM1 lista ambos, texto/reconciliação mantém somente EDA: prompt LLM2 contém apenas o item EDA e o caso chega a `WAIT_DOCTOR` com recomendação EDA;
2. espelho para Colonoscopia;
3. ambos reconciliados: prompt e resposta mantêm ambos;
4. nos cenários single, `case.structured_data.requested_procedures` ainda contém os dois itens originais;
5. segundo mismatch deixa caso `FAILED`, sem `suggested_action`, com erro de mismatch auditável;
6. número de chamadas distingue LLM1 da tentativa inicial/retry LLM2.

Os textos de teste devem usar referências históricas ou negações já reconhecidas pelo detector atual. Não adicionar grafias novas nem alterar regex para montar o cenário.

## Arquivos funcionais previstos

1. `apps/pipeline/orchestrator.py`
2. `apps/pipeline/llm2_service_v2.py`
3. `apps/pipeline/tests/test_slice_002_contracts.py`
4. `apps/pipeline/tests/test_slice_002_pipeline.py`

Após validação, somente `tasks.md` do change é atualizado. Qualquer quinto arquivo funcional exige revisão prévia de escopo.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Mutar o artefato original ao filtrar | Cópia profunda + teste de `case.structured_data` após o pipeline |
| Template ativo no banco ocultar o conjunto | Envelope dinâmico anexado pelo serviço, fora do conteúdo versionado |
| Retry mascarar resposta inválida | Subclasse exclusiva, orçamento de uma tentativa e validação integral repetida |
| Loop entre retry de idioma e conjunto | Dois flags one-shot; máximo físico de três chamadas |
| Retry disparar por schema/ID/JSON | Teste de não-retry e captura somente da subclasse de conjunto |
| Regressão do combinado | Teste integrado preserva ambos e uma recomendação por tipo |
| Ampliação indevida do detector | Arquivo proibido + inspeção Git/`rg` |
| Caso falho receber artefato parcial | Persistência continua posterior a `Llm2V2Result` válido + teste fail-closed |

## Rollout e rollback

O slice não executa operação em produção. Depois de aprovado, o rollout usa deploy normal sem migration, seguido de smoke dos três conjuntos suportados. As ocorrências afetadas são reapresentadas uma vez; registros antigos permanecem históricos.

Rollback é revert de código e redeploy. Não existe rollback de banco. A projeção é somente em memória e não altera JSON persistido.
