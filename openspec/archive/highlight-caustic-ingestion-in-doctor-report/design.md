# Design: Ênfase de ingestão cáustica/corrosiva no relatório médico

## Estado atual verificado

### Relatório médico

`apps/doctor/presenters.py::DoctorReportPresenter` monta o relatório técnico exibido em `templates/doctor/decision.html`.

Hoje o contexto do relatório inclui:

- procedimento solicitado, com subtipo canônico (`EDA`, `EDA para gastrostomia`, etc.);
- origem;
- transfusão;
- exames rastreados;
- marcador pediátrico (`paciente pediátrico: sim`).

Essas linhas são renderizadas no `report-meta` do template médico.

### Pediatria

A sinalização pediátrica é extraída principalmente de `patient.age < 16` e/ou `eda.is_pediatric`, validada no schema LLM1, propagada pela policy e exibida deterministicamente pelo presenter.

### Gastrostomia

Gastrostomia é tratada como subtipo suportado de EDA (`gastrostomy`). O presenter resolve o subtipo para `EDA para gastrostomia` e o template exibe isso no contexto do relatório.

### Ingestão cáustica/corrosiva

Não há regra, keyword, campo de schema ou destaque específico para ingestão cáustica/corrosiva. Busca por `caust`, `cáust`, `corros` não encontrou implementação funcional no projeto.

## Decisão de design

Implementar a feature em duas camadas, sem alterar decisão automática.

### Camada 1 — detector determinístico no relatório médico

Criar detecção determinística baseada no texto extraído do PDF, porque a presença e o tempo desde a ingestão são dados documentais que devem aparecer no relatório mesmo que o LLM não destaque espontaneamente.

O presenter passará a receber o texto extraído do caso, além de `structured_data`, `summary_text` e `suggested_action`.

Fluxo proposto:

```text
Case.extracted_text
  -> DoctorReportPresenter(..., source_text=case.extracted_text)
  -> detector documental de ingestão cáustica/corrosiva
  -> report.context.clinical_alert_lines
  -> templates/doctor/decision.html exibe alerta no Relatório Técnico
```

### Camada 2 — reforço de prompt LLM1

Atualizar o prompt canônico/default do LLM1 para orientar que o resumo narrativo mencione ingestão cáustica/corrosiva e tempo desde o evento quando disponível.

Essa camada melhora a qualidade do resumo, mas não é a fonte obrigatória para a tela. A tela final continua baseada no detector determinístico.

## Contrato do detector

O detector deve ser uma função pequena e testável, local ao domínio de apresentação médica. Pode ficar em `apps/doctor/presenters.py` se permanecer simples, ou em módulo novo `apps/doctor/caustic_ingestion.py` se a legibilidade exigir separação.

Saída conceitual:

```python
@dataclass(frozen=True)
class CausticIngestionAlert:
    detected: bool
    time_since_text: str | None
    evidence_excerpt: str | None
```

O presenter não precisa expor a dataclass diretamente no template; pode convertê-la para linhas de contexto:

```python
[
    "⚠️ ingestão cáustica/corrosiva relatada: sim",
    "tempo desde a ingestão: há 3 semanas",
]
```

Quando houver detecção sem tempo:

```python
[
    "⚠️ ingestão cáustica/corrosiva relatada: sim",
    "tempo desde a ingestão: não informado no relatório",
]
```

## Estratégia de detecção

### Normalização

- Usar normalização local com `unicodedata.normalize("NFD", ...)` para remover acentos.
- Converter para minúsculas e colapsar whitespace para matching.
- Preservar o texto original para `time_since_text` e `evidence_excerpt` quando possível.

### Sinais positivos

Detectar contexto em que termos de ingestão aparecem próximos a termos cáusticos/corrosivos.

Termos de evento:

- `ingestao`, `ingeriu`, `ingerido`, `ingesta`;
- `episodio`, quando próximo de substância cáustica/corrosiva;
- `acidente`, quando próximo de ingestão e substância.

Termos de substância/contexto:

- `caustico`, `caustica`;
- `corrosivo`, `corrosiva`;
- `substancia corrosiva`;
- `produto corrosivo`;
- `soda caustica`;
- `acido`, quando em contexto de ingestão.

Recomendação: exigir coocorrência em uma mesma sentença ou janela curta de caracteres, para reduzir falso positivo em textos longos.

### Negação conservadora

Não disparar alerta quando a mesma sentença/janela contiver negação clara, por exemplo:

- `nega ingestao`;
- `sem ingestao`;
- `nao ingeriu`;
- `não ingeriu`;
- `ingestao negada`.

A regra de negação deve ser conservadora: se o texto for ambíguo, melhor não suprimir o alerta quando houver forte evidência positiva.

### Extração do tempo

Procurar expressões temporais na mesma sentença ou em janela próxima ao evento detectado.

Padrões recomendados:

- relativos:
  - `há 3 dias` / `ha 3 dias`;
  - `há cerca de 2 semanas`;
  - `há aproximadamente 1 mês`;
  - `faz 10 dias`;
  - `ocorreu há 15 dias`;
- datas explícitas:
  - `em 12/05/2026`;
  - `no dia 12/05/2026`;
  - `episódio em 12/05`;
  - `ingestão em 12/05/2026`.

Não converter datas em intervalos calculados. O objetivo é documentar o que o relatório diz, não aplicar regra clínica.

## Renderização

Adicionar ao contexto do presenter uma lista `clinical_alert_lines` ou nome equivalente.

No template médico, renderizar após as linhas de exames/pediatria ou logo antes dos blocos do relatório.

Exemplo visual aceitável:

```html
{% for line in report.context.clinical_alert_lines %}
  <div class="alert alert-warning py-1 px-2 mb-1 small">{{ line }}</div>
{% endfor %}
```

Também é aceitável renderizar como linhas normais no `report-meta`, desde que a primeira linha tenha `⚠️` e seja facilmente visível.

## Prompt LLM1

Adicionar instrução explícita em `apps/pipeline/llm1_service.py`, preferencialmente:

1. em `LLM1_DEFAULT_USER_PROMPT`, para banco zerado/seed inicial;
2. em `_render_user_prompt`, para que a instrução seja anexada mesmo quando o banco já tiver prompt ativo customizado.

Texto sugerido:

```text
Se o relatório mencionar ingestão de substância cáustica/corrosiva, soda cáustica, produto corrosivo ou ácido em contexto de ingestão, mencione esse evento no summary.one_liner ou summary.bullet_points e inclua o tempo desde a ingestão quando o texto informar (por exemplo, "há 3 semanas" ou "em 12/05/2026"). Não transforme esse tempo em motivo automático de negativa.
```

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Falso negativo do detector | Prompt LLM1 também reforça menção no resumo; médico ainda pode abrir texto/PDF completo. |
| Falso positivo por menção histórica/negada | Exigir coocorrência de ingestão + substância e tratar negações simples no mesmo contexto. |
| Médico interpretar como regra automática de negativa | Texto deve ser documental; proposal e slice proíbem alteração de decisão/policy. |
| Scope creep para schema/policy | Slices proíbem schema LLM, LLM2, policy, FSM e banco. |
| Regex frágil para todos os formatos temporais | Implementar padrões comuns e fallback explícito `não informado no relatório`. |

## Rollback

Rollback simples por commit revert:

- remover detector/linhas de contexto do presenter;
- remover renderização no template;
- remover passagem de `source_text` na view;
- remover reforço de prompt LLM1.

Não há migration, alteração de dados persistidos ou reprocessamento histórico.

## Arquivos esperados por slice

### Slice 001 — Detector e renderização end-to-end

Arquivos esperados:

- `apps/doctor/presenters.py` ou `apps/doctor/caustic_ingestion.py`;
- `apps/doctor/views.py`;
- `templates/doctor/decision.html`;
- `apps/doctor/tests/test_presenter.py`;
- `apps/doctor/tests/test_views.py` se necessário para cobrir renderização.

### Slice 002 — Reforço de prompt LLM1

Arquivos esperados:

- `apps/pipeline/llm1_service.py`;
- `apps/pipeline/tests/test_llm1_service.py`;
- opcionalmente `apps/llm/tests/test_seed_prompts.py`, se houver teste existente de alinhamento do seed com default.

## Não decisões

- Não criar ADR: não há nova arquitetura, tecnologia ou persistência; trata-se de apresentação clínica + instrução de prompt.
- Não criar campo novo no banco nem no schema LLM1.
- Não criar regra clínica de tempo mínimo para EDA.
