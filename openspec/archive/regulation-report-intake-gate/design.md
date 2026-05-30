# Design: Barreira de Aceitação para PDFs de Relatório de Regulação

## D1. Ponto de aplicação da barreira

A barreira deve rodar no worker de extração PDF, não na request web.

Local preferencial:

```text
apps/intake/tasks.py::_do_extraction()
```

Fluxo desejado:

```text
R1_ACK_PROCESSING
  → EXTRACTING
  → extrai texto do PDF
  → limpa watermark e tenta extrair registro
  → avalia barreira de relatório de regulação
    → passa: persiste dados, LLM_STRUCT, enqueue_pipeline()
    → falha: persiste dados/auditoria, LLM_STRUCT, scope_gate_bypass(), sem enqueue_pipeline()
```

Justificativa:

- mantém upload rápido;
- aproveita texto já extraído;
- evita custo LLM para documentos inválidos;
- preserva FSM/`CaseEvent` como fonte da verdade.

## D2. Utilitário determinístico de classificação

Criar utilitário pequeno e testável, por exemplo:

```text
apps/intake/regulation_gate.py
```

API sugerida:

```python
@dataclass(frozen=True)
class RegulationReportGateResult:
    accepted: bool
    reason_code: str
    reason_text: str
    matched_header: bool
    matched_institutional_signals: list[str]
    matched_operational_sections: list[str]
    text_length: int


def evaluate_regulation_report_text(text: str) -> RegulationReportGateResult:
    ...
```

A função deve:

- normalizar acentos;
- normalizar caixa;
- colapsar espaços;
- preservar correspondência robusta para variantes como `Unid. Origem` e `Unidade de Origem`;
- retornar evidências suficientes para auditoria/testes.

## D3. Critérios iniciais

Aceitar se todos forem verdadeiros:

1. texto limpo com pelo menos `INTAKE_REGULATION_MIN_TEXT_CHARS`, default 500;
2. contém `RELATÓRIO DE OCORRÊNCIAS`;
3. contém ao menos 1 sinal institucional:
   - `Central Estadual de Regulação`;
   - `Secretaria da Saúde do Estado`;
   - `Governo do Estado da Bahia`;
4. contém ao menos `INTAKE_REGULATION_MIN_OPERATIONAL_SECTIONS`, default 3, entre:
   - `Código:`;
   - `Abertura:`;
   - `Unid. Origem`;
   - `Unidade de Origem`;
   - `Motivo da Solicitação`;
   - `Complemento da Solicitação`;
   - `Resumo Clínico`;
   - `Dias em tela`;
   - `Data Adm. Unid.`.

Configurações sugeridas em `config/settings/base.py`:

```python
INTAKE_REGULATION_MIN_TEXT_CHARS = 500
INTAKE_REGULATION_MIN_OPERATIONAL_SECTIONS = 3
```

## D4. Tratamento de falha da barreira

Em falha da barreira:

1. persistir `case.extracted_text`;
2. persistir `agency_record_number` somente se extraído por padrão explícito, ou deixar em branco se só houver fallback;
3. avançar extração como tecnicamente concluída (`EXTRACTING → LLM_STRUCT`) para permitir transição de scope gate existente;
4. setar `case.suggested_action`:

```json
{
  "schema_version": "1.1",
  "language": "pt-BR",
  "decision": "manual_review_required",
  "suggestion": "manual_review_required",
  "reason_code": "invalid_regulation_report",
  "reason_text": "O PDF não apresenta os sinais mínimos de relatório de regulação. Revisão manual obrigatória.",
  "evidence": {
    "matched_header": false,
    "matched_institutional_signals": [],
    "matched_operational_sections": [],
    "text_length": 0
  }
}
```

5. registrar `CaseEvent` antes da transição:

```text
REGULATION_REPORT_GATE_FAILED
```

6. chamar `case.scope_gate_bypass(reason_code="invalid_regulation_report")`;
7. registrar `FINAL_REPLY_POSTED` conforme padrão já usado para scope gate;
8. não chamar `enqueue_pipeline()`.

## D5. Tratamento de sucesso da barreira

Em sucesso:

- comportamento atual preservado;
- `case.extracted_text`, `agency_record_number`, `agency_record_extracted_at` persistidos;
- `EXTRACTING → LLM_STRUCT`;
- `enqueue_pipeline(case.case_id)` chamado normalmente.

Relatórios de regulação de colonoscopia/CPRE passam por esta barreira e continuam para LLM1/scope detection, que já decide `non_eda`/`unknown` quando aplicável.

## D6. Número de registro e fallback

A função atual `strip_watermark_and_extract_record()` usa timestamp quando não encontra número por padrões explícitos.

Para a barreira, isso é perigoso como evidência. O slice de implementação deve separar:

- extração explícita de registro real;
- fallback técnico para compatibilidade, se ainda necessário.

Opções aceitáveis:

1. criar função nova que retorna metadados:

```python
@dataclass(frozen=True)
class CleanedPdfText:
    text: str
    record_number: str
    record_number_source: Literal["explicit", "fallback"]
```

2. ou criar helper público específico para checar se o registro foi explícito.

A falha da barreira não deve gravar timestamp fallback como se fosse código de regulação.

## D7. UI/NIR

A tela de detalhe do caso já exibe `manual_review_required` com badge de revisão manual.

A feature deve garantir que `reason_text` para `invalid_regulation_report` seja claro para o NIR. Se necessário, ajustar presenter/view/template para exibir:

```text
O PDF não apresenta os sinais mínimos de relatório de regulação. Revisão manual obrigatória.
```

## D8. Testes

Usar TDD com textos sintéticos/anonimizados. Não versionar PDFs reais com PHI.

Cobrir:

- detector aceita texto sintético com assinatura de regulação;
- detector aceita relatório de regulação cujo motivo seja colonoscopia;
- detector rejeita laudo ECG;
- detector rejeita exame laboratorial;
- detector rejeita texto muito curto ou PDF sem texto extraível;
- task de extração não enfileira pipeline quando barreira falha;
- case barrado vai para `WAIT_R1_CLEANUP_THUMBS` com `manual_review_required`;
- eventos `REGULATION_REPORT_GATE_FAILED`, `SCOPE_GATE_BYPASS` e `FINAL_REPLY_POSTED` são registrados;
- caso aceito preserva fluxo atual e chama `enqueue_pipeline()`.

## D9. Observabilidade

Adicionar logs estruturados suficientes:

- case_id;
- accepted/rejected;
- reason_code;
- matched section count;
- text_length.

Não logar texto clínico completo.

## D10. Compatibilidade operacional

Não mudar a API de upload nem o comportamento síncrono da página do NIR.

Casos já processados não precisam ser reavaliados retroativamente neste change.
