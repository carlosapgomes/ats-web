# Tasks: Manual oficial do usuário, PDF e página in-app

## Slices verticais

- [x] Slice 001 — Manual oficial versionado + script de PDF (`slices/slice-001-official-manual-and-pdf.md`)
- [ ] Slice 002 — Página in-app autenticada + link no header (`slices/slice-002-in-app-manual-page.md`)

## Definition of Done global

- [x] `docs/manual/manual-usuarios.md` criado como fonte oficial.
- [x] Manual oficial contém seções por papel: NIR, Médico e CHD/Agendador.
- [x] Manual oficial cobre o fluxo CHD → NIR para alteração interna em caso histórico.
- [x] Manual oficial cobre intercorrência pós-agendamento aberta pelo NIR.
- [x] Manual oficial informa tipos/limites de arquivos de relatório e anexos.
- [x] Script versionado gera PDF válido a partir do Markdown oficial.
- [x] Script tem defaults documentados e aceita input/output customizados.
- [x] Testes validam artefato oficial e geração de PDF.
- [ ] Página `/manual/` renderiza o Markdown oficial para usuários autenticados.
- [ ] Usuário não autenticado é redirecionado/bloqueado ao acessar `/manual/`.
- [ ] Header mostra link **Manual** para usuário autenticado.
- [ ] Link **Manual** abre em nova aba (`target="_blank"`) com `rel="noopener"`.
- [ ] Página in-app não duplica o conteúdo do manual em template.
- [ ] Renderização do Markdown escapa HTML potencialmente perigoso.
- [x] Sem migrations.
- [x] Sem alteração de FSM, models de caso, filas ou workflows operacionais.
- [x] Testes relevantes passam.
- [x] Quality gate executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatório markdown temporário criado para cada slice e `REPORT_PATH` informado.
- [x] Tasks/spec atualizadas ao concluir cada slice.
- [ ] Commit e push realizados por slice.
