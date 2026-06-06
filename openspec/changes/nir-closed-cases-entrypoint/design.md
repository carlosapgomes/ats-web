# Design: Entrada NIR para Casos Encerrados

## Decisão

Manter duas experiências separadas:

1. `Meus Casos`: fila operacional do NIR, sem casos `CLEANED`.
2. `Casos Encerrados`: busca de casos concluídos para abertura de
   intercorrência pós-agendamento.

Não devemos corrigir o problema colocando `CLEANED` em `Meus Casos`, pois isso
contraria a regra operacional já coberta por testes: casos concluídos saem da
fila operacional.

## Ajuste esperado de UI

Adicionar a aba/link `Casos Encerrados` nos menus NIR relevantes, especialmente:

- `templates/intake/my_cases.html`
- `templates/intake/intake_home.html`

A tela `templates/intake/closed_cases_search.html` já possui a aba ativa.

## Ajuste esperado no filtro de status

A página `Meus Casos` hoje recebe `status_labels` completo, incluindo
`CLEANED`. Como a query exclui `CLEANED`, selecionar esse status não retorna
nada e parece bug para o usuário.

A solução preferida é passar para o template uma lista de status operacionais,
sem `CLEANED`, preservando a query atual:

```text
status_labels sem CaseStatus.CLEANED
```

Opcionalmente, se for mais claro, exibir texto curto perto dos filtros:

```text
Casos concluídos ficam em Casos Encerrados.
```

## Testes esperados

- NIR vê link `Casos Encerrados` em `Meus Casos`.
- NIR vê link `Casos Encerrados` em `Novo Encaminhamento`/home.
- Select de status de `Meus Casos` não inclui `CLEANED`/`Concluído`.
- `Meus Casos` continua não listando casos `CLEANED`.
- `closed_cases_search` continua encontrando caso `CLEANED` por número da
  ocorrência.

## Riscos

| Risco | Mitigação |
| --- | --- |
| Misturar fila operacional com arquivo de concluídos | Não alterar queryset de `Meus Casos` |
| Quebrar busca de intercorrência já implementada | Teste de regressão em `closed_cases_search` |
| Duplicar menus inconsistentes | Usar o mesmo padrão de abas já existente nos templates |
