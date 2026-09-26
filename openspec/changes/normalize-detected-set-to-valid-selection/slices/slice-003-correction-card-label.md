# Slice 003 — Label do card de correção sem duplicação de base

## Objetivo

O card NIR "Correção de Tipo de Exame" nunca mais exibe combinação
impossível: o label do "Tipo detectado" renderiza o conjunto do payload
(payload já normalizado pelo Slice 002) aplicando a regra anti-duplicação da
ADR-0011 D4 — base contida em pacote não é listada separadamente; pacotes
distintos juntam-se com " e ".

Pré-requisito: Slices 001 e 002 mergeados (payload normalizado).

## Contexto necessário

- `apps/intake/views.py` — `_correction_detected_label` `:191-209` (join
  cego em `:207`; docstring exige que nunca levante); injeção no contexto
  `:914`.
- `templates/intake/case_detail.html:379-381` — "Tipo detectado" +
  `correction_form_context.detected_exam_type_label`.
- `apps/cases/models.py:62-65` — labels: `EDA="EDA"`,
  `EDA_DILATION="eda_dilation","EDA + Dilatação"` (todos os pacotes começam
  pela label da base).
- `design.md` deste change: D4 (regra exata de renderização).
- ADR-0011 item 4.

## Requisitos verificáveis

- **R1** — `_correction_detected_label` aplica: (a) identidade-base contida
  em ao menos um pacote presente NÃO é listada separadamente; (b)
  identidades/pacotes restantes juntam-se com `" + "`; (c) quando dois ou
  mais PACOTES completos restam (conjunto inválido exibido como evidência),
  eles juntam-se com `" e "` (ex.: `EDA + Cápsula e EDA + Dilatação`).
- **R2** — Casos pinados por teste: `["eda","eda_dilation"]` →
  `EDA + Dilatação`; `["eda_dilation"]` → `EDA + Dilatação`; `["eda"]` →
  `EDA`; `["eda","eda_capsule","eda_dilation"]` → `EDA + Cápsula e EDA +
  Dilatação`; `["colonoscopy","rectosigmoidoscopy_dilation"]` →
  `Colonoscopia + Retossigmoidoscopy + Dilatação` (base reto absorvida pelo
  pacote; sem "e" porque há um só pacote); valores desconhecidos seguem
  exibidos como hoje (fallback do código cru).
- **R3** — A função continua nunca levantando (docstring/contrato).
- **R4** — Teste de card (view/template) além do unit test: no cenário de
  revisão por conflito com payload normalizado, o HTML renderiza o label sem
  duplicação (estende um teste existente de card em
  `apps/intake/tests/test_exam_type_correction.py`).

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/intake/views.py
  - apps/intake/tests/test_exam_type_correction.py
  - apps/intake/tests/test_correction_detected_label.py   # unit tests R1-R3 (novo; ajustar ao layout real)

allowed_incidental_files: []

out_of_scope:
  - pipeline/payload (slices anteriores), templates, CSS/combobox
  - queues/analytics
```

Escalar ao parent se: a regra de renderização colidir com outro consumidor
do label; se um template precisar mudar.

## Matriz requisito -> arquivo -> teste/check

| Requisito | Arquivo(s) | Teste/check |
| --- | --- | --- |
| R1-R3 | `apps/intake/views.py` | `test_correction_detected_label.py` (parametrizado) |
| R4 | `test_exam_type_correction.py` | teste de card estendido |

## Plano de testes do slice

### RED

- `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/intake/tests/test_correction_detected_label.py -q`
  — falha esperada: `["eda","eda_dilation"]` ainda produz `EDA + EDA + Dilatação`.

### GREEN / verificação local

- O mesmo comando → exit 0 (todos os casos de R2).
- `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/intake/tests/test_exam_type_correction.py -q` → exit 0.
- `uv run ruff check apps/intake && uv run ruff format --check apps/intake/views.py apps/intake/tests/test_correction_detected_label.py apps/intake/tests/test_exam_type_correction.py` → exit 0.
- `uv run mypy apps/intake` → exit 0.

Suíte completa NÃO roda neste slice (gate final do change).

## Critérios de aceitação

- [ ] R1-R4 verdes com os comandos acima (exit 0).
- [ ] Nenhum label de combinação impossível produzido pelos casos de R2.
- [ ] Função segue total (nunca levanta).
- [ ] Blast radius dentro do `expected_files`.

## Contrato de handoff

Worker com contexto fresco: leia `design.md` (D4) e a ADR-0011 item 4 antes
de editar. TDD RED→GREEN→REFACTOR. Não toque em `tasks.md`, não commit/push.
Reviewer: BEHAVIOR/TESTS/SCOPE/DESIGN; P2 isolado não reabre ciclo.
