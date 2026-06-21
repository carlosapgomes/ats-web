# Design: Caso corrigido / vínculo entre reenvios

## Estado atual

### Upload NIR

O upload normal está em:

```text
apps/intake/views.py::intake_home
apps/intake/services.py::process_uploaded_files
```

Ele aceita múltiplos PDFs principais. Cada PDF cria um `Case` independente. Anexos clínicos são aceitos somente quando há exatamente 1 PDF principal.

### Anexos

O change `case-attachments-initial-upload` adicionou `CaseAttachment` e os fluxos:

- anexos iniciais no upload único;
- supressão auditável;
- anexos complementares antes da decisão médica;
- bloqueio de complementação após decisão médica.

### Prior-case lookup

O change `fix-prior-case-lookup-after-closure` corrigiu o lookup automático para identificar negações recentes por campos estáveis de decisão, não por status transitório.

Esse lookup permanece como fallback para uploads normais/reenvios não declarados. Ele não cria vínculo formal entre casos e não captura motivo do NIR.

### Detalhes/decisão

A tela médica principal é:

```text
templates/doctor/decision.html
apps/doctor/views.py::_build_decision_context
```

O detalhe NIR compartilhado é:

```text
templates/intake/case_detail.html
apps/intake/views.py::case_detail
```

Casos `CLEANED` não são abertos pela rota operacional `case_detail`; há busca específica em:

```text
apps/intake/views.py::closed_cases_search
templates/intake/closed_cases_search.html
```

## Decisões

### D1. Novo `Case`, nunca sobrescrever o anterior

O reenvio corrigido explícito cria um novo `Case`. O caso anterior permanece intacto.

Motivos:

- preserva auditoria da decisão anterior;
- evita misturar documentos de versões diferentes;
- evita reabrir FSM;
- torna claro para médico e NIR qual versão está em avaliação.

### D2. Relação self-FK no `Case`

Adicionar campos opcionais em `Case`:

```python
corrects_case = models.ForeignKey(
    "self",
    null=True,
    blank=True,
    on_delete=models.PROTECT,
    related_name="corrected_by_cases",
)
correction_reason = models.TextField(blank=True)
correction_created_by = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    null=True,
    blank=True,
    on_delete=models.PROTECT,
    related_name="case_corrections_created",
)
correction_created_at = models.DateTimeField(null=True, blank=True)
```

`on_delete=PROTECT` impede apagar o caso anterior se houver caso corrigido dependente.

`correction_reason` fica `blank=True` para compatibilidade de banco, mas deve ser obrigatório no serviço/form quando `corrects_case` for preenchido.

### D3. Não adicionar estado FSM

Não criar status `SUPERSEDED`, `CORRECTED`, `REOPENED` ou similar.

A relação entre casos é metadado/auditoria, não estado operacional. O caso anterior pode continuar no estado em que já estava.

### D4. Não herdar documentos/anexos

O novo caso não deve copiar:

- `pdf_file`;
- `CaseAttachment`;
- `extracted_text`;
- `structured_data`;
- `summary_text`;
- `suggested_action`;
- decisões;
- eventos.

O novo PDF e novos anexos pertencem exclusivamente ao novo caso.

### D5. Serviço dedicado para reenvio corrigido

Criar serviço em `apps/intake/services.py`, por exemplo:

```python
def create_corrected_resubmission(
    *,
    original_case: Case,
    pdf_file: UploadedFile,
    user: AccountsUser,
    correction_reason: str,
    attachments: list[UploadedFile] | None = None,
) -> Case:
    ...
```

Responsabilidades:

1. validar `correction_reason` obrigatório;
2. validar exatamente 1 PDF principal;
3. validar PDF com `validate_single_file`;
4. validar anexos com validações existentes;
5. criar novo `Case` com campos de correção preenchidos;
6. salvar PDF do novo caso;
7. avançar FSM `NEW → R1_ACK_PROCESSING`;
8. enfileirar extração PDF;
9. salvar anexos do novo caso, se houver;
10. registrar eventos `CASE_CORRECTION_CREATED` no novo caso e `CASE_MARKED_SUPERSEDED` no original.

Esse serviço evita lógica de negócio pesada na view.

### D6. View/form NIR dedicado

Adicionar rota:

```python
path("<uuid:case_id>/corrected-resubmission/", views.corrected_resubmission, name="corrected_resubmission")
```

Comportamento:

- GET: renderiza formulário contextualizado pelo caso anterior.
- POST: chama serviço dedicado.
- Em sucesso: redireciona para o detalhe do novo caso.
- Em erro: mostra mensagem clara e re-renderiza o formulário.

Template sugerido:

```text
templates/intake/corrected_resubmission.html
```

O formulário deve ter:

```text
Motivo do reenvio corrigido [textarea obrigatório]
Novo relatório principal [file PDF obrigatório, single]
Anexos do novo caso [file múltiplo opcional]
Confirmação de que os documentos/anexos do caso anterior não serão herdados
```

### D7. Elegibilidade inicial simples

Para o MVP, não criar regra complexa de elegibilidade por status. Permitir que NIR crie reenvio corrigido a partir de qualquer caso existente que consiga localizar, operacional ou encerrado.

Motivos:

- edge cases variam: anexo errado, relatório errado, documento tardio, negativa, falha;
- o fluxo cria novo caso e não altera o anterior;
- auditoria registra a ação.

Restrições mínimas:

- o caso original deve existir;
- usuário precisa ter papel ativo `nir`;
- motivo obrigatório;
- novo PDF obrigatório e válido.

Se houver necessidade de restringir status no futuro, isso deve ser change separado após observação operacional.

### D8. Pontos de entrada NIR

Adicionar links/botões:

1. No detalhe operacional (`templates/intake/case_detail.html`) para casos não `CLEANED`.
2. Na busca de casos encerrados (`templates/intake/closed_cases_search.html`) para casos `CLEANED` ou encontrados ali.

Texto sugerido:

```text
Reenviar caso corrigido
```

### D9. Relação exibida no detalhe NIR

No detalhe do novo caso, mostrar card:

```text
↻ Reenvio corrigido
Este caso corrige o caso anterior <registro / id curto>.
Motivo do reenvio: ...
```

No detalhe do caso anterior, se ele tiver correções, mostrar:

```text
Este caso foi corrigido pelo(s) caso(s): <registro / id curto>.
```

Para casos `CLEANED`, a busca de encerrados pode mostrar um badge/linha resumida com essa relação. Não é necessário criar detalhe read-only completo de caso encerrado neste change.

### D10. Card médico no caso corrigido

Em `templates/doctor/decision.html`, se `case.corrects_case` existir, mostrar card antes do relatório técnico/decisão ou logo após o cabeçalho de dados do paciente:

```text
↻ Reenvio corrigido

Este caso foi reenviado pelo NIR para corrigir o caso anterior <registro / id curto>.

Motivo informado pelo NIR:
"..."

Desfecho do caso anterior:
<decisão/status resumido>

Atenção:
Os documentos e anexos do caso anterior não foram herdados. Avalie apenas o relatório e os anexos deste caso atual.
```

Informações do caso anterior no card:

- `agency_record_number` ou ID curto;
- data/hora de envio;
- paciente, se disponível;
- status/desfecho com label amigável;
- decisão médica anterior, data, médico e motivo, se houver;
- negativa de agendamento anterior, data, agendador e motivo, se houver;
- motivo do reenvio corrigido.

Não embutir PDF, anexos ou timeline completa do caso anterior na tela médica.

### D11. Evitar duplicidade visual com prior-case lookup automático

Se o novo caso tem `corrects_case`, o card explícito de reenvio corrigido deve ser o contexto principal.

O prior-case lookup pode continuar alimentando o relatório/pipeline, mas a UI deve evitar mostrar dois cards redundantes para o mesmo caso anterior quando for fácil detectar duplicidade.

Regra simples aceitável:

```text
Se case.corrects_case_id == prior_context.prior_case.prior_case_id,
não renderizar o card genérico “Caso Anterior — Negação Recente”; renderizar apenas o card “Reenvio corrigido”.
```

### D12. Eventos/timeline

Adicionar labels/dots nos mapas de timeline:

```text
CASE_CORRECTION_CREATED → Reenvio corrigido criado
CASE_MARKED_SUPERSEDED  → Caso corrigido por novo envio
```

Eventos continuam append-only. Não editar eventos antigos.

### D13. Semântica dos campos textuais

Manter separação:

| Campo/modelo | Papel |
| --- | --- |
| `doctor_reason` | motivo formal da negativa |
| `doctor_observation` | nota curta complementar à decisão |
| `correction_reason` | motivo do NIR para criar novo caso corrigido |
| `CaseCommunicationMessage` futuro | conversa operacional por caso |
| `CaseEvent` | auditoria de fatos |

Não remover `doctor_observation`.

## Dimensionamento de slices

Este change deve ter **2 slices verticais**.

### Slice 001 — Fluxo NIR de reenvio corrigido explícito

Entrega:

```text
NIR parte de caso anterior → informa motivo + novo PDF/anexos → sistema cria novo Case vinculado → eventos registrados
```

Inclui modelo/migration, serviço, rota/form/template NIR e testes do fluxo.

Justificativa de tocar mais arquivos: é o menor slice vertical que entrega criação real do vínculo. Separar modelo/serviço/UI criaria slices horizontais sem valor operacional.

### Slice 002 — Visibilidade operacional e médica da relação

Entrega:

```text
NIR e médico veem claramente que o novo caso corrige outro caso, sem misturar documentos
```

Inclui cards no detalhe NIR e tela médica, labels de eventos/timeline, busca de encerrados e testes de renderização/autorização.

## Arquivos previstos

### Slice 001

| Arquivo | Mudança |
| --- | --- |
| `apps/cases/models.py` | campos de correção no `Case` |
| `apps/cases/migrations/*` | migration dos campos |
| `apps/intake/services.py` | serviço `create_corrected_resubmission` |
| `apps/intake/views.py` | view GET/POST do reenvio corrigido |
| `apps/intake/urls.py` | rota `corrected_resubmission` |
| `templates/intake/corrected_resubmission.html` | formulário NIR |
| `apps/intake/tests/...` | testes do fluxo |

### Slice 002

| Arquivo | Mudança |
| --- | --- |
| `apps/intake/views.py` | contexto de relação para detalhe/lista |
| `templates/intake/case_detail.html` | card caso corrige / foi corrigido |
| `templates/intake/closed_cases_search.html` | botão/badge de correção em encerrados |
| `apps/doctor/views.py` | contexto do card médico |
| `templates/doctor/decision.html` | card de reenvio corrigido |
| `apps/*/tests/...` | testes de UI/contexto |

Se o implementador encontrar forma mais enxuta mantendo valor vertical, pode ajustar, mas deve justificar no relatório.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Misturar documentos entre casos | Não copiar PDF/anexos; aviso explícito na UI |
| Reabrir caso anterior indevidamente | Novo Case sempre; FSM preservada |
| Duplicar contexto com prior-case lookup | Card explícito prevalece sobre card genérico duplicado |
| NIR usar campo errado para conversa | `correction_reason` obrigatório só no reenvio; mensagens ficam para change futuro |
| Fluxo grande demais | 2 slices verticais enxutos |
| Caso anterior operacional continuar em fila | Este change só vincula/audita; encerramento administrativo é fluxo separado |

## Futuro fora deste change

- Comunicação operacional por caso (`CaseCommunicationMessage`).
- Menções/notificações in-app.
- Encerramento administrativo guiado a partir de reenvio corrigido.
- Visualização read-only completa de casos encerrados para NIR/médico, se necessário.
- Relações mais ricas entre múltiplas versões de um caso.
