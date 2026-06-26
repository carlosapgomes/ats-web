# Slice 001: Manual oficial versionado + script de PDF

## Handoff para implementador LLM com contexto zero

Você está no projeto ATS Web, um monolito Django SSR. Leia antes de codar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `tmp/manual.md`
4. `openspec/changes/official-user-manual-publication/proposal.md`
5. `openspec/changes/official-user-manual-publication/design.md`
6. `openspec/changes/official-user-manual-publication/tasks.md`
7. `openspec/changes/official-user-manual-publication/specs/user-manual-publication/spec.md`
8. Este arquivo

Implemente **somente este slice** usando TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Entregar o manual como artefato oficial versionado e permitir geração reprodutível de PDF para divulgação:

```text
tmp/manual.md
→ docs/manual/manual-usuarios.md
→ scripts/build_user_manual_pdf.py
→ PDF válido gerado por comando
```

Este slice não cria rota web nem link no header. Isso fica para o Slice 002.

## Escopo funcional

### R1. Criar manual oficial

Criar:

```text
docs/manual/manual-usuarios.md
```

Conteúdo inicial: partir de `tmp/manual.md`, preservando linguagem clara e instruções práticas.

O documento oficial deve conter, no mínimo:

- título do manual;
- resumo dos fluxos cobertos;
- seção NIR;
- seção Médico;
- seção CHD/Agendador;
- comunicação operacional e notificações;
- fluxo de intercorrência pós-agendamento aberta pelo NIR;
- fluxo de alteração interna comunicada pelo CHD via histórico;
- orientações sobre vinda imediata;
- tipos e limites de arquivos/anexos;
- observações finais sobre PDF e página in-app, se ainda fizer sentido.

### R2. Criar script de PDF

Criar:

```text
scripts/build_user_manual_pdf.py
```

Comportamento esperado:

```bash
uv run python scripts/build_user_manual_pdf.py
uv run python scripts/build_user_manual_pdf.py --input docs/manual/manual-usuarios.md --output /tmp/manual-usuarios.pdf
```

Defaults:

- input: `docs/manual/manual-usuarios.md`;
- output: `docs/manual/dist/manual-usuarios.pdf`.

Requisitos:

- usar `argparse`;
- criar diretório de saída automaticamente;
- falhar com mensagem clara se input não existir;
- gerar PDF válido;
- preservar caracteres pt-BR;
- produzir layout legível;
- suportar headings, parágrafos, listas e tabelas de forma simples;
- preferir stdlib + `pymupdf` já existente;
- não adicionar Pandoc, WeasyPrint, wkhtmltopdf ou dependência pesada.

O layout não precisa ser sofisticado. O objetivo é PDF legível para treinamento/divulgação.

### R3. Testes de sanidade

Criar testes, por exemplo:

```text
tests/test_user_manual_artifacts.py
```

Ou outro local coerente, desde que justificado no relatório.

Testes mínimos:

1. `test_official_user_manual_exists`
   - verifica que `docs/manual/manual-usuarios.md` existe.

2. `test_official_user_manual_has_required_sections`
   - verifica presença de seções/termos essenciais:
     - `Ações do usuário NIR`;
     - `Ações do usuário Médico`;
     - `Ações do usuário CHD` ou `CHD/Agendador`;
     - `Comunicação operacional`;
     - `Intercorrência Pós-Agendamento`;
     - `Buscar histórico`;
     - `Comunicar NIR`.

3. `test_official_user_manual_documents_file_limits`
   - verifica que o manual menciona:
     - PDF;
     - JPEG/JPG;
     - PNG;
     - 20 MB;
     - 10 arquivos;
     - 200 MB.

4. `test_build_user_manual_pdf_script_generates_valid_pdf`
   - executa a função principal ou subprocess com `--output` em `tmp_path`;
   - valida que o arquivo começa com `%PDF` ou abre com `fitz.open()`;
   - valida que há pelo menos 1 página.

5. `test_build_user_manual_pdf_missing_input_fails_clearly`
   - chama script/função com input inexistente;
   - valida erro e mensagem compreensível.

## Fora de escopo

Não implementar neste slice:

- rota `/manual/`;
- link no header;
- template HTML do manual;
- renderer Markdown para a aplicação web;
- download de PDF pela aplicação;
- alteração de `pyproject.toml`, salvo justificativa forte;
- qualquer alteração de FSM/models/workflows.

## Arquivos esperados

Idealmente tocar apenas:

1. `docs/manual/manual-usuarios.md`
2. `scripts/build_user_manual_pdf.py`
3. `tests/test_user_manual_artifacts.py`
4. `openspec/changes/official-user-manual-publication/tasks.md`

Se precisar tocar mais arquivos, justificar no relatório.

## TDD obrigatório

Antes da implementação, crie testes falhando.

### RED esperado

- testes falham porque `docs/manual/manual-usuarios.md` ainda não existe;
- testes falham porque `scripts/build_user_manual_pdf.py` ainda não existe;
- teste de PDF falha por ausência do script ou função.

Registre no relatório:

- comando RED executado;
- nomes dos testes falhando;
- resumo das falhas.

## Orientações de implementação

### Clean Code

- Crie funções pequenas no script, por exemplo:
  - `parse_args()`;
  - `read_markdown()`;
  - `build_pdf()`;
  - `main()`.
- Evite lógica gigante em `if __name__ == "__main__"`.
- Use nomes claros e mensagens de erro úteis.

### DRY

- O Markdown oficial deve ser a fonte única.
- Não crie outro arquivo com o mesmo conteúdo do manual.
- O script deve ler `docs/manual/manual-usuarios.md`, não duplicar texto.

### YAGNI

Não implementar:

- sumário automático complexo;
- CSS/HTML intermediário sofisticado;
- capa institucional avançada;
- múltiplos idiomas;
- watch mode;
- upload do PDF;
- integração com browser/headless.

## Critérios de sucesso

- [ ] `docs/manual/manual-usuarios.md` criado.
- [ ] Documento contém instruções por papel: NIR, Médico e CHD/Agendador.
- [ ] Documento cobre fluxo CHD → NIR histórico.
- [ ] Documento cobre intercorrência pós-agendamento aberta pelo NIR.
- [ ] Documento informa tipos/limites de arquivos.
- [ ] `scripts/build_user_manual_pdf.py` criado.
- [ ] Script gera PDF válido com output default.
- [ ] Script aceita `--input` e `--output`.
- [ ] Script falha claramente quando input não existe.
- [ ] Testes novos passam.
- [ ] Sem dependência pesada nova.
- [ ] Sem migrations.
- [ ] `tasks.md` atualizado ao concluir.

## Gates de autoavaliação

Responder no relatório:

1. Qual arquivo é a fonte oficial do manual?
2. O PDF é gerado a partir da fonte oficial ou há conteúdo duplicado?
3. Qual comando gera o PDF com output default?
4. Qual comando gera o PDF em caminho customizado?
5. O script adicionou alguma dependência nova? Se sim, por quê?
6. Qual teste prova que o PDF gerado é válido?
7. Qual teste prova que o fluxo CHD → NIR histórico está documentado?
8. Qual teste prova que limites/tipos de arquivos estão documentados?
9. Houve alteração em runtime web, FSM, models ou migrations? Esperado: não.
10. Quais comandos do quality gate foram executados?

## Relatório obrigatório

Criar relatório temporário:

```text
/tmp/official-user-manual-publication-slice-001-report.md
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
REPORT_PATH=/tmp/official-user-manual-publication-slice-001-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, tmp/manual.md and openspec/changes/official-user-manual-publication/{proposal.md,design.md,tasks.md,specs/user-manual-publication/spec.md,slices/slice-001-official-manual-and-pdf.md}.
Implement ONLY Slice 001 using TDD: first add failing tests for the official manual artifact and PDF generation, then implement minimal code, then refactor safely.
Goal: create docs/manual/manual-usuarios.md from tmp/manual.md as the official source, and create scripts/build_user_manual_pdf.py to generate a valid PDF from that Markdown. Use stdlib + existing dependencies, preferably pymupdf; do not add Pandoc/WeasyPrint/wkhtmltopdf. The script must support default input/output and --input/--output, create output directories, preserve pt-BR text, and fail clearly when input is missing.
Keep it lean. Do not implement /manual/, header link, web renderer, PDF download, model changes, migrations, FSM changes or workflow changes.
Apply clean code, DRY and YAGNI.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/official-user-manual-publication/tasks.md for Slice 001 when complete.
Create /tmp/official-user-manual-publication-slice-001-report.md with RED/GREEN evidence, snippets, quality gate results and self-evaluation answers.
Commit and push. Return REPORT_PATH=<path> and stop.
```
