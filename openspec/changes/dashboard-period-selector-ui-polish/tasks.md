<!-- markdownlint-disable MD013 -->

# Tasks: Polimento visual do seletor de período das métricas

## Slice vertical

- [x] Slice 001 — Reorganizar seletor de período como toolbar/card responsivo (`slices/slice-001-period-selector-toolbar.md`)
  - Follow-up mobile: campos `type="date"` do `Personalizado` receberam wrapper `.metrics-period-date-control` com SVG Bootstrap Icons `calendar-event` monocromático, evitando campos brancos sem dica visual no Android/iPhone sem depender de placeholder nativo. O ícone customizado fica oculto por padrão e aparece apenas em mobile (`max-width: 575.98px`), pois desktop já renderiza indicador/placeholder nativo.

## Definition of Done do change

- [x] Seletor `Período das métricas` renderiza dentro de `.metrics-period-card`.
- [x] Presets e `Personalizado` usam classes próprias `.metrics-period-option`.
- [x] Seletor não usa `btn-group`, `btn-primary` nem `btn-outline-primary`.
- [x] CSS usa paleta hospitalar e possui regra responsiva para mobile.
- [x] `Personalizado` continua SSR puro com dois mini-forms independentes.
- [x] Query params e hidden inputs existentes continuam preservados.
- [x] Nenhuma alteração em cálculo de métricas, models, migrations, FSM, permissões ou JS novo.
- [x] Testes relevantes passam.
- [x] Quality gate do AGENTS.md executado.
- [x] Relatório temporário criado com snippets antes/depois.
- [x] Commit e push realizados.
