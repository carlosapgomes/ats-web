# Design: Endurecer exibição e extração de exames rastreados

## Diagnóstico

O contrato LLM1 permite `tracked_exams[]` com:

```json
{
  "exam_type": "...",
  "exam_label": "...",
  "result_value": "...",
  "exam_datetime_iso": "...",
  "is_most_recent": true,
  "source_text_hint": "..."
}
```

O presenter médico renderiza esses itens no contexto do relatório técnico. Após a mudança para mostrar data do exame recente, itens cujo `result_value` era `Sem exame` passaram a aparecer com data e marcador de mais recente.

Isso é uma mistura indevida entre:

- **exame rastreado realizado**: deve aparecer em `tracked_exams` e no relatório;
- **evidência de ausência de exame**: deve alimentar pré-check/pendências, mas não deve ser exibida como exame realizado recente.

## Decisão de design

A correção será feita em duas camadas:

1. **Presenter determinístico**: proteger a tela médica contra `tracked_exams` com valores de ausência, mesmo que o LLM gere esses itens.
2. **Prompt LLM1**: reduzir a chance de o LLM gerar itens indevidos em `tracked_exams`.

## Presenter

### Regra de ausência

Adicionar helper local no presenter, por exemplo:

```python
def _is_absent_exam_result(value: Any) -> bool:
    ...
```

Ele deve retornar `True` para valores normalizados equivalentes a ausência de exame, como:

- `sem exame`;
- `sem exames`;
- `não realizado` / `nao realizado`;
- `não realizada` / `nao realizada`;
- `não consta` / `nao consta`;
- `ausente`;
- `sem laudo`;
- `sem resultado`.

A normalização deve ser simples, sem dependência externa:

- lowercase;
- remover acentos com `unicodedata`;
- compactar espaços;
- comparar por igualdade ou prefixo controlado.

Não usar heurística agressiva que oculte resultados válidos contendo palavras negativas em contexto clínico.

### Regra de renderização

Para cada item de `tracked_exams`:

1. Se não for dict, ignorar.
2. Se `result_value` indicar ausência de exame, ignorar na lista de exames rastreados.
3. Montar linha base:

```text
{label}: {valor}
```

4. Se `exam_datetime_iso` válido, sempre adicionar data:

```text
(data: DD/MM/AAAA)
```

ou:

```text
(data: DD/MM/AAAA HH:MM)
```

5. Se `is_most_recent=true`, adicionar destaque:

```text
(mais recente)
```

Formato recomendado combinado:

```text
LAB externo: HB 12,1; ... (data: 28/05/2026)
LAB interno: HB 12,9; ... (data: 01/06/2026 00:00; mais recente)
```

É aceitável usar variação textual equivalente, desde que os testes comprovem:

- data aparece em exame não recente;
- “mais recente” aparece somente no recente;
- ausência de exame não aparece como linha rastreada.

### Hora `00:00`

Não alterar neste change a regra de mostrar ou ocultar `00:00`. Se o helper atual mostra `00:00` quando a string ISO contém tempo, manter comportamento para evitar ampliar escopo. Caso o implementador queira ocultar `00:00`, deve justificar e cobrir com teste, mas não é requisito.

## Prompt LLM1

Adicionar instrução próxima ao bloco de `tracked_exams` em `_render_user_prompt` e no `LLM1_DEFAULT_USER_PROMPT`, pois production greenfield usará `seed_prompts` com banco zerado.

Texto alvo sugerido:

```text
Em tracked_exams, inclua apenas exames efetivamente realizados ou resultados disponíveis. Não inclua entradas cujo resultado indique ausência de exame, como "Sem Exame", "não realizado", "não consta", "ausente", "sem laudo" ou equivalentes; use essas menções apenas como evidência de ausência em campos de pré-check quando aplicável. Para todo exame incluído em tracked_exams, preencha exam_datetime_iso quando houver data/hora associada no laudo, não apenas para o exame mais recente.
```

## Testabilidade

### Presenter

Testar diretamente `DoctorReportPresenter.build_report()` com `structured_data` sintético.

### Prompt

Testar `_render_user_prompt()` e `LLM1_DEFAULT_USER_PROMPT`, sem chamar LLM externo.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| LLM ainda gera `Sem exame` em `tracked_exams` | Presenter filtra deterministicamente |
| Filtro oculta resultado válido por engano | Lista de termos de ausência deve ser conservadora e testada |
| Exames não recentes continuam sem data | Presenter mostra data para qualquer item com `exam_datetime_iso` válido |
| Prompt ativo em banco greenfield fica desatualizado | Atualizar `LLM1_DEFAULT_USER_PROMPT`; `seed_prompts` já usa esse default |

## Arquivos esperados por slice

### Slice 001

- `apps/doctor/presenters.py`
- `apps/doctor/tests/test_presenter.py`

### Slice 002

- `apps/pipeline/llm1_service.py`
- `apps/pipeline/tests/test_llm1_service.py`
- `apps/llm/tests/test_seed_prompts.py`

## Não decisões

- Não criar uma seção visual separada para “exames ausentes”.
- Não alterar o schema `tracked_exams`.
- Não reprocessar casos antigos.
