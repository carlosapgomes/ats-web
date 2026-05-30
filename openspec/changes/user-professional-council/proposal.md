# Proposal: Dados de conselho profissional no usuário

**Change ID**: `user-professional-council`
**Risco**: ESSENCIAL (campos opcionais em `User`, migration aditiva, UI administrativa)
**Dependências**: Gestão de usuários existente em `apps/admin_ui/`

## Objetivo

Permitir cadastrar, editar e visualizar dados facultativos de conselho profissional em usuários do sistema, para uso posterior em listagens e interfaces onde a identificação profissional seja necessária.

## Escopo

### Funcionalidades

1. Adicionar ao modelo `User` dois campos opcionais:
   - `professional_council`: conselho profissional, restrito a `COREN` e `CRM`.
   - `professional_council_number`: número/registro no conselho profissional.

2. Validar consistência dos campos:
   - ambos vazios: permitido;
   - conselho preenchido sem número: inválido;
   - número preenchido sem conselho: inválido.

3. Expor os campos na gestão de usuários (`admin_ui`):
   - formulário de criação;
   - formulário de edição;
   - listagem de usuários com exibição compacta, por exemplo `CRM 12345` ou `—`.

4. Expor os campos no Django Admin para manutenção técnica.

5. Cobrir com testes de modelo e CRUD administrativo.

## Fora de escopo

- Múltiplos conselhos por usuário.
- Histórico/auditoria específica de alteração dos dados profissionais.
- Validação externa contra conselhos profissionais.
- Campos de UF, data de validade, anexos ou comprovantes.
- Busca/filtro por conselho ou número na listagem; pode ser feito em change futuro se necessário.

## Observações de domínio

- Usar `COREN` para Conselho Regional de Enfermagem.
- Usar `CRM` para Conselho Regional de Medicina.
- Não criar choice separada para CREMEB neste momento; tratar como `CRM`.