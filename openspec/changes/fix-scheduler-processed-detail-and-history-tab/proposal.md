# Proposal: Corrigir detalhe do agendador e aba de busca histórica

**Change ID**: `fix-scheduler-processed-detail-and-history-tab`  
**Fase**: correção UX/segurança operacional pós-`scheduler-processed-today-tab` e pós-`scheduler-historical-intercurrence-requests`  
**Risco**: PROFISSIONAL (altera navegação e template de detalhe do agendador; não altera FSM nem models)  
**Dependências**: `scheduler-processed-today-tab`, `scheduler-historical-intercurrence-requests`, `case-operational-communication-mvp`, `case-communication-mentions-notifications`

## Problemas

### P1. `Processados Hoje` abre detalhe com template operacional do NIR

Na aba do agendador `Processados Hoje`, o botão `Ver detalhes` usa a rota:

```text
/scheduler/processed/<case_id>/
```

A view `apps/scheduler/views.py::scheduler_processed_detail` renderiza hoje:

```text
templates/intake/case_detail.html
```

Esse template é o detalhe operacional do NIR. Mesmo com algumas flags, ele ainda contém blocos e microcopy de NIR, incluindo ações de reenvio/correção e outras mensagens que não pertencem ao papel `scheduler`.

Resultado prático:

- o agendador vê uma tela parecida demais com a visão do NIR;
- o agendador pode ver ação/mensagem de `Reenviar caso corrigido`, que não deve aparecer para ele;
- o agendador não tem, a partir do caso processado hoje, o mesmo caminho claro para mandar mensagem ao NIR que existe no detalhe vindo da busca histórica;
- o usuário precisa buscar novamente um caso que acabou de processar para abrir a tela mais adequada.

### P2. Existem duas experiências de detalhe para o mesmo papel

Hoje o agendador vê detalhes por pelo menos dois caminhos:

| Origem | View | Template |
| --- | --- | --- |
| `Processados Hoje` | `scheduler_processed_detail` | `templates/intake/case_detail.html` |
| Busca histórica / contexto | `scheduler_context_detail` | `templates/scheduler/context_detail.html` |

Isso viola a expectativa de produto: o detalhe do agendador deve ser uma experiência única, read-only, sem ações de NIR, com comunicação operacional ao NIR quando aplicável.

### P3. Busca de caso antigo aparece como botão pouco visível

Na página do agendador, a busca histórica aparece como um botão pequeno com ícone/lupa:

```text
🔍 Buscar histórico
```

A navegação principal só mostra:

```text
Pendentes | Processados Hoje
```

Para o fluxo operacional, `Buscar caso antigo` é uma área tão importante quanto as outras abas. A UI deveria seguir o padrão mental das três entradas, semelhante ao NIR.

## Objetivos

1. Fazer `Processados Hoje` abrir o **mesmo template de detalhe do agendador** usado pela busca histórica/contextual.
2. Garantir que o detalhe do agendador nunca renderize ações exclusivas do NIR, especialmente `Reenviar caso corrigido` ou confirmação de recebimento.
3. Permitir que o agendador envie mensagem operacional ao NIR a partir de caso processado hoje, sem precisar buscar o caso novamente.
4. Manter a mensagem do agendador como comunicação operacional: não reabre caso, não muda FSM e não substitui a intercorrência estruturada do NIR.
5. Trocar o botão discreto de busca histórica por uma terceira aba/entrada principal: `Buscar caso antigo`.
6. Manter slices verticais, enxutos e com TDD.

## Escopo

### Funcionalidades

1. **Detalhe único do agendador**
   - `scheduler_processed_detail` deve parar de renderizar `templates/intake/case_detail.html`.
   - `Processados Hoje` e busca histórica devem usar o mesmo template de detalhe do scheduler (`templates/scheduler/context_detail.html` ou sucessor equivalente).
   - O template do scheduler deve continuar read-only para workflow.

2. **Mensagem ao NIR a partir de processados hoje**
   - O detalhe do scheduler deve mostrar a ação `Comunicar NIR` para casos em escopo histórico/processado do scheduler, inclusive os processados hoje.
   - O endpoint existente `scheduler_historical_message_nir` pode ser reaproveitado se as validações de escopo continuarem corretas.
   - A mensagem deve garantir `@nir`, preservar menções adicionais e não alterar `Case.status`.

3. **Remoção de ações indevidas no detalhe do scheduler**
   - O detalhe do scheduler não deve mostrar:
     - `Reenviar caso corrigido`;
     - `Confirmar Recebimento`;
     - formulário de agendamento/recusa;
     - resposta estruturada de intercorrência;
     - ações administrativas/NIR.

4. **Busca antiga como aba**
   - Navegação principal do agendador passa a mostrar:

```text
Pendentes | Processados Hoje | Buscar caso antigo
```

   - A aba `Buscar caso antigo` aponta para `scheduler:historical_search`.
   - A página de busca histórica deve mostrar a mesma navegação, com essa aba ativa.

## Fora de escopo

- Criar novo model/tabela de solicitação ao NIR.
- Criar novo estado FSM.
- Permitir que o agendador reabra ou mova diretamente caso para `WAIT_APPT`.
- Alterar o fluxo estruturado de intercorrência do NIR.
- Alterar permissões de NIR, médico, dashboard ou admin.
- Busca avançada por período, paginação, exportação ou filtros adicionais.
- WebSocket/SSE/push/SMS/email operacional.
- Refactor amplo de todos os detalhes read-only do sistema.

## Critérios globais de sucesso

- `Processados Hoje` abre detalhe do scheduler, não o template operacional do NIR.
- O detalhe aberto a partir de `Processados Hoje` não mostra `Reenviar caso corrigido`.
- O detalhe aberto a partir de `Processados Hoje` mostra `Comunicar NIR` quando o caso está no escopo scheduler.
- O agendador consegue enviar mensagem ao NIR a partir de caso processado hoje.
- A mensagem criada contém/gera menção a NIR e não altera `Case.status`.
- Busca histórica e Processados Hoje usam um único template de detalhe do scheduler.
- A navegação do scheduler mostra `Pendentes`, `Processados Hoje` e `Buscar caso antigo` como abas/links principais.
- O botão pequeno separado de busca histórica é removido.
- Testes relevantes são criados/ajustados via TDD.
- Quality gate do `AGENTS.md` passa.
- Cada slice gera relatório markdown temporário com `REPORT_PATH` para revisão por terceiro LLM.
