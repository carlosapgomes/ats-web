<!-- markdownlint-disable MD013 -->

# QUICK bugfix: ampliar heurística de marca d'água numérica

## Status

- [x] Concluído em 2026-09-27

## Classificação e justificativa

- **Tipo:** QUICK bugfix simples e reversível.
- **Risco:** baixo e localizado na limpeza do texto extraído antes do pipeline.
- **Design separado:** dispensado pela exceção QUICK do `AGENTS.md`.
- **BASE_REF:** `110b6baea704830a1550af893b98b9fe230d5553`.
- **Branch:** `quick/fix-watermark-numeric-token-heuristic`.

## Objetivo vertical

```text
PDF extraído contém um mesmo token numérico com 3+ dígitos mais de 10 vezes
→ limpeza identifica o token pela frequência no documento inteiro
→ todas as ocorrências isoladas do token são removidas
→ texto clínico limpo segue para o pipeline
```

## Handoff para implementador LLM com contexto zero

Leia `AGENTS.md`, `PROJECT_CONTEXT.md`, este arquivo, `apps/intake/pdf_utils.py` e `apps/intake/tests/test_pdf_utils.py`. Altere somente a heurística numérica de marca d'água. Hoje ela reconhece apenas tokens de 5–6 dígitos concentrados numa linha. O comportamento-alvo reconhece qualquer token ASCII com **3 ou mais dígitos**, sem limite superior, quando aparece **mais de 10 vezes no documento inteiro**. Remova todas as ocorrências isoladas dos tokens qualificados. Preserve a extração explícita do número de registro, o fallback por epoch, a normalização de whitespace e a extração de “Dias em tela”. Não adicione dependências, migration ou mudança de pipeline.

## Requisitos e critérios de sucesso

- **R1:** token numérico de 3, 5 ou mais de 6 dígitos, presente 11+ vezes em posições distintas do documento, é removido integralmente.
- **R2:** token de 3+ dígitos presente exatamente 10 vezes não é considerado marca d'água.
- **R3:** token com menos de 3 dígitos não é removido por frequência, mesmo com 11 ocorrências.
- **R4:** extração/remoção explícita do registro e normalização existentes permanecem verdes.

## TDD e gates de autoavaliação

1. **RED:** adicionar testes para R1–R3 e comprovar falha funcional antes de editar produção.
2. **GREEN:** implementar o mínimo em `apps/intake/pdf_utils.py` e rodar `uv run pytest apps/intake/tests/test_pdf_utils.py`.
3. **REFACTOR:** nomes e docstrings devem descrever 3+ dígitos e frequência global >10; remover a lógica antiga de banda por linha se ficar morta.
4. Rodar `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`, `uv run pytest` e `git status --short`.
5. Gerar relatório temporário com snippets antes/depois, marcar este status como concluído, fazer commit e push. Informar `REPORT_PATH` e parar.

## Evidências da execução

- RED: 3 falhas funcionais (tokens de 5 dígitos entre linhas, 3 dígitos e 9 dígitos repetidos 11 vezes).
- GREEN local: `apps/intake/tests/test_pdf_utils.py` — 18 passed.
- Integração de extração: `apps/intake/tests/test_pdf_extraction_task.py` — 28 passed.
- Quality gate: ruff check/format e mypy verdes; suíte completa — 4606 passed.
- Nota de ambiente: a primeira tentativa da suíte usou a porta default 5433 e falhou por autenticação do PostgreSQL local; repetição contra o container de teste saudável na porta publicada 55433 ficou integralmente verde.

## Fora de escopo

- OCR, leitura de imagem ou mudança em `extract_pdf_text`.
- Alterar padrões de número de registro (`Código:`/cabeçalho).
- Reprocessar casos já persistidos.
- Alterar prompts, FSM, banco ou telas.
