# Proposal: Tornar acessível a busca NIR de casos encerrados

**Change ID**: `nir-closed-cases-entrypoint`  
**Risco**: ESSENCIAL  
**Origem**: bug/UX observado em teste manual da feature
`post-schedule-intercurrence`

## Contexto

A feature de intercorrência pós-agendamento foi implementada e arquivada em:

```text
openspec/archive/post-schedule-intercurrence/
```

O Slice 002 criou a busca específica de casos encerrados em:

```text
/intake/closed-cases/
```

Essa rota permite ao NIR localizar casos `CLEANED` e abrir intercorrência quando
o caso for elegível. Porém, em teste manual, o usuário NIR tentou usar a busca e
o filtro da página operacional `Meus Casos`. Essa página exclui casos
`CLEANED`, por desenho operacional, e portanto não retorna casos concluídos.

## Problema

A funcionalidade existe, mas o ponto de entrada está pouco visível e o filtro de
status da fila operacional induz o usuário a procurar casos concluídos no lugar
errado.

## Objetivo

Melhorar a descoberta da busca de casos encerrados pelo NIR, sem misturar casos
`CLEANED` na fila operacional.

## Escopo

- Adicionar link/aba `Casos Encerrados` nas telas principais do NIR.
- Evitar que o filtro operacional `Meus Casos` sugira que `CLEANED` será listado
  ali.
- Manter `Meus Casos` como fila operacional, sem casos `CLEANED`.
- Manter `/intake/closed-cases/` como fluxo oficial para buscar casos concluídos
  e abrir intercorrência.
- Adicionar testes de caracterização/UX para o novo ponto de entrada.

## Fora de escopo

- Alterar regra de elegibilidade de intercorrência.
- Permitir casos `CLEANED` na fila operacional `Meus Casos`.
- Alterar FSM ou serviços de domínio.
- Criar busca avançada ou paginação nova.
- Alterar permissões além do papel `nir` já existente.

## Critérios de sucesso

- NIR consegue encontrar claramente o caminho `Casos Encerrados` a partir das
  telas NIR principais.
- Filtro de status em `Meus Casos` não oferece caminho enganoso para casos
  concluídos.
- Busca `/intake/closed-cases/` continua encontrando casos `CLEANED` por
  ocorrência/nome.
- Testes relevantes passam.
