# ADR-0009: Taxonomia oficial e compatibilidade histórica das causas de não realização

## Status

Accepted

## Contexto

O pós-procedimento registra, de forma versionada e append-only, se cada procedimento autorizado foi realizado e, em caso negativo, sua causa. A taxonomia atual possui `absenteeism`, `inadequate_prep`, `resource_shortage` com três submotivos e `other` com texto. O setor, porém, adota uma ficha de suspensão com 23 causas específicas. A diferença força o usuário a traduzir fatos operacionais para categorias genéricas e reduz a comparabilidade dos indicadores com o documento oficial.

As rows `CaseFollowUp`/`ProcedureFollowUp` e seus `CaseEvent` espelho são históricos auditáveis. Reescrever causas antigas ou seus eventos quebraria o contrato append-only. Ao mesmo tempo, manter duas taxonomias visíveis produziria filtros duplicados e séries históricas fragmentadas.

A ADR-0007 continua sendo a autoridade sobre quais procedimentos recebem pós-procedimento. Esta ADR supera apenas suas referências ao conjunto antigo de causas.

## Decisão

1. Novas gravações usarão exclusivamente as 23 causas da ficha oficial, na ordem fornecida pelo setor, mais `other` (**Outras causas**) ao final.
2. `other` continuará exigindo texto livre não vazio; qualquer outra causa continuará proibindo texto livre.
3. Novas gravações não usarão submotivo: **Falta de equipamentos**, **Prioridade para urgência** e **Tempo excedido** serão causas principais.
4. Os códigos legados permanecerão reconhecíveis no storage para leitura, mas serão excluídos das choices de entrada e da validação de novas gravações.
5. Nenhuma row histórica e nenhum `CaseEvent` será atualizado. As superfícies analíticas projetarão em tempo de leitura:
   - `absenteeism` → `patient_no_show`;
   - `resource_shortage` + `emergency_occupied` → `emergency_priority`;
   - `resource_shortage` + `insufficient_time` → `time_exceeded`;
   - `resource_shortage` + `equipment_unavailable` → `missing_equipment`.
6. Tabela, cards, filtro e CSV usarão a causa oficial projetada. O filtro oficial incluirá tanto rows atuais quanto as legadas equivalentes.
7. Dado histórico fora dos quatro mapeamentos confirmados não será convertido para uma causa oficial inventada: o deploy terá preflight fail-closed e a leitura defensiva exibirá a categoria técnica não filtrável **Causa legada não mapeada**, preservando os códigos brutos para diagnóstico sem gravar nada.
8. A coluna física `resource_shortage_detail` e seus constraints serão mantidos para integridade dos registros antigos; novas gravações sempre a deixarão vazia.
9. O formulário usará `select` nativo Bootstrap, sem dependência de combobox, preservando a ordem oficial e o comportamento condicional acessível.

## Alternativas Consideradas

1. **Migrar rows e eventos antigos para os novos códigos**
   - **Vantagens:** banco conteria uma única taxonomia física.
   - **Desvantagens:** viola a expectativa append-only, exige mutação coordenada de eventos e transforma fatos históricos.
   - **Por que não escolhida:** o ganho de uniformidade física não compensa a perda de rastreabilidade.

2. **Manter as duas taxonomias visíveis, sem projeção**
   - **Vantagens:** implementação mais simples e representação literal do storage.
   - **Desvantagens:** duplica causas equivalentes em indicadores/filtros e quebra comparabilidade com a ficha oficial.
   - **Por que não escolhida:** mantém exatamente o problema analítico que motivou o change.

3. **Lista oficial para novas escritas com projeção histórica em leitura (escolhida)**
   - **Vantagens:** preserva auditoria, oferece uma taxonomia operacional única e evita backfill.
   - **Desvantagens:** leitores precisam conhecer a projeção e o rollback para imagem antiga fica limitado após novas escritas.
   - **Por que escolhida:** equilibra verdade histórica, usabilidade e indicadores comparáveis.

4. **Combobox pesquisável customizado**
   - **Vantagens:** busca explícita entre as opções.
   - **Desvantagens:** maior custo de acessibilidade, JavaScript e manutenção para apenas 24 itens.
   - **Por que não escolhida:** o `select` nativo é compacto, responsivo e suficiente; busca customizada pode ser reconsiderada com evidência de uso.

## Consequências

### Positivas

- O registro passa a usar o mesmo vocabulário do documento oficial do setor.
- Indicadores e exportações consolidam corretamente as eras antiga e atual.
- Dados e eventos históricos permanecem imutáveis e auditáveis.
- O formulário não cresce verticalmente com 24 rádios e mantém boa experiência mobile.

### Negativas/Trade-offs

- O código precisa manter uma pequena camada permanente de compatibilidade histórica.
- `resource_shortage_detail` permanece no schema embora não seja preenchido por novos registros.
- Depois da primeira escrita nova, rollback direto para uma imagem anterior degrada labels/leitura e não é a estratégia preferida.

### Riscos e Mitigações

- **Mapeamento histórico semanticamente incorreto:** os quatro mapeamentos foram confirmados pelo owner em 2026-09-18 e serão cobertos por testes parametrizados.
- **Código legado voltar a ser aceito no POST:** choices atuais e validação autoritativa usarão um conjunto explícito separado do vocabulário persistido.
- **Divergência entre tabela, cards, filtros e CSV:** todas as superfícies consumirão a mesma projeção canônica, com testes de integração.
- **Dado legado não mapeável:** preflight bloqueia rollout; fallback técnico explícito evita label vazio/500 e não participa do filtro oficial.
- **Perda de contexto histórico:** rows e `CaseEvent` originais não serão alterados; a projeção ocorre apenas na leitura analítica.
- **Rollback após novas escritas:** ensaio `0019 → 0020 → 0019 → 0020` antes de writes; depois, preferir forward-fix e nunca remapear novas causas para `other`.

## Referências

- Change: `openspec/changes/align-followup-causes-with-suspension-form/`
- ADR-0007: `docs/adr/ADR-0007-cobertura-de-follow-up-restrita-a-procedimentos-autorizados.md`
- Specs: `supervisor-appointment-follow-up` e `supervisor-followup-history`

## Histórico de Mudanças

- 2026-09-18: Accepted após confirmação do catálogo e dos quatro mapeamentos históricos pelo owner.
