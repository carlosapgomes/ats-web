<!-- markdownlint-disable MD013 -->

# Design: Lease por contexto para a reserva de caso

## D1. Onde a resolução acontece

**Decisão: dentro de `apps/cases/services.py`, estendendo `_get_lease_seconds`.** O `context` já é parâmetro obrigatório de `claim_case_lock` e `renew_case_lock` (e já é persistido em `Case.lock_context`), portanto a resolução centralizada não altera nenhuma assinatura de view.

Assinatura proposta:

```python
_CONTEXT_LEASE_SETTINGS: dict[str, str] = {
    "doctor_decision": "CASE_LOCK_LEASE_SECONDS_DOCTOR",
}

def _get_lease_seconds(override: int | None = None, context: str | None = None) -> int:
    if override is not None:
        return override
    if context is not None:
        setting_name = _CONTEXT_LEASE_SETTINGS.get(context)
        if setting_name is not None:
            return getattr(settings, setting_name)
    return getattr(settings, "CASE_LOCK_LEASE_SECONDS", 300)
```

Precedência: **override explícito > setting por contexto > setting global**. Os dois call sites existentes (`seconds = _get_lease_seconds(lease_seconds)` em `claim_case_lock` e em `renew_case_lock`) passam a incluir `context=context`.

Alternativas rejeitadas:

- **Bump global para 1h**: um NIR/scheduler que abandona a página seguraria o caso por 1h antes de outro operador poder capturar; a reclamação é exclusivamente médica.
- **Passar `lease_seconds` nas views médicas**: espalharia política de tempo pela camada de apresentação (viola o `AGENTS.md`: lógica de negócio em services) e o renew exigiria a mesma repetição.
- **Dict de settings completo** (`CASE_LOCK_LEASE_SECONDS_BY_CONTEXT`): mais flexível do que o necessário (YAGNI); mapeamento em código com constante nomeada é suficiente e tipa bem para mypy.

## D2. Semântica do renew com lease maior

`renew_case_lock` hoje estende `locked_until = now + lease`. Com `doctor_decision` resolvendo 3600s, cada heartbeat válido estende para `now + 1h` — o médico ativo mantém a reserva indefinidamente, como já ocorre hoje com 5 min. O behavior de erro (renew de lock expirado falha e o JS desabilita o submit) é inalterado.

## D3. Interação com heartbeat/grace (por que 1h resolve)

`work_lock.js` renova a cada 60s apenas se houve atividade < 240s. Hoje: 4 min de inatividade param o renewal e o lease morre em ≤ 5 min. Com lease de 1h: médico inativo por até ~59 min ainda tem reserva válida; ao voltar, o primeiro tick de heartbeat (≤ 60s) renova antes do vencimento. Timers de aba em background são throttled pelo browser, mas qualquer retorno à aba dispara `focus`/atividade e o `setInterval` retoma — a janela de 1h dá margem suficiente para o padrão multitarefa relatado.

`CASE_LOCK_ACTIVITY_GRACE_SECONDS` (240s) **não** muda: grace maior faria renovação sem usuário presente.

## D4. Trade-off de takeover e rollback

- Takeover de reserva médica expirada por outro médico (`WORK_LOCK_EXPIRED`) passa a requerer 1h de abandono. Aceito: nenhuma reclamação de takeover lento; reclamações são de perda de reserva própria.
- Release best-effort no submit/navegação e o guard `ATS_WORK_LOCK_SUBMITTING` permanecem, então o caso bem encerrado não espera lease expirar.
- Rollback: remover a entrada do mapping ou redefinir a constante — sem migration, reversível em um deploy.

## D5. Settings

Em `config/settings/base.py`, imediatamente abaixo de `CASE_LOCK_LEASE_SECONDS`:

```python
# Per-context lease overrides (seconds). Falls back to CASE_LOCK_LEASE_SECONDS.
CASE_LOCK_LEASE_SECONDS_DOCTOR = 60 * 60
```

Constante de settings (não env var), seguindo o padrão das irmãs `CASE_LOCK_*`.

## D6. Testes

- Serviço (`apps/cases/tests/test_lock_service.py`), com `django.test.override_settings`:
  1. claim `context="doctor_decision"` → `locked_until - now` ≈ 3600s;
  2. claim `context="nir_receipt"` → ≈ 300s (global preservado);
  3. claim `context="doctor_decision", lease_seconds=120` → ≈ 120s (override vence);
  4. claim `context="scheduler_confirm"` → ≈ 300s;
  5. renew `context="doctor_decision"` estende para ≈ now + 3600s.
- Integração da view (`apps/doctor/tests/test_views.py`): GET na página de decisão → `Case.locked_until - timezone.now()` dentro de [3500, 3600]s.
- Tolerância: comparar com delta de segundos (estilo `timedelta` já usado no arquivo), não igualdade exata.
