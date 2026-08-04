# Proposal: Índice (sumário) navegável no manual do usuário

**Change ID**: `user-manual-toc`
**Risco**: BAIXO (apenas apresentação do manual; sem FSM/models/migrations/runtime operacional)
**Dependências**: `official-user-manual-publication`

## Problema

O manual do usuário (`/manual/` e o PDF) é extenso (~14 páginas, dezenas de seções). Hoje não há sumário/índice, forçando o usuário a rolar/deslizar para encontrar uma seção.

## Objetivo

Gerar automaticamente um índice (TOC) a partir dos cabeçalhos do Markdown oficial:

1. **Site (`/manual/`)**: sumário clicável no topo, com âncoras (`#slug`) em cada heading.
2. **PDF**: seção "Índice" no início, listando as seções.

## Escopo

### Dentro
- Renderer web (`apps/accounts/manual.py`) gera `id` nos headings e um bloco TOC.
- Template/CSS para exibir o TOC (colapsável, com scroll suave).
- Script de PDF renderiza um índice textual no início.
- Testes cobrindo ids, TOC e unicidade.

### Fora
- Links clicáveis entre páginas no PDF (requer two-pass com page numbers; deferido).
- Busca interna.
- TOC no PDF com numeração de páginas.

## Decisões

- **D1. TOC gerado do conteúdo, nunca escrito à mão** — evita divergência.
- **D2. Slugs ASCII sem acento** — máxima compatibilidade de âncoras.
- **D3. Ids únicos** — sufixo numérico em duplicatas.
- **D4. TOC inclui níveis 1 e 2** — equilíbrio entre útil e curto.
- **D5. Sem nova dependência** — stdlib (`re`, `unicodedata`) + `pymupdf` existente.

## Critérios de sucesso

- Headings renderizados têm `id`.
- TOC clicável aparece no topo de `/manual/`.
- Cliques levam à seção (âncora válida).
- PDF gerado contém seção "Índice".
- Sem alteração de FSM/models/migrations.
- Quality gate passa.
