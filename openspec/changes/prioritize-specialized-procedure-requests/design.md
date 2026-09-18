# Design: Precedência ampla de Ecoendoscopia e CPRE

## Contexto

A ADR-0006 introduziu Ecoendoscopia e CPRE como procedimentos independentes e definiu matriz fechada. A implementação atual separa:

1. `detect_requested_procedures_v3()` — produz evidência `strong/any` pela união do `requested_procedures` estruturado com ocorrências textuais atuais;
2. `detect_procedure_occurrences()` — qualifica deterministicamente ocorrências textuais como `current_request|historical|negated|mention` e preserva o vínculo local `EDA com/e especializado`;
3. `reconcile_detected_procedures()` — valida catálogo/duplicatas, aplica precedência ligada, valida matriz e compara detectado×declarado;
4. orchestrator — projeta `CaseProcedure`, registra `CASE_PROCEDURES_DETECTED`, filtra a visão efêmera do LLM2 e encaminha a `WAIT_DOCTOR` ou revisão NIR.

A regra ligada é estreita demais para relatórios de regulação: cabeçalho administrativo e conduta clínica podem estar em seções diferentes. Um documento pode conter `Motivo da Solicitação: EDA`, registrar EDA já realizada e repetir `Solicito Ecoendoscopia via regulação`. O detector pode produzir `{eda, echoendoscopy}` com ocorrências independentes; a matriz rejeita o conjunto antes de reconhecer que o especializado é o destino operacional.

## Goals / Non-Goals

**Goals:**

- priorizar exatamente um procedimento especializado sobre procedimentos convencionais detectados somente com ocorrência textual correspondente qualificada como atual;
- impedir que item estruturado especializado, sem ocorrência textual atual, acione a supressão de EDA/Colonoscopia;
- preservar declaração NIR, artefato LLM1 e evidências originais;
- deixar a aplicação da precedência explícita em auditoria e no relatório médico;
- manter todos os conflitos realmente ambíguos fail-closed.

**Non-Goals:**

- aceitar combinações com procedimento especializado;
- converter automaticamente a declaração do NIR;
- inferir Ecoendoscopia/CPRE por mera menção, histórico ou recomendação de laudo;
- alterar regex, aliases, prompts, schemas LLM ou hard rules clínicas;
- criar novo evento, model, migration, estado FSM, notificação ou split de caso;
- tratar a exceção excepcional de dois procedimentos especializados simultâneos.

## Decisions

### D1. A precedência exige ocorrência textual atual e ocorre antes da matriz

A reconciliação continuará validando catálogo, valores desconhecidos e duplicatas antes de qualquer redução. Como `detect_requested_procedures_v3()` aceita tanto o `requested_procedures` estruturado quanto ocorrências textuais atuais, o conjunto `strong/any` sozinho não comprova deterministicamente a atualidade do especializado. A redução aplicará um segundo gate usando as ocorrências já produzidas pelo detector:

```text
raw_detected = conjunto detectado por strong/any
specialized = raw_detected ∩ {echoendoscopy, cpre}
conventional = raw_detected ∩ {eda, colonoscopy}
current_occurrence_types = tipos com occurrence.qualification == current_request

se len(specialized) == 1 e specialized ⊆ current_occurrence_types:
    reconciled = specialized
    suppressed = conventional
senão:
    reconciled = raw_detected
    suppressed = ∅
```

A precedência é considerada **aplicada** somente quando `suppressed` não é vazio. Um singleton especializado sem EDA/Colonoscopia já é válido pelo comportamento existente, mas não gera aviso. Um item especializado estruturado sem ocorrência textual atual correspondente não pode suprimir EDA/Colonoscopia; o conjunto misto permanece fora da matriz e segue fail-closed.

Consequências determinísticas:

| Conjunto bruto | Ocorrência especializada | Resultado antes da comparação com NIR |
| --- | --- | --- |
| `{eda, echoendoscopy}` | Eco `current_request` | `{echoendoscopy}` |
| `{colonoscopy, echoendoscopy}` | Eco `current_request` | `{echoendoscopy}` |
| `{eda, colonoscopy, echoendoscopy}` | Eco `current_request` | `{echoendoscopy}` |
| `{eda, cpre}` | CPRE `current_request` | `{cpre}` |
| `{eda, colonoscopy, cpre}` | CPRE `current_request` | `{cpre}` |
| `{eda, echoendoscopy}` | Eco somente histórica/negada/menção ou ausente | incompatível → revisão NIR |
| `{eda, colonoscopy}` | nenhuma especializada | `{eda, colonoscopy}` |
| `{echoendoscopy, cpre}` | qualquer | incompatível → revisão NIR |
| `{eda, echoendoscopy, cpre}` | qualquer | incompatível → revisão NIR |

O vínculo `linked_eda` deixa de ser condição para precedência, mas `qualification == "current_request"` da ocorrência do especializado permanece obrigatório. As ocorrências já existem no contrato atual; nenhuma regex ou classificação será alterada.

### D2. Declaração NIR continua sendo gate independente

Depois da precedência, a matriz declarado×detectado atual permanece:

- NIR declarou o mesmo especializado → `proceed`;
- NIR declarou EDA, Colonoscopia ou combinado e o resultado é especializado → `exam_type_mismatch`/revisão NIR;
- NIR declarou um especializado e somente outro tipo foi detectado → revisão NIR;
- auto-upgrade continua exclusivo de single convencional para EDA + Colonoscopia com evidência forte.

Assim, o change elimina o falso “combinado incompatível”, mas não elimina uma divergência real entre declaração do NIR e solicitação reconciliada.

### D3. O resultado da reconciliação transporta metadados enxutos

`ProcedureReconciliationResult` ganhará informação imutável suficiente para consumidores posteriores:

```python
precedence_applied: bool = False
selected_specialized_type: str = ""
suppressed_conventional_types: tuple[str, ...] = ()
```

Nomes equivalentes são aceitáveis se mantiverem o contrato. Não incluir excerpts, texto integral ou dados pessoais nesse metadado.

Quando a regra for aplicada, o orchestrator anexará ao payload de `CASE_PROCEDURES_DETECTED` e ao `suggested_action`:

```json
{
  "procedure_precedence": {
    "rule": "specialized_over_conventional",
    "selected": "echoendoscopy",
    "suppressed": ["eda"]
  }
}
```

O campo fica ausente quando a precedência não foi aplicada, evitando confundir singleton normal com correção determinística.

### D4. Extração original e contexto do LLM2 têm autoridades distintas

`Case.structured_data` permanece exatamente como validado pelo LLM1, inclusive se `requested_procedures` contiver o especializado e os convencionais. Isso preserva auditoria e permite revisão do texto-fonte.

A projeção `CaseProcedure`, policy e lista fechada do LLM2 usam somente o conjunto reconciliado. O helper existente `_build_llm2_structured_data_view()` já filtra a cópia efêmera; nenhum schema, prompt ou serviço LLM precisa mudar.

### D5. Aviso médico reutiliza `report.notices`

`DoctorReportPresenter._build_notices()` continuará exibindo o aviso de anexos 3.0 e acrescentará, quando `suggested_action.procedure_precedence` for válido, aviso como:

> O relatório apresentou também solicitação de EDA/Colonoscopia. O sistema priorizou Ecoendoscopia pela regra de precedência de procedimento especializado. Revise o texto original e ajuste a decisão se necessário.

O aviso:

- é informativo e não altera formulário, validação ou sugestão;
- usa labels canônicos, não valores técnicos crus;
- não aparece em casos sem supressão, em conflito Eco+CPRE ou em artefatos legados;
- não exige alteração de template, pois `decision.html` já renderiza `report.notices`.

### D6. Detector, prompts e matriz final permanecem fechados

Nenhuma regex ou classificação de `current_request|historical|negated|mention` será alterada. A reconciliação reutiliza `occurrences` para exigir prova textual atual antes de suprimir convencionais; o item estruturado do LLM1, isoladamente, não satisfaz esse gate. Os schemas LLM continuam permitindo a extração bruta de até quatro tipos para que a reconciliação enxergue conflito em vez de falhar no parse.

A matriz persistida/autorizável continua exatamente:

```text
{eda}
{colonoscopy}
{eda, colonoscopy}
{echoendoscopy}
{cpre}
```

## Riscos e mitigações

- **Menção especializada indevida dominar convencionais:** a redução exige ocorrência textual do especializado com `qualification == "current_request"`; item estruturado isolado, histórico, negação ou menção não suprime convencionais. Este change não amplia aliases nem transforma mera menção em pedido.
- **Ecoendoscopia e CPRE simultâneas serem escolhidas arbitrariamente:** precedência exige exatamente um tipo especializado; dois especializados continuam fail-closed.
- **Declaração do NIR ser sobrescrita:** comparação declarado×reconciliado permanece depois da precedência; mismatch continua revisão manual.
- **Perda da evidência convencional:** `structured_data` permanece imutável e o evento registra tipos suprimidos; nenhum dado clínico é removido do artefato.
- **Aviso médico virar bloqueio:** apenas `report.notices` muda; forms/FSM/policy não são tocados.
- **Regressão EDA + Colonoscopia:** teste explícito prova que ausência de especializado preserva o combinado.

## Rollout / rollback

- Sem migration, backfill ou mudança de flags.
- Baseline global uma vez antes do slice se o HEAD não tiver CI verde confiável.
- RED/GREEN focado nos testes 3.0 de Ecoendoscopia/CPRE e regressão local do presenter.
- Gate final completo uma vez após o slice.
- Smoke pós-deploy usa somente casos sintéticos/operacionais autorizados e verifica evento, projeção, fila e aviso.
- Rollback por revert + deploy; não reabrir nem reprocessar automaticamente casos já encaminhados.

## Slice Strategy

Um único slice vertical entrega valor completo:

```text
relatório com convencional + especializado
→ detecção strong/any + ocorrência textual atual existente
→ precedência determinística com gate de proveniência
→ singleton especializado auditado
→ LLM2/policy do especializado
→ WAIT_DOCTOR
→ aviso médico não bloqueante
```

Separar reconciliação, auditoria e aviso criaria estados intermediários sem rastreabilidade ou sem proteção operacional. O footprint previsto é de cinco arquivos e não justifica múltiplos slices.
