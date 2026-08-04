# Design: Manual oficial do usuário, PDF e página in-app

## Estado atual

- Existe um rascunho do manual em `tmp/manual.md`.
- O rascunho já cobre os principais fluxos por papel:
  - NIR;
  - Médico;
  - CHD/Agendador.
- O rascunho também já incorpora respostas de produto sobre:
  - uso preferencial do termo CHD;
  - menções preferenciais `@medico` e `@chd`;
  - limites/tipos de arquivos;
  - campo Local no formulário do CHD;
  - vinda imediata;
  - possibilidade futura de página dentro do sistema.
- O sistema possui header global em `templates/base.html` para usuários autenticados.
- Rotas raiz ficam em `apps/accounts/urls.py`, incluídas por `config/urls.py` em `path("", include("apps.accounts.urls"))`.
- O projeto já depende de `pymupdf`, que pode ser usado para gerar PDF sem adicionar dependência pesada.

## Decisões técnicas

### D1. Local oficial do Markdown

Criar:

```text
docs/manual/manual-usuarios.md
```

Esse arquivo é a fonte oficial do manual.

Também criar, se útil:

```text
docs/manual/README.md
```

O README pode explicar como gerar PDF e como o manual é servido no sistema. Se o slice precisar manter escopo mínimo, o README é opcional desde que o script tenha `--help` e o slice documente o comando em relatório.

### D2. Script de PDF

Criar script versionado:

```text
scripts/build_user_manual_pdf.py
```

Comportamento recomendado:

```bash
uv run python scripts/build_user_manual_pdf.py
uv run python scripts/build_user_manual_pdf.py --input docs/manual/manual-usuarios.md --output /tmp/manual-usuarios.pdf
```

Defaults:

- input: `docs/manual/manual-usuarios.md`;
- output: `docs/manual/dist/manual-usuarios.pdf`.

Requisitos do script:

- falhar com mensagem clara se o Markdown não existir;
- criar diretório de output automaticamente;
- gerar PDF válido (`%PDF`);
- suportar caracteres pt-BR;
- incluir título, headings, parágrafos, listas e tabelas de forma legível;
- não depender de Pandoc/WeasyPrint/wkhtmltopdf;
- usar somente stdlib + dependências já existentes, preferencialmente `pymupdf`.

Observação: o PDF não precisa ter layout editorial sofisticado neste change. Precisa ser legível, reprodutível e suficiente para divulgação/treinamento.

### D3. Testes do manual e PDF

Adicionar testes de sanidade, por exemplo em:

```text
tests/test_user_manual_artifacts.py
```

Ou em app apropriado se o projeto preferir manter testes por app.

Testes recomendados:

- arquivo oficial existe;
- contém seções obrigatórias;
- contém fluxo CHD → NIR histórico;
- contém limites/tipos de arquivos;
- script gera PDF em diretório temporário;
- PDF gerado é válido e abre com `fitz.open()`.

### D4. Página in-app

Criar rota autenticada:

```text
/manual/
```

Nome de URL sugerido:

```python
path("manual/", views.user_manual_view, name="user_manual")
```

Local sugerido: `apps/accounts`, porque:

- já contém rotas raiz/autenticadas compartilhadas;
- header global e home por papel já estão nesse app;
- evita criar novo app só para uma página simples.

A view deve:

- exigir `@login_required`;
- ler `docs/manual/manual-usuarios.md`;
- renderizar HTML seguro;
- retornar `404` ou mensagem controlada se o arquivo não existir;
- não duplicar o conteúdo do manual em template.

### D5. Renderização Markdown segura e enxuta

Não adicionar dependência pesada para Markdown neste change.

Opções aceitáveis:

1. Criar helper simples, por exemplo `apps/accounts/manual.py`, com:
   - caminho canônico do manual;
   - leitura do Markdown;
   - renderização básica e escapada para HTML.
2. Renderizar como texto formatado dentro de `<pre>`/CSS, se ficar legível.

Preferência: helper simples com HTML básico para headings, parágrafos, listas, blockquotes e tabelas.

Regras de segurança:

- escapar HTML do Markdown antes de renderizar;
- não marcar Markdown cru como safe sem sanitização;
- testes devem cobrir que HTML bruto malicioso é escapado.

### D6. Header

Adicionar link no header autenticado em `templates/base.html`.

Requisitos:

```html
<a href="{% url 'user_manual' %}" target="_blank" rel="noopener">Manual</a>
```

O link deve aparecer apenas para usuários autenticados, junto dos controles existentes de sessão/notificações/perfil. Não deve aparecer na tela de login.

### D7. Sem alteração de autorização por papel

Todos os usuários autenticados podem ler o manual, independentemente do papel ativo.

Não há necessidade de `role_required`.

### D8. Sem alteração operacional

Este change não altera:

- FSM;
- models;
- migrations;
- filas;
- comunicação operacional;
- notificações;
- permissões de caso;
- processamento LLM.

## Slices planejados

### Slice 001 — Manual oficial + geração de PDF

Entrega:

```text
tmp/manual.md → docs/manual/manual-usuarios.md
script PDF → PDF válido gerado por comando reproduzível
testes → artefato oficial e PDF verificados
```

Arquivos prováveis:

| Arquivo | Mudança |
|---|---|
| `docs/manual/manual-usuarios.md` | novo documento oficial |
| `scripts/build_user_manual_pdf.py` | novo script de geração |
| `tests/test_user_manual_artifacts.py` | testes do documento e PDF |
| `openspec/changes/official-user-manual-publication/tasks.md` | marcar slice quando concluído |

### Slice 002 — Página in-app + link no header

Entrega:

```text
Usuário autenticado vê link Manual no header → abre nova aba → página renderiza docs/manual/manual-usuarios.md
```

Arquivos prováveis:

| Arquivo | Mudança |
|---|---|
| `apps/accounts/manual.py` | helper de leitura/renderização segura do Markdown |
| `apps/accounts/views.py` | view autenticada do manual |
| `apps/accounts/urls.py` | rota `/manual/` |
| `templates/accounts/manual.html` | template da página |
| `templates/base.html` | link no header |
| `apps/accounts/tests/test_user_manual_view.py` | testes de rota/header/renderização |
| `openspec/changes/official-user-manual-publication/tasks.md` | marcar slice quando concluído |

O slice pode tocar 6 arquivos de implementação/teste porque é a menor entrega vertical com rota, renderização e navegação global. O relatório deve justificar qualquer arquivo extra.

## Rollback

### Slice 001

- Remover `docs/manual/manual-usuarios.md`.
- Remover `scripts/build_user_manual_pdf.py`.
- Remover testes do artefato/PDF.

Sem migração ou impacto em runtime.

### Slice 002

- Remover rota `/manual/`.
- Remover link no header.
- Remover view/helper/template/testes.

Sem migração ou impacto em workflows operacionais.

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Manual divergente entre PDF e página | Markdown oficial único; PDF e página leem o mesmo arquivo |
| PDF exigir dependência externa no deploy | Usar `pymupdf` já existente ou justificar explicitamente |
| Página expor fluxos internos sem login | `@login_required` e teste de redirect para login |
| XSS ao renderizar Markdown | Escape de HTML + teste com `<script>` |
| Header poluído | Link simples e discreto, só para autenticados |
| Slice grande demais | Dividir em PDF/documento e página/header |

## Questões assumidas

As seguintes decisões foram assumidas para destravar o change. Se produto discordar, ajustar antes da implementação:

1. O PDF gerado não precisa ser commitado; o Markdown é a fonte oficial.
2. A página `/manual/` deve exigir login.
3. O link no header deve aparecer para todos os papéis autenticados.
4. Não será adicionada dependência pesada de PDF/Markdown neste change.
