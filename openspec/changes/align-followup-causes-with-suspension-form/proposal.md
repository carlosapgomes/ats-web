# Proposal: Alinhar causas do pós-procedimento à ficha oficial de suspensão

**Change ID:** `align-followup-causes-with-suspension-form`

**Risco:** CRÍTICO / HIGH-ARCH — o classificador determinístico atribuiu nível CRITICAL porque a mudança atravessa dados persistidos, validação, indicadores, exportação e documentação operacional em um sistema de saúde. O desenho evita reescrita histórica e mantém FSM, permissões e elegibilidade inalteradas.

**ADR:** [`ADR-0009 — Taxonomia oficial e compatibilidade histórica das causas de não realização`](../../../docs/adr/ADR-0009-taxonomia-oficial-causas-nao-realizacao.md), que supera parcialmente a descrição de causas da ADR-0007 sem alterar sua decisão de cobertura por procedimentos autorizados.

## Why

O formulário de pós-procedimento oferece quatro categorias próprias, enquanto o setor registra suspensões em uma ficha oficial com 23 causas específicas. Essa divergência força enquadramentos genéricos, reduz a qualidade dos indicadores e torna o formulário atual — baseado em rádios e submotivos — inadequado para o novo conjunto de opções.

## What Changes

- Substituir, para novas gravações, o conjunto atual pela lista fechada de 23 causas da ficha de suspensão, acrescida de **Outras causas**.
- Trocar a lista de rádios por um `select` nativo compacto, na ordem da ficha oficial, preservando o desabilitar da causa quando o procedimento foi realizado.
- Manter **Outras causas** como última opção e exigir sua descrição textual.
- Deixar de solicitar submotivo de falta de recursos em novas gravações; as causas equivalentes passam a existir no nível principal.
- Rejeitar os códigos legados `absenteeism` e `resource_shortage` em novos registros, mantendo sua leitura histórica.
- Preservar, sem backfill nem edição, todas as rows e todos os `CaseEvent` legados append-only.
- Projetar registros legados para a taxonomia oficial no Histórico, filtros, indicadores e CSV:
  - Absenteísmo → Não comparecimento do paciente;
  - Urgências que ocuparam o horário → Prioridade para urgência;
  - Falta de tempo hábil → Tempo excedido;
  - Equipamento quebrado/não disponível → Falta de equipamentos.
- Bloquear o rollout quando o preflight encontrar causa/detalhe legado fora desses mapeamentos e manter fallback técnico não filtrável para leitura defensiva.
- Atualizar manual e testes para o novo contrato.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `supervisor-appointment-follow-up`: altera o conjunto fechado de causas, a validação condicional e a apresentação compacta do campo.
- `supervisor-followup-history`: consolida registros das taxonomias antiga e atual sob as causas oficiais em tabela, filtros, indicadores e CSV.

## Impact

- **Domínio/persistência:** `FollowUpNonPerformanceReason`, validação de `record_case_follow_up` e migration de metadados de `choices`; sem alteração de coluna, backfill ou reescrita de eventos.
- **Dashboard:** formulário, JavaScript condicional, Histórico, filtros, cards-resumo e CSV.
- **Compatibilidade:** o storage continua reconhecendo códigos legados apenas para leitura; novas escritas usam exclusivamente a lista oficial.
- **Documentação:** manual do usuário e specs canônicas no arquivamento.
- **Sem impacto pretendido:** FSM, elegibilidade do pós-procedimento, versionamento append-only, cobertura por procedimentos autorizados, papéis/permissões, filas, notificações e fluxos de reagendamento.

## Critérios de sucesso globais

- O formulário exibe exatamente as 23 causas fornecidas pelo setor, na ordem oficial, mais **Outras causas** ao final, em um `select` compacto.
- Todo valor oficial é gravável sem submotivo; **Outras causas** continua exigindo texto e as demais causas rejeitam texto livre.
- Códigos antigos não podem ser enviados como novas causas, mas rows e eventos históricos permanecem byte a byte inalterados.
- Histórico, resumo, filtro e CSV agregam cada causa legada na equivalente oficial confirmada pelo owner; dados fora do mapeamento nunca recebem equivalência inventada nem label vazio.
- O filtro de causa oferece somente a taxonomia oficial; selecionar uma causa oficial encontra tanto registros atuais quanto legados projetados.
- Migration metadata-only passa por inspeção, aplicação e reversão `0019 → 0020 → 0019 → 0020` antes de qualquer write novo.
- Testes focados, quality gate global e `openspec validate ... --strict` passam.

## Rollout e rollback

A migration altera apenas metadados de `choices`; não transforma dados. O deploy deve ser acompanhado de smoke do formulário, de **Outras causas** e de cada mapeamento legado no Histórico/CSV.

Antes da primeira gravação com a taxonomia nova, rollback pode ser feito por revert da aplicação/migration. Após novas gravações, deve-se preferir forward-fix: uma imagem antiga não perde dados, mas não conhece os novos labels nem aceita os novos códigos em atualizações. Nenhuma rotina de rollback pode converter causas novas em `other` ou reescrever `CaseEvent`.
