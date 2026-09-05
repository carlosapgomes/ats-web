<!-- markdownlint-disable MD013 -->

# Proposal: Lease de 1 hora para a reserva de caso pelo médico

**Change ID**: `doctor-decision-lock-lease-1h`  
**Risco**: PROFISSIONAL (muda política de concorrência do lock de decisão médica; sem mutação de FSM, schema, auditoria ou permissões; rollback trivial por constante)  
**Dependências**: `apps/cases/services.py` (`claim_case_lock`, `renew_case_lock`, `_get_lease_seconds`), `config/settings/base.py` (`CASE_LOCK_*`), `static/js/work_lock.js` (heartbeat, somente leitura)

## Problema

O lease (tolerância) da reserva de caso é **global**: `CASE_LOCK_LEASE_SECONDS = 300` (5 min) para todos os contextos (`doctor_decision`, `nir_receipt`, `scheduler_confirm`), resolvido por `_get_lease_seconds()` em `apps/cases/services.py`.

O frontend renova a reserva por heartbeat (`work_lock.js`): a cada 60s (`CASE_LOCK_HEARTBEAT_SECONDS`), **somente se houve atividade do usuário nos últimos 240s** (`CASE_LOCK_ACTIVITY_GRACE_SECONDS`). O padrão de uso dos médicos é multitarefa: alternar para o prontuário, laudo ou outra aba por vários minutos. Ao voltar:

- se passaram mais de 4 min sem atividade, o heartbeat parou de renovar;
- com lease de 5 min, a reserva **expira** enquanto o médico ainda considera o caso "aberto";
- outro médico pode capturar o caso (evento `WORK_LOCK_EXPIRED`), e o médico original perde o trabalho em curso quando o renew falha ("Falha ao renovar reserva", submit desabilitado).

As reclamações recebidas são exclusivamente dos médicos; NIR e scheduler não reportaram o problema. A causa confirmada é **lease curto para o padrão multitarefa médico**, não falha do heartbeat.

## Objetivo

1. Resolução de lease **por contexto**: o contexto `doctor_decision` passa a usar `CASE_LOCK_LEASE_SECONDS_DOCTOR = 3600` (1 hora) tanto no claim quanto no renew.
2. Contextos `nir_receipt` e `scheduler_confirm` permanecem em `CASE_LOCK_LEASE_SECONDS = 300`.
3. Override explícito por chamada (`lease_seconds=`, usado por testes com `lease_seconds=0`) continua tendo precedência sobre qualquer setting.
4. Nada muda no frontend: heartbeat de 60s, grace de atividade de 240s, release best-effort na navegação e o guard de submit protegido permanecem intactos.

Efeito esperado: médico que sai até ~1h e volta encontra a reserva ainda válida; o próximo heartbeat a renova por mais 1h sem interrupção.

Trade-off aceito (decisão de produto): a captura de reserva expirada por outro médico (`WORK_LOCK_EXPIRED`) passa a esperar até 1h no contexto médico. Reclamações existentes apontam perda de reserva própria como o problema, não lentidão de takeover.

## Escopo incluído

- `_get_lease_seconds` resolve lease por contexto (mapeamento contexto → setting) com precedência: `lease_seconds` explícito > setting por contexto > `CASE_LOCK_LEASE_SECONDS`.
- `claim_case_lock` e `renew_case_lock` passam o `context` já recebido para a resolução do lease.
- Nova constante `CASE_LOCK_LEASE_SECONDS_DOCTOR = 60 * 60` em `config/settings/base.py`.
- Testes de serviço (resolução por contexto, precedência de override, renew) e um teste de integração da view médica (claim via GET da página de decisão estabelece `locked_until ≈ now + 1h`).
- Nova spec de capacidade `case-work-lock` (delta `ADDED`).

## Fora de escopo

- Alterar `CASE_LOCK_HEARTBEAT_SECONDS`, `CASE_LOCK_ACTIVITY_GRACE_SECONDS` ou qualquer JS/CSS/template.
- Alterar FSM, eventos de auditoria, modelos, migrations, URLs, permissões ou intranet guard.
- Lease por usuário, por prioridade de caso ou configurável por env var.
- UI de "quem segura o caso"/contato ao titular do lock.
- Alterar contexts `nir_receipt`/`scheduler_confirm` ou seus tempos.

## Dimensionamento em slices

O change terá **um único slice vertical**.

A resolução de lease vive em um único ponto (`_get_lease_seconds`) consumido por claim e renew; a prova vertical (view médica) usa a mesma resolução. Separar serviço e view seria horizontal com estado intermediário sem valor. O slice prevê 4 arquivos funcionais.

## Sucesso

- Médico abre a página de decisão de um caso `WAIT_DOCTOR` → `locked_until ≈ now + 1h`.
- Heartbeat renova para `now + 1h` a cada batida válida.
- NIR e scheduler continuam com `locked_until ≈ now + 5 min`.
- `lease_seconds` explícito continua vencendo (testes existentes com `lease_seconds=0` seguem verdes).
- Quality gate completo do `AGENTS.md` passa.
