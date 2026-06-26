# Slice 002: Página in-app autenticada + link no header

## Handoff para implementador LLM com contexto zero

Você está no projeto ATS Web, um monolito Django SSR. Leia antes de codar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/official-user-manual-publication/proposal.md`
4. `openspec/changes/official-user-manual-publication/design.md`
5. `openspec/changes/official-user-manual-publication/tasks.md`
6. `openspec/changes/official-user-manual-publication/specs/user-manual-publication/spec.md`
7. `openspec/changes/official-user-manual-publication/slices/slice-001-official-manual-and-pdf.md`
8. Este arquivo
9. Código atual em:
   - `apps/accounts/views.py`
   - `apps/accounts/urls.py`
   - `templates/base.html`
   - `templates/accounts/`

Assuma que o Slice 001 está completo e que existe:

```text
docs/manual/manual-usuarios.md
```

Implemente **somente este slice** usando TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Entregar acesso ao manual dentro do sistema:

```text
Usuário autenticado vê link Manual no header
→ link abre nova aba
→ /manual/ renderiza docs/manual/manual-usuarios.md
→ usuário consulta o manual sem sair do fluxo operacional
```

## Escopo funcional

### R1. Rota autenticada do manual

Criar rota:

```text
/manual/
```

Nome sugerido:

```python
path("manual/", views.user_manual_view, name="user_manual")
```

A view deve:

- exigir login;
- permitir qualquer papel autenticado;
- ler `docs/manual/manual-usuarios.md`;
- renderizar o conteúdo em página HTML;
- não duplicar o manual em template;
- retornar erro controlado se o arquivo não existir.

Local sugerido: `apps/accounts`, pois já contém rotas raiz autenticadas e o header global pertence à experiência de conta/sessão.

### R2. Renderização segura do Markdown

Criar helper simples, por exemplo:

```text
apps/accounts/manual.py
```

Funções sugeridas:

```python
USER_MANUAL_PATH = Path(...)

def read_user_manual_markdown(path: Path = USER_MANUAL_PATH) -> str: ...

def render_manual_markdown_to_html(markdown_text: str) -> str: ...
```

Requisitos:

- escapar HTML bruto do Markdown;
- suportar headings (`#`, `##`, `###`);
- suportar parágrafos;
- suportar listas simples;
- suportar blockquotes;
- suportar tabelas simples, se viável;
- manter legibilidade com Bootstrap;
- não adicionar dependência pesada.

Se optar por renderização mais simples em `<pre>`, justificar no relatório. Preferência: HTML básico escapado.

### R3. Template da página

Criar template:

```text
templates/accounts/manual.html
```

Requisitos:

- estender `base.html`;
- título claro, por exemplo `Manual de Uso`;
- mostrar conteúdo renderizado do Markdown;
- incluir link/botão opcional para voltar ao início, se simples;
- não incluir cópia manual do conteúdo.

### R4. Link no header

Editar `templates/base.html` para exibir link **Manual** para usuários autenticados.

Requisitos:

```html
<a href="{% url 'user_manual' %}" target="_blank" rel="noopener">Manual</a>
```

- Deve aparecer apenas dentro do bloco `user.is_authenticated`.
- Deve abrir em nova aba.
- Deve ser discreto e não atrapalhar notificações/perfil/troca de papel/logout.

### R5. Testes

Criar testes, por exemplo:

```text
apps/accounts/tests/test_user_manual_view.py
```

Testes mínimos:

1. `test_user_manual_requires_login`
   - GET `/manual/` anônimo redireciona para login ou é bloqueado conforme padrão `login_required`.

2. `test_authenticated_user_can_open_manual`
   - usuário autenticado com papel ativo acessa `/manual/`;
   - status 200;
   - contém título/conteúdo do manual.

3. `test_manual_page_uses_official_markdown_source`
   - valida que conteúdo vem de `docs/manual/manual-usuarios.md` ou usa monkeypatch do helper para provar que a view chama a leitura oficial.

4. `test_manual_renderer_escapes_raw_html`
   - chama helper com Markdown contendo `<script>alert(1)</script>`;
   - valida que `<script>` não aparece como tag HTML confiável e que versão escapada aparece.

5. `test_header_shows_manual_link_for_authenticated_user`
   - renderiza página que usa `base.html` autenticado;
   - valida texto `Manual`, URL de `user_manual`, `target="_blank"` e `rel="noopener"`.

6. `test_header_does_not_show_manual_link_for_anonymous_login_page`
   - GET login;
   - valida ausência do link autenticado, se viável.

## Fora de escopo

Não implementar neste slice:

- geração de PDF;
- download de PDF pela aplicação;
- edição/admin do manual;
- busca interna no manual;
- sumário dinâmico avançado;
- cache persistente;
- Markdown parser completo;
- nova dependência pesada;
- mudança em FSM/models/workflows.

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/accounts/manual.py`
2. `apps/accounts/views.py`
3. `apps/accounts/urls.py`
4. `templates/accounts/manual.html`
5. `templates/base.html`
6. `apps/accounts/tests/test_user_manual_view.py`
7. `openspec/changes/official-user-manual-publication/tasks.md`

Este slice toca mais de 5 arquivos porque a menor entrega vertical exige helper, rota, view, template, header e testes. Não ampliar além disso sem justificar no relatório.

## TDD obrigatório

Antes da implementação, crie testes falhando.

### RED esperado

- `/manual/` ainda não existe;
- helper de manual ainda não existe;
- header ainda não contém link `Manual`;
- renderer ainda não escapa Markdown.

Registre no relatório:

- comando RED executado;
- nomes dos testes falhando;
- resumo das falhas.

## Orientações de implementação

### Clean Code

- Isolar leitura/renderização em helper puro e testável.
- Manter a view fina: ler Markdown, renderizar HTML, chamar template.
- Usar nomes claros e mensagens controladas.

### DRY

- A página deve ler `docs/manual/manual-usuarios.md`.
- Não copiar o conteúdo do manual para `templates/accounts/manual.html`.
- Não duplicar listas de seções em múltiplos lugares sem necessidade.

### YAGNI

Não implementar:

- editor de manual;
- upload de PDF;
- cache complexo;
- permissões por papel;
- search box;
- anchors/sumário avançados;
- suporte Markdown completo.

## Critérios de sucesso

- [ ] `/manual/` existe.
- [ ] `/manual/` exige login.
- [ ] Qualquer usuário autenticado consegue acessar.
- [ ] Página renderiza conteúdo do Markdown oficial.
- [ ] Template não duplica conteúdo do manual.
- [ ] Renderer escapa HTML bruto.
- [ ] Header mostra link **Manual** para autenticados.
- [ ] Link abre em nova aba com `target="_blank"`.
- [ ] Link usa `rel="noopener"`.
- [ ] Login/anônimo não mostra link autenticado.
- [ ] Sem migrations.
- [ ] Sem alteração de workflows operacionais.
- [ ] Testes novos passam.
- [ ] `tasks.md` atualizado ao concluir.

## Gates de autoavaliação

Responder no relatório:

1. Qual rota foi criada e qual o nome da URL?
2. A rota exige login? Qual teste prova?
3. A página lê qual arquivo como fonte oficial?
4. O conteúdo do manual foi duplicado no template? Esperado: não.
5. Como o Markdown é renderizado com segurança?
6. Qual teste prova que HTML bruto é escapado?
7. O link do header aparece para quais usuários?
8. Qual teste prova `target="_blank"` e `rel="noopener"`?
9. Alguma dependência nova foi adicionada? Se sim, por quê?
10. Houve alteração em FSM/models/migrations/workflows? Esperado: não.
11. Quais comandos do quality gate foram executados?

## Relatório obrigatório

Criar relatório temporário:

```text
/tmp/official-user-manual-publication-slice-002-report.md
```

O relatório deve conter:

- resumo da implementação;
- arquivos alterados;
- evidência do RED;
- evidência do GREEN;
- snippets antes/depois;
- resultado do quality gate;
- respostas aos gates de autoavaliação;
- justificativa para qualquer arquivo extra tocado.

Responder ao final com:

```text
REPORT_PATH=/tmp/official-user-manual-publication-slice-002-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/official-user-manual-publication/{proposal.md,design.md,tasks.md,specs/user-manual-publication/spec.md,slices/slice-001-official-manual-and-pdf.md,slices/slice-002-in-app-manual-page.md}.
Assume Slice 001 is complete and docs/manual/manual-usuarios.md exists.
Implement ONLY Slice 002 using TDD: first add failing tests for /manual/, auth, safe rendering and header link, then implement minimal code, then refactor safely.
Goal: create an authenticated /manual/ page that reads docs/manual/manual-usuarios.md, renders it safely in HTML, and add a Manual link in templates/base.html for authenticated users with target="_blank" and rel="noopener". The page must be available to all authenticated roles and must not duplicate the manual content in the template.
Keep it lean. Do not implement PDF generation/download, manual editing, search, advanced TOC, cache complexity, new models, migrations, FSM changes or workflow changes. Avoid new heavy dependencies; prefer a small escaped Markdown renderer helper.
Apply clean code, DRY and YAGNI.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/official-user-manual-publication/tasks.md for Slice 002 when complete.
Create /tmp/official-user-manual-publication-slice-002-report.md with RED/GREEN evidence, snippets, quality gate results and self-evaluation answers.
Commit and push. Return REPORT_PATH=<path> and stop.
```
