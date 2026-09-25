# Design: Catálogo ampliado de procedimentos endoscópicos

## Context

Ver [`proposal.md`](proposal.md) para motivação, [`ADR-0010`](../../../docs/adr/ADR-0010-catalogo-ampliado-e-pacotes-atomicos-de-procedimentos-endoscopicos.md) para a decisão arquitetural e `specs/` para os contratos observáveis.

A base atual já possui as fronteiras necessárias, mas está fechada em quatro tipos:

- `CaseProcedure` separa declaração, detecção e disposição médica;
- `apps/cases/procedures.py` centraliza ordem, matriz e projeções, porém enumera quatro identidades;
- `ProcedureType.max_length=20`, filtros, templates, JS e analytics ainda contêm listas fechadas/hardcoded;
- `ExamProfile` concentra diferenças clínicas, enquanto GTT e dilatação continuam como subtipos/sinais legados de EDA;
- o writer strict 3.0 usa uniões discriminadas de quatro tipos e readers 1.1/2.0/3.0;
- detecção/reconciliação já preserva ocorrências qualificadas e precedência de Ecoendoscopia/CPRE;
- decisão médica já suporta inclusão/troca transacional sem rerun;
- a UI de upload/correção ainda usa radios e a decisão médica materializa campos por procedimento;
- filas e analytics misturam consumo do catálogo com listas estáticas.

O change precisa manter SSR, Vanilla JS, um único caso/agendamento, os estados FSM existentes e a matriz auditável. A branch só é implantável depois de todos os slices; estados intermediários dos commits não são rollout gradual.

## Goals / Non-Goals

**Goals:**

- tornar identidade, label, ordem, família/profile, aliases e opções de seleção derivados de um catálogo central;
- representar cada pacote como singleton ponta a ponta e preservar exatamente duas rows somente em EDA + Colonoscopia;
- evoluir o writer para 4.0 com detalhes clínicos tipados e readers históricos;
- manter policy procedure-neutral, com profile reutilizado e sem equivalência de histórico;
- separar revisão consultiva GTT da policy e provar invariância de decisão/FSM;
- oferecer um componente de combobox reutilizável, acessível e progressivamente aprimorado;
- eliminar pressupostos de “quatro tipos” nos consumidores operacionais/analíticos.

**Non-Goals:**

- criar threshold, diagnóstico ou score de infecção;
- criar regra clínica adicional para cápsula, dilatação, argônio ou Retossigmoidoscopia;
- distinguir EDA + Dilatação por sítio na identidade persistida;
- combinar variações com Colonoscopia, criar split, segundo caso ou segundo appointment;
- processar anexos para os novos detalhes;
- reclassificar sinais/subtipos históricos ou recomputar analytics antigos;
- adicionar flags, dependência frontend, framework JS, REST ou SPA;
- alterar roles, locks, intranet guard, FSM ou taxonomia de follow-up.

## Decisions

### D1. `ProcedureDefinition` será a fonte de metadados do catálogo

`ProcedureType` continuará sendo o enum Django persistível, com `max_length=32` (o maior código planejado tem 27 caracteres). `apps/cases/procedures.py` manterá um registro ordenado e imutável conceitualmente equivalente a:

```python
@dataclass(frozen=True)
class ProcedureDefinition:
    code: str
    label: str
    family: Literal["eda", "colonoscopy", "specialized"]
    profile_key: str
    detection_terms: tuple[str, ...]
    search_aliases: tuple[str, ...] = ()
    detail_kind: Literal["none", "dilation_site", "infection_review"] = "none"

PROCEDURE_CATALOG: tuple[ProcedureDefinition, ...] = (...dez entradas...)
```

Mapas/tuplas públicos (`SUPPORTED_PROCEDURE_TYPES`, ordem, labels, escolhas de UI) serão derivados desse registro. `ALLOWED_PROCEDURE_SETS` será `{singleton por código} ∪ {{eda, colonoscopy}}`; `SELECTIONS` adicionará `eda_colonoscopy` como chave derivada. O catálogo não conterá flags de rollout.

`ExamProfile` continuará separado porque contém regra clínica. Cada identidade resolverá explicitamente `profile_key`; desconhecido falhará fechado nos writers novos. O fallback histórico para EDA ficará isolado em adapter legado, não no caminho 4.0.

**Alternativa rejeitada:** ampliar cada lista local. Isso permitiria divergência de ordem, label, combinações e profiles.

### D2. Pacote atômico e combinado derivado terão representações distintas

Persistência e conjuntos:

```text
EDA + GTT                     -> {eda_gastrostomy}       -> 1 row
EDA + Cápsula                 -> {eda_capsule}           -> 1 row
EDA + Dilatação               -> {eda_dilation}          -> 1 row
Retossigmoidoscopia + Argônio -> {rectosigmoidoscopy_argon} -> 1 row
EDA + Colonoscopia            -> {eda, colonoscopy}      -> 2 rows
```

`selection_key()` primeiro validará/normalizará e só devolverá `eda_colonoscopy` para igualdade exata com `PAIRED_APPOINTMENT_SET`; singleton sempre devolve seu código, mesmo se a label contém `+`. Sets vazios continuam com o comportamento de leitura já contratado. `is_paired_appointment_set()` permanece a única autoridade de agendamento casado.

A migration altera `choices` e `max_length`, sem `RunPython`, backfill ou remoção de sinais.

### D3. Precedência de pacote exige ocorrência atual da mesma expressão

O detector textual produzirá ocorrências com `procedure_type`, qualificação (`current_request|historical|negated|mention`) e trecho local. Regras por ocorrência precedem a matriz:

- EDA + GTT/Cápsula/Dilatação atual colapsa a EDA base da mesma expressão;
- Retossigmoidoscopia + Dilatação/Argônio atual colapsa a base da mesma expressão;
- uma única variação atual pode suprimir o cabeçalho/base detectado, preservando metadado auditável de selecionado/suprimido;
- duas variações atuais, variação + Colonoscopia ou dois especializados permanecem incompatíveis;
- o `requested_procedures` do LLM sem ocorrência textual atual não autoriza supressão.

Para dilatação, a janela local precisa conter intenção de procedimento e EDA ou Retossigmoidoscopia. “Dilatação de colédoco”, anatomia dilatada como achado, histórico e negação são negativos obrigatórios. O vocabulário não adicionará siglas operacionais. `GTT`, `cápsula` e `dilatação` são aliases aprovados; nomes canônicos completos permanecem reconhecidos.

**Alternativa rejeitada:** colapsar pelo conjunto bruto do LLM. Isso permitiria que história ou achado anatômico alterasse identidade.

### D4. Profiles serão reutilizados por chave, não por herança de identidade

O catálogo mapeará:

| Identidades | Profile |
| --- | --- |
| `eda`, `eda_gastrostomy`, `eda_capsule`, `eda_dilation` | EDA |
| `colonoscopy`, `rectosigmoidoscopy`, `rectosigmoidoscopy_dilation`, `rectosigmoidoscopy_argon` | Colonoscopia |
| `echoendoscopy` | Ecoendoscopia |
| `cpre` | CPRE |

A policy receberá sempre o código de identidade e resolverá o profile para regras clínicas, mas retornará recomendação/pendência sob o código original. Histórico, filtros, eventos e volumes nunca consultam `profile_key` para equivalência.

Nos writes 4.0, `gastrostomy` e `esophageal_dilation` não serão persistidos como sinais prioritários quando já constituem a identidade. Leitores históricos continuam exibindo os sinais antigos.

### D5. LLM1/LLM2 4.0 ampliam tipos sem reescrever versões antigas

Novos módulos `llm1_v4.py` e `llm2_v4.py` serão criados; v3 permanece imutável para leitura. LLM1 usará união discriminada com dez variantes, máximo de dez itens brutos para que reconciliação possa explicar conjuntos incompatíveis. Cada variante preserva `evidence_spans`; somente as variantes aplicáveis carregam detalhes adicionais.

LLM2 aceitará os dez códigos e continuará exigindo igualdade exata com o conjunto reconciliado, com um retry corretivo apenas para mismatch schema-válido. Os quatro nomes administráveis de prompt permanecem; `seed_prompts` cria versões 4.0 idempotentes.

Adapters exporão `detect_schema_version`, `requested_procedure_types_v4` e `project_v4_to_llm1_shape`, preservando 1.1/2.0/3.0. Código procedure-neutral reconhecerá `2.0|3.0|4.0`; 1.1 continua no caminho legado.

### D6. Detalhe de dilatação pertence ao item `eda_dilation`

A variante 4.0 conterá:

```python
class DilationDetailV4(StrictModel):
    anatomical_site: Literal[
        "esophagus", "pylorus", "duodenum", "anastomosis",
        "jejunum", "other", "unknown",
    ]
    evidence_excerpt: str | None
```

Validator exige excerpt não vazio quando o sítio não é `unknown`. Um verificador confirma ocorrência única do excerpt no `Case.extracted_text`; mismatch/ambiguidade projeta `unknown` para apresentação e registra motivo técnico enxuto, sem falhar pipeline nem policy. Labels anatômicos são projetados no presenter.

Não haverá coluna no model nem novo `ProcedureType` por sítio; o detalhe permanece no artefato clínico versionado.

### D7. Revisão GTT usa coleção factual separada da policy

A variante `eda_gastrostomy` conterá:

```python
class InfectionEvidenceV4(StrictModel):
    category: Literal[
        "leukocytes", "crp", "procalcitonin", "lactate", "culture",
        "temperature_or_fever", "infectious_disease", "antibiotic",
    ]
    assessment: Literal[
        "normal_explicit", "abnormal_explicit", "positive_explicit",
        "negative_explicit", "febrile_explicit", "current_care_explicit",
        "antibiotic_in_use", "antibiotic_started",
        "antibiotic_escalated", "unclassified",
    ]
    temporal_status: Literal["current", "historical", "unknown"]
    value_text: str | None
    evidence_excerpt: str
```

O prompt exige todos os resultados presentes nas categorias fechadas, inclusive normais/negativos, preservando texto e unidade. Não converte números nem aplica reference ranges.

Um verificador determinístico:

1. ancora cada excerpt uma única vez no relatório principal normalizado conservadoramente;
2. rederiva a categoria por aliases versionados no mesmo trecho;
3. aceita `normal/abnormal/positive/negative/febrile` somente com marcador textual explícito local;
4. trata marcador histórico local como dominante;
5. reduz classificação não comprovada a `unclassified`, mantendo o valor ancorado visível;
6. deduplica por categoria + valor + excerpt e ordena pelo vocabulário canônico.

O destaque é derivado em código, nunca confiado a boolean do LLM. Gera alerta quando `temporal_status != historical` e `assessment` pertence ao conjunto preocupante (`abnormal_explicit`, `positive_explicit`, `febrile_explicit`, `current_care_explicit`, estados atuais de antibiótico). `normal_explicit`, `negative_explicit` e `unclassified` aparecem sem alertar isoladamente.

O resultado será um DTO/presenter separado, por exemplo `InfectionReviewView`, não um item de `PolicyEvaluation.failed_requirements` nem `priority_signals`. Orchestrator poderá persistir a coleção no artefato 4.0, mas não a passará como regra ao reconciliador LLM2.

### D8. Invariância consultiva será protegida por fronteira e testes

Para o mesmo caso/policy/recomendação, variar somente `infection_evidence` deve manter idênticos:

- `decision`, `reason_code` e `failed_requirements` da policy;
- sugestões/recomendações reconciliadas e suporte global;
- campos submetíveis/validações de decisão;
- transição FSM, destino e agendamento.

O presenter exibirá copy explícita: “Possível infecção sistêmica — revisar evidências; informação consultiva, não altera a sugestão automática.” Ausência/falha de extração produz seção vazia/neutra, nunca pendência.

### D9. Combobox será progressive enhancement de um `<select>` canônico

Criar `static/js/procedure_combobox.js` desacoplado das views. O HTML SSR renderiza `<select name="exam_type">` (ou o campo médico correspondente) com option values canônicos e aliases em `data-search-aliases`. Sem JS, o select permanece visível e funcional. Com JS, o script:

- mantém o `<select>` como valor autoritativo submetido;
- cria input com `role="combobox"`, `aria-expanded`, `aria-controls`, `aria-autocomplete="list"` e `aria-activedescendant`;
- cria listbox/options com ids estáveis;
- normaliza busca com `String.normalize("NFD")`, remoção de marcas e lowercase;
- implementa ArrowDown/ArrowUp/Home/End/Enter/Escape/Tab, clique fora e sincronização em re-render;
- não aceita texto livre: somente seleção de option atualiza o select.

O componente usa classes `procedure-combobox*` definidas em `static/css/app.css`, com foco visível e estados de erro. Cada template carrega o JS uma vez. `upload.js` deixa de consultar radios e passa a observar `select[name="exam_type"]`.

Na decisão médica, o catálogo continua gerando decisões das rows detectadas; o combobox serve à ação de incluir/substituir destino, evitando renderizar dez radios de destino. A validação final permanece no `DoctorDecisionForm`.

**Alternativa rejeitada:** `<input list>`; suporte/semântica visual e controle de opção ativa são inconsistentes e não permitem o contrato completo de listbox.

### D10. Intake/correção compartilham chaves de seleção do catálogo

Um helper devolve opções disponíveis por jornada:

- todos os novos pacotes/Retossigmoidoscopias disponíveis no cutover;
- EDA sempre conforme regra atual;
- Colonoscopia e `eda_colonoscopy` obedecem `COLONOSCOPY_INTAKE_ENABLED`;
- Ecoendoscopia/CPRE obedecem suas flags preexistentes;
- médico vê todas as identidades, pois flags de intake não limitam substituição.

O POST converte uma chave por `procedure_types_for_selection()`; aliases e labels nunca são valores válidos. Upload e reenvio criam rows pela mesma função transacional. Correção mantém UUID/documentos, invalida derivados e agenda uma análise 4.0.

### D11. Histórico e detalhes usam código exato

A consulta de prior case receberá o `procedure_type` original e filtrará igualdade na row. Não haverá fallback por `profile_key`, prefixo (`eda_*`) ou família. O presenter terá uma seção por row detectada; para pacote há somente uma seção. Troca médica para destino não analisado não sintetiza detalhe de dilatação nem revisão GTT e não reroda pipeline.

### D12. Filas, follow-up e analytics consomem opções derivadas

Views projetarão `procedure_filter_options` e mapas de contagem a partir das selection keys válidas, adicionando `all`/`none` conforme contexto. Templates iteram opções em vez de repetir radios. Os scripts de filtro inicializam contagens dinamicamente pelos `data-*`, sem objetos literais de quatro tipos.

Predicado de singleton exige conjunto exato daquela dimensão; `eda_colonoscopy` exige igualdade com o par. Follow-up mantém uma row por `CaseProcedure` autorizado e ganha labels automaticamente pelo catálogo.

Analytics manterá:

- categoria exclusiva case-level = selection key do conjunto exato;
- volume por componente = contagem por código atômico;
- `paired_confirmed` = caso autorizado exatamente `{eda, colonoscopy}`.

Conjunto persistido inválido não será reduzido a singleton e deverá aparecer como erro/inconsistência testável, não como categoria inventada.

### D13. Sinais legados permanecem legíveis, mas não são writers de identidade

`priority_signals.py` conserva códigos e renderização para artefatos históricos. Para 4.0, o orchestrator excluirá `gastrostomy` e `esophageal_dilation` quando o procedimento correspondente já é atômico; cápsula e Retossigmoidoscopia não ganham sinal equivalente. O painel GTT não reutiliza badge de priority signal porque possui evidências e semântica próprias.

### D14. Cutover será único, sem flags novas

Preparação pode ocorrer em commits/slices na branch, mas a implantação só acontece quando todos os artefatos estiverem prontos. Operação:

1. confirmar migration e versões 4.0 dos quatro prompts;
2. parar ingestão brevemente e drenar `LLM_STRUCT`/`LLM_SUGGEST` 3.0;
3. aplicar migration;
4. ativar exatamente uma versão 4.0 por prompt;
5. implantar a mesma imagem em web e workers;
6. executar smoke das dez identidades e EDA + Colonoscopia;
7. reabrir ingestão.

Não adicionar settings/flags. Flags atuais continuam apenas nos procedimentos aos quais já se aplicam. Depois de qualquer write 4.0 ou row de identidade nova, rollback de imagem/writer 3.0 é proibido; parar ingestão, preservar dados e corrigir para frente.

### D15. Inventário de pressupostos fechados é gate por jornada

Executar e classificar ocorrências, sem substituir cegamente regras clínicas intencionais:

```bash
rg -n "ProcedureType\.|SUPPORTED_PROCEDURE_TYPES|SELECTABLE_PROCEDURE_TYPES|eda_colonoscopy|len\([^)]*proced|schema_version.*3\.0|llm[12]_v3|gastrostomy|esophageal_dilation" apps templates static
```

Cada ocorrência deve ser uma destas:

- consumidor genérico migrado para catálogo;
- regra clínica/família intencional documentada;
- adapter/teste histórico preservado;
- bloqueio a resolver no slice correspondente.

Expansão para permissions, FSM, novas colunas clínicas ou processamento de anexos exige escalonamento, pois não pertence a este design.

## Risks / Trade-offs

- **Catálogo central virar objeto excessivo** → limitar metadados a identidade/seleção/profile/apresentação; regras clínicas continuam em profiles/policy.
- **Schema 4.0 quebrar serviço/orchestrator** → cutover vertical com EDA/Colonoscopia primeiro, strict-schema tests e adapters 1.1/2.0/3.0.
- **LLM omitir resultado normal GTT** → prompt e fixtures positivos obrigatórios; painel nunca afirma completude diagnóstica e médico mantém relatório original ao lado.
- **Classificação clínica inventada** → sem thresholds; marcador explícito local, rebaixamento para `unclassified` e excerpt visível.
- **Pacote confundido com combinado por `+`** → lógica exclusivamente por set/código, nunca parsing de label ou `len == 2`.
- **UI acessível sem harness JS dedicado** → testes SSR/contrato do script, smoke manual de teclado/leitor no gate final e nenhuma dependência de JS para submit.
- **Número de opções degradar filas** → opções iteradas por catálogo e contadores derivados; volume atual é pequeno, sem query por opção.
- **Analytics histórico parecer incompleto** → copy de cutover e ausência deliberada de backfill; não misturar sinal legado com identidade nova.

## Migration Plan

### Preparação da branch

1. Aceitar ADR-0010 antes do primeiro slice de código.
2. Criar branch `feature/support-expanded-endoscopy-procedure-catalog`, registrar `BASE_REF` e baseline global uma vez se não houver CI verde confiável.
3. Implementar os slices em RED → GREEN → REFACTOR, um por vez, sem implantar commits intermediários.

### Implantação

1. Fazer backup operacional normal e confirmar ausência de jobs 3.0 em voo.
2. Validar que os quatro prompts 4.0 existem e exatamente uma versão de cada será ativada.
3. Pausar ingestão, drenar filas, aplicar migration de choices/`max_length` e implantar web/workers da mesma imagem.
4. Ativar prompts 4.0 e executar smoke: cada singleton; pacote com evidência/local; resultados GTT normais e preocupantes; combinado EDA + Colonoscopia; combinação proibida.
5. Confirmar filas/filtros/analytics e reabrir ingestão.

### Rollback

- Antes do primeiro write 4.0 e sem rows novas, pode-se reverter imagem/prompt após precheck e drenagem.
- Depois do primeiro write 4.0 ou primeira row nova, não reativar writer 3.0, não apagar rows e não reclassificar como EDA/Colonoscopia. Pausar ingestão e corrigir para frente.
- Não executar reverse data migration; readers 4.0 continuam aceitando versões históricas.

## Open Questions

Nenhuma decisão de domínio permanece aberta. Copy visual e labels anatômicos em português podem ser refinados sem alterar enum, matriz, regra de alerta ou breakdown de slices.

## Slice Strategy

1. **Cutover 4.0 preserva o fluxo atual:** catálogo/migration/adapters/writer 4.0 e processamento EDA/Colonoscopia até o médico.
2. **Intake pesquisável persiste pacotes EDA:** combobox SSR/JS e declaração exata das três variações, sem flags novas.
3. **Cápsula e dilatação chegam ao médico:** detecção/reconciliação/profile EDA, local ancorado e relatório consultivo.
4. **EDA + GTT oferece revisão infecciosa:** extração/ancoragem/painel com normais e alerta não bloqueante, provando invariância da policy.
5. **Retossigmoidoscopias chegam ao médico:** três identidades, aliases canônicos, profile Colonoscopia e matriz fechada.
6. **Médico decide/troca por catálogo:** combobox de destino, atomicidade, histórico exato e ausência de síntese/rerun.
7. **Jornada NIR pós-intake:** correção/reenvio, acompanhamento, resposta final, encerrados e filtros exatos.
8. **Jornada médica/CHD/follow-up:** filas, agendamento, histórico e pós-procedimento para todo o catálogo; combinado exato preservado.
9. **Jornada gerencial:** categorias exclusivas, filtros e volumes para dez identidades e combinado.
10. **Cutover e gate final:** prompts/runbook/prechecks, inventário final, smoke acessível e quality gate global único.

O Slice 001 tem footprint maior inevitável: schema strict, cliente/serviço e orchestrator não podem ficar incompatíveis no mesmo commit. Os demais são jornadas verticais por pacote ou ator. Se um slice exigir nova persistência clínica, FSM, permissão, flag ou arquivos substancialmente além do blast radius, o worker deve parar e escalar ao planner.
