<!-- markdownlint-disable MD013 -->

# Design: Default diário completo com acessos transversais no dashboard

## Estado atual confirmado

- `apps/dashboard/views.py::_dashboard_case_list_context()` resolve ausente, vazio ou inválido `case_scope` como `active`.
- `active` exclui `CaseStatus.CLEANED` e não aplica restrição temporal.
- `date_from` e `date_to` são filtros independentes da lista sobre `created_at`; vazios significam ausência de limite.
- `dashboard_index()` resolve `metrics_period` ausente como `today`, mas não aplica esse período à lista.
- O select de escopo já oferece `Casos ativos` e `Todos (inclui encerrados)`.
- Links e JavaScript foram escritos considerando `active` como default; em vários pontos somente `case_scope=all` é propagado.
- “Atenção necessária” já exclui `CLEANED`, usa critérios globais e seu contador padrão não é limitado pela data da lista.
- Paginação server-side de 20 e faixa elidida já estão corretas e devem ser preservadas.

## D1. Separar escopo de estado e recorte temporal

As duas dimensões permanecem independentes:

- `case_scope=active|all` controla somente a exclusão de `CLEANED`;
- `date_from`/`date_to` controlam somente `Case.created_at`;
- `metrics_period` continua controlando somente métricas/analytics.

O default inicial combina as dimensões sem fundi-las:

```text
case_scope=all
date_from=<data-local-hoje>
date_to=<data-local-hoje>
```

Usar `timezone.localdate().isoformat()` para preencher o estado efetivo dos controles. Não criar `date=today`, enum temporal novo, model ou helper genérico fora do app.

## D2. Resolução determinística e compatível

A resolução precisa distinguir ausência de parâmetros de uma seleção explícita. Tabela normativa:

| Request da lista | Escopo efetivo | Datas efetivas | Resultado |
| --- | --- | --- | --- |
| `/dashboard/` | `all` | hoje/hoje | recebidos hoje em todos os estados |
| `?metrics_period=7d` sem parâmetros da lista | `all` | hoje/hoje | métricas 7d, lista recebidos hoje |
| `?case_scope=` ou valor inválido, sem datas | `all` | hoje/hoje | fallback canônico seguro |
| `?case_scope=all` sem datas | `all` | vazias | histórico completo, compatibilidade v0.4 |
| `?case_scope=active` sem datas | `active` | vazias | backlog ativo de qualquer data |
| `?case_scope=all&date_from=&date_to=` | `all` | vazias | datas explicitamente limpas |
| `?case_scope=all&date_from=D&date_to=D` | `all` | D/D | todos os estados no dia escolhido |
| `?attention=1` sem datas/escopo | `active` | vazias | atenção transversal ao backlog |
| `?attention=1&date_from=D&date_to=D` | `active` se escopo ausente | D/D | atenção explicitamente limitada pelo usuário |

Regra mínima sugerida em `_dashboard_case_list_context()`:

1. detectar `attention_filter`;
2. aceitar apenas `active|all` como escopo explícito;
3. se escopo válido foi fornecido, respeitá-lo;
4. se `attention=1` e não há escopo válido, resolver `active`;
5. nos demais casos ausentes/vazios/inválidos, resolver `all`;
6. ler datas normalmente;
7. aplicar hoje/hoje somente quando não há atenção, não há escopo válido e ambas as datas estão ausentes/vazias.

Um helper privado pequeno e coeso é aceitável se eliminar duplicação e melhorar testabilidade. Não criar dataclass, service, form Django ou abstração genérica para cinco valores.

## D3. Ação visível “Casos ativos”

O select existente continua permitindo composição avançada entre escopo, status e datas. Além dele, o header da lista deve oferecer uma ação curta e visível para o backlog:

```text
Casos ativos → ?case_scope=active
```

Esse link não leva `date_from` nem `date_to`; pela regra D2, abre ativos de todas as datas. Pode preservar somente contexto de métricas se isso já for necessário para a página, mas não deve preservar filtros da lista que impeçam a visão do backlog. Não adicionar JavaScript para limpar datas nem criar nova página.

Na visão ativa, o select deve refletir `active` e os inputs de data devem estar vazios. O usuário ainda pode preencher datas e combinar filtros deliberadamente.

## D4. “Atenção necessária” permanece transversal

A ação de atenção deve continuar sendo um acesso ao backlog problemático, não aos recebidos de hoje.

Contrato:

- o href canônico inclui `attention=1` e `case_scope=active`;
- não inclui `date_from` ou `date_to` herdados do default diário;
- o backend também trata `?attention=1` sem escopo/datas como ativo sem data, protegendo bookmarks e chamadas diretas;
- a query existente de `_attention_q(now)` e a exclusão de `CLEANED` não mudam;
- filtros de data explicitamente fornecidos junto com `attention=1` continuam sendo respeitados;
- contagem, critérios e thresholds de atenção não são alterados.

Não expandir este change para redefinir quais casos necessitam atenção.

## D5. Propagação SSR e busca parcial

Com o novo default, omitir `case_scope` em uma navegação pode mudar a modalidade. Para evitar perda de intenção:

- o formulário mantém exatamente um select `name="case_scope"`;
- links de métricas e formulários personalizados preservam o escopo resolvido;
- paginação preserva `case_scope` tanto em `active` quanto em `all`;
- datas não vazias continuam preservadas;
- links de dimensão derivados de `request.GET` permanecem funcionais;
- `dashboard_search.js::getFilterParams()` envia o valor atual do select para ambos os escopos, não apenas `all`;
- debounce, mínimo de três caracteres, `AbortController`, header `X-ATS-Partial` e fallback SSR permanecem intactos;
- o botão “Limpar” volta para `/dashboard/`, agora o default hoje/all.

Preservar explicitamente ambos os escopos é preferível a inferir intenção pela ausência do parâmetro. Não criar utilitário global de query strings.

## D6. Semântica de “recebidos hoje”

A lista usa os filtros existentes sobre `Case.created_at`. Casos criados ontem e avaliados hoje não entram no default. Isso é deliberado e deve constar nos testes/relatório.

Não alterar:

- summary/admission flow baseados no período;
- average times baseados em timestamps de conclusão;
- `_compute_stage_waiting()` como snapshot global;
- procedure analytics;
- ordenação `-created_at`.

## D7. TDD e cobertura

Os testes devem provar populações, não apenas strings:

1. hoje ativo + hoje `CLEANED` aparecem no default;
2. antigo ativo + antigo `CLEANED` não aparecem no default;
3. contexto default é `all` com duas datas de hoje;
4. `?case_scope=active` inclui ativo antigo e exclui qualquer `CLEANED`;
5. `?case_scope=all` sem datas inclui histórico antigo;
6. valor vazio/inválido cai para hoje/all;
7. ação “Casos ativos” tem href sem datas;
8. `?attention=1` inclui caso antigo que atende `_attention_q` e mantém datas vazias;
9. link de atenção força ativo e não herda datas;
10. paginação/partial preserva `active` e `all`;
11. JS envia o valor atual de ambos os escopos e mantém contratos existentes;
12. permissões, paginação 20/elidida e métricas não regridem.

Usar datas locais determinísticas e atualizar `created_at` via ORM quando necessário. Para atenção antiga, preferir `FAILED` ou timestamps claramente além do threshold, evitando flakiness.

## Arquivos funcionais previstos

1. `apps/dashboard/views.py`
2. `templates/dashboard/index.html`
3. `templates/dashboard/_case_list.html`
4. `static/js/dashboard_search.js`
5. `apps/dashboard/tests/test_dashboard.py`

Após validação, atualizar apenas `tasks.md` do change. A spec delta e demais artefatos são planejamento, não arquivos funcionais do slice.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Backlog antigo deixar de ser percebido | Ação visível “Casos ativos” + atenção transversal |
| Atenção ficar limitada a hoje | Regra especial sem data implícita + teste com caso antigo |
| Busca/paginação trocar `active` por default `all` | Propagar sempre o select e testar partial/hrefs |
| Histórico `?case_scope=all` virar apenas hoje | Distinguir escopo explícito e preservar teste de compatibilidade |
| Datas limpas reaplicarem hoje | Escopo explícito preservado em SSR/JS e teste de campos vazios |
| “Hoje” ser confundido com atividade do dia | Documentar `created_at`; não consultar timestamps/eventos de conclusão |
| Refactor de query strings ampliar escopo | Alterações locais nos templates existentes; YAGNI |

## Rollback

Reverter o slice restaura `active` sem data como default. Não há rollback de banco, cache, filas ou dados.