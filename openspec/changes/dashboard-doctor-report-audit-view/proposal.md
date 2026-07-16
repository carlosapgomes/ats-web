<!-- markdownlint-disable MD013 -->

# Proposal: Relatório automático médico reconstruído no detalhe do dashboard

**Change ID**: `dashboard-doctor-report-audit-view`

**Fase**: observabilidade e auditoria clínica no dashboard

**Risco**: PROFISSIONAL (FEATURE)

**Dependências**: `dashboard-supervisor`, `align-llm-contract-and-doctor-routing`, `doctor-observation`

## Classificação de risco

Classificação manual ESAA: **PROFISSIONAL**.

Fatores considerados:

- impacto de auditoria sobre casos clínicos e dados pessoais sensíveis;
- necessidade de manter paridade com o relatório mostrado ao médico;
- pequeno refactor compartilhado entre `doctor` e `dashboard`;
- ausência de mudança em autenticação, autorização, banco, migrations, FSM, API externa ou persistência;
- rollback simples por reversão de código e template.

Uma classificação automática baseada apenas na palavra “auditoria” tende a superestimar este change. O escopo é read-only e não amplia o conjunto de casos já acessível a `manager`/`admin`. `design.md` é obrigatório por ser uma feature, mas ADR não é necessária: não há decisão arquitetural duradoura, nova dependência, modelo de dados, contrato externo ou política de segurança.

## Problema

Supervisores (`manager`) e administradores conseguem abrir qualquer caso pelo dashboard e inspecionar resultado final, documentos, texto extraído, comunicação e timeline. Entretanto, o detalhe não mostra o relatório automático que subsidiou a decisão médica.

Isso dificulta a análise posterior de uma possível conduta equivocada, pois o auditor não consegue comparar na mesma tela:

1. os dados disponíveis no caso;
2. a recomendação automática apresentada ao médico;
3. a decisão e observações registradas pelo médico;
4. o desfecho operacional posterior.

Hoje o relatório médico não é um campo textual único. `apps/doctor/views.py` monta dinamicamente o `DoctorReportPresenter` com:

- `Case.structured_data`;
- `Case.summary_text`;
- `Case.suggested_action`;
- `Case.extracted_text`;
- contexto atual de negativa anterior.

O dashboard reutiliza `templates/intake/case_detail.html`, mas não prepara nem renderiza esse relatório.

## Objetivo

Permitir que `manager` e `admin` visualizem, no detalhe do caso aberto pelo dashboard, uma versão textual colapsável do mesmo relatório automático reconstruído pelo presenter usado na tela médica.

Fluxo esperado:

```text
Manager/admin abre um caso que foi encaminhado ao médico
→ detalhe mostra “Relatório automático apresentado ao médico (reconstruído)”
→ elemento inicia recolhido
→ usuário expande e lê contexto + sete blocos técnicos
→ decisão médica, documentos, timeline e demais comportamentos permanecem inalterados
```

## Escopo incluído

- Criar preparação compartilhada do relatório para que doctor e dashboard usem a mesma composição de entradas e o mesmo `DoctorReportPresenter`.
- Reconstruir o relatório apenas para caso com evento histórico `CASE_READY_FOR_DOCTOR`.
- Exibir no dashboard o texto produzido por `DoctorReportPresenter.build_text_report()`.
- Usar Bootstrap Collapse, fechado por padrão, sem JavaScript customizado.
- Informar explicitamente que o conteúdo é reconstruído a partir dos artefatos armazenados e não constitui snapshot imutável.
- Manter a exibição restrita ao contexto `show_dashboard_nav`, já protegido por `manager`/`admin`.
- Cobrir paridade, autorização existente, escaping e ausência do card para casos nunca enviados ao médico.

## Fora de escopo

- Persistir snapshot do relatório no `Case` ou em `CaseEvent`.
- Garantir reprodução forense byte a byte da tela histórica.
- Versionar o presenter ou registrar versão de prompt/modelo LLM por caso.
- Mostrar o JSON completo de `structured_data` ou `suggested_action` no dashboard.
- Alterar prompts, schemas LLM, pipeline, policy engine ou reconciliação.
- Alterar decisão médica, formulários, filas, locks, FSM, estados ou eventos.
- Alterar models, migrations, permissões ou rotas.
- Expor o relatório no detalhe NIR, médico, scheduler ou em listagens do dashboard.
- Criar novo endpoint, API, HTMX, AJAX, WebSocket ou framework frontend.

## Limitação conscientemente aceita

Este change implementa a **Opção B: reconstrução atual**, escolhida pelo solicitante.

O relatório será reconstruído usando os artefatos atualmente persistidos e a versão de código do presenter instalada no momento da auditoria. Se o presenter mudar no futuro, o texto reconstruído de um caso antigo poderá mudar. A UI deve declarar essa limitação e não usar linguagem como “snapshot original” ou “cópia exata histórica”.

## Dimensionamento

### Escolha: um slice vertical

A entrega completa exige poucos arquivos e só gera valor quando backend, template e testes chegam juntos:

```text
evento de handoff + artefatos persistidos
→ preparação canônica do relatório
→ contexto do dashboard
→ texto colapsável para manager/admin
→ regressão da tela médica e autorização preservadas
```

Separar helper, view e template em slices diferentes criaria slices horizontais sem valor observável. Portanto, o change terá **um único slice vertical enxuto**.

## Critérios de sucesso

- `manager` e `admin` veem o relatório textual colapsável em casos com `CASE_READY_FOR_DOCTOR`.
- O relatório começa recolhido e usa Bootstrap Collapse acessível.
- O texto contém o mesmo contexto e os mesmos sete blocos gerados pelo presenter médico.
- Doctor e dashboard usam uma preparação compartilhada das entradas do presenter, evitando divergência futura.
- A UI identifica o conteúdo como reconstruído, não como snapshot histórico imutável.
- Casos nunca enviados ao médico não exibem o card.
- NIR, doctor e scheduler não ganham acesso novo ao dashboard nem ao card compartilhado.
- Conteúdo clínico continua escapado pelo Django; texto potencialmente malicioso não vira HTML executável.
- Nenhum model, migration, FSM, prompt, policy, permissão, rota ou endpoint é alterado.
- Testes e quality gate do `AGENTS.md` passam.
