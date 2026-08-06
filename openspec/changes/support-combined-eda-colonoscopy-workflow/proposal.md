# Proposal: Suportar EDA e Colonoscopia combinadas de ponta a ponta

**Change ID**: `support-combined-eda-colonoscopy-workflow`

**Branch obrigatória**: `feature/support-combined-eda-colonoscopy-workflow`

**Risco**: CRÍTICO / HIGH-ARCH (score determinístico anterior: 86,4)

**ADR requerida antes do Slice 001**: `docs/adr/ADR-0004-procedimentos-multiplos-e-contrato-llm-neutro.md` (deve superar parcialmente a ADR-0003; este change não implementa a ADR por estar limitado a artefatos OpenSpec).

**Base funcional**: change arquivado `openspec/archive/introduce-colonoscopy-exam-workflow/` e specs canônicas em `openspec/specs/`.

## Why

O fluxo atual assume um único `Case.exam_type` (`eda` ou `colonoscopy`) como declaração do NIR, seleção de prompt/policy, filtro operacional e tipo agendado. Solicitações atuais simultâneas de EDA e Colonoscopia são classificadas como `mixed_exam_request`, bloqueadas e devolvidas ao NIR para separação.

Na rotina confirmada pela equipe, EDA e Colonoscopia combinadas são frequentes e normalmente usam o mesmo dia/horário. O CHD precisa receber um único caso identificado como **agendamento casado**, não dois casos nem duas marcações. O médico também precisa decidir cada procedimento independentemente e pode negar, incluir ou substituir um procedimento, sempre com justificativa por componente.

Sobrescrever um único tipo apagaria a diferença entre o que o NIR declarou, o que a análise detectou e o que o médico autorizou, contaminando auditoria e analytics. Executar dois pipelines LLM independentes duplicaria a história clínica e poderia gerar artefatos conflitantes.

## What Changes

- Normalizar EDA/Colonoscopia como componentes de um único caso, separando declaração, detecção e autorização.
- Aceitar EDA + Colonoscopia no intake e fazer upgrade automático conservador de solicitação única para combinada.
- Evoluir novos processamentos para schemas LLM procedure-neutral v2 e quatro prompts comuns.
- Permitir decisão médica e justificativa por componente, com inclusão/substituição sem rerun LLM.
- Entregar ao CHD um conjunto autorizado com um único agendamento casado.
- Adaptar NIR, filas e analytics às dimensões declarado/detectado/autorizado.
- Remover `Case.exam_type` e dispatches específicos somente após cutover integral e testado.

## Objetivos

1. Representar EDA e Colonoscopia como procedimentos associados a um único caso, com projeções separadas de declaração, detecção e decisão médica.
2. Permitir que o NIR envie lote homogêneo de casos EDA, Colonoscopia ou EDA + Colonoscopia.
3. Substituir o contrato LLM centrado no envelope `eda` por schema procedure-neutral v2 para novos processamentos, extraindo a história comum uma única vez.
4. Avaliar policy e recomendação separadamente por procedimento detectado, sem duplicar pipeline nem inventar procedimento ausente.
5. Fazer upgrade automático e auditável de declaração única para análise combinada quando houver evidência forte das duas solicitações atuais, sem ACK prévio do NIR.
6. Manter mismatch único, tipo desconhecido e combinado declarado com apenas um procedimento detectado em revisão do NIR.
7. Permitir decisão médica por procedimento, inclusive inclusão/substituição não solicitada, com razões obrigatórias por componente e sem reexecutar LLM.
8. Produzir uma recomendação global de suporte pelo nível mais restritivo, mantendo a escolha final do médico.
9. Entregar ao CHD um único caso e um único horário para o conjunto aprovado, com badge `EDA + Colonoscopia · Agendamento casado` e alterações explícitas.
10. Consultar históricos anteriores separadamente para EDA e Colonoscopia.
11. Mostrar ao NIR, na resposta final, solicitado, detectado, autorizado e razões por procedimento.
12. Aplicar filtros pela dimensão correta: NIR=declarado, médico=detectado, CHD=autorizado; dashboard permite escolher dimensão.
13. Preservar casos/eventos/artefatos legados, sem inferir ou reescrever JSON clínico 1.1.
14. Remover ao final a fonte operacional única `Case.exam_type` e os dispatches de prompts específicos, após todos os consumidores migrarem.

## Decisões de produto confirmadas

- Um caso combinado é um único `Case` e possui um único `appointment_at`.
- Se o NIR declarar combinado e somente um procedimento for detectado, o caso retorna ao NIR.
- Declaração única com ambos detectados recebe upgrade automático, segue ao médico e apenas informa o NIR; não exige ACK prévio.
- Contradição entre dois tipos únicos continua retornando ao NIR.
- O médico pode incluir procedimento não declarado/detectado; isso não reexecuta o LLM e exige justificativa específica.
- Troca completa exige motivo da negativa do procedimento removido e motivo da inclusão do procedimento adicionado.
- Cada procedimento negado exige razão específica.
- Um suporte/anestesia global é suficiente; a sugestão automática usa o nível mais restritivo e o médico decide o valor final.
- Históricos anteriores são mostrados separadamente por procedimento.
- O CHD sempre agenda os procedimentos aprovados no mesmo horário, ainda que remaneje pacientes; não existe split de agenda neste change.
- A resposta final ao NIR compara solicitação, detecção e autorização.
- `COLONOSCOPY_INTAKE_ENABLED=false` bloqueia Colonoscopia isolada e combinação; EDA isolada continua.
- CPRE permanece fora de escopo.

## Escopo incluído

### Dados e auditoria

- `ProcedureType` com `eda` e `colonoscopy`.
- Entidade normalizada por caso/procedimento, única por `(case, procedure_type)`.
- Projeções operacionais de declaração NIR, detecção da análise e disposição médica.
- Razão médica por componente.
- Backfill conservador do `exam_type` atual para um procedimento declarado.
- Eventos append-only para detecção, upgrade, decisão por componente e snapshot enviado ao CHD/NIR.
- Ponte transitória de compatibilidade durante os slices; remoção final de `Case.exam_type` antes do rollout.

### Pipeline procedure-neutral

- Schema LLM1 v2 com história/pré-operatório comuns e `requested_procedures[]` tipado.
- Uma chamada LLM1 por caso.
- Policy determinística executada por procedimento detectado.
- Schema LLM2 v2 com `procedure_recommendations[]` e suporte global.
- Uma chamada LLM2 por caso.
- Validação de que LLM2 não adiciona/remove procedimentos recebidos.
- Quatro prompts comuns administráveis (`exam_llm1_system`, `exam_llm1_user`, `exam_llm2_system`, `exam_llm2_user`).
- Leitura compatível de artefatos históricos 1.1; sem rewrite de JSON antigo.

### Médico, CHD e NIR

- Relatório médico com seções e histórico por procedimento.
- Aprovação/negativa independente; inclusão/substituição médica auditável.
- Razões obrigatórias por componente.
- CHD agenda conjunto aprovado uma única vez.
- NIR corrige declaração em revisão segura e reprocessa o mesmo caso.
- Reenvio corrigido aceita as três seleções.
- Resposta final explicita todas as transformações.

### Filas, métricas e operação

- Badges e filtros por dimensão de estágio.
- Breakdown por seleção exclusiva (`EDA`, `Colonoscopia`, `EDA + Colonoscopia`, e `Nenhum` quando aplicável).
- Contagem de casos separada de volume de procedimentos.
- Matriz declarado → detectado → autorizado e contagem de agendamentos casados.
- Runbook de migration/cutover/rollback, prompts, drenagem e flag.

## Fora de escopo

- CPRE ou qualquer terceiro procedimento.
- Dois `Case` para uma solicitação combinada.
- Duas datas/horários para o mesmo caso combinado.
- Split posterior pelo CHD.
- Reexecução de LLM quando o médico adiciona procedimento.
- LLM sugerir procedimento que não foi detectado.
- Decisão automática final sem médico.
- Preparo intestinal, biópsia, polipectomia ou suspensão medicamentosa.
- Alteração dos 18 valores executáveis atuais de `CaseStatus`.
- Nova role, atribuição por especialidade, REST API, SPA, WebSocket ou framework JS.
- Reescrita/inferência de JSON clínico legado.
- Reset obrigatório de banco de produção.

## Capabilities

### New Capabilities

- `procedure-neutral-analysis`: extração comum, detecção/reconciliação e recomendação por procedimento.
- `per-procedure-medical-decision`: decisão, inclusão e razão médica por componente.

### Modified Capabilities

- `exam-type-intake-routing`: de tipo único/mixed bloqueado para conjunto declarado e combinação suportada.
- `exam-type-work-queues`: dimensão específica por estágio e agendamento casado.
- `exam-type-correction`: correção do conjunto, reprocessamento v2 e resposta comparativa.
- `exam-type-analytics`: casos versus componentes, dimensões e conversões.

## Impact

- Dados: novo modelo normalizado, migrations de backfill/cutover e remoção final de `Case.exam_type`.
- Pipeline: schemas/prompts/orchestrator/policy/presenters procedure-neutral.
- Fluxos: intake NIR, decisão médica, CHD, correção, resposta final e filtros.
- Analytics: novos breakdowns, volumes e matriz de conversão.
- Operação: migration incompatível com imagem antiga, exigindo rollout serializado e bridge excepcional.
- Segurança clínica: mudanças permanecem humanas/auditáveis; LLM não autoriza nem adiciona procedimento.

## Riscos principais

| Risco | Mitigação |
| --- | --- |
| Duas fontes divergentes durante transição | Ponte explicitamente temporária, dual-write centralizado, flag desligada e remoção obrigatória no Slice 007 |
| LLM duplicar/inventar procedimentos | Schemas estritos, igualdade de conjuntos e uma chamada por estágio |
| Upgrade por menção histórica | Detecção por ocorrência/proveniência, testes de histórico/negação e evidência forte |
| Médico alterar sem rastreabilidade | Serviço transacional, lock existente, razão por componente e eventos append-only |
| Agregado contar combinado incorretamente | Separar casos exclusivos de volume de procedimentos; testes de fechamento |
| Histórico combinado contaminar lookup | Consultas independentes por `procedure_type` e deduplicação visual consciente |
| Rollback para imagem antiga após remoção de coluna | Runbook com imagem nova preferencial e bridge de schema fail-fast para exceção |
| Change transversal grande | Oito slices verticais, caps por slice, inspeções `rg` e revisão independente |

## Critérios de sucesso do change

- NIR cria um único caso EDA, Colonoscopia ou combinado; combinado possui dois procedimentos declarados.
- LLM extrai uma história comum em uma chamada e produz avaliações por procedimento em uma chamada de sugestão.
- Single→combined recebe upgrade auditável e chega ao médico sem ACK NIR.
- Combinado→single e mismatch único retornam ao NIR sem chegar ao médico.
- Médico aprova/nega cada componente, adiciona ou substitui exame com razões obrigatórias e sem rerun LLM.
- CHD recebe somente o conjunto autorizado e confirma um único horário casado.
- Históricos, filtros e resposta final usam a dimensão correta.
- Dashboard distingue casos, procedimentos e conversões sem dupla contagem indevida.
- Artefatos legados continuam legíveis; `Case.exam_type` deixa de ser fonte e é removido antes do rollout.
- Flag desliga Colonoscopia e combinado somente no intake.
- Todos os oito slices comprovam baseline, RED, GREEN, REFACTOR, inspeções, quality gate e relatório temporário revisável.
