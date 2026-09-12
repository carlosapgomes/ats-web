# Design: Ecoendoscopia e CPRE como procedimentos independentes

## Context

Ver [`proposal.md`](proposal.md) para motivação e [`ADR-0006`](../../../docs/adr/ADR-0006-ecoendoscopia-e-cpre-como-procedimentos-independentes.md) para as decisões de domínio.

O estado atual já fornece a base correta, mas está fechado em dois tipos:

- `CaseProcedure` preserva declaração, detecção e disposição médica;
- `ProcedureType`, `apps/cases/procedures.py`, loops de formulários/views, filtros e analytics enumeram apenas EDA/Colonoscopia;
- `selection_key()` trata qualquer conjunto de tamanho dois como `eda_colonoscopy`;
- schemas strict 2.0 limitam `requested_procedures` e recomendações a EDA/Colonoscopia;
- Ecoendoscopia ainda é subtipo de EDA e `priority_signal` persistido;
- policy atual retorna no primeiro requisito ausente;
- `tracked_exams.exam_type` é texto livre e não serve como hard rule;
- troca médica já persiste deny+approve sem rerun, mas a UI/validação não conhece os novos destinos;
- mensagens sistêmicas são projeções idempotentes de eventos e não geram `UserNotification`.

A mudança deve manter schemas 1.1/2.0 legíveis, os 18 valores atuais de `CaseStatus`, roles, locks, fluxo SSR e um único `appointment_at` por caso.

## Goals / Non-Goals

**Goals:**

- estabelecer catálogo e matriz únicos para todos os consumidores;
- introduzir contrato strict 3.0 e hard rules testáveis de imagem;
- preservar o pipeline único por caso e recomendação por procedimento;
- fazer troca médica significar `trocar e aprovar`, sem reanálise;
- projetar o autorizado e sua transformação em CHD/NIR/comunicação;
- entregar rollout independente e observável de Ecoendoscopia e CPRE.

**Non-Goals:**

- modelar salas, equipamentos, agenda por sala ou disponibilidade de executor;
- criar segundo caso/appointment ou split automático;
- processar anexos na automação clínica inicial;
- criar validade temporal para imagem;
- criar regras de preparo, suspensão medicamentosa ou indicação clínica não aprovadas;
- reclassificar/backfill de casos históricos de Ecoendoscopia;
- alterar FSM, permissões, intranet guard, roles ou frontend para SPA.

## Decisions

### D1. Catálogo, ordem e matriz ficam centralizados no domínio

`apps/cases/procedures.py` será a fonte única conceitual para:

```python
SUPPORTED_PROCEDURE_TYPES = (
    ProcedureType.EDA,
    ProcedureType.COLONOSCOPY,
    ProcedureType.ECHOENDOSCOPY,
    ProcedureType.CPRE,
)

PROCEDURE_ORDER = {type_: position for position, type_ in enumerate(SUPPORTED_PROCEDURE_TYPES)}
PAIRED_APPOINTMENT_SET = frozenset({ProcedureType.EDA, ProcedureType.COLONOSCOPY})
ALLOWED_PROCEDURE_SETS = frozenset(
    {
        frozenset({ProcedureType.EDA}),
        frozenset({ProcedureType.COLONOSCOPY}),
        PAIRED_APPOINTMENT_SET,
        frozenset({ProcedureType.ECHOENDOSCOPY}),
        frozenset({ProcedureType.CPRE}),
    }
)
```

Helpers públicos validarão conjunto declarado/detectado/autorizado, ordenarão tipos, gerarão `selection_key` e identificarão agendamento casado. `selection_key` usará igualdade exata com `PAIRED_APPOINTMENT_SET`; `len(types) == 2` é proibido como regra de domínio.

Duplicações em `doctor/reporting.py`, `procedure_reconciliation.py`, orchestrator, forms/views, scheduler e analytics serão removidas progressivamente. Templates receberão chaves/labels projetados pela view e não consultarão ORM implicitamente.

`ProcedureType` ganhará `ECHOENDOSCOPY="echoendoscopy"` e `CPRE="cpre"`. `max_length=20` já comporta ambos. Uma migration `AlterField` manterá o estado de migrations alinhado às choices; não haverá data migration nem backfill.

**Alternativa rejeitada:** adicionar condicionais locais em cada app. Isso preservaria os atuais pressupostos binários e permitiria matrizes divergentes.

### D2. A matriz protege cada fronteira, com tratamento específico por etapa

- **Intake/reenvio/correção:** POST inválido é rejeitado antes de criar/alterar rows.
- **LLM1:** aceita coleção única de até quatro tipos para não transformar resposta incompatível em erro de parse opaco.
- **Reconciliação:** valida todos os valores antes de ordenar/filtrar, aplica precedência especializada, valida a matriz e envia tipos desconhecidos ou conjuntos incompatíveis ao NIR com motivo explícito. Nenhum valor desconhecido pode ser descartado para fazer o restante parecer válido.
- **Médico:** valida o conjunto aprovado final dentro da transação; conjunto incompatível não persiste rows/evento/FSM.
- **CHD/analytics:** `is_paired_appointment_set()` define exclusivamente EDA + Colonoscopia.

O upgrade automático permanece somente:

```text
{eda} ou {colonoscopy} declarado + {eda, colonoscopy} detectado com evidência forte
→ upgrade detectado auditado
```

Qualquer mismatch envolvendo Ecoendoscopia/CPRE retorna ao NIR. Não há conversão automática de EDA para especializado.

### D3. Precedência especializada ocorre antes da matriz declarado×detectado

A resposta bruta e o detector textual preservarão evidências por ocorrência. O contrato entre detecção e reconciliação deixará de transportar apenas conjuntos `strong/any`: cada ocorrência relevante levará `procedure_type`, qualificação (`current_request|historical|negated|mention`), trecho/evidence id e vínculo textual com EDA quando houver `com/e`. Assim, a reconciliação diferencia uma expressão composta que deve colapsar de solicitações independentes incompatíveis; ela não infere precedência a partir do conjunto isolado.

A reconciliação colapsará exatamente:

```text
{eda, echoendoscopy} → {echoendoscopy}
{eda, cpre}          → {cpre}
```

quando a solicitação atual expressar `EDA com/e ...`. Conjuntos que também contenham Colonoscopia ou os dois especializados não são colapsados e seguem como combinação incompatível.

A regra existirá no prompt e em código. Prompt reduz erro; reconciliação é autoridade.

### D4. Flags especializadas são independentes e web-only

Adicionar settings booleanos, false por padrão:

```text
ECHOENDOSCOPY_INTAKE_ENABLED
CPRE_INTAKE_ENABLED
```

Upload, correção e reenvio ocultam e rejeitam a opção desativada. Workers, médico e CHD não consultam as flags: caso existente sempre conclui, e o médico pode trocar para qualquer tipo suportado mesmo que sua flag de intake esteja desligada.

Se o pipeline detectar procedimento especializado diferente do declarado enquanto a flag está desligada, o caso fica em revisão NIR; não há fallback silencioso para EDA. Operação decide manter o caso aguardando habilitação ou tratá-lo fora do ATS.

### D5. Contrato strict 3.0 substitui 2.0 somente para novos writes

Criar `llm1_v3.py` e `llm2_v3.py`, sem editar a semântica fechada dos modelos 2.0. Adapters/presenters leem 1.1/2.0/3.0 e nunca reescrevem JSON histórico.

`Llm1ResponseV3` mantém história/pré-operatório comuns e adiciona quatro variantes discriminadas de procedimento. Ecoendoscopia não é subtipo EDA em 3.0. A lista é única, possui evidence spans e aceita até quatro itens brutos; a matriz é responsabilidade da reconciliação, que consegue então distinguir mismatch de combinação não suportada.

`Llm2ResponseV3` aceita os quatro tipos e exige igualdade exata com o conjunto reconciliado. Preservar retry corretivo único para mismatch schema-válido, retry de idioma finito e normalização strict `oneOf → anyOf` já existente.

Os quatro nomes administráveis continuam:

```text
exam_llm1_system
exam_llm1_user
exam_llm2_system
exam_llm2_user
```

O seed cria versões 3.0 idempotentes. Cutover ativa exatamente uma versão 3.0 por nome e desativa 2.0 após drenagem; histórico de prompts não é apagado.

### D6. Evidência abdominal separa modalidade, anatomia e achado

Adicionar a `common_preop` coleção tipada conceitual:

```python
class AbdominalImagingEvidenceV3(StrictModel):
    modality: Literal["ultrasound", "ct", "mri", "mrcp", "other"]
    anatomical_site: Literal[
        "abdomen", "upper_abdomen", "hepatobiliary", "unspecified", "other"
    ]
    report_finding_present: Literal["yes", "no", "unknown"]
    source_document: Literal["main_report"]
    evidence_context_excerpt: str
    finding_excerpt: str | None
    exam_datetime_iso: str | None
```

Validator de schema exige ambos os excerpts não vazios quando `report_finding_present="yes"`, mas nenhum valor declarado pelo LLM basta para uma hard rule. Antes da policy, um verificador determinístico recebe exclusivamente `Case.extracted_text` do relatório principal e valida, em ordem:

1. `evidence_context_excerpt` corresponde a trecho real após normalização conservadora de Unicode, caixa e espaços; `finding_excerpt` é substring desse contexto;
2. modalidade e anatomia são **derivadas novamente** do mesmo contexto por aliases versionados e devem coincidir com os enums declarados;
3. o contexto é uma única oração/entrada de laudo e contém predicado positivo versionado de resultado (`demonstrou`, `evidenciou`, `identificou`, `revelou` ou equivalente explicitamente testado), ou está sob heading de linha reconhecido por forma estrita como `Conclusão:`, `Achados:`, `Laudo:` ou `Resultado:`; os substantivos isolados `laudo`, `resultado` e `achado` nunca são marcadores positivos;
4. qualquer marcador de intenção/estado futuro na mesma oração (`solicita`, `pedido`, `agendado`, `aguarda`, `programado`, `indicado`, `a realizar`) rejeita a evidência, mesmo se a oração também contém as palavras `laudo` ou `resultado`; um resultado concluído só pode qualificar em outra oração/entrada inequívoca;
5. mais de uma ocorrência normalizada do contexto, aliases conflitantes de modalidade/anatomia, mais de uma imagem distinta no contexto ou impossibilidade de delimitar uma única oração/entrada tornam a evidência ambígua e a rejeitam fail-closed.

Não usar fuzzy match que acrescente/remova palavras clínicas, nem confiar em `report_finding_present` para reclassificar a oração. Negativos obrigatórios incluem `solicita TC de abdome`, `solicita laudo de TC de abdome`, `laudo de TC agendado`, mera menção sem predicado/heading, contexto duplicado, contexto amplo com imagens distintas e aliases conflitantes. Um trecho real não relacionado não pode ancorar modalidade/anatomia inventadas. Evidência rejeitada produz pendência/deny; não causa aceite nem é silenciosamente descartada do relatório de falhas.

A policy recebe somente evidência verificada e exige modalidade e anatomia aceitas; `unspecified|other` nunca satisfaz. CPRM/colangiorressonância é normalizada como `mrcp` com sítio hepatobiliar. O payload passado à policy identifica que a origem verificada é o relatório principal. Os aliases/marcadores ficam centralizados junto ao verificador, não duplicados em prompt e policy.

`tracked_exams` permanece disponível para apresentação histórica/recência, mas não participa da hard rule. Apenas `Case.extracted_text` do PDF principal alimenta LLM1/verificador; textos de `CaseAttachment` não são concatenados, consultados nem enviados. A data é persistida quando disponível e ignorada para aceite/negativa.

### D7. Perfis declarativos contêm somente diferenças clínicas aprovadas

`ExamProfile` receberá requisito opcional de imagem, sem se transformar em engine genérica. Perfis:

| Procedimento | Exceção corpo estranho | Imagem adicional aceita |
| --- | --- | --- |
| EDA | sim | nenhuma |
| Colonoscopia | não | nenhuma |
| Ecoendoscopia | não | CT/MRI × abdome/abdome superior |
| CPRE | não | US × abdome/abdome superior/hepatobiliar; CT/MRI × abdome/abdome superior; MRCP hepatobiliar |

Nos perfis novos, `pediatric` é o único sinal prioritário legado projetado por padrão. `echoendoscopy` deixa de ser sinal em artefatos 3.0; sinais EDA específicos como corpo estranho, dilatação e gastrostomia não são herdados. Não será criada regra nova de sinalização cáustica para procedimentos especializados.

### D8. Policy agrega falhas sem romper consumidores legados

A avaliação deixará de retornar na primeira falha, exceto pelo bypass exclusivo de corpo estranho em EDA. Ela coletará em ordem estável:

1. exames mínimos ausentes;
2. thresholds não atendidos;
3. exames condicionais ausentes;
4. imagem especializada ausente/insuficiente.

Formato aditivo:

```json
{
  "decision": "deny",
  "reason_code": "<primeiro código>",
  "reason_text": "<resumo determinístico>",
  "failed_requirements": [
    {"code": "...", "label": "...", "category": "minimum|threshold|conditional|imaging"}
  ],
  "evidence_spans": [],
  "pediatric_flag": false
}
```

`reason_code` primário e códigos atuais permanecem para compatibilidade com presenter, correção NIR e dashboard. O relatório e o prompt LLM2 usam `failed_requirements[]`. A reconciliação 3.0 força `suggestion="deny"` sempre que `decision="deny"`, independentemente de o LLM2 afirmar alinhamento.

Códigos de imagem serão específicos e estáveis, distinguindo ausência de modalidade aceita, localização não aceita e ausência de conclusão/achado. Todos podem orientar correção documental do NIR, mas não bloqueiam decisão médica.

### D9. O relatório deixa explícito o limite dos anexos

Para casos 3.0, o relatório mostra:

- sugestão por procedimento;
- todas as pendências da policy em uma lista;
- evidências extraídas do relatório principal;
- aviso: anexos disponíveis na tela não participaram da sugestão automática.

O aviso não afirma que o anexo é inválido clinicamente; apenas descreve o limite técnico. O médico pode consultá-lo e decidir de forma divergente.

### D10. Troca médica é uma ação explícita de aprovação

Para caso detectado simples, a UI oferecerá uma ação semanticamente explícita:

```text
Manter e aprovar | Negar | Trocar e aprovar como <procedimento>
```

Uma troca exige justificativa, que é persistida nas rows original/destino conforme o contrato de auditoria. O serviço converte a ação para decisões atômicas:

```text
origem → denied
destino → approved + added_by_doctor
```

Não chamar LLM1, LLM2, orchestrator, fila Q nem `evaluate_preop_policy` no GET/POST da troca. Não renderizar sugestão/checklist do destino. A única validação clínica automatizada exibida continua sendo a produzida antes da avaliação para o conjunto detectado.

Casos detectados como EDA + Colonoscopia preservam decisão por componente. Eles podem:

- aprovar ambos;
- reduzir a um por negativa do outro;
- negar ambos;
- substituir integralmente por um único procedimento permitido.

É bloqueado manter um componente e adicionar Ecoendoscopia/CPRE, pois o conjunto final seria incompatível. Não existe split.

### D11. Evento dedicado evita ruído na comunicação

`DOCTOR_PROCEDURE_DECISIONS_RECORDED` continua registrando toda decisão. Quando `approved_set != detected_set`, o mesmo serviço/transação cria adicionalmente:

```text
DOCTOR_PROCEDURE_SET_CHANGED
```

Payload mínimo:

```json
{
  "detected": ["eda"],
  "approved": ["cpre"],
  "reason_present": true
}
```

A razão autoritativa permanece em `CaseProcedure.doctor_reason`; se o texto for incluído no payload/mensagem conforme padrão existente, será limitado e não copiará conteúdo do PDF.

O evento entra em `SUPPORTED_SYSTEM_NOTICE_EVENT_TYPES`. Seu formatter projeta uma mensagem como `Procedimento autorizado alterado pelo médico: EDA → CPRE. Motivo registrado na decisão médica.` `source_event` garante idempotência. A projeção não chama o serviço de mensagem manual, não cria outro evento e não cria `UserNotification`.

### D12. CHD e NIR projetam o autorizado e a transformação

Helpers de card/detalhe usarão dimensões explícitas:

- NIR operacional: declarado;
- médico pendente: detectado;
- médico decidido/CHD: autorizado;
- resposta final NIR: declarado + detectado + autorizado + razões.

Quando houver diferença, texto acessível acompanha o badge principal. Ecoendoscopia/CPRE nunca recebem sufixo de agendamento casado. CHD continua com um único formulário/data/hora/localização e não altera procedimentos.

Todos os fluxos de admissão existentes são aceitos. `appointment_location` continua texto livre; não haverá validação por sala.

### D13. Filtros e analytics tornam-se orientados ao catálogo

Filtros válidos:

```text
all | eda | colonoscopy | eda_colonoscopy | echoendoscopy | cpre
```

`none` permanece apenas em dimensões/universos que contêm negativa integral. Predicados de singleton exigem presença do tipo e ausência dos demais; combinado exige exatamente EDA+Colonoscopia. Analytics separa categoria exclusiva de caso de volume por `CaseProcedure` e mantém agendamento casado como contagem case-level.

Follow-up já grava uma row por `CaseProcedure`; será validado para labels e formulários dos novos tipos, sem mudar o modelo ou a semântica de desfecho.

### D14. Compatibilidade do sinal histórico é por versão

Leitura 1.1/2.0 continua exibindo `echoendoscopy` como subtipo/sinal legado. Novos artefatos 3.0 persistem Ecoendoscopia apenas como `CaseProcedure`; o resolvedor não adiciona o mesmo código de sinal para esses casos.

Não há backfill. Um caso antigo aberto pode ser trocado/aprovado como Ecoendoscopia pelo médico usando a ação normal, mas o sistema não sugere nem executa essa transformação automaticamente.

### D15. Inventário de pressupostos binários é gate do change

Antes de concluir os slices operacionais, executar inventário ao menos para:

```bash
rg -n "ProcedureType\.(EDA|COLONOSCOPY)|len\([^)]*proced|_PROCEDURE_ORDER|_PROCEDURE_TYPES|eda_colonoscopy" apps templates static
```

Cada ocorrência deve ser classificada como:

- catálogo genérico migrado;
- regra intencional exclusiva de EDA/Colonoscopia;
- adapter histórico preservado;
- dívida bloqueante a corrigir no slice correspondente.

Em especial, remover lógica binária `other = COLONOSCOPY if dimension == EDA else EDA` e `len == 2` em scheduler/analytics.

## Risks / Trade-offs

- **Contrato 3.0 divergir dos leitores atuais** → adapters explícitos e testes 1.1/2.0/3.0 antes do cutover.
- **Resposta LLM incompatível virar caso parcial** → schemas strict, coleção única, matriz e persistência transacional.
- **LLM inventar imagem/achado, rotular solicitação como resultado ou usar anexo** → contexto/finding ancorados, modalidade/anatomia rederivadas, heading/predicado positivo estrito, intenção dominante e ambiguidade fail-closed; testes cobrem solicitação com/sem `laudo`, agendamento, menção, conflito, duplicidade, contexto amplo, mismatch e anexo-only.
- **Agregação mudar motivo primário** → contrato aditivo com ordem estável e regressão dos consumidores de `reason_code`.
- **Troca disparar automação por engano** → testes que espiam fila, orchestrator e policy; ação explícita `trocar e aprovar`.
- **Mensagem sistêmica virar inbox** → evento dedicado, projector idempotente e teste de zero `UserNotification`.
- **Ecoendoscopia duplicada como sinal/procedimento** → comportamento condicionado à versão; sem backfill.
- **Flag desligada deixar mismatch em revisão** → copy operacional explícita; nenhum downgrade silencioso do procedimento.
- **Imagem antiga quebrar com novas rows** → flags false por padrão e fix-forward como rollback suportado.
- **Blast radius exceder o previsto** → inventário por slice e escalonamento antes de ampliar expected files/cap.

## Migration Plan

### Preparação

1. Criar branch de implementação e registrar `BASE_REF` com working tree limpa.
2. Executar baseline global uma vez se não houver CI verde confiável do HEAD.
3. Aplicar migration de choices e código de catálogo com flags false.
4. Instalar schemas/adapters/policies 3.0 ainda sem intake especializado.
5. Semear versões 3.0 dos quatro prompts, mantendo-as inativas.

### Cutover 3.0

1. Parar/drenar jobs em `LLM_STRUCT`/`LLM_SUGGEST`.
2. Validar strict schemas localmente e presença de exatamente uma versão 3.0 candidata por prompt.
3. Ativar versões 3.0 e desativar 2.0 em operação serializada.
4. Subir workers/web da mesma imagem e executar smoke EDA/Colonoscopia com flags especializadas false.

### Rollout Ecoendoscopia

1. Ativar `ECHOENDOSCOPY_INTAKE_ENABLED=true`; manter CPRE false.
2. Executar smoke de declaração, detecção, policy negativa/positiva, decisão, troca, CHD/NIR e mensagem sistêmica.
3. Monitorar mismatches, falhas schema, negativas por imagem e tempos do pipeline durante a janela piloto.

### Rollout CPRE

1. Após aceite humano do piloto de Ecoendoscopia, ativar `CPRE_INTAKE_ENABLED=true`.
2. Executar smoke equivalente incluindo USG hepatobiliar, CPRM, imagem sem sítio e sem achado.
3. Manter capacidade de desligar cada flag independentemente.

### Rollback

- **Antes do cutover e sem qualquer write/job 3.0:** é possível manter/reativar prompts 2.0 e retornar à imagem anterior após drenagem e prechecks de ausência.
- **Após o primeiro write 3.0, mesmo de EDA/Colonoscopia, ou após a primeira row especializada:** desligar flags, preservar imagem/schema 3.0, drenar jobs e corrigir para frente. Não reativar writer 2.0, remover rows, reclassificar como EDA nem usar reverse migration destrutiva.

Prechecks de downgrade antigo devem falhar se existir qualquer `CaseProcedure` Ecoendoscopia/CPRE, artefato `schema_version="3.0"`, evento especializado ou job 3.0 em voo. A fronteira é o cutover do writer, não a ativação posterior das flags de intake.

## Open Questions

Nenhuma questão de domínio permanece aberta para iniciar os slices. Copy final de labels/mensagens pode ser refinada no slice sem alterar semântica, matriz ou task breakdown.

## Slice Strategy

Todos os slices entregam um fluxo observável por ator; não haverá slice horizontal exclusivo de model/schema/policy.

1. **Cutover vertical EDA/Colonoscopia:** expande catálogo/matriz, introduz contrato/policy 3.0 e prova um processamento atual completo até o médico sem regressão, com flags especializadas desligadas. O blast radius maior é inevitável para manter o repositório executável no mesmo slice.
2. **Ecoendoscopia NIR → médico:** seleção, proveniência por ocorrência, precedência, policy e relatório médico.
3. **Ecoendoscopia médico → CHD/NIR:** aprovação/troca, agenda/fluxo, transformação auditável e mensagem sistêmica.
4. **CPRE ponta a ponta:** reutiliza a infraestrutura aprovada e entrega NIR → pipeline → médico → CHD/NIR, incluindo troca.
5. **Jornada médica nas filas:** Pendentes e Decididos Hoje com filtros/badges especializados e transformação visível.
6. **Jornada CHD e pós-procedimento:** filas, agendamento/histórico e follow-up por procedimento especializado.
7. **Jornada NIR após intake:** acompanhamento, correção, encerrados e filtros especializados.
8. **Jornada gerencial:** breakdown, tabela e volumes dimensionais para os quatro tipos.
9. **Operação e rollout:** documentação, prechecks, smoke Eco antes de CPRE, rollback e gate global.

O Slice 001 é vertical apesar do footprint alto: o cutover de um strict writer não pode ser dividido deixando schema, serviço e orchestrator incompatíveis entre commits. Se o inventário superar o cap declarado, o implementador deve parar e o planner deve redesenhar antes de qualquer edição extra. Os Slices 005–008 substituem o antigo fechamento horizontal por jornadas independentes de médico, CHD, NIR e gestor.
