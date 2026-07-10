# Proposal: Fluxos de aceite médico com ciência operacional do CHD

**Change ID**: `doctor-admission-operational-flows`  
**Fase**: ajuste de fluxo operacional médico/NIR/CHD  
**Risco**: PROFISSIONAL — altera decisão médica, roteamento de casos aceitos, fila do CHD, resultado do NIR e métricas gerenciais.  
**Classificação**: `classify-change-risk` em 2026-07-10 → PROFESSIONAL; `design.md` obrigatório.

## Problema

No aceite médico atual, o campo **Suporte Necessário** permite `Anestesista + UTI`. Isso induz o CHD/agendador a entender que a reserva de UTI faz parte da sua atribuição operacional, mas em pacientes de transferência essa reserva cabe ao NIR.

Além disso, o campo **Fluxo de Admissão** tem apenas:

- `Agendamento` — abre fila operacional para o CHD agendar;
- `Vinda Imediata` — não abre agendamento; CHD apenas toma ciência operacional e NIR conduz o restante.

Há outros fluxos que também dependem de ação prévia do NIR antes de qualquer agenda do CHD:

- vinda prévia para UTI;
- vinda para enfermaria com retaguarda em UTI;
- compartilhamento com coordenador da EM Pediátrica.

Hoje não há como registrar essas diferenças de forma estruturada no aceite médico.

## Objetivo

Ajustar o aceite médico para refletir melhor a divisão real de responsabilidades:

1. Médico escolhe suporte CHD apenas entre `Nenhum` e `Anestesista`.
2. Médico escolhe um dos cinco fluxos de admissão:
   - `Agendamento`;
   - `Vinda Imediata`;
   - `Vinda prévia para UTI`;
   - `Vinda para enfermaria (para retaguarda em UTI)`;
   - `Compartilhar com EM pediátrica`.
3. Apenas `Agendamento` abre fila de agendamento para o CHD.
4. Todos os demais fluxos geram ciência operacional para o CHD e resultado final para o NIR, sem abrir agendamento.
5. NIR vê mensagens específicas por fluxo para orientar a ação esperada.
6. CHD consegue ver histórico de ciências operacionais, incluindo quem confirmou ciência.
7. Dashboard mostra métricas separadas por fluxo de admissão.

## Escopo

### Incluído

- Atualizar opções do formulário médico e validação backend.
- Manter compatibilidade de exibição para casos históricos com `anesthesist_icu`.
- Persistir novos valores estruturados em `doctor_admission_flow` sem migration, usando códigos curtos compatíveis com `max_length=15`.
- Roteamento de `accept + fluxo não agendamento` para resultado final/NIR com ciência operacional CHD.
- Mensagens específicas no CHD e no NIR por fluxo.
- Histórico CHD de ciências operacionais com ator da confirmação.
- Métrica gerencial de fluxo de admissão com contagem separada dos cinco fluxos.
- Testes de formulário, submit médico, fila/histórico CHD, NIR e dashboard.

### Fora de escopo

- Integração da EM Pediátrica ao sistema.
- Novo papel de usuário para EM Pediátrica.
- Automação de reserva de UTI ou enfermaria.
- Alteração do pipeline LLM para impedir `anesthesist_icu` como recomendação automática.
- Migration de schema para enum/tabela de domínio.
- Migração retroativa de casos históricos `anesthesist_icu`.

## Critérios de sucesso

- Médico não consegue selecionar `Anestesista + UTI` no campo final de suporte.
- Backend rejeita POST novo com `support_flag=anesthesist_icu`.
- Médico consegue selecionar os cinco fluxos de admissão.
- `accept + scheduled` continua indo para `WAIT_APPT`.
- `accept + immediate/pre_icu/ward_icu_backup/pediatric_em` não abre `WAIT_APPT`.
- CHD vê cards de ciência operacional para todos os fluxos não agendamento, com mensagens específicas.
- CHD confirma ciência com o mesmo botão para todos os fluxos não agendamento.
- Após ciência, o item sai da fila ativa e aparece no histórico de ciências com ator e data/hora.
- NIR vê mensagem final específica conforme fluxo escolhido.
- Dashboard mostra contagem separada dos cinco fluxos.
- Quality gate do `AGENTS.md` passa antes de commit/push da implementação.
