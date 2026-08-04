# Proposal: Introduzir colonoscopia como tipo de exame suportado

**Change ID**: `introduce-colonoscopy-exam-workflow`

**Branch de implementação**: `feature/colonoscopy-exam-workflow`

**Risco**: CRÍTICO / HIGH-ARCH

**ADR**: `docs/adr/ADR-0003-perfis-procedimento-tipo-exame-explicito.md`
**Dependências funcionais**: intake NIR, pipeline LLM, policy pré-operatória, fila médica, fila CHD, dashboard e auditoria existentes.

## Problema

O ATS suporta operacionalmente apenas EDA. Colonoscopia aparece hoje em `apps/pipeline/scope_detection.py` como exame explicitamente fora do escopo, recebe `manual_review_required` e não chega ao médico.

O sistema também não possui um tipo de exame persistido no `Case`. As filas médica e CHD agrupam casos apenas por status, os prompts e presenters usam terminologia EDA, e o NIR não declara o procedimento no upload. Isso impede separação operacional confiável e torna arriscada a inclusão futura de CPRE, que terá requisitos pré-procedimento mais amplos.

Além disso, o pipeline atual avalia coagulograma, mas não extrai nem apresenta de forma estruturada medicamentos relevantes, anticoagulantes ou antiagregantes. Uma menção pode aparecer em texto livre, porém não há alerta médico canônico e auditável.

## Objetivos

1. Adicionar `Case.exam_type` como tipo operacional explícito e auditável, com `eda` e `colonoscopy`.
2. Exigir que o NIR selecione o tipo antes do upload e garantir lote homogêneo.
3. Reconhecer colonoscopia por termos conservadores e contexto de solicitação atual.
4. Bloquear PDF com solicitações atuais simultâneas de EDA e colonoscopia, pedindo envios separados.
5. Permitir que colonoscopia percorra o mesmo fluxo operacional de EDA: pipeline, decisão médica, fluxos pediátricos, CHD, resultado e encerramento NIR.
6. Separar regras pré-operatórias em perfis de procedimento, compartilhando a base entre EDA e colonoscopia e mantendo a exceção de corpo estranho exclusiva de EDA.
7. Extrair medicamentos descritos e alertar o médico sobre anticoagulantes/antiagregantes sem automatizar aceite, negativa ou orientação de suspensão.
8. Manter abas primárias por estado e adicionar filtros `Todos | EDA | Colonoscopia` com contadores nas telas acordadas.
9. Permitir correção auditável do tipo e reprocessamento do mesmo caso somente antes da fila médica ou após divergência/scope manual.
10. Oferecer métricas consolidadas e breakdown por tipo de exame.
11. Permitir desligar globalmente apenas novos uploads de colonoscopia por configuração.

## Decisões de produto confirmadas

- O NIR é responsável por declarar o tipo.
- Todo lote deve conter PDFs do mesmo tipo.
- EDA e colonoscopia solicitadas no mesmo PDF exigem casos/PDFs separados.
- EDA e colonoscopia compartilham exames mínimos, thresholds, suporte, ASA e fluxo pediátrico.
- A exceção de corpo estranho não vale para colonoscopia.
- Preparo intestinal, biópsia e classificação diagnóstica/terapêutica não serão avaliados neste change.
- Medicamentos serão extraídos e exibidos como alerta; não haverá hard rule medicamentosa.
- Os mesmos médicos e o mesmo formulário CHD processam os dois exames.
- A prioridade continua por `regulation_days_on_screen DESC NULLS LAST, created_at ASC`.
- Todos os casos prévios serão backfillados como EDA; nenhum caso histórico será reprocessado.
- `Todos` será o filtro padrão.
- A busca médica preservará o termo ao trocar tipo e terá limpeza rápida.
- `Decididos Hoje` e `Processados Hoje` terão badge e filtro simples por tipo.
- O histórico CHD permitirá listar os últimos casos por tipo mesmo sem termo.
- NIR terá filtro por tipo em casos operacionais e encerrados.
- Dashboard mostrará métricas consolidadas e breakdown por tipo.
- Não haverá piloto por grupo; haverá interruptor global de novos uploads.

## Escopo incluído

### Dados e auditoria

- `ExamType` e `Case.exam_type` não nulo.
- Migration com backfill integral para EDA, sem inferência em texto histórico.
- Índice adequado às filas por status/tipo.
- Tipo incluído em criação, reenvio corrigido, cards, detalhes e eventos novos relevantes.
- Correção de tipo no mesmo caso com evento append-only e reprocessamento controlado.

### Pipeline e policy

- Perfis explícitos EDA/colonoscopia sobre regras pré-operatórias comuns.
- Detecção de colonoscopia por `colonoscopia`, `endoscopia digestiva baixa`, `EDB` contextual, `videocolonoendoscopia` e variantes diagnóstica/terapêutica.
- Distinção entre solicitação atual e referência histórica.
- Scope mismatch e solicitação mista voltam ao NIR para correção.
- Prompts de colonoscopia versionados separadamente e administráveis.
- Prior-case lookup limitado ao mesmo tipo de exame.
- Sinais prioritários EDA não vazam para colonoscopia; colonoscopia mantém pediatria e dias em tela.

### Segurança medicamentosa

- Lista estruturada de medicamentos explicitamente descritos, com evidência.
- Classe informativa, uso descrito e última dose/posologia quando disponível.
- Destaque especial para anticoagulante e antiagregante.
- Alerta no relatório médico e reconstrução de auditoria.
- Nenhuma decisão automática, recomendação de suspensão ou instrução farmacológica.

### UI/UX

- Tipo obrigatório no upload, sem default visual.
- Filtros por tipo nas filas e buscas acordadas.
- Badge de tipo em cards/detalhes.
- Busca médica client-side compõe termo + tipo, preserva termo no polling/troca e possui botão `Limpar`.
- CHD filtra todas as categorias que compõem `Pendentes`.
- Histórico CHD combina nome/ocorrência e tipo, ou lista recentes somente por tipo.
- Dashboard mantém totais globais e apresenta breakdown por tipo.

### Operação

- `COLONOSCOPY_INTAKE_ENABLED` bloqueia apenas novos uploads.
- Casos já criados continuam processáveis quando a flag é desligada.
- Runbook de ativação, monitoramento e rollback não destrutivo.

## Fora de escopo

- Suporte funcional a CPRE.
- Requisitos clínicos adicionais de CPRE.
- Avaliação de preparo intestinal.
- Decisão sobre biópsia/polipectomia ou caráter diagnóstico/terapêutico.
- Regras automáticas de suspensão de medicamentos.
- Aceite/negativa automática por anticoagulante ou antiagregante.
- Nova equipe, atribuição por especialidade ou permissão por tipo.
- Novo estado FSM permanente para tipo de exame.
- API REST, SPA, WebSocket ou framework frontend.
- Reprocessamento de casos históricos.
- Migração/reescrita dos JSONs LLM históricos.
- Feature flag por usuário/grupo.

## Riscos principais

| Risco | Mitigação |
| --- | --- |
| Colonoscopia seguir policy EDA com exceção indevida | Perfil explícito e testes negativos para `foreign_body_exception` |
| EDA regressar por generalização excessiva | Compatibilidade do contrato atual, testes de caracterização e mudanças incrementais |
| Documento histórico causar classificação errada | Contexto local e prioridade para solicitação atual |
| Solicitação mista chegar à fila médica | Gate determinístico e teste EDA+colonoscopia atual |
| Correção disputar com worker | Serviço transacional, estados estáveis e guarda contra processamento concorrente |
| Medicamento gerar conduta clínica indevida | Alerta informativo, evidência explícita, nenhuma hard rule |
| Rollback deixar casos presos | Flag apenas de intake e runbook para casos em voo |
| Slices centrais tocarem muitos arquivos | Limites explícitos, justificativa obrigatória e proibição de antecipar slices |

## Critérios de sucesso do change

- NIR não consegue enviar lote sem tipo e recebe validação de homogeneidade.
- EDA existente continua percorrendo todo o fluxo sem alteração clínica não aprovada.
- Colonoscopia válida chega ao médico e segue todos os fluxos aceitos/negados existentes.
- Colonoscopia não usa exceção de corpo estranho nem badges procedimentais EDA.
- Solicitação atual mista não chega ao médico.
- Divergência pode ser corrigida e reprocessada antes de `WAIT_DOCTOR`, com auditoria.
- Anticoagulantes/antiagregantes explicitamente descritos geram alerta médico, mas não mudam decisão.
- Médico, CHD e NIR conseguem filtrar por tipo conforme requisitos.
- Dashboard apresenta total consolidado e breakdown EDA/colonoscopia.
- Casos históricos permanecem intactos e classificados como EDA.
- Flag global bloqueia novos uploads sem parar casos existentes.
- Todos os slices passam baseline, TDD, inspeções, quality gate e revisão por relatório temporário.
