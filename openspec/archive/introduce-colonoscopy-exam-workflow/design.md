# Design: Colonoscopia, tipo explícito e perfis pré-operatórios

## 1. Estado atual verificado

### 1.1 Case e upload

`apps/cases/models.py::Case` não possui tipo de exame. `apps/intake/services.py::process_uploaded_files` recebe somente arquivos/usuário/anexos e cria cada `Case` sem classificação operacional. O upload múltiplo em `templates/intake/intake_home.html` não solicita tipo.

O reenvio corrigido em `create_corrected_resubmission` também cria caso sem tipo. Casos históricos, operacionais, busca e dashboard não podem filtrar por procedimento.

### 1.2 Pipeline

O contrato estrito `apps/pipeline/schemas/llm1.py` usa `preop_screening.exam_type = eda | non_eda | unknown` e mantém campos clínicos sob o bloco legado `eda`. Os defaults e instruções finais de `apps/pipeline/llm1_service.py` dizem explicitamente que colonoscopia é fora do escopo.

`apps/pipeline/scope_detection.py` contém colonoscopia na lista `_SCOPE_EXPLICIT_NON_EDA_TERMS`. O orchestrator só prossegue para policy/LLM2 quando `classify_exam_scope()` retorna `None`.

A policy está dividida entre `eda_preop_policy.py`, `eda_policy.py` e `eda_recommendation_synthesis.py`, com nomes e textos EDA. A exceção de corpo estranho é aplicada por subtipo/indicação.

### 1.3 Medicamentos

O schema não possui coleção de medicamentos. A policy avalia coagulograma, mas não há extração estruturada ou alerta canônico para anticoagulante/antiagregante. Este change não receberá regra farmacológica automática.

### 1.4 Filas e busca

A fila médica possui abas primárias `Pendentes` e `Decididos Hoje`. A busca pendente é client-side e sobrevive ao polling HTMX porque fica fora de `#doctor-queue-content`.

A fila CHD possui `Pendentes`, `Processados Hoje` e busca histórica. O contador pendente soma `WAIT_APPT`, notices operacionais e issues operacionais. A busca histórica exige termo e limita resultados a 50.

O NIR possui filtros server-side em casos operacionais e busca separada de encerrados. O dashboard possui métricas por período e tabela paginada com filtros/busca dinâmica.

## 2. Decisões arquiteturais

### D1. Tipo do Case é a fonte operacional

Adicionar `ExamType` e `Case.exam_type`:

```python
class ExamType(models.TextChoices):
    EDA = "eda", "EDA"
    COLONOSCOPY = "colonoscopy", "Colonoscopia"
```

O tipo declarado pelo NIR é fonte para:

- seleção de prompt/perfil;
- validação de escopo esperado;
- filtros/contadores;
- labels e procedimento canônico;
- prior-case lookup;
- sinais permitidos.

A classificação do LLM não substitui silenciosamente `Case.exam_type`. Divergência exige ação auditável do NIR.

Migration:

1. adicionar campo com default histórico `eda`;
2. preencher todas as linhas existentes como EDA, inclusive scope-gated antigos;
3. não ler PDF/JSON/texto;
4. não reprocessar, alterar FSM, decisão, agenda ou eventos;
5. adicionar índice composto pelo menos em `status, exam_type`;
6. no estado final do modelo, novos serviços passam tipo explicitamente; compatibilidade de fixtures pode usar default EDA somente se o custo de remover o default for desproporcional e isso for documentado.

### D2. Seleção obrigatória e lote homogêneo

O formulário NIR apresenta radios sem opção marcada. O backend exige `exam_type` válido.

`process_uploaded_files` recebe um único `exam_type` para o lote. Como o tipo é único no request, o lote é homogêneo por construção. Não criar seletor por arquivo.

Quando `COLONOSCOPY_INTAKE_ENABLED` estiver falso:

- a opção colonoscopia fica indisponível/oculta com explicação;
- POST manual de `colonoscopy` é rejeitado;
- EDA continua disponível;
- casos colonoscopia já existentes continuam no pipeline e nas filas.

### D3. Perfis explícitos sem framework prematuro

Criar uma abstração pequena, sem God object, que resolva comportamento pelo tipo. API conceitual:

```python
get_exam_profile(exam_type) -> ExamProfile

evaluate_preop_policy(*, structured_data, exam_type) -> dict
```

Um perfil contém somente diferenças reais:

- código/label;
- aliases de solicitação;
- nomes de prompts;
- procedimento canônico;
- exceções permitidas;
- sinais prioritários permitidos.

As regras clínicas comuns continuam em funções coesas compartilhadas. Não transformar thresholds em metaprogramação complexa e não adicionar perfil CPRE agora.

EDA:

- mantém subtipos existentes;
- permite `foreign_body_exception`;
- mantém sinais EDA.

Colonoscopia:

- usa requisitos comuns;
- não permite `foreign_body_exception`;
- usa somente `pediatric` entre os sinais persistidos atuais; `regulation_days_on_screen` continua sendo campo separado.

### D4. Compatibilidade do contrato LLM

Para manter o slice central executável e reduzir regressão clínica, este change não reescreve JSON histórico nem exige migração de `structured_data`.

O contrato estrito evolui incrementalmente:

- `preop_screening.exam_type` aceita `colonoscopy`;
- o bloco legado `eda` continua sendo o envelope compatível para labs, ECG, ASA e procedimento nos outputs novos deste change;
- para colonoscopia, `requested_procedure.name` identifica colonoscopia, `subtype` permanece `standard`/`unknown`, e a policy não interpreta subtipos EDA como exceção;
- presenters deixam de usar o nome do bloco como fonte do tipo e recebem `Case.exam_type`.

Essa compatibilidade é uma decisão deliberada de escopo. A chegada de CPRE poderá introduzir schema procedure-neutral em change próprio, sem misturar implementação CPRE neste change. O ganho preparado agora é a separação da policy/perfis, que é a parte clinicamente crítica.

### D5. Prompts por procedimento

Preservar os quatro prompts canônicos EDA. Adicionar quatro nomes colonoscopia, administráveis e sem substituir versões EDA:

```text
colonoscopy_llm1_system
colonoscopy_llm1_user
colonoscopy_llm2_system
colonoscopy_llm2_user
```

O orchestrator seleciona pelo perfil. Fallbacks de código e seed devem existir. A UI administrativa aceita os oito nomes.

Prompts de colonoscopia:

- descrevem colonoscopia como exame suportado;
- exigem os mesmos dados pré-operatórios;
- não criam exceção de corpo estranho;
- não avaliam preparo, biópsia ou diagnóstico/terapêutica como gate;
- extraem nome do procedimento e `exam_type=colonoscopy`;
- usam o mesmo schema estrito e idioma pt-BR.

### D6. Medicamentos estruturados e somente informativos

Adicionar ao LLM1 uma coleção com default vazio, por exemplo:

```text
medications_described[]
├── name
├── normalized_name
├── medication_class
├── use_status
├── last_dose_or_schedule
└── source_text_hint
```

Enums mínimos:

- classe: `anticoagulant`, `antiplatelet`, `other`, `unknown`;
- uso: `current`, `recent`, `historical`, `suspended`, `unknown`.

Regras:

- somente medicamento explicitamente descrito;
- `source_text_hint` obrigatório para item não vazio;
- lista limitada para impedir payload excessivo;
- ausência gera `[]`;
- não inferir medicamento por doença, idade ou exame;
- alerta especial quando classe for anticoagulante/antiagregante;
- classe incerta aparece como informação a confirmar, nunca como decisão;
- não recomendar suspensão, janela farmacológica ou dose.

O presenter médico mostra um alerta no relatório técnico e a reconstrução gerencial usa o mesmo presenter. Não é necessário novo campo no `Case`: a coleção pertence ao artefato LLM validado.

### D7. Scope esperado, histórico e solicitação mista

O detector passa a classificar solicitação atual em `eda`, `colonoscopy`, `mixed` ou `unknown`, reconciliada com o tipo esperado.

Termos colonoscopia:

- colonoscopia;
- endoscopia digestiva baixa;
- `EDB` apenas com boundary e contexto local de solicitação/exame/procedimento;
- videocolonoendoscopia;
- colonoscopia diagnóstica;
- colonoscopia terapêutica.

Regras de proveniência:

- `Motivo da Solicitação` e campo estruturado de procedimento têm prioridade;
- referência histórica ao outro exame não torna o caso misto;
- negação/ausência do outro exame não torna o caso misto;
- duas solicitações atuais distintas produzem `mixed_exam_request`;
- o comportamento anterior “EDA prevalece sobre colonoscopia simultânea” é substituído para novas solicitações atuais: agora o caso é bloqueado e o NIR deve separar PDFs.

Resultados:

| Esperado | Detectado | Ação |
| --- | --- | --- |
| EDA | EDA | prossegue |
| Colonoscopia | Colonoscopia | prossegue |
| EDA | Colonoscopia | manual review |
| Colonoscopia | EDA | manual review |
| Qualquer | mixed | manual review |
| Qualquer | unknown | manual review |

Eventos/payloads novos devem ser genéricos e incluir `declared_exam_type`, `detected_exam_type` e `reason_code`, sem copiar texto clínico longo.

### D8. Policy e prior-case são type-aware

A policy comum recebe `exam_type`. `foreign_body_exception` só é consultada quando `exam_type == eda`.

Textos persistidos/apresentados deixam de afirmar “rulebook EDA” para colonoscopia. Podem usar “critérios pré-operatórios de Colonoscopia” ou texto neutro.

`lookup_prior_case_context` recebe tipo e filtra candidatos pelo mesmo `exam_type`. Um caso EDA anterior não influencia colonoscopia da mesma ocorrência e vice-versa.

### D9. Sinais prioritários não vazam

`resolve_priority_signals` recebe `exam_type` ou seus callers filtram por perfil antes de persistir.

EDA preserva:

- foreign_body;
- caustic_ingestion;
- pediatric;
- echoendoscopy;
- esophageal_dilation;
- gastrostomy.

Colonoscopia preserva somente:

- pediatric.

`regulation_days_on_screen` não faz parte de `priority_signals` e continua visível/ordenando ambos.

### D10. Fluxos downstream são compartilhados

Após `WAIT_DOCTOR`, colonoscopia usa sem branches novos:

- mesmo `DoctorDecisionForm`;
- mesmos support flags;
- mesmos admission flows;
- `pediatric_appt` para nova decisão pediátrica;
- mesmos locks;
- mesmo `WAIT_APPT` e `SchedulerDecisionForm`;
- mesmos fluxos operacionais sem agendamento;
- mesmas intercorrências;
- mesmo resultado e confirmação NIR.

Não duplicar views/forms/FSM por exame.

### D11. Filtro médico é uma dimensão secundária

Manter tabs primárias de lifecycle.

Pendentes:

```text
Todos (total) | EDA (n) | Colonoscopia (n)
```

- controle segmentado/radio acessível;
- default Todos;
- filtro client-side porque todos os cards já estão no DOM;
- compõe com busca por nome/ocorrência;
- termo permanece ao trocar tipo;
- `Limpar` apaga termo e reaplica resultado imediatamente;
- troca de tipo não apaga termo;
- polling HTMX reaplica ambos;
- status diz `Mostrando X de Y casos de ...`.

Decididos Hoje:

- badge em cada card;
- filtro simples client-side, default Todos;
- sem nova busca.

### D12. Filtros CHD

Pendentes:

- filtro por tipo abrange `WAIT_APPT`, notices iniciais e issues operacionais;
- contagem por tipo soma os mesmos grupos do badge primário;
- default Todos;
- nenhum workflow/lock/form é alterado.

Processados Hoje:

- badge e filtro simples por tipo.

Histórico:

- GET server-side `exam_type=all|eda|colonoscopy`;
- busca compõe nome/ocorrência + tipo;
- tipo específico sem `q` lista últimos 50 do tipo;
- `all` sem `q` pode listar últimos 50 gerais, conforme implementação mais simples consistente;
- botão limpar remove termo e restaura Todos.

### D13. Filtros NIR

Casos operacionais e encerrados recebem filtro server-side `exam_type` com default Todos. O filtro compõe com ocorrência/status e preserva polling/query string.

Todo card/detalhe recebe badge textual de tipo. Reenvio corrigido exige escolha explícita e pode divergir do original sem aviso adicional obrigatório.

### D14. Correção e reprocessamento do mesmo Case

Permitir correção somente:

- em resultado `manual_review_required` por mismatch/mixed/unknown; ou
- em estado estável anterior a `WAIT_DOCTOR`, sem worker ativo.

Nunca permitir em `WAIT_DOCTOR` ou depois.

Fluxo seguro:

1. adquirir `select_for_update`/lock transacional do caso;
2. validar papel NIR, status e ausência de reserva/processamento incompatível;
3. registrar tipo anterior/novo;
4. invalidar `structured_data`, `summary_text`, `suggested_action` e `priority_signals` derivados;
5. preservar PDF, anexos, `extracted_text`, ocorrência e eventos;
6. transicionar por método FSM explícito de reprocessamento para `LLM_STRUCT` (sem novo estado permanente);
7. enfileirar novamente LLM, sem reextrair PDF;
8. registrar eventos antes/depois de modo append-only.

A implementação deve recusar alteração durante execução ativa em vez de tentar cancelar worker sem token de geração. Se a única janela segura disponível for o estado manual após o pipeline, documentar essa limitação e não introduzir race.

### D15. Métricas consolidadas e breakdown

Cards atuais continuam consolidados.

Adicionar breakdown por `exam_type` no período ativo, no mínimo:

- total;
- aceitos;
- negados;
- encerrados administrativamente;
- em andamento;
- aguardando médico;
- aguardando CHD;
- aguardando confirmação NIR.

A tabela de casos recebe filtro `exam_type`, compondo com busca/status/datas/atenção e paginação. Não duplicar as fórmulas semânticas de accepted/denied; parametrizar QuerySet/helper existente.

### D16. Feature flag de intake

Configuração:

```python
COLONOSCOPY_INTAKE_ENABLED = env in {true, 1, yes}
```

Default recomendado antes de ativação: `false`.

Propagar a env para web/worker nos compose aplicáveis apenas se necessário; workers não devem bloquear casos existentes pela flag. A flag é consultada no intake e não no processamento downstream.

### D17. Auditoria e nomes de eventos

Preservar eventos históricos EDA. Novos fatos genéricos:

- `EXAM_TYPE_MISMATCH_DETECTED`;
- `EXAM_TYPE_CORRECTED`;
- `CASE_REPROCESSING_REQUESTED`.

Payloads enxutos, sem PDF/texto integral. `CASE_CREATED` pode passar a incluir `exam_type` para novos casos sem backfill de eventos históricos.

### D18. Rollback

1. Desligar `COLONOSCOPY_INTAKE_ENABLED`.
2. Consultar casos colonoscopia não `CLEANED`.
3. Permitir conclusão ou encerramento administrativo individual.
4. **Preferido: manter a imagem nova rodando** (schema-compatible — coluna sem default é ok porque a imagem nova sempre envia `exam_type`).
5. Se a reversão para a imagem antiga for exigida: **bridge de schema obrigatório e verificável** (`ALTER COLUMN exam_type SET DEFAULT 'eda'` após drenagem completa) — código antigo omite `exam_type` no INSERT e falharia NOT NULL mantendo a coluna sem default; remover o default temporário no redeploy forward (`DROP DEFAULT`, mesma janela de manutenção).
6. Manter coluna/index e prompts no banco; rollback destrutivo não é o padrão.
7. Se prompts EDA forem versionados pelo change de medicamentos, reativar a versão anterior antes de rollback para código que não aceite o novo campo.

## 3. Dimensionamento dos slices

Foram escolhidos **8 slices**. Menos slices tornaria o núcleo pipeline/UI grande demais para DeepSeek4-Flash; mais slices criaria fatias horizontais sem valor observável.

### Slice 001 — Medicamentos relevantes chegam ao relatório médico

Valor vertical independente: EDA atual → extração estruturada → alerta médico/auditoria reconstruída. Prepara o contrato compartilhado sem depender de colonoscopia.

### Slice 002 — NIR cria caso com tipo explícito e rastreável

Valor vertical: seleção obrigatória → persistência/backfill → caso EDA segue pipeline existente → tipo aparece no acompanhamento NIR e detalhe médico. Inclui flag de intake e base de corrected resubmission.

### Slice 003 — Colonoscopia chega ao médico pelo pipeline seguro

Valor vertical central: upload colonoscopia → prompt/schema/scope/profile/policy → fila/relatório médico → decisão existente. É o maior slice; ampliar arquivos é inevitável e deverá ser justificado por requisito.

### Slice 004 — Médico separa e pesquisa filas por tipo

Valor vertical UX: Pendentes e Decididos Hoje filtram instantaneamente por tipo; busca existente compõe e preserva termo.

### Slice 005 — CHD separa pendências, processados e histórico

Valor vertical CHD: todas as categorias pendentes, processados e histórico são type-aware sem alterar agendamento/locks.

### Slice 006 — NIR corrige tipo e reprocessa com auditoria

Valor vertical: mismatch manual → NIR corrige → mesmo caso reentra no LLM com texto/PDF preservados → chega à fila correta.

### Slice 007 — NIR filtra operacionais/encerrados e escolhe tipo no reenvio

Valor vertical NIR: localizar casos por tipo e criar reenvio corrigido com tipo escolhido, sem herança silenciosa.

### Slice 008 — Gestor acompanha breakdown e operação pode ativar/reverter

Valor vertical gerencial/operacional: métricas consolidadas + breakdown + filtro de tabela, manual/runbook e configuração de rollout verificável.

## 4. Limites globais

- Sem CPRE funcional.
- Sem DRF/SPA/framework JS.
- Sem tabela nova para medicamentos.
- Sem hard rule medicamentosa.
- Sem duplicar FSM/forms por exame.
- Sem reprocessar histórico.
- Sem inferir tipo histórico.
- Sem alterar permissões de roles.
- Sem iniciar slice seguinte sem revisão explícita do relatório anterior.

## 5. Gates globais

Cada slice executa baseline completo antes de editar e quality gate completo ao final:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

O change só pode ser arquivado quando os oito relatórios temporários estiverem revisados, a flag estiver documentada e o runbook de rollback estiver testável.
