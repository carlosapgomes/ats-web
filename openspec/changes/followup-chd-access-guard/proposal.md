# Proposal: Acesso à aba Follow-up restrito a supervisores do CHD

## Problema

Hoje toda pessoa com papel ativo `manager` (ou `admin`) vê e opera a aba Follow-up
(registro de desfechos e Histórico & Exportação). O registro de desfecho
pós-exame é uma operação do **CHD** (Centro de Agendamento Hospitalar), e os
supervisores médicos e do NIR — que também usam o papel `manager` — não deveriam
ter acesso: a aba gera ruído para eles e expõe uma operação que não é deles.

## Decisão do dono (2026-09-06)

1. "Perfil CHD" = papel existente **`scheduler`** (Agendador). Não será criado um
   Role novo; o manual e o sistema já tratam CHD como sinônimo de Agendador.
2. **`admin` ativo continua acessando sem possuir `scheduler`** (papel de
   emergência/suporte).
3. Quem não satisfizer: **aba some da navegação** e **URL redireciona** com
   mensagem de erro (defense in depth, mesma UX do `role_required` atual).

Dados de produção que motivam: dos supervisores ativos, exatamente 5 possuem
`manager`+`scheduler` (equipe CHD); os demais `manager` são supervisores
médicos/NIR e ficarão fora.

## Política de acesso (formulação única)

> Um request pode acessar as rotas de follow-up se, e somente se:
> autenticado **e** papel ativo ∈ {`manager`, `admin`} **e**
> (papel ativo == `admin` **ou** o usuário possui o Role `scheduler`).

Usuários com papel ativo `scheduler` (operadores CHD) continuam **bloqueados**
(o registro exige o papel ativo de supervisor).

## Escopo

- Novo helper de política + decorator composto + variável de contexto em
  `apps/accounts` (primeiro guard "papel ativo + posse de papel" do projeto).
- Aplicação nas 4 views de follow-up (`apps/dashboard/views.py`) e ocultação do
  pill em `templates/dashboard/_nav.html`.
- Deltas de spec MODIFICANDO os requisitos de acesso das duas capabilities
  existentes (`supervisor-appointment-follow-up`, `supervisor-followup-history`).
- Testes: matriz de acesso (unit + views) e visibilidade da aba.

## Não-goals

- Criar/migrar papéis (`Role` é dado existente; nenhuma migration).
- Mudar o guard de intranet (`scheduler` ativo continua restrito à intranet).
- Mudar URLs, templates de conteúdo, flash messages de sucesso, CSV, specs de
  comportamento além dos requisitos de acesso.
- Renomear rótulos de UI (couverture do change `followup-pos-procedimento-ui`).
- Atualizar o manual do usuário (absorvido pelo change de renomeação, que
  reescreve §6 depois deste change).

## Sucesso

- `manager` sem `scheduler`: pill ausente + 4 rotas redirecionam com flash (sem conteúdo).
- `manager` com `scheduler`: comportamento atual preservado (list/form/history/export).
- `admin` (com ou sem `scheduler`): acesso integral.
- `scheduler` ativo (mesmo possuindo `manager`): redirecionado como hoje.
- Suíte completa verde no gate final; specs validadas.
