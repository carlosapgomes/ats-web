# Design: Taxonomia oficial no pós-procedimento com compatibilidade histórica

## Context

Ver `proposal.md` para a motivação e a ADR-0009 para a decisão de produto. Hoje `FollowUpNonPerformanceReason` é simultaneamente vocabulário persistido, choices do formulário, conjunto aceito pelo service e fonte dos labels/ordem do Histórico. `resource_shortage` ainda condiciona `resource_shortage_detail`; `other` condiciona `other_reason`. O template renderiza causas como rádios e `followup_form.js` procura especificamente inputs radio.

`CaseFollowUp` e `ProcedureFollowUp` são versionados append-only e cada gravação é espelhada em `CaseEvent`. O Histórico trabalha em Python sobre a versão corrente e deriva da mesma lista de choices seus labels, filtros, cards e CSV. Essas características permitem compatibilidade por projeção de leitura sem alterar rows ou eventos.

## Goals / Non-Goals

**Goals:**

- separar o vocabulário persistido entre eras do conjunto permitido para novas gravações;
- oferecer a lista oficial completa em uma UI compacta e responsiva;
- manter validação server-side autoritativa e o texto obrigatório somente para `other`;
- consolidar causas legadas e atuais em uma única taxonomia analítica;
- preservar byte a byte as rows e os `CaseEvent` históricos.

**Non-Goals:**

- remover a coluna `resource_shortage_detail` ou seus constraints;
- executar backfill, editar eventos ou reclassificar causas sem mapeamento confirmado;
- alterar elegibilidade, cobertura por procedimento autorizado, versionamento, FSM, papéis ou permissões;
- criar busca/autocomplete customizado, nova dependência frontend ou CSS próprio;
- alterar fluxos de intercorrência, cancelamento ou reagendamento.

## Decisions

### D1. Catálogo atual fechado e códigos estáveis

As choices atuais serão declaradas explicitamente, nesta ordem. Todos os códigos cabem no `max_length=30` existente.

| Ordem | Código | Label oficial |
| --- | --- | --- |
| 1 | `missing_exam_consent` | Ausência do preenchimento do TCLE para realização de exame |
| 2 | `missing_anesthesia_consent` | Ausência do preenchimento do TCLE anestésico |
| 3 | `clinical_conditions` | Condições clínicas desfavoráveis |
| 4 | `scheduling_error` | Erro na programação do procedimento |
| 5 | `missing_gastroenterologist` | Falta de médico gastroenterologista |
| 6 | `missing_anesthesiologist` | Falta de anestesiologista |
| 7 | `missing_equipment` | Falta de equipamentos |
| 8 | `missing_tests` | Falta de exames |
| 9 | `missing_blood_products` | Falta de hemoderivados |
| 10 | `fasting_not_observed` | Falta de jejum |
| 11 | `missing_material_opme` | Falta de material/OPME |
| 12 | `missing_icu_bed` | Falta de vaga na UTI |
| 13 | `inadequate_prep` | Preparo inadequado |
| 14 | `difficult_intubation` | Intubação difícil |
| 15 | `medical_plan_changed` | Mudança de conduta médica |
| 16 | `patient_no_show` | Não comparecimento do paciente |
| 17 | `patient_death` | Paciente foi a óbito |
| 18 | `emergency_priority` | Prioridade para urgência |
| 19 | `time_exceeded` | Tempo excedido |
| 20 | `transferred_other_hospital` | Transferência para outro hospital |
| 21 | `patient_delay` | Atraso do paciente |
| 22 | `divergent_report` | Relatório divergente |
| 23 | `patient_refusal` | Recusa do paciente |
| 24 | `other` | Outras causas |

`inadequate_prep` e `other` preservam os códigos atuais para não criar duplicatas artificiais. Labels devem ser exatamente os fornecidos pelo setor; não abreviar TCLE, OPME ou UTI.

Alternativa rejeitada: usar labels como valores persistidos. Códigos estáveis em inglês seguem o padrão do domínio e desacoplam storage de correções futuras de copy.

### D2. Storage reconhece eras; novas escritas aceitam somente o catálogo atual

`FollowUpNonPerformanceReason` continuará contendo os códigos persistidos legados (`absenteeism`, `resource_shortage`) e os atuais para que migrations/model state documentem tudo que pode existir no banco. As constantes explícitas `CURRENT_FOLLOWUP_NON_PERFORMANCE_REASON_CHOICES` e `CURRENT_FOLLOWUP_NON_PERFORMANCE_REASON_VALUES`, ordenadas conforme D1, serão a fonte única para:

- `FollowUpForm.non_performance_reason`;
- validação de `_validate_outcomes`;
- opções do filtro do Histórico após a projeção.

Assim, `FollowUpNonPerformanceReason.values` não poderá mais ser usado para autorizar novas escritas. O service rejeitará `absenteeism` e `resource_shortage` em novas versões, inclusive se enviados manualmente no POST.

A migration será apenas `AlterField` de metadados de choices; não altera tipo, tamanho, constraint nem conteúdo de rows. `resource_shortage_detail` e os checks existentes permanecem para as rows históricas. Toda nova row gravará esse campo vazio.

Alternativa rejeitada: remover imediatamente os códigos/coluna legados. Isso tornaria o model state incapaz de descrever o storage real e exigiria backfill destrutivo.

### D3. Regras condicionais ficam simples e fail-closed

Para `performed=False`:

- a causa é obrigatória e deve pertencer ao catálogo atual;
- `other` exige `other_reason.strip()` não vazio;
- qualquer outra causa rejeita `other_reason` não vazio;
- `resource_shortage_detail` é rejeitado para qualquer nova gravação.

Para `performed=True`, o comportamento atual permanece: causa, detalhe e texto são normalizados para vazio pelo service.

Erros continuam amigáveis no form e no service, sem expor `IntegrityError`.

### D4. Select nativo substitui 24 rádios sem nova dependência

O campo de causa será um `forms.Select` com `class="form-select"`, placeholder vazio **Selecione uma causa...** e label obrigatório. O template renderizará um único select por bloco. A ordem será exatamente D1 e `other` permanecerá ao final.

`followup_form.js` deixará de procurar um radio de causa e passará a observar o controle pelo sufixo de `name`, independentemente do tipo. Quando **Realizado** estiver marcado, o fieldset continuará desabilitado e a seleção será limpa. Quando **Não realizado** estiver ativo, o select será habilitado; somente `other` revela o textarea. O estado inicial/re-render pós-erro continuará respeitado.

Alternativas rejeitadas:

- 24 rádios, por degradarem altura e escaneabilidade, especialmente com dois procedimentos;
- combobox pesquisável customizado, por elevar o custo de acessibilidade/JS sem evidência de necessidade;
- agrupamento visual, por alterar a ordem oficial confirmada.

### D5. Projeção canônica única para Histórico e CSV

Uma função pura no domínio de follow-up receberá `non_performance_reason` e `resource_shortage_detail` persistidos e devolverá o código oficial para leitura analítica:

| Persistido | Detalhe persistido | Projetado |
| --- | --- | --- |
| `absenteeism` | vazio | `patient_no_show` |
| `resource_shortage` | `emergency_occupied` | `emergency_priority` |
| `resource_shortage` | `insufficient_time` | `time_exceeded` |
| `resource_shortage` | `equipment_unavailable` | `missing_equipment` |
| código atual | vazio | o próprio código |

`_followup_history_rows` aplicará a projeção antes de compor `reason`, `reason_label`, filtros e resumo. Consequências:

- cards agregam rows antigas e novas sob um único código oficial;
- `?reason=patient_no_show` encontra `patient_no_show` e `absenteeism`;
- códigos legados deixam de ser opções válidas do filtro;
- tabela e CSV mostram label oficial;
- `other_reason` continua visível somente para `other`;
- o campo/coluna existente de submotivo permanece no CSV por compatibilidade estrutural, mas fica vazio após a projeção canônica.

A função não salva nada. Testes devem recarregar as rows/eventos legados e provar que permaneceram inalterados após consultas/exportação.

Dados não mapeáveis terão política fail-closed explícita:

- um preflight ORM antes do rollout procura rows `performed=False` cujo motivo não pertença ao catálogo atual nem a `absenteeism`, ou cujo `resource_shortage_detail` não pertença aos três detalhes confirmados;
- qualquer ocorrência faz o preflight retornar exit code não zero e bloqueia rollout até análise humana;
- como defesa em profundidade para corrupção posterior/carga direta, a projeção retorna o código apenas de leitura `legacy_unmapped`, com label **Causa legada não mapeada**;
- essa categoria técnica pode aparecer na tabela/cards/CSV e preserva reason/detail brutos no campo de detalhe para diagnóstico, mas não integra choices de model/form nem opções/filtros oficiais;
- nenhuma equivalência nova é inferida e nenhuma row/evento é alterado.

O preflight deve executar depois do Slice 001, quando o catálogo atual estiver disponível, e novamente imediatamente antes do deploy. A evidência registra contagem e, em caso de falha, no máximo IDs/códigos técnicos — nunca dados clínicos/pessoais.

Alternativa rejeitada: projetar apenas no template. Isso faria tabela, filtros, cards e CSV divergirem. Também foi rejeitado lançar exceção/500 para dado desconhecido: o rollout é bloqueado pelo preflight, mas a leitura defensiva deve continuar diagnóstica se corrupção surgir depois.

### D6. Manual e contrato de CSV

O manual listará as 23 causas oficiais + **Outras causas**, explicará o select e removerá a instrução de submotivo. A exportação mantém endpoint, BOM, separador, ordem de colunas e paginação atuais. A coluna `Submotivo` é mantida para compatibilidade do arquivo, embora novas rows e rows legadas projetadas a emitam vazia; a coluna de texto de **Outras causas** permanece.

### D7. Estratégia de slices

Dois slices verticais evitam uma mudança monolítica sem criar estado quebrado:

1. **Registro oficial compacto:** domínio aceita somente as novas causas, formulário/JS grava a taxonomia oficial e o model state ainda reconhece os códigos legados. No mesmo slice, fixtures de Histórico que representam a era antiga deixam de chamar o service de novas escritas e passam a criar versões/rows legadas diretamente; suas expectativas visuais permanecem antigas até o Slice 002. A suíte de Histórico integra o aceite do slice, mantendo o repositório verde.
2. **Consolidação histórica:** aplica a projeção única em tabela/filtros/cards/CSV, fallback técnico/preflight e atualiza o manual. Entrega comparabilidade entre eras sem mutação.

O Slice 001 excede a heurística de cinco arquivos porque atravessa obrigatoriamente model state, service autoritativo, form SSR, JS progressivo, migration, fixtures históricas e seus testes; separar essas partes deixaria um contrato de gravação ou a suíte incoerente. Nenhum slice altera arquitetura fora do follow-up.

## Risks / Trade-offs

- **Lista longa continuar lenta para operadores frequentes** → começar com select nativo; só considerar busca customizada após evidência operacional.
- **Choices persistidas confundidas com values aceitos** → constantes atuais nomeadas e testes que rejeitam os dois códigos legados em novas gravações.
- **Cards ou filtros contarem eras separadamente** → projeção antes da construção da row analítica e testes parametrizados de agregação/filtro/CSV.
- **Dado legado fora do mapeamento** → preflight fail-closed + fallback técnico não filtrável coberto por teste.
- **Migration aparentar backfill** → inspecionar operação gerada, testar ida/volta com `MigrationExecutor` e executar `migrate --plan`.
- **Rollback para imagem antiga após novas escritas** → ensaiar reversão antes de writes; depois, preferir forward-fix e nenhuma conversão destrutiva para `other`.
- **Expansão do blast radius para remover coluna/constraints** → explicitamente fora de escopo; escalar ao owner antes de qualquer remoção.

## Migration Plan

1. Registrar `BASE_REF` e confirmar baseline/CI confiável antes do Slice 001.
2. Gerar/inspecionar a migration metadata-only e testar com `MigrationExecutor` a sequência `0019 → 0020 → 0019 → 0020`, provando que rows legadas permanecem idênticas.
3. Executar o Slice 001 e sua suíte de Histórico já adaptada para fixtures legadas diretas; o repositório deve terminar verde.
4. Executar o preflight de códigos/detalhes legados não mapeáveis; resultado diferente de zero bloqueia o Slice 002/rollout e exige decisão humana.
5. Executar o Slice 002 em RED → GREEN → REFACTOR, com review independente.
6. Executar o quality gate global, `migrate --plan` e `openspec validate ... --strict` uma única vez ao final.
7. Em staging sem writes concorrentes, repetir preflight, aplicar `0020`, validar leitura, reverter para `0019`, reaplicar `0020` e somente então liberar novas gravações.
8. No smoke, validar uma causa oficial comum, `other` com texto, rejeição de código legado, fallback técnico sintético e os quatro mapeamentos no Histórico/CSV.
9. Deploy web/worker juntos; não há flag ou ordem de serviço especial.

**Rollback:** antes da primeira nova gravação, a reversão ensaiada da aplicação/migration é segura. Depois disso, não fazer data downgrade; preferir forward-fix. Em emergência, uma imagem de compatibilidade deve continuar sabendo ler os novos códigos. Rows e eventos nunca serão reescritos como parte do rollback.
