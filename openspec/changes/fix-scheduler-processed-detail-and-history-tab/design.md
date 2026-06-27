# Design: Detalhe único do agendador e busca antiga como aba

## Estado atual confirmado

### Rotas e templates relevantes

- `apps/scheduler/views.py::scheduler_processed_detail`
  - rota: `scheduler:processed_detail`
  - template atual: `templates/intake/case_detail.html`
  - problema: template operacional do NIR é usado para detalhe do agendador.

- `apps/scheduler/views.py::scheduler_context_detail`
  - rota: `scheduler:context_detail`
  - template atual: `templates/scheduler/context_detail.html`
  - comportamento atual: detalhe read-only mais adequado ao scheduler; já inclui thread de comunicação e bloco `Comunicar NIR` em casos históricos `CLEANED`.

- `apps/scheduler/views.py::scheduler_historical_message_nir`
  - rota: `scheduler:historical_message_nir`
  - cria `CaseCommunicationMessage` com `allow_cleaned=True` após validar escopo histórico scheduler;
  - garante menção a `@nir` quando ausente;
  - não altera `Case.status`.

- `templates/scheduler/queue.html`
  - hoje mostra abas `Pendentes` e `Processados Hoje`;
  - mostra busca histórica como botão pequeno separado.

- `templates/scheduler/historical_search.html`
  - página de busca histórica existe, mas não compartilha a navegação em abas com a fila.

## Decisões

### D1. O template único do detalhe do agendador será o template scheduler

Para manter slice enxuto, **não renomear** o template neste change.

Usar como template único:

```text
templates/scheduler/context_detail.html
```

Apesar do nome `context_detail`, ele já representa o detalhe read-only do agendador em dois contextos: notificação e histórico. O renome para `scheduler/case_detail.html` fica fora de escopo para evitar churn em testes e rotas.

### D2. `scheduler_processed_detail` deve renderizar o template scheduler

A rota `/scheduler/processed/<uuid>/` pode continuar existindo para não quebrar links existentes da aba `Processados Hoje`.

Mas a view deve deixar de renderizar `templates/intake/case_detail.html` e passar a montar contexto compatível com `templates/scheduler/context_detail.html`.

Regras de autorização preservadas:

```text
- login obrigatório;
- active role scheduler;
- case.scheduler == request.user;
- appointment_status in {confirmed, denied};
```

Não restringir ao dia atual no detalhe, pois o link pode ter sido renderizado antes da virada de data.

### D3. Evitar duplicar montagem de contexto

Criar helper interno em `apps/scheduler/views.py`, por exemplo:

```python
def _build_scheduler_detail_context(
    *,
    request: HttpRequest,
    case: Case,
    back_url: str,
    back_label: str,
    allow_message_nir: bool,
) -> dict[str, Any]:
    ...
```

Esse helper deve centralizar dados usados pelo template do scheduler:

- dados do paciente;
- decisão médica;
- dados de agendamento;
- timeline enriquecida;
- stepper;
- comunicação operacional;
- flags de read-only;
- `show_historical_message_nir`/URL de mensagem ao NIR quando permitido;
- `back_url`/`back_label`.

`scheduler_context_detail` e `scheduler_processed_detail` devem chamar esse helper quando possível.

Aceitável para slice enxuto: extrair somente o comum necessário entre as duas views. Não fazer refactor amplo de detalhes NIR/dashboard.

### D4. Regra para exibir `Comunicar NIR`

O bloco `Comunicar NIR` deve aparecer para detalhe scheduler quando:

```python
is_scheduler_historical_case(case) is True
```

Isso inclui casos aceitos para agendamento com `appointment_status` processado, sejam eles `CLEANED`, `WAIT_R1_CLEANUP_THUMBS` ou outro status final/pós-agendamento consistente com o helper atual.

A regra atual, se estiver assim, deve ser ampliada:

```python
show_historical_message_nir = is_historical and case.status == CaseStatus.CLEANED
```

para uma regra equivalente a:

```python
show_historical_message_nir = is_historical
```

ou nome melhor, por exemplo:

```python
show_message_nir = can_message_nir
```

O endpoint `scheduler_historical_message_nir` já valida `_is_scheduler_historical_case(case)` e pode ser reutilizado.

### D5. Comunicação genérica vs. formulário específico ao NIR

Evitar duplicidade visual confusa.

Para detalhes scheduler de casos históricos/processados, preferir:

- mostrar a thread de comunicação;
- não mostrar formulário genérico se o formulário específico `Comunicar NIR` estiver visível;
- mostrar `Comunicar NIR` como CTA principal, pois ele garante `@nir` automaticamente.

Para detalhe contextual por menção em caso ainda não histórico, manter comportamento existente:

- thread + formulário genérico quando `case.status != CLEANED`;
- sem ações de workflow.

Implementação sugerida com mínimo acoplamento:

```python
can_message_nir = _is_scheduler_historical_case(case)
can_post_communication = case.status != CaseStatus.CLEANED and not can_message_nir
```

Se o implementador optar por manter ambos os formulários temporariamente, deve justificar no relatório e garantir que `Comunicar NIR` exista nos detalhes de processados hoje.

### D6. Ações NIR nunca aparecem no detalhe scheduler

O detalhe do scheduler não deve usar `templates/intake/case_detail.html`. Assim, por construção, não deve aparecer:

- `Reenviar caso corrigido`;
- `Confirmar Recebimento`;
- `Novo Encaminhamento` como ação de retorno;
- formulários de anexo/complemento/supressão do NIR;
- ações administrativas do NIR/admin.

Adicionar testes de regressão buscando strings críticas.

### D7. Busca antiga vira aba na navegação principal

Criar navegação com três abas no bloco `nav` de `templates/scheduler/queue.html`:

```text
Pendentes | Processados Hoje | Buscar caso antigo
```

A terceira aba deve apontar para:

```django
{% url 'scheduler:historical_search' %}
```

Na página `templates/scheduler/historical_search.html`, renderizar a mesma navegação com `Buscar caso antigo` ativa.

Para DRY e consistência visual, preferir extrair partial pequeno:

```text
templates/scheduler/_nav.html
```

Contexto sugerido:

```python
scheduler_active_tab = "pending" | "processed" | "historical"
pending_count
total_notice_count
processed_today_count
```

Mas, para slice enxuto, é aceitável duplicar poucas linhas de nav em `historical_search.html` se a extração gerar mais churn. Se duplicar, justificar no relatório.

### D8. Badges na aba histórica

`Buscar caso antigo` não precisa de badge numérico neste change.

Manter badges existentes para:

- `Pendentes` (`total_notice_count`);
- `Processados Hoje` (`processed_today_count`).

### D9. Nenhuma mudança de modelo/FSM

Não criar migrations. Não alterar `CaseStatus`. Não alterar regras de `open_post_schedule_issue`.

## Arquivos previstos por slice

### Slice 001 — detalhe único e mensagem ao NIR

Idealmente tocar:

| Arquivo | Mudança |
| --- | --- |
| `apps/scheduler/views.py` | helper de contexto, `scheduler_processed_detail` usando template scheduler, regra de `Comunicar NIR` |
| `templates/scheduler/context_detail.html` | microcopy/condicional para `Comunicar NIR` se necessário |
| `apps/scheduler/tests/test_views.py` | testes de regressão e mensagem ao NIR a partir de processados hoje |
| `openspec/changes/fix-scheduler-processed-detail-and-history-tab/tasks.md` | marcar slice ao concluir |

Evitar tocar URLs, models, services e templates do NIR.

### Slice 002 — busca antiga como aba

Idealmente tocar:

| Arquivo | Mudança |
| --- | --- |
| `templates/scheduler/queue.html` | substituir botão por aba |
| `templates/scheduler/historical_search.html` | adicionar nav com aba ativa |
| `apps/scheduler/tests/test_views.py` | testes de navegação |
| `openspec/changes/fix-scheduler-processed-detail-and-history-tab/tasks.md` | marcar slice ao concluir |

Opcionalmente criar `templates/scheduler/_nav.html` se isso reduzir duplicação sem ampliar demais.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Quebrar acesso por notificação do scheduler | Testar `scheduler_context_detail` existente para caso por notificação |
| Remover comunicação genérica necessária para contexto não histórico | Condicionar apenas quando `can_message_nir` for verdadeiro |
| Duplicar formulários de mensagem | Preferir esconder form genérico quando `Comunicar NIR` aparece |
| Agendador acessar ações NIR | Nunca renderizar `templates/intake/case_detail.html` em `scheduler_processed_detail`; testar strings críticas |
| UI de busca perder contadores | Manter badges existentes nas abas pendente/processados; histórico sem badge |
| Scope creep/refactor horizontal | Não renomear template nem refatorar detalhes NIR/dashboard neste change |

## Estratégia de validação

Cada slice deve seguir TDD:

1. Adicionar testes falhando para o comportamento alvo.
2. Implementar o mínimo para passar.
3. Refatorar somente para clareza/DRY local.
4. Rodar validação relevante e, ao final, quality gate completo:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

Cada slice deve gerar relatório temporário em `/tmp` com snippets antes/depois e responder aos gates do arquivo de slice.
