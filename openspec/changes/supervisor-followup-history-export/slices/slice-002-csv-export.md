# Slice 002 — Exportação CSV do Histórico

## Objetivo

Comportamento observável: na página Histórico, um botão **Exportar CSV** baixa `GET /dashboard/follow-ups/history/export/` — resposta `text/csv; charset=utf-8` com BOM, separador `;`, header em português, uma linha por desfecho de procedimento da versão corrente (janela/busca já suportados no Slice 001; aqui também `performed/reason/admitted` se o Slice 003 já estiver aplicado — contratos idênticos), nome de arquivo `followups_<start>_<end>.csv`. Sem papel → bloqueado. Nenhum `CaseEvent` criado.

## Contexto necessário (ler antes de editar)

- Slice 001 aplicado: view `followup_history` + helpers que compõem a população/linhas (reaproveite a MESMA composição — a exportação não pode divergir da página; extraia/refatore helper compartilhado se o Slice 001 o deixou inline).
- `apps/dashboard/urls.py` (rota `followup_history` como referência de nome/estilo).
- `templates/dashboard/followup_history.html` (onde entra o botão, dentro do form de filtros para herdar os params via querystring).
- Padrões de resposta no projeto: views usam `HttpResponse`/`render`; não há CSV prévio — este slice introduz o primeiro export (design **D5**).
- Python: módulo `csv` com `io.StringIO` (BOM prefixado na string final) e `delimiter=";"` — escaping de `;`, aspas e quebras é automático; NÃO concatenar campos manualmente.
- Design: seção **D5** (contrato completo do CSV) de `../design.md`.

## Requisitos verificáveis

- **R1** — Rota `followup_history_export` em `apps/dashboard/urls.py`; view `@role_required("manager", "admin")` que responde 200 com `Content-Type: text/csv; charset=utf-8`, `Content-Disposition: attachment; filename="followups_<start>_<end>.csv"` (datas da janela ATIVA — default inclusa — no formato `YYYYMMDD`).
- **R2** — Corpo: BOM `\ufeff` no início; header único com colunas exatas nesta ordem: `Case ID;Ocorrência;Paciente;Data;Procedimento;Desfecho;Causa;Submotivo;Outra causa (texto);Internação;Versão;Registrado por;Registrado em`.
- **R3** — 1 linha por desfecho de procedimento da versão corrente, MESMA população/ordem/filtros da página (`start/end/q` — e `performed/reason/admitted` quando presentes; valores inválidos ignorados igual à página); conteúdo com labels humanos: `Realizado`/`Não realizado`, labels das choices de causa/submotivo/procedimento, internação canônica `Sim`/`Não`, datas `dd/mm/yyyy` e `dd/mm/yyyy hh:mm` locais, autor `author_label`. **O CSV exporta TODAS as linhas da população filtrada, ignorando `?page=`** (tabela pagina em 25; CSV nunca truncado).
- **R7** — Guard do export: `manager`/`admin` recebem 200; anônimo e papéis sem acesso (`nir`, `scheduler`) são bloqueados SEM conteúdo de follow-up no corpo.
- **R4** — Escaping: campo de texto com `;`, aspas e quebra de linha permanece em UMA célula (CSV parseável; teste re-parseia com `csv.reader` delimitador `;` e confere colunas/valores).
- **R5** — Sem efeitos colaterais: nenhum `CaseEvent` criado pela exportação (contagem antes/depois inalterada).
- **R6** — Botão **Exportar CSV** na página Histórico, dentro do form de filtros (herda a querystring corrente), estilizado `btn btn-sm btn-outline-primary`.

## Matriz requisito → arquivo(s) → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `apps/dashboard/urls.py`, `apps/dashboard/views.py` | `pytest apps/dashboard/tests/test_followup_history.py -k export_content_type` (novo) |
| R7 | `apps/dashboard/views.py` | `... -k "export_role or export_anonymous"` (novo: anônimo + `nir`/`scheduler` bloqueados; `manager`/`admin` 200) |
| R2 | `apps/dashboard/views.py` | `... -k export_header` (novo) |
| R3 | `apps/dashboard/views.py` (+helper compartilhado) | `... -k "export_rows or export_labels or export_filters"` (novo) |
| R3 (paginação) | `apps/dashboard/views.py` | `... -k export_ignores_pagination` (novo: população com >25 linhas → CSV com `?page=2` é IDÊNTICO ao CSV sem `?page`, ambos contendo todas as linhas) |
| R4 | `apps/dashboard/views.py` | `... -k export_escaping` (novo; re-parse com `csv.reader`) |
| R5 | `apps/dashboard/views.py` | `... -k export_no_events` (novo) |
| R6 | `templates/dashboard/followup_history.html` | `... -k export_button` (novo) |

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/dashboard/views.py                         # + followup_history_export (pode refatorar helper do Slice 001 p/ reuso)
  - apps/dashboard/urls.py                          # +1 rota
  - templates/dashboard/followup_history.html       # + botão
  - apps/dashboard/tests/test_followup_history.py   # + testes R1–R6

allowed_incidental_files: []

out_of_scope:
  - filtros performed/reason/admitted NOVOS (só os aceita se Slice 003 já aplicado)
  - Excel/xlsx, streaming, form POST, JS
  - aba Registrar, models/migrations, tasks.md/commit/push (parent)
```

Escale se: a página do Slice 001 não expuser helper reutilizável sem refactor estrutural além do módulo; ou surgir necessidade de streaming (volumes).

## Plano de testes do slice

### RED

Ordem: escreva os testes novos primeiro, depois execute (arquivo já existe desde o Slice 001). Com os testes escritos:

- `uv run pytest apps/dashboard/tests/test_followup_history.py -k export -q` → 404/`NoReverseMatch` (rota inexistente) e botão ausente no HTML.

### GREEN / verificação local

```bash
uv run pytest apps/dashboard/tests/test_followup_history.py -q   # exit 0
uv run pytest apps/dashboard/tests -q                            # exit 0
uv run ruff check apps/dashboard && uv run ruff format --check apps/dashboard  # exit 0
```

## Critérios de aceitação

- [ ] R1–R7 verdes; CSV parseável com `csv.reader` nos testes (sem assert de string crua para linhas com escaping).
- [ ] Mesma população/filtros da página comprovada por teste parametrizado ou caso análogo.
- [ ] Diff dentro do blast radius; nenhum evento de auditoria criado.
