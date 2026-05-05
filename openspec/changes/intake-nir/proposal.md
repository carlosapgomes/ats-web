# Change Proposal: Intake NIR

## Resumo

Implementar o fluxo completo de intake do operador NIR: upload de PDF, criação do caso, extração de texto, lista de "meus casos" e tela de detalhe com timeline.

## Motivação

Primeiro fluxo end-to-end do sistema. É o ponto de entrada de todos os casos de triagem EDA.

## Risco

**ESSENCIAL** — fluxo de CRUD com upload de arquivo e processamento síncrono. Sem integrações externas.

## Scope

- App Django `apps/intake/` com views exclusivas do papel NIR
- Integração da paleta hospitalar do demo-reference no template base
- Upload de PDF com drag & drop (Vanilla JS)
- Criação do Case com transição FSM NEW → R1_ACK_PROCESSING → EXTRACTING
- Extração de texto do PDF via PyMuPDF (síncrono)
- Lista de "Meus Casos" com cards por status
- Tela de detalhe do caso com timeline de CaseEvents
- Proteção de views por role (apenas `nir`)

## Non-Goals

- Pipeline LLM (Fase 2)
- Decisão médica (Fase 3)
- Agendamento (Fase 4)
- Resultado final / confirmação (Fase 5)
- Extração automática do número de registro (pode ser manual no primeiro slice)
- Notificações em tempo real (websocket/polling)
