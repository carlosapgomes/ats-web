<!-- markdownlint-disable MD013 -->

# Design: Badges compactos e próximo passo no dashboard

## Estado atual

A lista de casos do dashboard é renderizada por `templates/dashboard/_case_list.html`. O presenter `_enrich_case()` em `apps/dashboard/views.py` inclui `result_label` e `result_css`, calculados por `_compute_result(case)`.

Hoje, `_compute_result()` usa `ADMISSION_FLOW_MAP` para fluxos operacionais aceitos sem agendamento. Para `ward_icu_backup`, o label completo é:

```text
Vinda para enfermaria (para retaguarda em UTI)
```

Com prefixo `✓`, esse texto vira um badge longo. Em mobile, o template coloca o badge em `col-8` e a data/hora em `col-4`, o que permite sobreposição/overflow porque `.badge` do Bootstrap usa `white-space: nowrap`.

No detalhe do caso, `templates/intake/case_detail.html` renderiza o card `Resultado Final`. Para fluxos operacionais, o badge usa `result_info.badge`, vindo de `get_admission_flow_notice_copy()`. Em mobile, textos como `✓ Vinda para enfermaria com retaguarda em UTI` podem transbordar o card.

## Decisões

### D1. Labels compactos apenas para badges

Não alterar `ADMISSION_FLOW_CHOICES`, `ADMISSION_FLOW_MAP` nem labels exibidos ao médico no formulário de decisão. Criar labels compactos somente na camada de apresentação do dashboard/detalhe.

Sugestão de mapa compacto:

| Fluxo | Label completo preservado | Badge compacto sugerido |
| --- | --- | --- |
| `scheduled` | Agendamento | ✓ Agendamento |
| `immediate` | Vinda Imediata | ✓ Vinda imediata |
| `pre_icu` | Vinda prévia para UTI | ✓ Pré-UTI |
| `ward_icu_backup` | Vinda para enfermaria (para retaguarda em UTI) | ✓ Enfermaria + retaguarda UTI |
| `pediatric_em` | Compartilhar com EM pediátrica | ✓ EM pediátrica |

O implementador pode ajustar microcopy, desde que preserve clareza e reduza overflow.

### D2. Próximo passo como presenter, não modelo

Adicionar helper determinístico no dashboard, por exemplo `_compute_next_step(case)`, retornando `(label, css)` ou `None`.

Mapa inicial sugerido:

| Status / condição | Próximo passo sugerido |
| --- | --- |
| `WAIT_DOCTOR` | Pendente: médico |
| `DOCTOR_ACCEPTED`, `R3_POST_REQUEST`, `WAIT_APPT` com fluxo `scheduled` | Pendente: agendador |
| `APPT_CONFIRMED`, `APPT_DENIED`, `R1_FINAL_REPLY_POSTED`, `WAIT_R1_CLEANUP_THUMBS` | Pendente: NIR |
| fluxo operacional sem agendamento já aceito, antes de cleanup | Pendente: NIR |
| `FAILED` | Pendente: suporte |
| `CLEANUP_RUNNING` | Encerrando |
| `CLEANED` | Encerrado |

O label deve ser curto e visualmente secundário. Não precisa aparecer para todos os estados iniciais de processamento, mas deve cobrir os estados operacionais que o usuário citou: falta agendamento/agendador, falta OK do NIR e encerramento.

### D3. Layout mobile: separar status/pendência de data

No card do dashboard, evitar colocar badge longo e data na mesma linha estreita. Recomenda-se:

- área de badges com `d-flex flex-wrap gap-1` e classe dedicada, por exemplo `dashboard-case-badges`;
- data/hora em linha/coluna própria no mobile, podendo ficar abaixo dos badges;
- desktop pode preservar layout em colunas, desde que badges não estourem.

### D4. CSS pontual para badges quebráveis

Adicionar classe dedicada em vez de alterar globalmente todos os `.badge`:

```css
.badge-wrap {
  max-width: 100%;
  white-space: normal;
  overflow-wrap: anywhere;
  text-align: left;
  line-height: 1.25;
}
```

Usar a classe apenas nos badges que podem receber texto longo (`result_label`, `next_step_label`, badge do resultado final).

### D5. Resultado Final: evitar overflow e preservar texto descritivo

No card `Resultado Final`, o badge pode usar label compacto ou apenas receber `badge-wrap`. Preferência: usar label compacto para o chip e manter o texto completo/explicativo no corpo (`result_info.body` e campo `Fluxo`) para não perder informação.

O detalhe NIR/dashboard deve continuar mostrando o fluxo completo no campo textual quando já existe (`result_info.flow`) ou no corpo explicativo.

## Slices

### Slice 001 — Cards do dashboard: badge compacto + próximo passo

Entrega valor na lista principal: corrige sobreposição em mobile e adiciona sub-badge de próximo passo.

Arquivos esperados:

- `apps/dashboard/views.py`
- `templates/dashboard/_case_list.html`
- `apps/dashboard/tests/test_dashboard.py`
- `static/css/app.css` se necessário

### Slice 002 — Detalhe do caso: Resultado Final mobile sem overflow

Entrega correção no detalhe: badge do Resultado Final não transborda no mobile, preservando texto completo fora do badge.

Arquivos esperados:

- `templates/intake/case_detail.html`
- `apps/dashboard/views.py` e/ou `apps/intake/views.py` somente se precisar passar label compacto
- testes em `apps/dashboard/tests/test_dashboard.py` e/ou `apps/intake/tests/test_case_detail.py`
- `static/css/app.css` se necessário

## Preservação de comportamento

- Sem migrations.
- Sem mudança em `CaseStatus` ou transições FSM.
- Sem mudança de permissões.
- Sem alteração de queries/filtros/paginação.
- Sem alteração das opções completas que o médico escolhe.

## Rollback

Reverter templates, helpers de presenter, CSS e testes deste change. Não há alteração de dados.
