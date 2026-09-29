# queue-filtering — delta: filtro por tipo via `<select>` com aplicação imediata

## ADDED Requirements

### Requirement: Filtro por tipo de exame em `<select>` com aplicação imediata

As filas do scheduler e do médico SHALL oferecer UM controle `<select>` por aba para
filtrar por tipo de exame; trocar a seleção SHALL filtrar os cards imediatamente, sem
botão de ação adicional.

#### Scenario: Seleção filtra na hora sem clique extra

- **WHEN** o usuário troca a option do select de tipo de exame
- **THEN** os cards fora do tipo ficam `hidden` imediatamente, sem acionar
  nenhum outro botão.

#### Scenario: Universo do catálogo preservado

- **WHEN** a fila é renderizada
- **THEN** o select contém `Todos` (default) + uma option por conjunto do
  catálogo entregue pelo backend (médico/Decididos inclui `Nenhum autorizado`),
  com contadores refletidos no texto das options.

#### Scenario: Estado da fila preservado

- **WHEN** o poll htmx substitui os cards (ou o usuário usa a busca do médico)
- **THEN** a seleção do select é mantida e o filtro reaplicado sem reset;
  status e aviso sem-resultado seguem informados.
