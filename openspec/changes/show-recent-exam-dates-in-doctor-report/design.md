# Design: Mostrar datas dos exames recentes no relatório médico

## Estado atual verificado

### Prompt LLM1

`apps/pipeline/llm1_service.py` contém instruções para:

- identificar `tracked_exams`;
- preencher `exam_datetime_iso`;
- usar data/hora para determinar o exame mais recente.

Trecho atual relevante:

```text
Para recencia de exames rastreados (tracked_exams):
usar data/hora (exam_datetime_iso) quando disponivel para determinar o mais recente;
sem data/hora, inferir recencia pela posicao textual;
em caso de empate, desempate pela ultima ocorrencia no texto.
Marcar is_most_recent=true apenas para o mais recente de cada tipo.
```

O prompt não diz explicitamente que `summary.one_liner` ou `summary.bullet_points` devem mencionar a data quando falarem de exames recentes.

### Presenter médico

`apps/doctor/presenters.py::_build_tracked_exam_lines` monta linhas do relatório técnico usando `tracked_exams`.

Com `exam_datetime_iso` presente, o comportamento atual é:

```python
line += " (mais recente)"
```

Ou seja, a data extraída existe no JSON, mas não aparece no relatório final.

## Decisão de design

A correção será feita em duas camadas, sem depender de geração textual do LLM para a tela final:

1. **Camada determinística obrigatória** — presenter médico:
   - parsear `exam_datetime_iso` quando disponível;
   - formatar data/hora em pt-BR;
   - incluir essa data na linha do exame recente.

2. **Camada probabilística de reforço** — prompt LLM1:
   - instruir que campos narrativos de resumo sempre incluam a data quando mencionarem exames;
   - atualizar também o `LLM1_DEFAULT_USER_PROMPT`, pois o deploy previsto é greenfield com banco zerado e `seed_prompts` criará o prompt ativo a partir desse default;
   - manter contrato JSON 1.1 inalterado.

## Formatação recomendada

Para exame recente com data:

```text
Hb: 10.0 g/dL (mais recente em 01/12/2025 10:00)
```

Para exame recente com data sem hora útil:

```text
Hb: 10.0 g/dL (mais recente em 01/12/2025)
```

Para exame recente sem data:

```text
Hb: 10.0 g/dL (recência indeterminada (sem data no laudo))
```

Para exame não marcado como mais recente:

```text
Creatinina: 1.2 mg/dL
```

## Parsing de `exam_datetime_iso`

Implementar helper pequeno e local no presenter, por exemplo:

```python
def _format_exam_datetime(value: Any) -> str:
    ...
```

Regras:

- aceitar strings ISO comuns vindas do Pydantic/LLM, como:
  - `2025-12-01`;
  - `2025-12-01T10:00:00`;
  - `2025-12-01T10:00:00Z`;
  - `2025-12-01T10:00:00-03:00`.
- retornar string vazia se valor ausente, vazio ou inválido;
- não lançar exceção no presenter por data malformada;
- para data com hora, exibir `DD/MM/AAAA HH:MM`;
- para data sem hora, exibir `DD/MM/AAAA`.

Não criar dependência externa. Usar apenas `datetime` da biblioteca padrão.

## Prompt LLM1

Adicionar instrução explícita próxima ao bloco de `tracked_exams`, preferencialmente em `_render_user_prompt`, porque essa instrução é sempre anexada ao prompt ativo do banco.

Texto alvo sugerido:

```text
Ao mencionar exames no summary.one_liner ou summary.bullet_points, sempre inclua a data do exame quando ela estiver disponível no laudo ou em exam_datetime_iso. Nunca escreva apenas "exames mais recentes" se a data estiver disponível; escreva "exames mais recentes de DD/MM/AAAA" ou equivalente.
```

Também deve ser adicionada versão curta em `LLM1_DEFAULT_USER_PROMPT`, com teste provando que o default usado por `seed_prompts` contém a instrução. Em banco zerado, esse será o prompt ativo inicial.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| LLM ignora a instrução narrativa | Presenter exibe data deterministicamente a partir do JSON |
| Data malformada quebra tela médica | Helper retorna vazio e cai no texto sem data |
| Escopo cresce para mudar schema ou lógica LLM2 | Slices proíbem novos campos e alterações em LLM2 |
| Prompts ativos do banco não mudam automaticamente | Instrução em `_render_user_prompt` é anexada independentemente do conteúdo ativo |

## Arquivos esperados por slice

### Slice 001

- `apps/doctor/presenters.py`
- `apps/doctor/tests/test_presenter.py`

### Slice 002

- `apps/pipeline/llm1_service.py`
- `apps/pipeline/tests/test_llm1_service.py`
- `apps/llm/tests/test_seed_prompts.py` para provar alinhamento default/seed em deploy greenfield.

## Não decisões

- Não será criada ADR, pois não há mudança arquitetural duradoura nem nova tecnologia.
- Não haverá migração de banco.
- Não haverá atualização automática de prompts ativos já existentes via management command neste change.
