# Slice 003: Médico — heartbeat, idle detection e release

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`, monolito Django SSR com Bootstrap, HTMX e Vanilla JS. O slice anterior deve ter implementado lock básico médico e serviço de lock em `apps/cases/services.py`.

Leia antes de codar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/shared-work-queue-leases/proposal.md`
4. `openspec/changes/shared-work-queue-leases/design.md`
5. `openspec/changes/shared-work-queue-leases/slices/slice-002-doctor-basic-lease.md`
6. Este arquivo

Implemente **somente este slice** com TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Tornar a reserva médica robusta para trabalho humano real:

```text
Médico abre caso
→ lock inicial curto é adquirido
→ enquanto houver atividade recente na tela, heartbeat renova lock
→ se usuário abandonar a tela, heartbeat para e lock expira
→ ao fechar/navegar, frontend tenta liberar lock imediatamente
```

## Escopo funcional

- Adicionar/usar `renew_case_lock` no serviço centralizado.
- Criar endpoints médicos de renew/release.
- Criar Vanilla JS compartilhável para heartbeat e idle detection.
- Integrar JS na tela de decisão médica.
- Exibir feedback mínimo de status de reserva.
- Não registrar evento a cada heartbeat.
- Registrar `WORK_LOCK_RELEASED` quando release explícito ocorrer.

## Fora de escopo

- Aplicar heartbeat ao scheduler ou NIR.
- Criar framework JS.
- Adicionar dependências externas.
- WebSocket.
- Mudança de FSM.

## Arquivos prováveis

1. `apps/cases/services.py`
2. testes de serviço
3. `apps/doctor/views.py`
4. `apps/doctor/urls.py`
5. testes de doctor endpoints
6. `templates/doctor/decision.html`
7. `static/js/work_lock.js`
8. `openspec/changes/shared-work-queue-leases/tasks.md` ao final

Se tocar `config/settings/base.py` para settings de tempo, justifique e teste defaults.

## Plano TDD obrigatório

### RED — serviço

Testes para `renew_case_lock`:

1. Renova lock válido do mesmo user+token+context, estendendo `locked_until`.
2. Não renova lock expirado.
3. Não renova com token errado.
4. Não renova para usuário errado.
5. Não cria `CaseEvent` repetitivo de heartbeat.

Testes para release:

1. Release com user+token+context válidos limpa campos de lock.
2. Release com token errado não limpa lock de outro token.
3. Release válido cria `WORK_LOCK_RELEASED` uma única vez.

### RED — endpoints médicos

1. POST renew com token válido retorna JSON sucesso.
2. POST renew com token inválido retorna erro apropriado e não altera lock.
3. POST release com token válido limpa lock.
4. Endpoints exigem papel ativo doctor.
5. Endpoints exigem POST.

### RED — template/JS

Testar renderização do template contendo configuração necessária para o JS:

- URL de renew;
- URL de release;
- token;
- intervalos.

Não é obrigatório testar comportamento JS no browser se o projeto não tiver harness de JS. Teste presença dos atributos/scripts essenciais.

## GREEN — implementação mínima

### Serviço

Implementar `renew_case_lock` e robustecer `release_case_lock` se necessário.

### Settings

Adicionar defaults, se ainda não existirem:

```python
CASE_LOCK_LEASE_SECONDS = 5 * 60
CASE_LOCK_HEARTBEAT_SECONDS = 60
CASE_LOCK_ACTIVITY_GRACE_SECONDS = 4 * 60
```

### Endpoints

Em `apps/doctor/urls.py`, adicionar rotas POST simples:

```text
<uuid:case_id>/lock/renew/
<uuid:case_id>/lock/release/
```

Views retornam `JsonResponse`, protegidas por `@login_required` e `@role_required("doctor")`.

### Vanilla JS

Criar `static/js/work_lock.js` sem dependências.

Comportamento esperado:

- ler configuração de um elemento ou `data-*` no template;
- monitorar eventos de atividade humana;
- `setInterval` envia renew apenas se atividade recente;
- `pagehide` tenta release via `navigator.sendBeacon` ou `fetch(..., keepalive: true)`;
- ao erro de renew, exibir aviso em elemento dedicado e desabilitar submit se apropriado.

Manter JS pequeno e específico. Não criar classe complexa se funções simples bastarem.

## Critérios de aceitação

- [ ] Lock médico é renovado por heartbeat enquanto houver atividade recente.
- [ ] Lock não é renovado indefinidamente se usuário abandonar aba sem atividade.
- [ ] Release explícito tenta limpar lock ao sair da tela.
- [ ] Renew/release exigem user+token+context corretos.
- [ ] Heartbeat não gera eventos de auditoria repetitivos.
- [ ] Release gera auditoria útil sem poluir timeline.
- [ ] Nenhuma dependência JS adicionada.
- [ ] Testes do slice passam.

## Gates de autoavaliação

Responder no relatório:

1. Como o JS detecta atividade humana?
2. Qual é a garantia real quando navegador fecha sem release?
3. Heartbeat cria `CaseEvent`? Deve criar?
4. Endpoints aceitam GET? Devem aceitar?
5. O JS é reaproveitável para scheduler/NIR sem virar framework genérico?

## Comandos de validação mínimos

```bash
uv run pytest apps/cases/tests apps/doctor/tests -q
uv run ruff check apps/cases apps/doctor static/js/work_lock.js
uv run ruff format --check apps/cases apps/doctor
uv run mypy apps/cases apps/doctor
```

Quality gate completo, se possível:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório final obrigatório

Criar:

```text
/tmp/ats-web-slice-003-doctor-heartbeat-release-report.md
```

Incluir:

- resumo;
- arquivos alterados;
- snippets antes/depois;
- detalhes do protocolo renew/release;
- estratégia de idle detection;
- testes;
- comandos executados;
- atualização de `tasks.md`;
- commit hash e push.

Resposta final:

```text
REPORT_PATH=/tmp/ats-web-slice-003-doctor-heartbeat-release-report.md
```

Pare e peça confirmação explícita antes do próximo slice.

## Prompt pronto para implementador

```text
Read AGENTS.md, PROJECT_CONTEXT.md and the shared-work-queue-leases OpenSpec files through Slice 003.
Implement ONLY Slice 003 using TDD.
Add renew/release support for doctor locks, POST JsonResponse endpoints, and a small Vanilla JS heartbeat with idle detection. Renew only with recent activity. Release on pagehide as best effort. Do not add dependencies, do not implement scheduler/NIR, and do not log heartbeat events.
Run validations, update tasks.md, create /tmp/ats-web-slice-003-doctor-heartbeat-release-report.md, commit and push, then reply REPORT_PATH and stop.
```
