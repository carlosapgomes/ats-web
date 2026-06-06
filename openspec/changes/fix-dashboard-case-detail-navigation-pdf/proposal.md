# Proposal: Corrigir detalhe de caso do dashboard e acesso a PDF

**Change ID**: `fix-dashboard-case-detail-navigation-pdf`  
**Risco**: ESSENCIAL  
**Origem**: teste manual no dashboard de supervisor/administrador

## Contexto

Supervisor (`manager`) e administrador (`admin`) acessam o dashboard e clicam em
"Ver detalhes" de um caso. O link aponta corretamente para a rota do dashboard:

```text
/dashboard/<case_id>/
```

Porém a view `dashboard_case_detail` reutiliza o template do NIR:

```text
templates/intake/case_detail.html
```

Esse template contém navegação fixa do NIR no topo:

```text
Novo Encaminhamento
Meus Casos
```

Como consequência, supervisor e administrador veem abas operacionais do NIR em
uma página que deveria ser gerencial/read-only.

Durante a investigação também foi identificado que o bloco de PDF do mesmo
template aponta para a rota NIR `intake:serve_pdf`, protegida por `role_required("nir")`.
Assim, caso o detalhe gerencial exiba PDF, supervisor/admin podem ver a página,
mas não têm uma rota autorizada para abrir/embutir o PDF.

## Problema

A reutilização do template de detalhe NIR no dashboard mistura contexto
operacional e contexto gerencial:

- abas `Novo Encaminhamento` e `Meus Casos` aparecem indevidamente para
  supervisor/admin;
- o botão inferior `Voltar para lista` aponta para `intake:my_cases`, que também
  é uma navegação NIR;
- o embed/link de PDF usa rota NIR e não contempla acesso gerencial;
- a view do dashboard já é própria e read-only, mas o template não diferencia a
  superfície de origem.

## Objetivo

Corrigir o detalhe de caso aberto pelo dashboard para que supervisor e
administrador vejam uma experiência gerencial consistente e tenham acesso ao PDF
do caso quando houver arquivo anexado.

## Escopo

- Remover/ocultar navegação NIR no detalhe quando renderizado pelo dashboard.
- Substituir o botão de retorno NIR por retorno ao dashboard para supervisor/admin.
- Criar ou expor rota segura de PDF para dashboard com acesso apenas a
  `manager` e `admin`.
- Parametrizar o template compartilhado para usar a URL de PDF adequada por
  superfície.
- Preservar comportamento atual do NIR no detalhe operacional.
- Adicionar testes de regressão para manager e admin.

## Fora de escopo

- Reescrever toda a página de detalhe em templates separados, salvo se a
  implementação demonstrar que a parametrização ficaria insegura ou confusa.
- Alterar permissões da rota operacional `intake:serve_pdf` para incluir
  manager/admin.
- Alterar regras de negócio, FSM, status ou auditoria.
- Alterar visibilidade de dados clínicos além do PDF já associado ao caso.
- Criar API REST ou endpoints JSON.

## Critérios de sucesso

- Supervisor/admin acessam `/dashboard/<case_id>/` sem ver `Novo Encaminhamento`.
- Supervisor/admin acessam `/dashboard/<case_id>/` sem ver `Meus Casos`.
- Supervisor/admin veem navegação/ação de retorno apropriada ao dashboard.
- Supervisor/admin conseguem abrir/embutir o PDF do caso quando `pdf_file` existe.
- Usuários sem papel `manager` ou `admin` não acessam a rota de PDF gerencial.
- NIR continua vendo as abas e usando a rota de PDF operacional no detalhe NIR.
- Testes relevantes passam.
