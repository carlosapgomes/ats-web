# Proposal: Barreira de Aceitação para PDFs de Relatório de Regulação

## Contexto

Após o upload múltiplo assíncrono, o intake aceita qualquer arquivo com extensão `.pdf` dentro dos limites de tamanho/lote. A extração de texto roda em background e o pipeline LLM tenta classificar o conteúdo depois.

Teste manual e amostra local comparativa indicaram que relatórios de regulação possuem assinatura textual consistente, enquanto PDFs não-regulatórios como laudos, exames laboratoriais e imagens não possuem esses sinais.

Amostra analisada:

- `~/temp/regulacoes`: 12 PDFs de regulação.
- `~/temp/nao-regulacoes`: 4 PDFs não-regulatórios.

Sinais fortes encontrados nos relatórios de regulação:

- `RELATÓRIO DE OCORRÊNCIAS`
- `Governo do Estado da Bahia`
- `Secretaria da Saúde do Estado`
- `Central Estadual de Regulação`
- `Código:`
- `Abertura:`
- `Dias em tela`
- `Data Adm. Unid.`
- `Unid. Origem`
- `Motivo da Solicitação`
- `Complemento da Solicitação`
- `Resumo Clínico`

Os PDFs não-regulatórios podem conter termos genéricos como `Paciente` ou `Solicitante`, portanto esses termos não devem ser usados como critério isolado.

## Problema

Hoje um PDF válido tecnicamente, mas que não é relatório de regulação, pode:

1. criar um `Case`;
2. extrair texto;
3. receber número de registro artificial por fallback de timestamp;
4. consumir pipeline LLM desnecessariamente;
5. produzir resultado incerto ou falhar tardiamente.

Isso aumenta custo, ruído operacional e risco de interpretação indevida de documentos fora do fluxo de regulação.

## Objetivos

1. Criar uma barreira determinística pós-extração para identificar se o PDF é relatório de regulação.
2. Evitar chamada ao pipeline LLM quando o documento não passar na barreira.
3. Preservar rastreabilidade via FSM e `CaseEvent`.
4. Direcionar documentos fora do padrão para resultado NIR de revisão manual obrigatória, sem fila médica.
5. Manter aceitos relatórios de regulação que solicitem exames fora do escopo EDA, como colonoscopia; a barreira valida o formato de regulação, não o tipo de exame.
6. Cobrir o comportamento com testes automatizados usando textos sintéticos/anonimizados, sem depender de PDFs reais sensíveis no repositório.

## Não Objetivos

- Não implementar OCR para PDFs escaneados sem camada de texto.
- Não bloquear no upload síncrono com leitura pesada de PDF.
- Não rejeitar arquivo antes de criar `Case`; a decisão ocorre no worker de extração para manter o upload rápido.
- Não alterar a regra de scope gate EDA vs `non_eda`/`unknown` existente.
- Não treinar classificador ML/LLM para detectar regulação.
- Não armazenar PDFs reais de pacientes no repositório.

## Critério de Aceitação Proposto

Um texto extraído deve ser aceito como relatório de regulação se:

```text
has_text_minimum
AND has_header
AND has_institutional_signal
AND operational_section_count >= 3
```

Onde:

- `has_text_minimum`: texto limpo com tamanho mínimo configurável, inicialmente 500 caracteres.
- `has_header`: contém `RELATÓRIO DE OCORRÊNCIAS` com normalização de acentos/caixa.
- `has_institutional_signal`: contém ao menos um de:
  - `Central Estadual de Regulação`
  - `Secretaria da Saúde do Estado`
  - `Governo do Estado da Bahia`
- `operational_section_count`: quantidade de seções presentes entre:
  - `Código:`
  - `Abertura:`
  - `Unid. Origem` ou `Unidade de Origem`
  - `Motivo da Solicitação`
  - `Complemento da Solicitação`
  - `Resumo Clínico`
  - `Dias em tela`
  - `Data Adm. Unid.`

## Resultado Esperado para Falha da Barreira

Quando a barreira falhar:

- salvar `extracted_text` para auditoria;
- salvar `agency_record_number` apenas se encontrado por padrão explícito, evitando fallback artificial como identificador de regulação;
- não enfileirar `enqueue_pipeline()`;
- persistir `suggested_action` com:
  - `decision = manual_review_required`;
  - `suggestion = manual_review_required`;
  - `reason_code = invalid_regulation_report`;
  - `reason_text` claro para o NIR;
- transicionar para `WAIT_R1_CLEANUP_THUMBS` via FSM rastreável;
- registrar `CaseEvent` específico, por exemplo `REGULATION_REPORT_GATE_FAILED`.

## Riscos

- Relatórios de regulação de outro emissor/layout podem ser barrados se não tiverem a assinatura esperada.
- Se a régua for frouxa demais, laudos com palavras genéricas podem passar.
- PDFs escaneados sem texto seguirão sem OCR; devem falhar por texto insuficiente.
- A função atual de extração de número usa timestamp como fallback; a feature precisa evitar tratar esse fallback como evidência de relatório válido.

## Decisões Confirmadas

- A barreira valida o formato/documento de regulação, não o escopo EDA.
- Relatórios de regulação de colonoscopia/CPRE devem passar a barreira e continuar para o scope gate existente.
- PDFs fora do padrão devem evitar LLM e cair em revisão manual obrigatória no NIR.
- Critérios devem ser determinísticos, testáveis e sem dependência de LLM.
