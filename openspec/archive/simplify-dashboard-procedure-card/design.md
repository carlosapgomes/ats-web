<!-- markdownlint-disable MD013 -->

# Design: Simplificação do card de procedimentos do dashboard

## Decisão de slicing

Implementar em **1 slice vertical enxuto**.

Justificativa:

- o valor só existe quando template, contexto e testes entregam juntos a nova experiência;
- separar “remoção da matriz”, “novo resumo” e “rótulos” criaria estados intermediários incoerentes e slices horizontais;
- o escopo cabe em até cinco arquivos de produto/teste, sem alterar domínio ou infraestrutura;
- a mudança é reversível por um único commit e não exige migration.

## Estado atual relevante

- `templates/dashboard/index.html` renderiza o card completo, incluindo tabela de breakdown, volume de componentes, agendamentos casados e matriz.
- `apps/dashboard/views.py` monta `procedure_breakdown_rows`, `_matrix_display_rows()` e várias chaves de contexto exclusivas da apresentação avançada.
- `apps/dashboard/procedure_analytics.py` centraliza chaves/rótulos e calcula breakdown, volume, matriz e `paired_confirmed`.
- `apps/dashboard/tests/test_procedure_analytics.py` já prova fechamento por dimensão, `1 caso / 2 componentes`, caminho exato da matriz, agendamento casado e filtros.
- A lista de casos usa os mesmos parâmetros `procedure_dimension` e `procedure_selection`; esse contrato não pode mudar.

## Design de UI

### D1. Um único resumo case-level

O card passa a ter marcador estrutural `.procedure-summary-card`; cada categoria usa `.procedure-summary-item` para tornar verificável a cardinalidade do resumo. O título é compacto:

```text
PROCEDIMENTOS — <período ativo>
```

A dimensão ativa continua selecionável pelos links SSR existentes. Abaixo, uma grade Bootstrap responsiva apresenta exatamente quatro categorias exclusivas:

- EDA;
- Colonoscopia;
- EDA + Colonoscopia;
- Nenhum.

Cada item mostra label e contagem. Uma nota curta informa que cada caso é contado uma vez. Não apresentar unidade de componentes no card.

### D2. Rótulos orientados ao usuário

As chaves técnicas e URLs permanecem inalteradas:

| Chave | Rótulo visível |
| --- | --- |
| `declared` | `Solicitado (NIR)` |
| `detected` | `Detectado (análise)` |
| `approved` | `Autorizado (médico)` |

`DIMENSION_LABELS` deve ser a fonte única desses rótulos no dashboard. O select da lista deve usar os mesmos textos, evitando “Declarado” em um controle e “Solicitado” em outro.

Não renomear campos de model, helpers de domínio, parâmetros ou chaves internas.

### D3. Retirada da comparação avançada

O HTML principal não deve renderizar:

- `BREAKDOWN POR CATEGORIA`;
- `VOLUME DE PROCEDIMENTOS`;
- `MATRIZ DE CONVERSÃO`;
- explicações de componentes versus casos;
- tabela de caminhos declarado→detectado→autorizado.

Não esconder esses blocos em accordion, `<details>`, modal ou CSS. Eles deixam de fazer parte da visão principal até que uma demanda futura justifique uma experiência analítica própria.

### D4. Analytics subjacente preservado

`compute_procedure_analytics()` e seus testes permanecem como estão quanto a:

- `breakdown`;
- `volume`;
- `matrix`;
- `paired_confirmed`.

O slice pode remover apenas adaptação de apresentação sem consumidores, como `_matrix_display_rows()` e chaves de contexto exclusivas da matriz/volume. Não criar um segundo agregador nem parametrizar prematuramente o existente.

Essa decisão evita um refactor horizontal do motor analítico e preserva auditabilidade conforme ADR-0004.

### D5. Agendamentos combinados por exceção

O contador `paired_confirmed` é secundário e independente da dimensão ativa. Renderizá-lo em uma linha compacta somente quando `paired_confirmed > 0`, com label explícito `Agendamentos combinados confirmados`.

Quando for zero, nenhum bloco ou placeholder deve ocupar espaço.

### D6. Contratos preservados

Continuam inalterados:

- janela de `metrics_period` usada no breakdown;
- links `_procedure_dimension_links()` e preservação da query string;
- `procedure_dimension`/`procedure_selection` na lista e no partial;
- badges dimensionais dos casos, atualizados apenas no texto visível da dimensão;
- busca Vanilla JS e fallback SSR;
- guards `manager`/`admin`.

## Arquivos esperados de produto/teste

1. `templates/dashboard/index.html`
2. `apps/dashboard/views.py`
3. `apps/dashboard/procedure_analytics.py`
4. `apps/dashboard/tests/test_dashboard.py`
5. `apps/dashboard/tests/test_procedure_analytics.py`

Qualquer arquivo adicional de produto/teste exige justificativa no relatório e aprovação antes de ampliar o escopo.

## Estratégia de testes

### Estruturais/UI

- card contém `.procedure-summary-card`, exatamente quatro `.procedure-summary-item`, título compacto e as quatro categorias;
- labels das três dimensões são consistentes no seletor do card e no filtro da lista;
- HTML não contém os títulos/textos técnicos removidos;
- resposta não expõe chaves de contexto exclusivas da apresentação removida;
- `paired_confirmed=0` não renderiza indicador; valor positivo renderiza uma vez.

### Regressão

Executar os testes existentes que provam:

- breakdown fecha uma vez por caso;
- combinado continua sendo um caso e dois componentes no motor analítico;
- matriz continua classificando caminho exato internamente;
- agendamento casado conta uma vez;
- dimensão + seleção continuam compondo filtros e paginação.

## Rollback

Reverter o único commit do slice restaura template, contexto, rótulos e testes anteriores. Não há migration, transformação de dados, flag ou passo operacional.
