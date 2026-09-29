# Slice 001: Script tags das filas via `{% static %}`

## 1. Objetivo

As duas filas passam a referenciar seus JS via `{% static 'js/…' %}` (com
`{% load static %}`), de modo que em produção as URLs carreguem o hash do
manifest e cada deploy sirva HTML+JS consistentes. Comportamento de filtro
inalterado.

## 2. Contexto necessário

Ler antes de editar (mínimo suficiente):

- `templates/scheduler/queue.html` — só o bloco `extra_js` (`:72-74`).
- `templates/doctor/queue.html` — só o bloco `extra_js` (`:100-102`).
- `templates/scheduler/confirm.html:1-2,230-231` — o padrão a replicar
  (`{% extends %}` + `{% load static %}` + `{% static 'js/…' %}`).
- `config/settings/prod.py:31-40` — confirma o manifest storage em prod
  (leitura; **não alterar**).
- Restrições: `AGENTS.md` (TDD quando aplicável; `uv`; sem vocabulário CSS novo).

## 3. Requisitos verificáveis

- **R1.** `templates/scheduler/queue.html` referencia o JS via
  `{% static 'js/scheduler_queue_filter.js' %}`, sem URL hardcoded; `{% load
  static %}` presente no arquivo.
- **R2.** `templates/doctor/queue.html` idem com `doctor_queue_filter.js`.
- **R3.** Nenhuma outra referência hardcoded `src="/static/` ou
  `href="/static/` restante em `templates/` (grep comprova).
- **R4.** As páginas das filas continuam renderizando 200 nos testes existentes
  (nenhum `TemplateSyntaxError`, nenhum regressão de fila).

## 4. Escopo e expected blast radius

```yaml
expected_files:
  - templates/scheduler/queue.html
  - templates/doctor/queue.html

allowed_incidental_files:
  - apps/scheduler/tests/test_exam_type_filters.py  # só se precisar de assert novo
  - apps/doctor/tests/test_queue_exam_type_filters.py  # só se precisar de assert novo

out_of_scope:
  - settings, storage, WhiteNoise, Cloudflare, views, lógica JS, CSS, FSM, migrations, prompts
```

Na prática espera-se diff em **só os 2 templates**; asserts novos são
opcionais e só nos 2 arquivos de teste listados. Escalar em vez de ampliar se:

- precisar mudar settings/storage para o teste passar;
- qualquer teste de fila quebrar por causa da tag (investigar antes de tocar o teste);
- surgir necessidade de versionar outros estáticos além dos 2 (há evidência de
  que são os únicos — revalidar com grep).

## 5. Plano de testes do slice

### Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
|---|---|---|
| R1–R2 | 2 templates | asserts de `{% static 'js/…_filter.js' %}` + ausência de `src="/static/js/…_filter.js"` |
| R3 | `templates/` | `grep -rn 'src="/static/\|href="/static/' templates/ \| wc -l` → 0 |
| R4 | suítes de fila | `uv run pytest apps/scheduler/tests/test_exam_type_filters.py apps/doctor/tests/test_queue_exam_type_filters.py -q` |

### RED

- Comando: teste novo/atualizado que afirma `{% static 'js/scheduler_queue_filter.js' %}`
  (e doctor) presente no template-fonte — falha contra o `src` hardcoded atual.
- Alternativa aceita: demonstrar via `grep` que os hardcoded existem antes e
  somem depois (registrar saídas).

### GREEN / verificação local

- `POSTGRES_TEST_HOST_PORT=55433 uv run pytest
  apps/scheduler/tests/test_exam_type_filters.py
  apps/doctor/tests/test_queue_exam_type_filters.py -q` → exit 0.
- `uv run ruff check` nos Python tocados (se algum) → exit 0.
- `git diff --name-only` → só arquivos previstos.

## 6. Critérios de aceitação

- [ ] R1: scheduler via `{% static %}`, sem hardcoded.
- [ ] R2: doctor via `{% static %}`, sem hardcoded.
- [ ] R3: grep de hardcoded em `templates/` → 0.
- [ ] R4: testes das duas filas verdes.

## 7. Contrato de handoff

Worker com contexto fresco implementa só este slice via `/slice-loop`. Não
mudar lógica JS, settings ou outros templates; não atualizar `tasks.md`, não
commitar. Reviewer verifica BEHAVIOR/TESTS/SCOPE/DESIGN com veredito
`OK`/`BLOCK`.
