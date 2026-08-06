# ADR-0004: Procedimentos múltiplos e contrato LLM neutro

## Status

Accepted

**Aceita em:** 2026-08-06

**Supera parcialmente:** [ADR-0003 — Perfis de procedimento e tipo de exame explícito](ADR-0003-perfis-procedimento-tipo-exame-explicito.md), decisões 1, 2, 3, 5, 6, 8 e 9.

**Change associado:** [`support-combined-eda-colonoscopy-workflow`](../../openspec/changes/support-combined-eda-colonoscopy-workflow/proposal.md).

## Contexto

O ATS já suporta EDA e Colonoscopia isoladas por meio de `Case.exam_type`, profiles/policies e prompts separados. Entretanto, a rotina hospitalar também recebe solicitações atuais de EDA + Colonoscopia que devem compartilhar paciente, história clínica, caso e horário. O comportamento atual classifica essa combinação como `mixed_exam_request` e exige separação em dois casos.

Usar um único tipo mutável não preservaria a diferença entre:

- o conjunto declarado pelo NIR;
- o conjunto detectado na solicitação atual;
- o conjunto autorizado pelo médico.

Criar dois casos ou executar dois pipelines completos duplicaria história clínica, decisões, auditoria e agendamento, além de permitir recomendações conflitantes. A solução precisa preservar os dados e contratos históricos, continuar SSR, manter os estados FSM existentes e possibilitar rollback seguro durante uma migração transversal.

As decisões foram formalizadas no change OpenSpec `support-combined-eda-colonoscopy-workflow`, classificado como CRÍTICO/HIGH-ARCH.

## Decisão

1. **Um caso, componentes normalizados.** Um PDF cria exatamente um `Case`. EDA e Colonoscopia são rows únicas de `CaseProcedure`, com constraint `(case, procedure_type)`. Não existe row genérica `combined`, segundo caso ou segundo appointment.
2. **Três dimensões autoritativas.** `declared_by_nir`, `detection_status` e `doctor_disposition` representam, respectivamente, declaração, detecção e autorização. Nenhuma dimensão sobrescreve outra; `CaseEvent` preserva fatos append-only.
3. **Intake e reconciliação por conjunto.** O NIR escolhe EDA, Colonoscopia ou EDA + Colonoscopia. Single→combined com evidência forte recebe upgrade automático auditado e segue ao médico sem ACK. Combined→single, troca entre tipos únicos e unknown/non-supported retornam ao NIR.
4. **Contrato LLM procedure-neutral 2.0.** Novos casos usam uma chamada LLM1 para história comum e `requested_procedures[]`, policy determinística por procedimento e uma chamada LLM2 com recomendação exata por componente. Artefatos 1.1 permanecem legíveis e não são reescritos.
5. **Quatro prompts neutros.** Novos jobs usam `exam_llm1_system`, `exam_llm1_user`, `exam_llm2_system` e `exam_llm2_user`. Versões antigas são preservadas para auditoria/rollback, mas deixam de participar do dispatch após drenagem e cutover.
6. **Decisão médica por componente.** O médico pode aprovar, negar, incluir ou substituir procedimentos. Negativa e inclusão divergente exigem razão por componente; inclusão não reexecuta LLM. A sugestão global de suporte usa o requisito mais restritivo, mas a escolha final permanece médica.
7. **Um agendamento casado.** O CHD recebe somente o conjunto aprovado e confirma uma única data, hora e localização. Ambos aprovados são apresentados como `EDA + Colonoscopia · Agendamento casado`; o CHD não altera silenciosamente os componentes.
8. **Histórico, filas e analytics dimensionais.** Históricos são consultados separadamente por `procedure_type`. NIR filtra pelo declarado, médico pelo detectado/autorizado e CHD pelo autorizado. Analytics separam casos, componentes, agendamentos casados e conversões declarado→detectado→autorizado.
9. **Migração preservadora e cutover obrigatório.** `Case.exam_type` funciona apenas como ponte transitória com dual-write centralizado. Backfill preserva casos, eventos, PDFs, decisões, agendas e JSON. Todos os readers/writers são migrados antes da remoção da coluna. Rollback preferencial mantém schema/imagem novos; imagem antiga exige bridge fail-closed e drenagem.
10. **Limites mantidos.** Os 18 valores executáveis atuais de `CaseStatus`, roles, locks, intranet guard, policies clínicas compartilhadas, flag web-only e alerta medicamentoso informativo permanecem. CPRE, split de agenda e recomendação automática de suspensão medicamentosa continuam fora de escopo.

### Relação com a ADR-0003

| Decisão da ADR-0003 | Situação após esta ADR |
| --- | --- |
| 1 — `Case.exam_type` como fonte operacional | Superada: `CaseProcedure` torna-se fonte após o cutover; `exam_type` é ponte temporária. |
| 2 — um tipo por lote | Superada: o lote recebe uma seleção, que pode conter os dois procedimentos. |
| 3 — solicitação mista vai sempre para revisão | Superada: combinação confirmada pode prosseguir ou receber upgrade automático; divergências continuam em revisão. |
| 5 — evolução incremental discriminada por `exam_type` | Superada: novos processamentos usam schema neutro 2.0; leitura 1.1 permanece. |
| 6 — prompts EDA/Colonoscopia separados | Superada: quatro prompts neutros tornam-se canônicos. |
| 8 — tipo como filtro secundário único | Superada: cada etapa usa sua dimensão declarada, detectada ou autorizada. |
| 9 — correção de tipo singular | Superada: correção altera conjunto declarado, preservando as demais dimensões e eventos. |

Permanecem válidas as decisões 4 (profiles/policy com exceções explícitas), 7 (lifecycle/FSM/locks compartilhados), 10 (feature flag somente para novos intakes) e 11 (alerta medicamentoso sem hard rule).

## Alternativas Consideradas

### 1. Manter `Case.exam_type` singular e continuar bloqueando combinação

- **Vantagens:** nenhuma migration transversal; menor mudança imediata.
- **Desvantagens:** não atende o fluxo real; obriga duplicação manual de caso e agendamento; mantém perda de rastreabilidade.
- **Por que não escolhida:** não entrega o requisito operacional confirmado.

### 2. Criar dois casos e executar dois pipelines independentes

- **Vantagens:** reutiliza integralmente os fluxos simples existentes.
- **Desvantagens:** duplica história, chamadas LLM, decisão e agenda; exige merge não auditável e pode produzir recomendações divergentes.
- **Por que não escolhida:** viola o invariante de um caso e um horário e aumenta risco clínico/operacional.

### 3. Manter extração e prompts separados e mesclar apenas no final

- **Vantagens:** reduz mudanças iniciais nos schemas LLM.
- **Desvantagens:** duplica interpretação clínica e deixa policies/recomendações sem contrato comum; merge continua ambíguo.
- **Por que não escolhida:** não resolve a duplicação na origem nem garante igualdade do conjunto recomendado.

### 4. Extração clínica neutra com avaliações por procedimento — escolhida

- **Vantagens:** uma história comum, separação explícita das regras clínicas, validação exata por componente e auditoria completa.
- **Desvantagens:** exige schema 2.0, novos prompts, modelo normalizado e cutover coordenado.
- **Por que escolhida:** atende integralmente o domínio sem duplicar casos/pipeline e mantém diferenças clínicas tipadas.

### 5. Criar engine genérica para qualquer procedimento, incluindo CPRE

- **Vantagens:** extensibilidade aparente.
- **Desvantagens:** requisitos de CPRE não estão definidos; ampliaria schema, regras e risco sem necessidade atual.
- **Por que não escolhida:** YAGNI; somente EDA e Colonoscopia são suportadas neste change.

## Consequências

### Positivas

- Um caso e um agendamento preservam a unidade assistencial.
- Declaração, detecção e autorização permanecem distinguíveis e auditáveis.
- História clínica é extraída uma única vez.
- Policies e recomendações continuam específicas sem duplicação do pipeline.
- Negativas e inclusões médicas possuem razões granulares.
- Filas e analytics passam a declarar explicitamente a dimensão usada.
- JSON e eventos históricos permanecem legíveis.

### Negativas/Trade-offs

- Mudança transversal em modelo, pipeline, prompts, médico, CHD, NIR e dashboard.
- A branch não é deployável enquanto a ponte existir e os consumidores não estiverem migrados.
- Há custo temporário de dual-write, adapters 1.1/2.0 e prompts legados preservados.
- Rollback para imagem antiga torna-se excepcional e exige bridge de schema/prompt.
- Queries dimensionais exigem índices e validação de plano.

### Riscos e Mitigações

- **Divergência entre ponte e projeção:** serviço único, transação/row lock, testes de correção e remoção obrigatória no Slice 007.
- **Backfill inferir história incorretamente:** tabela fechada por status/marcador, sem leitura de texto clínico e sem reprocessamento.
- **LLM inventar ou omitir componente:** schemas estritos, evidence spans, reconciliação conservadora e igualdade exata no LLM2.
- **Menção histórica causar upgrade:** proveniência por ocorrência e evidência forte de solicitação atual.
- **Decisão médica parcial ou sem razão:** validação fail-closed e persistência atômica por componente.
- **Dupla contagem:** métricas de casos e componentes separadas, com matriz de conversão explícita.
- **Índice insuficiente em filas:** índices dimensionais desde o primeiro slice e revalidação contra queries reais.
- **Imagem antiga incompatível:** flag desligada, writers drenados/parados, backup e bridge executável com asserts binários.
- **Prompts incompatíveis em voo:** uma versão ativa por nome canônico, drenagem e troca serializada entre modos neutro/legado.

## Histórico de Mudanças

- 2026-08-06: ADR criada, revisada e aceita como pré-condição do Slice 001 do change `support-combined-eda-colonoscopy-workflow`.
