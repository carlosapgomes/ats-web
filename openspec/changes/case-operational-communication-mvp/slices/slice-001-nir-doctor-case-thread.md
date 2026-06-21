# Slice 001: Thread operacional NIR ↔ Médico

## Contexto zero para implementador

O ATS é um monolito Django SSR. O `Case` é a entidade central (`apps/cases/models.py`) e `CaseEvent` é a trilha auditável append-only. O sistema já tem workflows estruturados para decisões médicas, agendamento, anexos, supressão, intercorrência e reenvio corrigido.

Este slice cria o núcleo de comunicação operacional por caso para NIR e médico, sem notificações e sem polling.

Fluxo alvo:

```text
NIR abre detalhe operacional do caso
→ posta mensagem contextual
→ médico abre tela de decisão do mesmo caso
→ vê mensagem e pode responder
→ mensagens ficam persistidas no Case
→ cada post gera evento auditável
```

A comunicação não altera FSM e não substitui decisão formal.

## Objetivo do slice

Entregar verticalmente:

```text
Modelo + serviço + rota POST + partial UI + NIR case_detail + doctor decision
```

Ao final, NIR e médico conseguem ler/postar mensagens do mesmo caso usando SSR normal.

Agendador fica para o Slice 002.

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/cases/models.py`
2. `apps/cases/migrations/<nova_migration>.py`
3. `apps/cases/services.py`
4. `apps/intake/views.py`
5. `apps/intake/urls.py`
6. `apps/doctor/views.py`
7. `templates/cases/_communication_thread.html`
8. `templates/intake/case_detail.html`
9. `templates/doctor/decision.html`
10. testes em `apps/cases/tests/...`, `apps/intake/tests/...`, `apps/doctor/tests/...` ou equivalentes
11. `openspec/changes/case-operational-communication-mvp/tasks.md` ao concluir

Este slice toca mais de 5 arquivos porque é o menor fluxo vertical útil entre dois papéis. Não separar modelo/serviço/UI em slices horizontais.

## Requisitos funcionais

### R1. Modelo `CaseCommunicationMessage`

Adicionar modelo em `apps/cases/models.py`:

```python
class CaseCommunicationMessage(models.Model):
    message_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="communication_messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="case_communication_messages")
    author_role = models.CharField(max_length=30)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["case", "created_at"])]
```

Criar migration.

Não adicionar edição/deleção/supressão neste slice.

### R2. Serviço de domínio

Adicionar em `apps/cases/services.py`:

```python
ALLOWED_COMMUNICATION_ROLES = {"nir", "doctor", "scheduler", "manager", "admin"}
CASE_COMMUNICATION_MAX_LENGTH = 2000

class CaseCommunicationError(ValueError):
    pass


def post_case_communication_message(*, case: Case, author: User, author_role: str, body: str) -> CaseCommunicationMessage:
    ...
```

O serviço deve:

1. validar `author_role` permitido;
2. rejeitar `body` vazio/apenas espaços;
3. normalizar `body.strip()`;
4. rejeitar tamanho acima de `CASE_COMMUNICATION_MAX_LENGTH`;
5. bloquear post em `case.status == CaseStatus.CLEANED` no MVP;
6. criar `CaseCommunicationMessage`;
7. criar `CaseEvent` `CASE_COMMUNICATION_MESSAGE_POSTED`.

Payload do evento:

```json
{
  "message_id": "...",
  "author_role": "doctor",
  "body_preview": "primeiros 120 caracteres"
}
```

Não duplicar o corpo inteiro em `CaseEvent.payload`.

### R3. Endpoint POST SSR

Adicionar rota em `apps/intake/urls.py`:

```python
path("<uuid:case_id>/communication/", views.post_case_communication, name="post_case_communication")
```

Como `apps.intake.urls` está montado em `/cases/`, a URL final fica:

```text
/cases/<case_id>/communication/
```

Criar view em `apps/intake/views.py`:

- `@login_required`;
- aceitar apenas POST;
- ler `active_role` da sessão;
- chamar `post_case_communication_message`;
- usar `messages.success` em sucesso;
- usar `messages.warning` em erro validável;
- redirecionar para `next` seguro ou fallback.

Segurança do redirect:

- usar `url_has_allowed_host_and_scheme` ou helper Django equivalente;
- se `next` inválido/externo, redirecionar para `intake:case_detail` quando possível;
- não criar open redirect.

### R4. Partial compartilhado

Criar:

```text
templates/cases/_communication_thread.html
```

Contexto esperado:

```python
communication_messages
can_post_communication
communication_post_url
communication_next_url
communication_max_length
```

Renderizar:

- título `💬 Comunicação operacional`;
- texto de ajuda:

```text
Use este espaço para esclarecimentos e coordenação sobre este caso. Decisões formais, agendamento e encerramento continuam nos fluxos estruturados.
```

- estado vazio;
- lista cronológica com:
  - autor;
  - papel;
  - data/hora;
  - corpo com quebra de linha preservada;
- form POST com:
  - CSRF;
  - textarea `name="body"`;
  - hidden `next`;
  - botão `Enviar mensagem`.

Não criar JS. Não criar polling.

### R5. NIR vê/posta no detalhe do caso

Em `apps/intake/views.py::case_detail`, adicionar contexto:

```python
communication_messages = case.communication_messages.select_related("author").all()
can_post_communication = case.status != CaseStatus.CLEANED
communication_post_url = reverse("intake:post_case_communication", args=[case.case_id])
communication_next_url = request.get_full_path() + "#case-communication"
communication_max_length = CASE_COMMUNICATION_MAX_LENGTH
```

Em `templates/intake/case_detail.html`, incluir partial em local visível, idealmente depois de anexos/contexto e antes da timeline ou ações finais.

### R6. Médico vê/posta na tela de decisão

Em `apps/doctor/views.py`, na montagem de contexto da decisão médica, adicionar os mesmos dados de comunicação.

Em `templates/doctor/decision.html`, incluir o partial em local visível, sem atrapalhar a decisão formal. Preferência: abaixo do resumo/relatório e antes ou depois do formulário de decisão, conforme layout existente.

Não alterar validação da decisão médica.

### R7. Timeline label

Adicionar em `apps/intake/views.py`:

```python
EVENT_LABELS["CASE_COMMUNICATION_MESSAGE_POSTED"] = "Mensagem operacional registrada"
EVENT_DOT_CSS["CASE_COMMUNICATION_MESSAGE_POSTED"] = "system"  # ou papel neutro
```

Se `doctor` importa esses mapas, evitar duplicação.

## TDD obrigatório

Antes da implementação, criar testes falhando.

### Testes mínimos de modelo/serviço

1. `test_post_case_communication_message_creates_message`
   - cria mensagem com case, author, author_role, body normalizado.

2. `test_post_case_communication_message_rejects_blank_body`
   - body vazio/apenas espaços não cria mensagem.

3. `test_post_case_communication_message_rejects_too_long_body`
   - acima do limite não cria mensagem.

4. `test_post_case_communication_message_rejects_disallowed_role`
   - papel não permitido não cria mensagem.

5. `test_post_case_communication_message_rejects_cleaned_case`
   - caso `CLEANED` não aceita post no MVP.

6. `test_post_case_communication_message_records_case_event`
   - evento `CASE_COMMUNICATION_MESSAGE_POSTED` criado com preview e id.

### Testes mínimos NIR

7. `test_nir_case_detail_shows_communication_thread`
   - GET detalhe do caso mostra título e mensagens existentes.

8. `test_nir_posts_case_communication_message`
   - POST válido cria mensagem e redireciona.

9. `test_post_case_communication_uses_safe_next_redirect`
   - `next=https://evil.example` não redireciona externamente.

### Testes mínimos médico

10. `test_doctor_decision_shows_case_communication_messages`
   - mensagem criada pelo NIR aparece na tela de decisão.

11. `test_doctor_posts_case_communication_message`
   - médico posta resposta e NIR vê depois.

12. `test_doctor_decision_form_still_works_with_communication_thread`
   - regressão: presença da partial não quebra decisão médica existente.

### RED esperado

Antes da implementação, os testes devem falhar por ausência de modelo/serviço/rota/UI.

Registrar no relatório:

- comando RED executado;
- nomes dos testes falhando;
- resumo das falhas.

## Orientações de implementação

### Clean code

- Regra de negócio no serviço, não na view.
- View deve apenas adaptar request/response.
- Template deve receber contexto pronto.
- Nomes explícitos: `communication_messages`, `post_case_communication_message`, `author_role`.

### DRY

- Usar um único serviço para criar mensagens.
- Usar um único partial para renderizar thread/form.
- Não duplicar HTML de thread em NIR e médico.

### YAGNI

Não implementar neste slice:

- scheduler UI;
- notificações;
- polling;
- HTMX;
- websocket/SSE;
- menções reais;
- read/unread;
- edição/deleção/supressão;
- anexos em mensagens;
- mensagens sistêmicas;
- filtros/busca na thread.

## Critérios de sucesso

- [ ] Modelo e migration criados.
- [ ] Serviço cria mensagens e valida regras.
- [ ] Mensagem vazia, longa demais, papel inválido e caso `CLEANED` são rejeitados.
- [ ] Evento auditável é criado em cada post.
- [ ] NIR vê e posta mensagens no detalhe do caso.
- [ ] Médico vê e posta mensagens na decisão.
- [ ] Mensagens aparecem em ordem cronológica.
- [ ] UI usa partial compartilhado.
- [ ] Não há notificações/polling/HTMX/WebSocket.
- [ ] FSM não muda.
- [ ] Testes novos passam.
- [ ] Quality gate completo passa.

## Gates de autoavaliação

Responder no relatório:

1. Onde está a regra de negócio principal: service ou view?
2. Qual teste prova que mensagem vazia não é aceita?
3. Qual teste prova que usuário/papel inválido não posta?
4. Qual teste prova que cada post gera evento auditável?
5. Qual teste prova que o médico vê mensagem criada pelo NIR?
6. Qual teste prova que o NIR vê resposta criada pelo médico?
7. Foi implementado polling/notificação/HTMX? Se sim, está fora de escopo.
8. Algum estado FSM foi alterado? Se sim, está errado.

## Relatório obrigatório

Criar relatório temporário, por exemplo:

```text
/tmp/case-operational-communication-mvp-slice-001-report.md
```

O relatório deve conter:

- resumo da implementação;
- arquivos alterados;
- evidência do RED;
- evidência do GREEN;
- snippets antes/depois;
- resultados do quality gate;
- respostas aos gates de autoavaliação;
- justificativa para qualquer arquivo extra tocado.

Responder ao final com:

```text
REPORT_PATH=/tmp/case-operational-communication-mvp-slice-001-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/case-operational-communication-mvp/proposal.md, design.md, tasks.md and slices/slice-001-nir-doctor-case-thread.md.
Implement ONLY Slice 001.
Use TDD: first add failing tests for the case-scoped NIR↔Doctor operational communication thread, then implement the minimal code.
Create CaseCommunicationMessage, a migration, and a domain service in apps/cases/services.py. Add an SSR POST endpoint under /cases/<case_id>/communication/ that validates active_role, rejects blank/too-long messages and CLEANED cases, creates a message, and records CASE_COMMUNICATION_MESSAGE_POSTED.
Add a reusable partial templates/cases/_communication_thread.html and include it in the NIR case detail and doctor decision pages. Messages must show author, role, date/time and body in chronological order. Use safe next redirects.
Do not implement scheduler UI, notifications, polling, HTMX, websocket/SSE, read/unread state, mentions, message attachments, message deletion/editing, or system notices. Do not alter FSM or decision workflows.
Apply clean code, DRY and YAGNI. Keep business logic out of views/templates.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/case-operational-communication-mvp/tasks.md for Slice 001 when complete.
Create /tmp/case-operational-communication-mvp-slice-001-report.md with RED/GREEN evidence, snippets, quality gate results and self-evaluation answers.
Commit and push.
Return REPORT_PATH=<path> and stop.
```
