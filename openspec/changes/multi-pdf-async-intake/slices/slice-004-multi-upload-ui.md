# Slice 004 — UI/JS de Upload Múltiplo

## Handoff para Implementador LLM

Leia:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/multi-pdf-async-intake/proposal.md`
4. `openspec/changes/multi-pdf-async-intake/design.md`
5. Slices 001–003 deste change
6. Este arquivo.

Implemente somente este slice.

## Problema

Mesmo com backend múltiplo, a UI atual foi desenhada para um único arquivo: input sem `multiple`, JS usa `files[0]` e o preview mostra apenas um PDF. Para o NIR confiar no lote, a interface precisa listar todos os arquivos selecionados e comunicar que o processamento seguirá em background.

## Objetivo

Atualizar template e Vanilla JS para seleção/drag & drop de múltiplos PDFs, validação client-side e feedback claro do lote.

## Escopo Preferencial

Arquivos prováveis:

- `templates/intake/intake_home.html`
- `static/js/upload.js`
- `apps/intake/tests/test_upload.py` ou teste de renderização/template
- possivelmente `static/css/app.css` se precisar de pequenos ajustes visuais

Não usar framework JS.

## Requisitos Funcionais

1. Input de arquivo deve ter `multiple` e `accept=".pdf"`.
2. O campo deve usar o mesmo nome esperado pelo backend (`pdf_files` ou equivalente).
3. Drag & drop deve aceitar múltiplos arquivos.
4. JS deve validar cada arquivo:
   - extensão/tipo PDF;
   - tamanho por arquivo;
   - quantidade máxima;
   - tamanho total se o valor estiver disponível no frontend.
5. Preview deve listar arquivos selecionados com nome e tamanho.
6. Botão de submit deve ficar habilitado quando houver pelo menos 1 arquivo válido.
7. UI deve mostrar contagem do lote.
8. Texto da tela deve comunicar processamento em background, por exemplo: “Você pode sair desta tela; o processamento continuará na fila.”
9. Erros server-side do form/lote devem ser exibidos.
10. Manter acessibilidade básica: labels/textos claros e sem depender apenas de emoji/cor.

## TDD — Testes RED Esperados

Antes de implementar, crie/ajuste testes que falhem:

1. Template renderiza input com `multiple`.
2. Template renderiza nome de campo múltiplo correto.
3. Página menciona processamento em background/fila.
4. `upload.js` não contém mais lógica limitada a `files[0]` como único caminho.

Testes JS unitários não são obrigatórios se não houver infraestrutura; nesse caso, registrar validação manual no relatório.

## Critérios de Sucesso

- Usuário consegue selecionar 20–30 arquivos em uma única ação.
- Preview mostra lista do lote antes do envio.
- Mensagem pós-envio deixa claro que o processamento é assíncrono.
- Backend do slice 003 continua passando.

## Comandos de Validação Focados

```bash
uv run pytest apps/intake/tests/test_upload.py -q
uv run ruff check apps/intake
uv run mypy apps/intake
```

Além disso, registrar no relatório uma validação manual ou inspeção do JS/template.

## Relatório Obrigatório

Crie:

```text
/tmp/ats-web-slice-004-multi-upload-ui-report.md
```

Inclua:

- snippets do input antes/depois;
- snippets do JS antes/depois;
- testes executados;
- validação manual da UX.

Responda com:

```text
REPORT_PATH=/tmp/ats-web-slice-004-multi-upload-ui-report.md
```

## Stop Rule

Não altere infraestrutura/worker neste slice, exceto correção mínima de regressão causada pela UI.
