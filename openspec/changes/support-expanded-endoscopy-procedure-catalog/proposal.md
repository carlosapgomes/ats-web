# Proposal: Catálogo ampliado de procedimentos endoscópicos

**Change ID:** `support-expanded-endoscopy-procedure-catalog`

**Branch de implementação:** `feature/support-expanded-endoscopy-procedure-catalog`

**Risco:** CRÍTICO / HIGH-ARCH — altera identidades clínicas persistidas, matriz de combinações, contrato LLM strict, reconciliação, seleção operacional, decisão médica, filas e analytics.

**ADR:** [`ADR-0010 — Catálogo ampliado e pacotes atômicos de procedimentos endoscópicos`](../../../docs/adr/ADR-0010-catalogo-ampliado-e-pacotes-atomicos-de-procedimentos-endoscopicos.md), proposta junto deste change e requerida como aceita antes do primeiro slice de código.

## Why

O catálogo atual não representa Retossigmoidoscopia nem os pacotes indivisíveis de EDA/Retossigmoidoscopia, fazendo GTT e dilatação sobreviverem apenas como sinais/subtipos e forçando seleções que não escalam. O ATS precisa preservar exatamente o procedimento solicitado ao longo de intake, análise, decisão, filas e histórico, sem alterar a independência já existente de EDA + Colonoscopia e sem transformar uma revisão clínica consultiva em bloqueio automático.

## What Changes

- Expandir o catálogo atômico para `eda`, `eda_gastrostomy`, `eda_capsule`, `eda_dilation`, `colonoscopy`, `rectosigmoidoscopy`, `rectosigmoidoscopy_dilation`, `rectosigmoidoscopy_argon`, `echoendoscopy` e `cpre`.
- Tratar EDA + GTT, EDA + Cápsula, EDA + Dilatação, Retossigmoidoscopia + Dilatação e Retossigmoidoscopia + Argônio como identidades indivisíveis, não como duas rows ou sinais prioritários novos.
- Manter `eda_colonoscopy` somente como seleção derivada que cria duas rows independentes (`eda` e `colonoscopy`); proibir qualquer combinação com uma variação.
- Fazer as três variações de Retossigmoidoscopia reutilizarem os pré-requisitos determinísticos da Colonoscopia e as variações de EDA reutilizarem os da EDA.
- Evoluir novos writes para schemas strict LLM 4.0, preservando leitura de 1.1/2.0/3.0, e reconciliar os pacotes por evidência de solicitação atual.
- Extrair para EDA + Dilatação um local anatômico informativo (`esophagus|pylorus|duodenum|anastomosis|jejunum|other|unknown`) sem criar novos tipos de procedimento nem alterar policy.
- Exibir em EDA + GTT um painel de revisão com evidências ancoradas de leucócitos, PCR, procalcitonina, lactato, culturas, temperatura/febre, infectologia e antibióticos. Resultados presentes, inclusive normais/negativos, serão exibidos; somente qualificação preocupante explicitamente documentada gera alerta visual de possível infecção sistêmica.
- Garantir que o alerta GTT nunca bloqueie, negue, crie pendência de policy, altere sugestão automática, decisão, FSM ou encaminhamento.
- Substituir seletores de procedimento por radio buttons nas jornadas de upload, correção/reenvio NIR e inclusão/substituição médica por combobox pesquisável e acessível, com busca sem acentos, progressive enhancement em JavaScript vanilla, fallback SSR e validação backend por código exato.
- Generalizar labels, filtros, filas, follow-up e analytics para todo o catálogo, mantendo categoria case-level exclusiva e volume por componente.
- Preservar histórico por código exato; não reclassificar casos antigos, não executar backfill e não criar flags ou rollout gradual para as novas identidades.
- Fazer cutover coordenado de web, workers e prompts 4.0; após o primeiro write 4.0, rollback suportado é fix-forward, sem reativar writer 3.0.

## Capabilities

### New Capabilities

- `gastrostomy-infection-review`: contrato e apresentação consultiva de evidências de possível infecção sistêmica para EDA + GTT, incluindo resultados normais presentes e invariantes de não bloqueio.
- `searchable-procedure-selection`: comportamento acessível, pesquisável e com fallback SSR dos seletores de procedimento nas jornadas NIR e médica.

### Modified Capabilities

- `procedure-combination-policy`: amplia o catálogo autoritativo, define pacotes atômicos, famílias/perfis e a nova matriz fechada.
- `exam-type-intake-routing`: aceita as novas seleções sem flags adicionais, preserva EDA + Colonoscopia e detecta solicitações atuais conservadoramente.
- `procedure-neutral-analysis`: evolui o writer para schema 4.0, inclui detalhes tipados de GTT/dilatação e mantém adapters históricos.
- `per-procedure-medical-decision`: permite decisão por nova identidade, histórico por código exato e apresentação dos detalhes consultivos.
- `exam-type-correction`: permite corrigir/reencaminhar para as novas identidades com o mesmo contrato de auditoria e reprocessamento.
- `exam-type-work-queues`: amplia labels, filtros e projeções operacionais sem transformar pacotes em combinados.
- `exam-type-analytics`: amplia categorias e volumes, preservando a semântica exclusiva de caso e o agendamento casado somente para EDA + Colonoscopia.

## Impact

- **Domínio/persistência:** `ProcedureType`, `CaseProcedure`, migration de choices/`max_length`, catálogo e validação de conjuntos; sem data migration.
- **Pipeline:** profiles, schemas/adapters 4.0, prompts versionados, detecção por escopo, reconciliação, projeções e orchestrator.
- **Experiência NIR/médica:** forms, views, templates, CSS e JavaScript vanilla do combobox; painel GTT e detalhe de dilatação.
- **Operação:** web/workers/prompt writer devem fazer cutover único e coordenado; flags atuais permanecem com sua semântica e nenhuma nova flag é criada.
- **Filas/gestão:** filtros, labels, follow-up e analytics passam a consumir metadados do catálogo em vez de listas binárias/hardcoded.
- **Sem impacto pretendido:** FSM, roles, intranet guard, locks, quantidade de casos/agendamentos, processamento de anexos, thresholds laboratoriais clínicos, API REST ou SPA.
