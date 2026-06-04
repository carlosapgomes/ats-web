# Proposal: Alinhar anotações UUID em parâmetros de rota

**Change ID**: `align-uuid-route-parameter-annotations`  
**Risco**: ESSENCIAL (tipagem/refactor, sem mudança funcional esperada)

## Contexto

Durante o change `post-schedule-intercurrence`, foi observado que views com
rotas Django `<uuid:case_id>` ainda anotam `case_id` como `str` em alguns apps.
Isso reduz precisão de tipagem. O padrão aparece em mais de um app, então deve
ser tratado como refactor transversal pequeno, não como ajuste isolado do
scheduler.

## Objetivo

Alinhar type hints de parâmetros recebidos por converters `<uuid:...>` para
`uuid.UUID`, preservando comportamento runtime e testes.

## Escopo

- Inventariar views com rotas `<uuid:...>` e parâmetro anotado como `str`.
- Ajustar anotações para `uuid.UUID` onde o converter Django entrega UUID.
- Ajustar imports e testes, se necessário.
- Não alterar URLs, nomes de rotas ou comportamento.

## Fora de escopo

- Alterar campos de modelo.
- Mudar serialização de IDs em templates.
- Refatorar serviços que realmente recebem string externa.
- Corrigir todos os `case_id: str` de schemas/LLM, pois esses podem representar
  payload textual e não rota Django.

## Critérios de sucesso

- Views com `<uuid:...>` usam anotação `uuid.UUID`.
- `mypy` permanece verde.
- Suíte completa permanece verde.
- Nenhuma mudança funcional foi introduzida.
