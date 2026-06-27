# Tasks: Índice navegável no manual

## Slices

- [x] Slice 001 — TOC web (ids + sumário clicável) + índice no PDF (`slices/slice-001-toc.md`)

## Definition of Done

- [ ] Headings do manual (web) têm `id` ASCII único.
- [ ] TOC clicável aparece no topo de `/manual/`.
- [ ] Cliques no TOC levam à seção correta.
- [ ] PDF gerado contém seção "Índice".
- [ ] Slugs sem acento e únicos (testados).
- [ ] XSS continue escapado (teste existente passa).
- [ ] Sem migrations / FSM / models.
- [ ] Quality gate: ruff, ruff format, mypy, pytest.
- [ ] Relatório temporário + REPORT_PATH informado.
- [ ] Commit + push.
