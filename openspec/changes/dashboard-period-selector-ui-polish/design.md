<!-- markdownlint-disable MD013 -->

# Design: Polimento visual do seletor de período das métricas

## Decisão de slicing

Implementar em **1 slice vertical enxuto**.

Justificativa:

- mudança puramente visual/localizada;
- valor depende de template + CSS + teste juntos;
- separar CSS/template seria slice horizontal sem entrega observável;
- não há alteração de domínio, migrations ou workflows.

## Arquivos esperados

1. `templates/dashboard/index.html`
2. `static/css/app.css`
3. `apps/dashboard/tests/test_dashboard.py`
4. artefatos OpenSpec deste change

## Design de UI

### D1. Card/toolbar compacto

Substituir o wrapper atual solto por um card leve:

```html
<div class="card metrics-period-card mb-3">
  <div class="card-body ...">
    ...
  </div>
</div>
```

O título `Período das métricas` e o label ativo (`Métricas de hoje`) ficam agrupados como cabeçalho do controle.

### D2. Presets e personalizado no mesmo sistema visual

Remover `btn-group`, `btn-primary` e `btn-outline-primary` do seletor de período.

Usar classes próprias:

- `.metrics-period-options`
- `.metrics-period-option`
- `.metrics-period-option.is-active`
- `.metrics-period-custom`
- `.metrics-period-custom-panel`

As classes usam `--hospital-primary`, `--hospital-border`, `--hospital-accent-light`.

### D3. Responsivo

Desktop/tablet:

- opções em linha/flex com gap consistente;
- `Personalizado` com mesma altura/largura mínima dos presets.

Mobile:

- grid de 2 colunas para presets;
- `Personalizado` ocupa largura completa;
- painel personalizado e inputs ocupam largura útil, sem inline widths rígidos.

### D4. SSR puro preservado

Manter `<details>` nativo para expandir o personalizado.

Dentro dele, manter dois mini-forms independentes:

- `metrics_period=custom_date` + `metrics_date`;
- `metrics_period=custom_range` + `metrics_start`/`metrics_end`.

Não introduzir JS novo.

### D5. Não alterar semântica

Não mexer em:

- `_period_bounds`, parsing ou labels de métricas;
- `_compute_summary`, `_compute_admission_flow`, `_compute_average_times`;
- filtros/lista/busca dinâmica, exceto se alguma classe estrutural afetar o DOM esperado pelo JS.

## Testes

Adicionar testes estruturais que falhem antes do polish:

- seletor renderiza `.metrics-period-card`, `.metrics-period-options`, `.metrics-period-option` e `.metrics-period-custom-panel`;
- trecho do seletor não contém `btn-group`, `btn-primary` ou `btn-outline-primary`;
- `static/css/app.css` contém regras para `.metrics-period-options`, `.metrics-period-option.is-active` e media query responsiva.

## Rollback

Reverter:

- `templates/dashboard/index.html`
- `static/css/app.css`
- testes adicionados em `apps/dashboard/tests/test_dashboard.py`

Sem migration.
