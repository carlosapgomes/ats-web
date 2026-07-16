<!-- markdownlint-disable MD013 -->

# Design: Relatório automático médico reconstruído no detalhe do dashboard

## Estado atual verificado

### Artefatos do caso

`apps/cases/models.py::Case` já persiste os artefatos usados na apresentação médica:

```text
structured_data   JSONField
summary_text      TextField
suggested_action  JSONField
extracted_text    TextField
```

Não é necessário novo campo ou migration para reconstruir o relatório atual.

### Tela médica

`apps/doctor/views.py` prepara o contexto de negativa anterior, instancia `DoctorReportPresenter` e chama `build_report()`.

`apps/doctor/presenters.py::DoctorReportPresenter` produz:

- contexto: procedimento, origem, comorbidades, transfusão, exames rastreados, pediatria e alertas;
- sete blocos: resumo clínico, achados críticos, pendências críticas, decisão sugerida, suporte recomendado, ASA estimado e motivo objetivo;
- contexto opcional de negativa recente;
- `build_text_report()`, que serializa esse conteúdo em texto legível.

`templates/doctor/decision.html` renderiza os sete blocos e oferece separadamente o JSON completo de `suggested_action`.

### Detalhe do dashboard

`apps/dashboard/views.py::dashboard_case_detail`:

- exige `@role_required("manager", "admin")`;
- carrega qualquer `Case` e seus eventos;
- renderiza `templates/intake/case_detail.html` com `show_dashboard_nav=True`;
- não prepara relatório médico.

O template compartilhado já usa Bootstrap Collapse para texto extraído, PDF e timeline. Bootstrap 5.3 e seu bundle JS são carregados em `templates/base.html`.

## Decisões

### D1. Reconstrução atual, sem snapshot

O dashboard reconstruirá o relatório a partir dos artefatos persistidos e do código atual.

A UI deve usar texto explícito semelhante a:

```text
Relatório automático apresentado ao médico (reconstruído)
```

E aviso:

```text
Conteúdo reconstruído a partir dos artefatos armazenados do caso. Não é um snapshot imutável da tela histórica.
```

Essa decisão implementa deliberadamente a Opção B solicitada. Não adicionar persistência “preventiva” para uma possível Opção C futura.

### D2. Só mostrar quando houve handoff médico

A presença de dados LLM não prova que o médico recebeu o caso. Casos scope-gated ou com falha podem ter parte dos artefatos, mas nunca entrar na fila médica.

A condição canônica será a existência de `CaseEvent.event_type == "CASE_READY_FOR_DOCTOR"` para o caso.

A view já percorre `case.events.all()` para montar a timeline. O implementador deve preferir derivar `was_ready_for_doctor` durante essa iteração, evitando uma consulta extra apenas para o gate.

Consequências:

- casos enviados e posteriormente encerrados/limpos continuam mostrando o relatório;
- casos `FAILED`, `non_eda` ou `unknown` sem handoff não mostram relatório enganoso;
- status FSM atual não é usado como proxy de handoff histórico.

### D3. Preparação canônica compartilhada em `apps/doctor/reporting.py`

Criar módulo pequeno, por exemplo `apps/doctor/reporting.py`, responsável por preparar o presenter a partir de um `Case`:

1. executar `lookup_prior_case_context(...)` quando houver `agency_record_number`;
2. mapear `doctor_denied`/`appointment_denied` para o contrato esperado pelo presenter;
3. montar `recent_denial_context`;
4. instanciar `DoctorReportPresenter` com exatamente os cinco inputs atuais.

Uma API aceitável é uma função que devolva um objeto/dataclass preparado, por exemplo:

```python
prepared = prepare_doctor_case_report(case)
report = prepared.presenter.build_report()
text = prepared.presenter.build_text_report()
prior_context = prepared.prior_context
prior_decision_display = prepared.prior_decision_display
```

A forma exata pode variar, desde que:

- a lógica atual de preparação não fique duplicada em doctor e dashboard;
- `apps/doctor/views.py` passe a usar o helper sem mudar seu contexto/template;
- `apps/dashboard/views.py` use o mesmo helper;
- não haja import de `apps.doctor.views` pelo dashboard;
- não haja ciclo de import.

A dependência `dashboard → doctor.reporting` é deliberada e unidirecional: o dashboard reutiliza o presenter clínico canônico, enquanto `doctor` não depende do dashboard.

### D4. Texto canônico via `build_text_report()`

O dashboard deve usar `DoctorReportPresenter.build_text_report()` em vez de:

- duplicar loops dos sete blocos no template compartilhado;
- serializar manualmente `structured_data`/`suggested_action`;
- copiar o HTML da tela médica.

Vantagens:

- elemento textual simples e apropriado à solicitação;
- mesmos labels e regras do presenter;
- menor risco de divergência;
- template do dashboard permanece enxuto.

O JSON completo opcional da tela médica fica fora de escopo. O relatório textual deve conter contexto e os sete blocos; não precisa incluir dump de artefatos internos.

### D5. Card condicionado ao contexto do dashboard

Adicionar a `templates/intake/case_detail.html` um bloco semelhante a:

```django
{% if show_dashboard_nav and doctor_report_text %}
  ... botão Bootstrap Collapse ...
  <pre>{{ doctor_report_text }}</pre>
{% endif %}
```

A condição dupla é obrigatória porque o template é compartilhado com NIR. Não condicionar apenas a `doctor_report_text`.

Posicionamento recomendado: junto das informações médicas/auditáveis, antes de documentos e timeline. Não mover ações existentes nem redesenhar a página.

### D6. Collapse acessível e fechado por padrão

O controle deve usar os contratos Bootstrap existentes:

- `data-bs-toggle="collapse"`;
- `data-bs-target` ou `href` para ID único e estável;
- `aria-expanded="false"`;
- `aria-controls` correspondente;
- container com classes `collapse` e sem `show` inicial.

O texto deve usar `<pre>` ou bloco com `white-space: pre-wrap`, largura responsiva e limite vertical/scroll quando necessário. Não adicionar JS customizado.

### D7. Escaping e acesso

Usar autoescaping padrão do Django. Não aplicar `safe` ao relatório e não montar HTML dentro do presenter.

Preservar:

```python
@login_required
@role_required("manager", "admin")
def dashboard_case_detail(...):
```

Não alterar decorators, URL ou query de autorização. O novo card deve ficar ausente quando o mesmo template for renderizado no contexto NIR.

### D8. Paridade funcional, não fidelidade forense

“Mesmo relatório” neste change significa:

- mesmas entradas preparadas por helper compartilhado;
- mesmo `DoctorReportPresenter`;
- mesmo contexto atual de negativa anterior;
- mesmos sete blocos e regras de formatação textual.

Não significa:

- HTML idêntico à tela médica;
- snapshot do instante de handoff;
- prompt/modelo/versionamento histórico;
- prova de quais seções o médico expandiu ou leu.

## Fluxo proposto

```text
dashboard_case_detail(case_id)
  ├─ carrega Case + eventos
  ├─ monta timeline e detecta CASE_READY_FOR_DOCTOR
  ├─ se handoff existiu:
  │    └─ prepare_doctor_case_report(case)
  │         ├─ lookup de negativa anterior
  │         └─ DoctorReportPresenter(...)
  │              └─ build_text_report()
  └─ render intake/case_detail.html
       └─ show_dashboard_nav + doctor_report_text
            └─ Bootstrap Collapse fechado
```

A tela médica passa a usar `prepare_doctor_case_report(case)` para seu `report`, `prior_context` e `prior_decision_display`, preservando todo o restante do contexto.

## Arquivos previstos

Idealmente, o slice toca apenas:

1. `apps/doctor/reporting.py` — novo helper de preparação compartilhada;
2. `apps/doctor/views.py` — consumir helper e remover preparação duplicada;
3. `apps/dashboard/views.py` — detectar handoff e preparar texto;
4. `templates/intake/case_detail.html` — card textual colapsável restrito ao dashboard;
5. `apps/dashboard/tests/test_dashboard.py` — testes end-to-end e regressões.

`tasks.md` será atualizado apenas após todos os gates. Se testes médicos existentes não cobrirem uma regressão necessária, tocar `apps/doctor/tests/test_views.py` é aceitável, mas deve ser justificado no relatório.

## Estratégia de testes

### Dashboard

Cobrir no mínimo:

1. `manager` vê o card em caso com `CASE_READY_FOR_DOCTOR`;
2. `admin` também vê;
3. texto contém o resumo e labels dos sete blocos;
4. markup começa recolhido e possui atributos ARIA coerentes;
5. aviso de reconstrução está presente;
6. caso sem evento de handoff não mostra o card;
7. conteúdo HTML malicioso em `summary_text` é escapado;
8. `doctor_report_text` corresponde ao resultado do helper/presenter canônico para os mesmos dados;
9. acesso NIR ao dashboard continua bloqueado pelos testes existentes e o bloco do template exige `show_dashboard_nav`.

### Médico

Executar os testes existentes de `apps/doctor/tests/test_views.py` e `apps/doctor/tests/test_presenter.py` para provar que o refactor de preparação não alterou a tela médica.

## Performance

- Nenhuma consulta adicional para detectar handoff se o gate for derivado da iteração já existente de eventos.
- O helper pode executar o mesmo lookup de negativa anterior já usado pela tela médica: no máximo uma consulta adicional no detalhe individual do dashboard.
- A construção do texto é CPU local e pequena.
- Nenhuma alteração em listagem, paginação ou busca do dashboard.

## Compatibilidade

- Casos antigos com `CASE_READY_FOR_DOCTOR` e artefatos parciais usam fallbacks já existentes no presenter.
- Casos sem handoff não mostram o card.
- Sem backfill, migration ou reprocessamento.
- NIR continua usando o mesmo template sem o novo bloco.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Auditor interpretar reconstrução como cópia histórica exata | Título e aviso explícitos; testes de microcopy. |
| Doctor e dashboard divergirem no preparo do presenter | Helper único consumido pelas duas views. |
| Expor relatório no detalhe NIR por template compartilhado | Condição `show_dashboard_nav and doctor_report_text`; teste/inspeção. |
| XSS por texto clínico/LLM | Autoescape Django; proibir `safe`; teste com payload HTML. |
| Mostrar relatório em caso nunca enviado ao médico | Gate pelo evento `CASE_READY_FOR_DOCTOR`, não por status/artefato. |
| Refactor quebrar contexto de negativa anterior da tela médica | Preservar `prior_context` e `prior_decision_display`; rodar suíte doctor. |
| Escopo crescer para JSON/snapshot/prompt versioning | Proibições explícitas no slice; YAGNI. |

## Rollout

Deploy normal, sem etapa de banco. Após deploy, validar manualmente:

1. caso encerrado que passou pelo médico;
2. expansão/recolhimento no desktop e mobile;
3. conteúdo e aviso de reconstrução;
4. caso scope-gated sem card;
5. navegação e ações existentes inalteradas.

## Rollback

Reverter os arquivos do slice. Não há dados a restaurar, migration a reverter ou evento novo a remover.
