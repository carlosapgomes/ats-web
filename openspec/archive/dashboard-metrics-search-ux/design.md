<!-- markdownlint-disable MD013 -->

# Design: Melhorias de UX e busca do dashboard

## Estado atual relevante

- `apps/dashboard/views.py::dashboard_index` monta métricas e lista de casos.
- `_compute_summary()` e `_compute_admission_flow()` usam o dia local atual.
- `_compute_average_times()` calcula médias sem seleção explícita de data.
- `_fmt_duration()` retorna apenas minutos.
- `templates/dashboard/index.html` mostra filtros de status e data na lista
  "Todos os Casos".
- `Case.agency_record_number` já existe e tem índice composto com `created_at`.
- O nome do paciente vem de `Case.structured_data["patient"]["name"]`.

## Decisão 1: polimento de UX antes de funcionalidades maiores

O primeiro slice tratará dois problemas de baixo risco:

- labels visíveis para `date_from` e `date_to`;
- duração média formatada como minutos ou horas/minutos.

Isso entrega valor imediato e reduz ruído antes de alterar queries de métricas.

Formato definido para duração:

| Entrada aproximada | Saída esperada |
| --- | --- |
| `None` | `—` |
| `0` a `59` minutos | `N min` |
| `60` minutos | `1 h` |
| `65` minutos | `1 h 05 min` |
| `1100` minutos | `18 h 20 min` |

O helper deve continuar coeso e testável. Não criar dependência de template tag
para esta formatação; ela já é responsabilidade da view.

## Decisão 2: seletor de data na seção de métricas

Usar query string:

```text
/dashboard/?metrics_date=2026-07-08
```

Sem parâmetro, usar `timezone.localdate()`.

Com data inválida, não quebrar a view: voltar para o dia local atual e expor um
estado de erro leve no contexto se o implementador optar por mostrar aviso.

A data selecionada deve afetar:

- summary cards de casos do dia;
- fluxo de admissão;
- tempos médios.

A data selecionada não deve afetar:

- card "Aguardando por etapa", que é snapshot operacional atual;
- lista "Todos os Casos", que já possui filtros próprios `date_from` e
  `date_to`.

Para evitar ambiguidade, o template deve indicar que "Aguardando por etapa" é
um snapshot atual.

### Filtros preservados

Como tudo fica na mesma página, formulários devem preservar parâmetros relevantes
por hidden inputs quando simples:

- o formulário de métricas preserva filtros da lista quando existirem;
- o formulário da lista preserva `metrics_date`.

Não preservar `page` ao alterar filtros, para evitar páginas vazias.

## Decisão 3: busca server-side indexada

Usar query string:

```text
/dashboard/?search=ana
```

A busca deve ser aplicada apenas quando `search.strip()` tiver pelo menos 3
caracteres. Para 1 ou 2 caracteres, manter a lista não filtrada e mostrar ajuda
visual. Isso evita queries amplas e combina com a busca dinâmica do slice final.

Campos pesquisados:

- nome do paciente em `structured_data -> patient -> name`;
- `agency_record_number`.

A busca deve ser case-insensitive e server-side. Accent-insensitive é desejável,
mas não obrigatório neste change porque índice funcional com `unaccent` no
PostgreSQL exige cuidado adicional de imutabilidade. Não criar wrapper SQL de
`unaccent` neste change.

### Índices PostgreSQL

Criar migration em `apps/cases/migrations/` que habilite `pg_trgm` e crie índices
GIN trigram para:

```sql
lower(agency_record_number)
lower((structured_data #>> '{patient,name}'))
```

Preferir migration reversível. Em produção, se usar `CREATE INDEX CONCURRENTLY`,
marcar `atomic = False`. Se o implementador escolher índice não concorrente para
simplicidade, deve justificar no relatório e avaliar janela de lock.

A query deve tentar usar expressões compatíveis com os índices. Caso a expressão
ORM gerada não bata com o índice funcional, o implementador deve registrar a
limitação e ajustar a expressão de forma limpa, sem espalhar SQL cru sem
necessidade.

## Decisão 4: busca dinâmica SSR parcial

O slice final é melhoria progressiva, não requisito para funcionamento básico.

- Vanilla JS no dashboard apenas.
- Debounce entre 300 ms e 500 ms.
- Fetch somente quando o termo tiver 3 ou mais caracteres, ou quando o campo for
  esvaziado para limpar a busca.
- Reaproveitar `/dashboard/` com header de partial, sem endpoint JSON.
- A view retorna HTML parcial dos cards e paginação.
- Sem JavaScript, o submit do formulário continua funcionando.
- Respostas antigas devem ser ignoradas ou canceladas com `AbortController`.

O partial pode ser algo como:

```text
templates/dashboard/_case_list.html
```

`index.html` deve incluir o partial para manter DRY e evitar duplicar markup.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Métricas históricas serem interpretadas como snapshot completo da fila | Rotular "Aguardando por etapa" como atual |
| Query de busca lenta em base grande | Migration com `pg_trgm` e mínimo de 3 caracteres |
| Migração com lock em tabela grande | Preferir `CREATE INDEX CONCURRENTLY` ou justificar alternativa |
| Placeholders invisíveis no Android | Labels visíveis e associadas por `for`/`id` |
| Busca dinâmica gerar muitas requisições | Debounce, mínimo de 3 caracteres e cancelamento/ignorar stale |
| Regressão em filtros existentes | Testes de composição com status, datas, attention e paginação |

## Rollback

- Slices 1 e 2: reverter helpers e template do dashboard.
- Slice 3: reverter view/template/testes e dropar índices pela migration reversa.
- Slice 4: remover JS, partial e condição de renderização parcial.

Sem mudança de FSM, permissões ou dados essenciais de caso.

## Política para implementadores

Cada slice deve seguir TDD, clean code, DRY e YAGNI. Não criar abstrações
genéricas antes de necessidade real.

Ao concluir um slice:

1. rodar o quality gate do `AGENTS.md`;
2. criar relatório Markdown temporário com snippets antes/depois;
3. aplicar `markdownlint-cli2` apenas no relatório ou Markdown criado no slice;
4. commitar somente arquivos de implementação, testes, migrations e novos
   assets da aplicação;
5. não commitar arquivos de especificação OpenSpec antes do arquivamento final;
6. retornar `REPORT_PATH=<caminho>` e parar.
