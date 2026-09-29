# queue-filtering — delta: URLs dos JS das filas com hash do manifest

## ADDED Requirements

### Requirement: Script tags das filas com URLs cache-busted

Os templates das filas do scheduler e do médico SHALL referenciar seus
JavaScript via tag `{% static %}`, de modo que em produção as URLs contenham o
hash do manifest e cada deploy sirva HTML e JS consistentes entre si.

#### Scenario: URLs com hash em produção

- **WHEN** as filas são renderizadas em produção (manifest storage ativo)
- **THEN** os `<script>` apontam para `scheduler_queue_filter.<hash>.js` e
  `doctor_queue_filter.<hash>.js`, mudando a cada deploy que altere os arquivos.

#### Scenario: Nenhuma URL fixa restante

- **WHEN** o repositório é inspecionado
- **THEN** não existe `src="/static/` nem `href="/static/` hardcoded em
  `templates/` e as filas seguem renderizando com sucesso.
