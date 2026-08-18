<!-- markdownlint-disable MD013 -->

# Design: Casos ativos por padrão e paginação compacta no dashboard

## Estado atual confirmado

- `apps/dashboard/views.py::_dashboard_case_list_context()` inicia com `Case.objects.select_related(...).order_by("-created_at")`, aplica filtros e cria `Paginator(cases_qs, 20)`.
- QuerySets Django são lazy; o `Paginator` executa a contagem e materializa somente a página atual. O problema observado não significa que todos os casos estejam sendo enviados ao navegador.
- `templates/dashboard/_case_list.html` percorre `page_obj.paginator.page_range`, portanto cria um link para cada página.
- `templates/dashboard/index.html` contém o formulário GET da lista e links de período/atenção que preservam filtros manualmente.
- `static/js/dashboard_search.js` atualiza somente o partial via header `X-ATS-Partial: case-list` e recompõe os parâmetros ativos.
- `CaseStatus.CLEANED` é o estado que retira o caso das filas operacionais e o mantém para histórico/auditoria.

## D1. Escopo explícito e default operacional

Adicionar query string canônica:

```text
case_scope=active|all
```

Sem parâmetro, vazio ou inválido, resolver para `active`.

Semântica:

| Valor resolvido | Query da lista |
| --- | --- |
| `active` | excluir `status=CaseStatus.CLEANED` |
| `all` | não aplicar predicado adicional de escopo |

“Active” não significa “criado hoje”. Casos de qualquer data continuam visíveis enquanto não alcançarem `CLEANED`, incluindo falhas que exigem atenção. O escopo deve ser aplicado antes da paginação e compor por `AND` com busca, dimensão/procedimento, status, datas e atenção.

Se o usuário combinar `case_scope=active` com `status=CLEANED`, o resultado vazio é correto: os predicados são incompatíveis. A UI exibe simultaneamente os controles de escopo e status, permitindo selecionar `all` + `CLEANED` em um único submit. Não criar regra mágica em que um filtro altera silenciosamente o outro.

O formulário terá controle visível “Escopo” com:

- `Casos ativos` (`active`, selecionado por padrão);
- `Todos (inclui encerrados)` (`all`).

O título do card deve deixar de afirmar “Todos os Casos” quando o padrão não inclui encerrados; usar título neutro `Casos`.

## D2. Preservação e URLs

`case_scope=active` pode ser omitido das URLs por ser o default canônico. `case_scope=all` deve ser preservado em:

- submit do formulário GET;
- links Anterior/Próxima/números da paginação;
- links de períodos das métricas;
- botão “Atenção necessária”;
- links de dimensão já derivados de `request.GET`;
- fetch parcial montado por `dashboard_search.js`.

O formulário não deve preservar `page`, para que qualquer alteração de filtro volte à primeira página. “Limpar” volta à URL canônica do dashboard e, portanto, ao escopo `active`.

Não introduzir template tag genérica ou refactor amplo de query strings neste change. A duplicação preexistente pode ser reduzida localmente se isso não ampliar o número de arquivos, mas não é requisito.

## D3. Paginação compacta

Manter:

```python
Paginator(cases_qs, 20)
```

Depois de resolver `page_obj`, preparar no contexto uma faixa com `Paginator.get_elided_page_range`, usando uma janela pequena e constante. Decisão recomendada:

```python
paginator.get_elided_page_range(
    page_obj.number,
    on_each_side=2,
    on_ends=1,
)
```

O template percorre somente essa faixa. Itens iguais a `Paginator.ELLIPSIS` são texto desabilitado, nunca links. Para muitas páginas, exemplo conceitual:

```text
Anterior  1  …  31  32  [33]  34  35  …  66  Próxima
```

Contratos:

- primeira e última páginas quando aplicável;
- página atual com `aria-current="page"`;
- vizinhas limitadas;
- reticências não clicáveis;
- `Anterior`/`Próxima` mantidos;
- lista Bootstrap com wrap para não gerar overflow em viewport estreita;
- nenhum loop sobre `page_obj.paginator.page_range` completo.

Não construir algoritmo próprio de elisão; usar a API Django reduz risco e mantém YAGNI.

## D4. Resumo da página

Quando houver resultados, mostrar próximo à paginação:

```text
Exibindo {{ page_obj.start_index }}–{{ page_obj.end_index }} de {{ page_obj.paginator.count }} casos
```

Para zero resultados, manter o estado vazio atual sem exibir intervalo `0–0`. O total refere-se ao queryset após todos os filtros, não ao banco inteiro.

## D5. Testabilidade

Os testes devem provar comportamento, não apenas procurar strings soltas:

1. default inclui um caso antigo não `CLEANED` e exclui `CLEANED`;
2. `case_scope=all` inclui ambos;
3. valor inválido cai para `active`;
4. escopo compõe com pelo menos um filtro existente e é preservado nos links/fetch;
5. página intermediária de um conjunto com muitas páginas recebe faixa elidida limitada, com primeira/atual/última e reticências, sem todos os números;
6. resumo X–Y/Z está correto;
7. página materializa no máximo 20 cards, preservando paginação server-side;
8. permissões e partial SSR existentes não são relaxados.

Preferir asserts sobre `response.context`, ids/atributos estáveis e trechos do nav identificado, evitando falso positivo por números existentes nas métricas ou nos dados dos casos.

## Arquivos funcionais previstos

1. `apps/dashboard/views.py`
2. `templates/dashboard/index.html`
3. `templates/dashboard/_case_list.html`
4. `static/js/dashboard_search.js`
5. `apps/dashboard/tests/test_dashboard.py`

Nenhum model, migration, URL, CSS, dependência ou outro app é necessário.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Encerrados parecerem removidos | Controle “Todos (inclui encerrados)” e nenhum delete/mutation |
| Backlog antigo desaparecer com filtro diário | Escopo por estado, não por data |
| Busca dinâmica resetar `all` para `active` | Ler/preservar `case_scope` no JS e testar partial |
| Paginação perder filtros | Testes dos hrefs com `case_scope=all` e parâmetros existentes |
| Números das métricas causarem falso positivo no teste | Isolar nav por id/contexto |
| Modelo rápido criar algoritmo próprio | Exigir `get_elided_page_range` e inspeção `rg` |
| `COUNT` ficar caro em escala futura | Fora de escopo; monitorar antes de cursor pagination |

## Rollback

Reverter o slice restaura a listagem histórica inicial e a faixa completa de páginas. Não há rollback de banco, cache ou dados. FSM, auditoria, permissões e URLs de detalhe permanecem intactos.
