# Proposal: Conjunto detectado normalizado para seleção válida

## Problema

Caso real de produção (2026-09-26, `v0.10.0-rc.1`): o painel NIR de correção
exibiu `Tipo detectado: EDA + EDA + Dilatação` — combinação impossível, fora
do catálogo selecionável — e a correção do NIR para `EDA + Dilatação` não
desfez a revisão. Causas confirmadas (relatório
`.pi/reports/detected-set-normalization-investigation-2026-09-26.md`):

1. o gate de conflito devolve `detected = any_set ∪ conflicting_set` (base +
   pacote que já contém a base) **antes** da precedência e da matriz
   (`procedure_reconciliation.py:481-495`);
2. o label do card concatena labels por identidade, duplicando a base
   (`views.py:191-209`);
3. o gate é **cego ao declarado** — a correção preserva o texto imutável,
   re-executa o LLM1 e a revisão re-firma indefinidamente. O caso não tem
   saída clínica pela UI (só encerramentos que perdem o agendamento).

O comportamento é contrato vigente (spec + design + ~10 testes pinados), com
tensão normativa entre `procedure-neutral-analysis` (union no detectado) e
`procedure-combination-policy` (matriz fechada "após reconciliação").

## Objetivo

Implementar o princípio do operador: **o sistema encaixa o que detectou nas
combinações POSSÍVEIS — nunca exibe nem decide por combinação inexistente —
com heurística de cobertura máxima** (a opção válida mais completa que cobre a
detecção), e a **correção humana para essa opção resolve o conflito**:

1. função pura `best_covering_selection()` (absorve base no pacote; sentinela
   `invalid` quando nenhuma combinação cobre — fail-closed preservado);
2. gate de conflito declarado-aware: `declared == best-covering ⇒ proceed`
   (primeira passada divergente continua fail-closed);
3. evento de auditoria preserva o union bruto; payload de revisão/correção
   carrega o normalizado;
4. card exibe o conjunto sem duplicação de base.

## Escopo

- `apps/cases/procedures.py` (helper novo), `apps/pipeline/
  procedure_reconciliation.py` (gate + payload), `apps/pipeline/orchestrator.
  py` (evento bruto permanece), `apps/intake/views.py` (label).
- Deltas: `procedure-neutral-analysis` (requisito do gate), `exam-type-
  correction` (resolução por best-covering), `procedure-combination-policy`
  (matriz aplica-se ao conjunto normalizado na decisão/exibição).
- ADR-0011 (Proposed; aceite é pré-condição).

### Fora de escopo

- Classificação de seções de detecção (Complemento da Solicitação) — change
  separado `solicitation-complement-as-current-request`.
- Mudanças em precedências de detecção automática (ADR-0008/0010 dec.4
  permanecem: colapso de base na detecção continua exigindo ocorrência
  atual).
- Writers/schemas LLM, prompts, matriz de combinações, FSM, filas/analytics.

## Sucesso

- Reprodução do caso real (fixture sintética): Motivo EDA + dilatação
  não-atual + item estruturado → revisão na 1ª passada; correção NIR para
  `eda_dilation` → **prossegue ao médico** (regressão do beco sem saída;
  condicionada à reprodução do item pelo LLM1 no mesmo texto — risco
  registrado na ADR).
- Coincidência sem evidência atual (negação/histórico com declaração igual)
  permanece em revisão (guardas de cápsula negada/histórica e reto).
- Card nunca exibe combinação impossível; par válido no payload inalterado.
- `{eda_capsule, eda_dilation}` e afins continuam fail-closed (revisão).
- Evento de auditoria carrega o union bruto em todos os desfechos.
- Gate final verde (ruff/format/mypy/pytest + node quando aplicável).
