# Design: Procedimentos múltiplos e pipeline LLM procedure-neutral

## 1. Estado atual verificado

### 1.1 Fonte única e solicitação mista

`apps/cases/models.py::Case.exam_type` aceita `eda|colonoscopy` e é usado como declaração, dispatch de prompt/profile, filtro e badge downstream. `apps/pipeline/scope_detection.py` já distingue duas solicitações atuais, mas sempre retorna `mixed_exam_request` e orienta separação.

### 1.2 Contratos LLM e prompts

LLM1 schema 1.1 mantém história clínica e procedimento dentro do envelope legado `eda`; `preop_screening.exam_type` é singular. LLM2 produz uma única recomendação. Quatro prompts EDA e quatro Colonoscopia são administrados separadamente. Rodar ambos os pares sobre o mesmo PDF duplicaria paciente, história e recomendação, exigindo merge não auditável.

### 1.3 Médico e CHD

`DoctorDecisionForm` persiste uma decisão global `accept|deny`, razão global de negativa e um suporte/admission flow. O CHD confirma um único `appointment_at`, o que já representa corretamente uma agenda casada, mas cards/filtros usam `Case.exam_type` original.

### 1.4 Auditoria, correção e analytics

`CaseEvent` é append-only e fonte histórica. Correção NIR troca `exam_type` somente antes do médico, invalida derivados e reprocessa. Dashboard e filas assumem duas categorias exclusivas cujo fechamento é igual ao total de casos.

## 2. Invariantes do novo domínio

1. Um PDF cria exatamente um `Case`.
2. Um caso possui no máximo os procedimentos EDA e Colonoscopia, uma ocorrência de cada.
3. Um caso combinado nunca cria segundo caso ou segundo horário.
4. Declaração NIR, detecção da análise e disposição médica são fatos diferentes.
5. LLM não altera a declaração e médico não altera a detecção; cada ator grava sua dimensão.
6. Médico pode autorizar procedimento não detectado, mas precisa justificar e não reexecuta LLM.
7. CHD agenda somente procedimentos aprovados e não altera o conjunto.
8. Histórico é append-only via eventos; models guardam a projeção operacional atual.
9. Novos artefatos usam schema 2.0; históricos 1.1 são lidos, não reescritos.
10. Os 17 estados FSM permanecem.

## 3. Decisões arquiteturais

### D1. `CaseProcedure` normaliza componentes do caso

Introduzir estrutura conceitual mínima:

```python
class ProcedureType(models.TextChoices):
    EDA = "eda", "EDA"
    COLONOSCOPY = "colonoscopy", "Colonoscopia"

class DetectionStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    DETECTED = "detected", "Detectado"
    NOT_DETECTED = "not_detected", "Não detectado"

class DoctorDisposition(models.TextChoices):
    PENDING = "pending", "Pendente"
    APPROVED = "approved", "Aprovado"
    DENIED = "denied", "Negado"

class CaseProcedure(models.Model):
    case = models.ForeignKey(Case, related_name="procedures", ...)
    procedure_type = models.CharField(choices=ProcedureType.choices, ...)
    declared_by_nir = models.BooleanField(default=False)
    detection_status = models.CharField(choices=DetectionStatus.choices, default="pending")
    doctor_disposition = models.CharField(choices=DoctorDisposition.choices, default="pending")
    doctor_reason = models.TextField(blank=True)

    class Meta:
        constraints = [UniqueConstraint(fields=["case", "procedure_type"], ...)]
```

Não adicionar row genérica `combined`: combinação é o conjunto das duas rows. Não adicionar CPRE. Não duplicar `doctor`, timestamps e support em cada row: ator/instante global continuam no `Case`/eventos, e razão é o único dado verdadeiramente por componente.

Rows podem permanecer com flags false/pending para preservar projeção de uma transformação; eventos preservam a história integral. Helpers de domínio retornam conjuntos ordenados e labels, evitando lógica de combinação espalhada.

### D2. Ponte transitória de `Case.exam_type`

Remover a coluna no Slice 001 quebraria todos os consumidores e criaria um slice horizontal enorme. Portanto:

1. Slice 001 cria/backfilla `CaseProcedure` e mantém `Case.exam_type` como ponte interna temporária;
2. writes de intake/correção usam serviço único que atualiza projeção e ponte;
3. combinação pode usar valor transitório explícito `eda_colonoscopy`, somente para compatibilidade durante a branch;
4. flag de Colonoscopia permanece falsa e a branch não é deployável até o cutover;
5. Slices 002–006 migram todos os readers para helpers/querysets da projeção;
6. Slice 007 prova ausência de readers/writers e remove `Case.exam_type`/dispatch dependente.

Dual-write fora do serviço central é proibido. `CaseProcedure` é a fonte alvo desde o início; a ponte existe apenas para manter cada slice verde.

### D3. Migration preserva dados sem inferência

Backfill cria uma row declarada correspondente ao `exam_type` atual. Para casos já decididos:

- `doctor_decision=accept` ou downstream: disposição correspondente pode ser `approved` somente quando a semântica anterior é inequívoca;
- `doctor_decision=deny`: `denied` com `doctor_reason` existente;
- antes da decisão: `pending`.

Detecção histórica não deve ser inferida de texto clínico nem de heurística nova. Para casos que já alcançaram `WAIT_DOCTOR` ou estado posterior após o scope gate, a seleção operacional antiga é evidência inequívoca de match e pode ser projetada como detectada; casos anteriores ao gate ou em manual review permanecem `pending`, salvo payload/evento estruturado inequívoco já persistido. A regra exata deve ser codificada por grupos de status e testada na migration. Nenhum JSON, evento, status, PDF ou agenda é alterado. Produção não exige reset.

### D4. API de domínio centraliza conjuntos

Criar helpers/serviço coeso, sem God object:

```text
set_declared_procedures(case, types, actor)
set_detected_procedures(case, types, evidence_codes)
record_doctor_procedure_decisions(case, decisions, actor)
get_declared_procedure_types(case)
get_detected_procedure_types(case)
get_approved_procedure_types(case)
format_procedure_selection(types)
```

Writes críticos usam `transaction.atomic()` e row lock no `Case`. Queries de fila usam `Exists`/annotations ou QuerySet dedicado, sempre com `distinct` consciente. Templates nunca montam conjuntos consultando ORM implicitamente.

### D5. LLM1 v2 extrai uma história comum

Criar schema 2.0 procedure-neutral para novos processamentos:

```text
Llm1ResponseV2
├── patient
├── common_preop
│   ├── labs/ecg/asa/cardiovascular risk
│   ├── comorbidities
│   └── medications
├── requested_procedures[]
│   ├── procedure_type
│   ├── indication/subtype tipado por procedimento
│   └── evidence_spans limitados
├── policy_precheck/common evidence
├── summary
├── origin_context/transfusion/tracked_exams
└── extraction_quality
```

Usar união discriminada ou validators explícitos para impedir subtype EDA em Colonoscopia. Uma chamada LLM1 recebe a declaração como contexto, mas deve extrair o que o documento sustenta. O conjunto não pode ter duplicatas e só aceita EDA/Colonoscopia.

Presenters/adapters detectam `schema_version`; 1.1 continua legível. Não criar migration de JSON.

### D6. Quatro prompts neutros substituem oito dispatches

Novos nomes canônicos:

```text
exam_llm1_system
exam_llm1_user
exam_llm2_system
exam_llm2_user
```

Prompts descrevem história comum e coleção de procedimentos. Regras determinísticas/thresholds permanecem em código; prompt não vira rule engine. Seed/admin/fallback usam conteúdo equivalente e idempotente. Prompts antigos permanecem no banco, inicialmente ativos se necessário para rollback, e são desativados somente após drenagem/cutover comprovados. Não deletar histórico de versões.

### D7. Reconciliação de detecção é conservadora

Separar detecção de solicitação atual da produção do payload manual. Reutilizar proveniência por ocorrência já endurecida.

Matriz:

| Declarado | Detectado | Ação |
| --- | --- | --- |
| EDA | EDA | prossegue |
| Colon | Colon | prossegue |
| Ambos | Ambos | prossegue |
| EDA | Ambos | upgrade automático; prossegue |
| Colon | Ambos | upgrade automático; prossegue |
| Ambos | EDA ou Colon | revisão NIR |
| EDA | Colon | revisão NIR |
| Colon | EDA | revisão NIR |
| Qualquer | unknown/non-supported | revisão NIR |

Upgrade exige evidência forte de duas solicitações atuais; uma afirmação LLM sem span/proveniência suficiente não basta. Referência histórica/negação nunca adiciona componente. Evento `PROCEDURE_SELECTION_AUTO_UPGRADED` contém somente códigos, conjuntos e ids/versões, sem texto integral.

### D8. Policy roda por componente; LLM2 roda uma vez

Para cada procedimento detectado:

```python
evaluate_preop_policy(structured_data=common_data, procedure_type=type)
```

EDA mantém exceção de corpo estranho; Colonoscopia nunca recebe essa exceção. LLM2 v2 recebe o conjunto exato de resultados e devolve um item por procedimento. Validator exige igualdade de conjuntos, sem omissão, duplicata ou adição.

Sugestão global de suporte usa ordenação explícita:

```text
none < anesthesist < anesthesist_icu
```

É recomendação; médico escolhe valor final. Não automatizar decisão médica.

### D9. Decisão médica é por componente e atômica

O form apresenta EDA e Colonoscopia com estado de origem (`declarado`, `detectado`, `não detectado`) e disposição `approved|denied` quando aplicável. Regras:

- todo procedimento detectado recebe disposição;
- negado exige razão própria;
- aprovado sem ter sido detectado exige razão de inclusão própria;
- troca completa exige razão em ambas as rows afetadas;
- pelo menos um aprovado → `Case.doctor_decision=accept` e fluxo aceito atual;
- zero aprovados → `deny` e fluxo negado atual;
- não executar LLM ao adicionar;
- `doctor_reason` global pode ser apresentação derivada/compatibilidade, mas razões autoritativas são por row;
- lock, role e transição FSM atuais são validados antes de qualquer write.

Evento `DOCTOR_PROCEDURE_DECISIONS_RECORDED` inclui lista de `{procedure_type, disposition, reason_present, added_by_doctor}`; texto completo da razão permanece nos campos/evento apropriado conforme política atual de auditoria, sem dados do PDF.

### D10. Históricos anteriores são consultados por procedimento

`lookup_prior_case_context` evolui para receber `procedure_type`. Caso combinado executa duas consultas lógicas e renderiza seções EDA/Colonoscopia. Se o mesmo caso anterior combinado servir aos dois componentes, a UI pode identificá-lo uma vez visualmente, mas cada seção deve manter sua decisão por componente. Não usar igualdade de uma combinação inteira.

### D11. CHD agenda o conjunto aprovado uma vez

Fila e detalhe CHD usam apenas `approved`:

- um aprovado → label simples;
- ambos aprovados → `EDA + Colonoscopia · Agendamento casado`;
- comparação detectado → autorizado sempre que divergir;
- `SchedulerDecisionForm` continua com uma data/hora/local;
- submit gera uma única transição e um único `appointment_at`;
- CHD não edita conjunto; impedimento operacional usa comunicação/intercorrência existente;
- evento de confirmação inclui snapshot de tipos aprovados.

### D12. NIR corrige declaração e recebe comparação final

Correção segura passa a alterar `declared_by_nir` sob lock, zerar `detection_status`/disposições pendentes e invalidar artefatos v2. Preserva PDF/anexos/texto e enfileira uma análise, sem reextração. Continua proibida em `WAIT_DOCTOR` ou posterior.

Upgrade automático não mostra CTA obrigatório. Manual review é usado para combined→single, mismatch único e unknown. Reenvio corrigido não herda rows e aceita as três seleções.

Resposta final apresenta:

```text
Solicitado pelo NIR
Detectado na análise
Decisão médica por procedimento + razões
Conjunto encaminhado ao CHD / resultado de agenda
```

### D13. Cada fila usa uma dimensão explícita

- NIR operacional/encerrados: declarado;
- médico Pendentes: detectado;
- médico Decididos Hoje: autorizado/nenhum;
- CHD Pendentes/Processados/Histórico: autorizado;
- labels sempre textuais e acessíveis;
- opções: Todos, EDA, Colonoscopia, EDA + Colonoscopia; `Nenhum` apenas onde negativa integral pertence ao universo.

Helpers JS recebem chave de seleção já projetada no `data-*`; não inferem pela presença de texto do badge.

### D14. Analytics separa casos e procedimentos

Métricas consolidadas continuam case-level. Breakdown por dimensão classifica cada caso em categoria exclusiva:

```text
eda | colonoscopy | eda_colonoscopy | none
```

Volume por procedimento conta componentes e não promete fechar com casos. Agendamento casado conta uma vez quando ambos aprovados e appointment confirmado. Matriz de conversão usa conjuntos ordenados declarado→detectado→autorizado. Query helpers centralizam predicates para evitar fórmulas divergentes.

### D15. Feature flag permanece web-only

`COLONOSCOPY_INTAKE_ENABLED=false` remove/bloqueia Colonoscopia e EDA + Colonoscopia no intake e reenvio. Workers/pipeline/médico/CHD não consultam a flag. Casos existentes sempre concluem.

### D16. FSM, permissões e segurança não mudam

Nenhum estado, role ou endpoint público novo é necessário além de submits SSR existentes/adaptados. Writes de procedimentos exigem os mesmos decorators, papel ativo, locks e ownership/contexto atuais. Redirects continuam seguros. `CaseEvent` permanece append-only.

### D17. Eventos mínimos e genéricos

Novos fatos sugeridos:

- `CASE_PROCEDURES_DECLARED`;
- `CASE_PROCEDURES_DETECTED`;
- `PROCEDURE_SELECTION_AUTO_UPGRADED`;
- `DOCTOR_PROCEDURE_DECISIONS_RECORDED`;
- `SCHEDULER_PAIRED_APPOINTMENT_CONFIRMED` (somente quando ambos);
- `CASE_PROCEDURE_DECLARATION_CORRECTED`.

Payloads usam códigos/conjuntos ordenados, ids, versões e presença de razão; não copiam texto clínico integral. Eventos legados continuam legíveis.

### D18. Cutover é obrigatório antes do rollout

Slice 007 deve:

1. provar por `rg`/testes que nenhum reader/write operacional usa `Case.exam_type`;
2. remover coluna, enum combinado transitório e adapters de dual-write;
3. tornar `CaseProcedure` única fonte operacional;
4. trocar prompts canônicos para os quatro neutros;
5. preservar adapters de leitura schema 1.1;
6. atualizar fixtures/factories sem defaults silenciosos.

Se algum consumidor residual depender do campo, Slice 007 é `INCOMPLETE`; não adiar como dívida.

### D19. Rollout e rollback

Rollout exige backup, janela controlada, imagem nova, writers parados durante migrations, quatro prompts neutros ativos e prechecks binários. Casos em `LLM_STRUCT/LLM_SUGGEST` devem ser drenados ou tratados por procedimento explícito antes do cutover; não misturar imagens old/new escrevendo schemas diferentes.

Rollback preferido: flag false e imagem nova, preservando schema novo. Voltar à imagem antiga é exceção e exige bridge executável que recrie/backfille `exam_type` de modo fail-fast a partir de `CaseProcedure`, com regra que recuse combinação ou converta somente após drenagem comprovada. Forward posterior remove novamente a ponte somente com writers antigos parados e assert binário.

### D20. ADR-0004 antes de código

Este design supera parcialmente ADR-0003: fonte única, bloqueio de mixed, envelope incremental, prompts separados, filtro único e correção de tipo. Criar/aceitar ADR-0004 antes do Slice 001. A ADR-0003 não é apagada; seu status deve indicar supersessão parcial e preservar decisões ainda válidas (profiles/policy, FSM compartilhada, flag, medicamentos).

## 4. Dimensionamento dos slices

Foram escolhidos **8 slices**. Menos juntaria intake/model/pipeline/decisão em mudanças impossíveis de revisar; mais criaria slices horizontais de schema, templates ou testes sem fluxo observável.

1. **Intake + projeção**: NIR cria e acompanha um caso combinado; ponte mantém sistema verde.
2. **Pipeline neutro**: história única, detecção/reconciliação, policy/LLM2 por componente e chegada ao médico. É o slice central e possui cap maior explicitamente.
3. **Decisão médica**: decisão/razão por componente, inclusão sem rerun, histórico e filtros médicos.
4. **CHD**: conjunto aprovado, uma agenda casada e filtros/histórico.
5. **NIR**: correção/reprocessamento, reenvio, filtros e resposta final.
6. **Analytics**: dimensões, volumes e conversões.
7. **Cutover**: remove ponte/fonte antiga e torna schema/prompts novos autoritativos.
8. **Operação**: manual/contexto/runbook/testes de contrato e rollback verificável.

A branch não é deployável entre Slices 001–006; flag deve permanecer falsa. Cada slice ainda entrega comportamento observável e testável no ambiente de desenvolvimento.

## 5. Limites globais

- Sem CPRE.
- Sem segundo caso/appointment para combinado.
- Sem duas chamadas completas por estágio LLM.
- Sem rerun por inclusão médica.
- Sem alteração de FSM/roles.
- Sem JSON rewrite histórico.
- Sem reset de produção como estratégia.
- Sem procedure engine genérica para exames desconhecidos.
- Sem DRF/SPA/framework JS.
- Sem implementar slice futuro antecipadamente.

## 6. Gates globais

Cada slice executa baseline completo e, ao final:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

Além disso:

```bash
openspec validate support-combined-eda-colonoscopy-workflow --strict
git diff --check
```

O change só pode ser arquivado após Slice 008 aprovado, ADR-0004 aceita, `Case.exam_type` removido, quatro prompts neutros documentados, migration/rollback testáveis e oito relatórios temporários revisados.
