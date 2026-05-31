# Slice 007: Hardening, auditoria cruzada e quality gate final

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`. Os slices 001–006 devem estar implementados. Este slice não deve abrir uma frente funcional grande; ele consolida, remove inconsistências e valida o change completo.

Leia:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/shared-work-queue-leases/proposal.md`
4. `openspec/changes/shared-work-queue-leases/design.md`
5. todos os slices anteriores e seus relatórios
6. Este arquivo

Implemente **somente este slice** com TDD para qualquer ajuste comportamental encontrado.

## Objetivo do slice

Garantir que a feature esteja consistente de ponta a ponta:

- auditoria de expiração funciona nos três contextos;
- contadores/filas não ficam inconsistentes por locks expirados;
- não há duplicação desnecessária entre doctor/scheduler/intake;
- quality gate completo passa;
- documentação/tasks refletem o estado final.

## Escopo funcional

- Revisar testes cruzados de lock para contextos:
  - `doctor_decision`;
  - `scheduler_confirm`;
  - `nir_receipt`.
- Garantir que `WORK_LOCK_EXPIRED` sempre inclui usuário anterior quando havia `locked_by`.
- Garantir que heartbeats não criam eventos repetitivos.
- Garantir que views de fila expiram locks stale antes de contar/renderizar.
- Revisar `apps/accounts/context_processors.py::queue_counts`, se necessário, para que contagens reflitam filas operacionais após expiração lazy.
- Remover duplicação evidente em helpers de lock-card se houver sem ampliar demais.
- Atualizar `tasks.md` marcando conclusão somente se tudo estiver verde.

## Fora de escopo

- Novas funcionalidades.
- Override admin/manager.
- WebSocket.
- Redis/fila dedicada.
- Reescrever UI.
- Refactor amplo não relacionado.

## Arquivos prováveis

Este slice deve tocar poucos arquivos e somente se necessário:

1. testes em `apps/cases/tests/`, `apps/doctor/tests/`, `apps/scheduler/tests/`, `apps/intake/tests/`
2. `apps/accounts/context_processors.py` se contadores estiverem inconsistentes
3. pequenos ajustes em `apps/cases/services.py` se testes revelarem edge cases
4. `openspec/changes/shared-work-queue-leases/tasks.md`

Se tocar templates/views extensivamente, provavelmente está escapando do escopo; justificar no relatório.

## Plano TDD obrigatório

### RED — caracterização cruzada

Adicionar testes de regressão se ainda não existirem:

1. Expiração em doctor registra usuário anterior.
2. Expiração em scheduler registra usuário anterior.
3. Expiração em NIR registra usuário anterior.
4. Heartbeat renew múltiplo não aumenta quantidade de `CaseEvent` de heartbeat.
5. Release indevido por token errado não limpa lock.
6. Fila/count após lock expirado não trata o caso como bloqueado.
7. NIR compartilhado mostra todos os casos operacionais (`status != CLEANED`) e não mostra casos `CLEANED` na rota operacional.
8. Scheduler continua bloqueado para papel ativo não-scheduler.

### GREEN

Corrigir apenas o necessário para os testes passarem.

### REFACTOR

- Extrair helpers pequenos se houver duplicação clara.
- Não criar abstrações genéricas desnecessárias.
- Preferir nomes explícitos: `build_lock_display`, `is_locked_by_user`, etc.

## Critérios de aceitação

- [ ] Auditoria de expiração contém usuário anterior nos três contextos.
- [ ] Heartbeat não polui timeline.
- [ ] Locks expirados não deixam cards eternamente bloqueados.
- [ ] Contadores globais não ficam claramente errados por locks expirados.
- [ ] Permissões scheduler permanecem corretas.
- [ ] NIR compartilhado mantém a regra aprovada: todos os casos operacionais (`status != CLEANED`) e nenhum caso `CLEANED` na rota operacional.
- [ ] Quality gate completo passa.
- [ ] Todos os slices estão marcados em `tasks.md`.
- [ ] Relatório final consolida evidências.

## Gates de autoavaliação

Responder no relatório:

1. Há alguma duplicação de lock remanescente que deveria virar helper agora?
2. Algum teste prova a auditoria de usuário anterior nos três contextos?
3. O change introduziu dependência nova? Não deveria.
4. Algum estado FSM foi adicionado/alterado? Não deveria.
5. O quality gate completo passou? Se não, qual bloqueio exato?
6. Há recomendações para change futuro?

## Comandos de validação obrigatórios

Neste slice, o quality gate completo é obrigatório, salvo impedimento de infraestrutura explicitamente documentado:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

Também registrar:

```bash
git status --short
```

## Relatório final obrigatório

Criar:

```text
/tmp/ats-web-slice-007-shared-work-queue-leases-closeout-report.md
```

Incluir:

- resumo final do change;
- arquivos alterados neste slice;
- lista dos relatórios dos slices anteriores, se disponíveis;
- evidências de testes/quality gate;
- snippets antes/depois de ajustes finais;
- confirmação dos critérios de aceitação globais;
- riscos residuais;
- recomendações futuras;
- atualização de `tasks.md`;
- commit hash e push.

Resposta final:

```text
REPORT_PATH=/tmp/ats-web-slice-007-shared-work-queue-leases-closeout-report.md
```

Depois pare. Não iniciar novo change sem confirmação.

## Prompt pronto para implementador

```text
Read AGENTS.md, PROJECT_CONTEXT.md and all shared-work-queue-leases OpenSpec files and prior reports.
Implement ONLY Slice 007.
Do not add new product features. Add/adjust tests and small fixes so audit, expiry, permissions, NIR visibility and counts are consistent across doctor/scheduler/NIR. Run the full quality gate. Update tasks.md, create /tmp/ats-web-slice-007-shared-work-queue-leases-closeout-report.md, commit and push, reply REPORT_PATH and stop.
```
