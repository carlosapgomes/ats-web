<!-- markdownlint-disable MD013 -->

# QUICK fix de UI: contraste do botão "Atenção necessária" no dashboard

## Status

- [x] Concluído

> Executado via loop parent-controlled (worker + reviewer pi-subagents, contexto
> fresh) em 2026-09-05. Veredito do reviewer: `Merge verdict: OK with notes`
> (0 P0, 0 P1, 3 P2 report-only). Relatório com evidências inline na sessão do
> parent; protocolo de commit/push executado pelo parent conforme o loop.

## Classificação e justificativa

- **Tipo:** QUICK fix simples e reversível (apresentação: classes CSS + template).
- **Risco:** baixo; um único botão do dashboard, sem lógica, sem backend, sem FSM.
- **Design separado:** dispensado pela exceção QUICK do `AGENTS.md`.
- **Problema de acessibilidade concreto:** o botão inativo usa `btn-outline-warning` do Bootstrap 5.3 — texto/borda `#ffc107` sobre fundo branco ≈ **1.9:1** de contraste (WCAG 2.1 AA exige ≥ 4.5:1 para texto normal). Usuário reportou "amarelo muito claro, quase ilegível em fundo branco". O estado ativo (`btn-warning`, fundo `#ffc107`) também é percebido como claro demais.

## Handoff para implementador LLM com contexto zero

Este projeto é um monolito Django SSR com Bootstrap 5.3 e CSS customizado em `static/css/app.css`. Leia integralmente, antes de editar:

1. `AGENTS.md` e `PROJECT_CONTEXT.md`
2. este arquivo: `tasks/quick-ui-attention-button-contrast.md`
3. `static/css/app.css` — variáveis `:root` (~linha 8-21, já existe `--hospital-warning: #b05b0c`) para reutilizar o token, e a seção de estilos do dashboard para posicionar as novas classes
4. `templates/dashboard/index.html` — o link "⚠ Atenção necessária" (~linha 288), único ponto a alterar
5. `apps/dashboard/tests/test_dashboard.py` — teste existente do link de atenção (~linha 2954) que será fortalecido
6. `apps/dashboard/views.py` — somente leitura, para entender `attention_filter` e `attention_count` (não alterar)

### Estado técnico atual

```django
<a href="..." class="btn btn-sm {% if attention_filter %}btn-warning{% else %}btn-outline-warning{% endif %}">
  ⚠ Atenção necessária ... </a>
```

Amarelo padrão do Bootstrap (`#ffc107`) em ambos os estados. O projeto já possui o âmbar hospitalar escuro `--hospital-warning: #b05b0c` (contraste ≈ **4.8:1** sobre branco e com texto branco sobre ele — passa WCAG AA), usado em `.waiting-time` e na timeline.

### Correção esperada (decisão aprovada pelo usuário)

Substituir as classes Bootstrap por classes próprias com o âmbar hospitalar:

- estado ativo: `btn-attention` — fundo `var(--hospital-warning)`, texto `#ffffff`, borda `var(--hospital-warning)`;
- estado inativo: `btn-attention-outline` — fundo transparente, texto e borda `var(--hospital-warning)`;
- hover/focus em ambos: escurecer o fundo (ex.: `#93490a`) mantendo texto branco, garantindo contraste ≥ 4.5:1;
- manter `btn btn-sm` (espaçamento/tamanho) e todo o `href`/query string **intocados**.

## Protocolo obrigatório para o implementador

**Se qualquer item obrigatório falhar ou não tiver evidência, o fix está INCOMPLETO. Não marque o status acima, não faça commit/push e reporte o bloqueio.**

1. Antes de editar: `git status --short` (árvore limpa, exceto as deleções pré-existentes não relacionadas em `.pi/skills/`), crie a branch `quick/attention-button-contrast` a partir do `main` atualizado e registre `BASE_REF=$(git rev-parse HEAD)`.
2. Rode o baseline `uv run pytest` e registre exit code/totais. Baseline vermelho → pare antes de codar.
3. Escreva a matriz `Requisito → arquivo(s) → teste/check` no relatório.
4. TDD real: RED primeiro (teste fortalecido falhando porque as classes novas não existem), GREEN mínimo depois.
5. Execute o check determinístico de contraste (abaixo), as inspeções e o quality gate completo, interpretando cada resultado no relatório.
6. Compare o pytest final com o baseline: exit code 0, zero failures/errors e `passed_final >= passed_baseline`.
7. Somente após todos os gates: marque este arquivo como concluído, gere o relatório, commit claro, push da branch, responda com `REPORT_PATH` e pare.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 classes acessíveis no template | `templates/dashboard/index.html` | teste fortalecido: `btn-attention` presente e `btn-outline-warning`/`btn-warning` ausentes no link |
| R2 CSS com token hospitalar e estados hover/focus | `static/css/app.css` | check `rg -n "btn-attention" static/css/app.css` + cálculo de contraste |
| R3 contraste WCAG AA ≥ 4.5:1 | — | cálculo determinístico (comando abaixo) com os valores usados |
| R4 sem expansão | — | `git diff --stat` limitado aos 3 arquivos previstos |

## RED

- Comando: `uv run pytest apps/dashboard/tests/test_dashboard.py -k "attention_link" -x`
- Fortaleça o teste existente do link de atenção (~linha 2954) para exigir: `"btn-attention" in content` **e** `"btn-outline-warning" not in content` (e `btn-warning` ausente como classe isolada do link — verifique o template renderizado dos dois estados: com e sem `attention=1`).
- Falha esperada: asserção falha porque o template ainda renderiza `btn-outline-warning`/`btn-warning`. RED por import/fixture não conta.

## GREEN / verificação local

- `uv run pytest apps/dashboard/tests/test_dashboard.py -k "attention_link"` — exit code 0.
- `uv run pytest apps/dashboard/tests/test_dashboard.py` — exit code 0.
- `uv run ruff check . && uv run ruff format --check .` (CSS/template não são cobertos pelo ruff; rodar mesmo assim para o diff geral) — exit code 0.
- Check determinístico de contraste (use os valores hex efetivamente usados no CSS; para `#b05b0c` vs `#ffffff` e para o hover escolhido):

```bash
python3 - <<'PY'
def lum(h):
    c=[int(h[i:i+2],16)/255 for i in (0,2,4)]
    c=[x/12.92 if x<=0.03928 else ((x+0.055)/1.055)**2.4 for x in c]
    return 0.2126*c[0]+0.7152*c[1]+0.0722*c[2]
def ratio(a,b):
    la,lb=sorted((lum(a),lum(b)),reverse=True)
    return (la+0.05)/(lb+0.05)
print("texto/fundo ativo #b05b0c vs #ffffff:", round(ratio("b05b0c","ffffff"),2))
print("hover #93490a vs #ffffff:", round(ratio("93490a","ffffff"),2))
PY
```

Resultado esperado: ambos ≥ 4.5 (≈ 4.8 para `#b05b0c`). Registre os números no relatório; se algum par ficar < 4.5, ajuste o tom antes de prosseguir.
- Inspeção: `rg -n "btn-outline-warning|btn-warning" templates/dashboard/index.html` deve retornar apenas usos fora do link de atenção, se existirem (interprete; o alvo é o link "⚠ Atenção necessária").

## Quality gate completo

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

## Objetivo vertical

```text
Manager/admin abre /dashboard/
→ botão "⚠ Atenção necessária" legível em fundo branco (âmbar hospitalar, AA)
→ estado ativo e inativo distinguíveis
→ hover/focus com feedback e contraste mantido
→ sem mudança de href, contadores, filtros ou backend
```

## Requisitos funcionais

### R1. Template usa classes acessíveis

O link "⚠ Atenção necessária" usa `btn btn-sm btn-attention` (ativo) / `btn btn-sm btn-attention-outline` (inativo), sem `btn-warning`/`btn-outline-warning`. Nenhum atributo além de `class` muda.

### R2. CSS com o token do design system

`.btn-attention` e `.btn-attention-outline` definidos em `static/css/app.css` usando `var(--hospital-warning)`, com hover/focus escurecidos (ex.: `#93490a`) e texto branco; sem `!important` e sem alterar outras regras existentes.

### R3. Contraste WCAG AA

Todos os pares texto/fundo dos estados (repouso, ativo, hover/focus) ≥ 4.5:1, comprovado pelo cálculo determinístico no relatório.

### R4. Sem expansão

Diff limitado a `templates/dashboard/index.html`, `static/css/app.css`, `apps/dashboard/tests/test_dashboard.py`. Nenhum outro botão, componente ou página é alterado.

## Out of scope

- Auditar/alterar outros usos de cores de alerta no sistema, dark mode, novos componentes, mudar o texto/ícone/contagem do botão, alterar views/JS/URLs.
