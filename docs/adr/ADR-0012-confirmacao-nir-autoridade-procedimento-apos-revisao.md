# ADR-0012: Confirmação NIR como autoridade do procedimento após revisão manual

## Status

Accepted — intenção de produto e contrato técnico ADR-0012/design D1–D9 aceitos explicitamente pelo owner em 2026-10-09. Execução dos slices autorizada via change-loop; aceite técnico não afirma implementação, implantação ou recuperação de casos de produção.

## Contexto

Casos de produção 5073320 e 5075227 repetiram gates de procedimento após uploads/correções. A resolução restrita da ADR-0011 não atende evidências sem cobertura na matriz ou confirmação da mesma seleção. O operador decidiu que a revisão manual do NIR deve resolver a identificação sem exigir reescrita do relatório e que a Linha do Tempo deve identificar quem confirmou qual procedimento.

Há também falha técnica independente: U+0000 em JSON LLM1 rejeitado pelo PostgreSQL; handler reutiliza a instância contaminada, falha ao auditar e retorna sucesso ao worker, deixando LLM_STRUCT órfão. Essa falha não pode ser resolvida por autoridade humana sobre identificação.

## Decisão

1. **Consentimento humano explícito, não declaração comum:** somente em revisão elegível pré-médica, NIR com lease válido confirma a seleção permitida (mesma ou diferente), leitura e justificativa. O evento append-only `CASE_PROCEDURE_REVIEW_CONFIRMED` registra actor, conjuntos anterior/confirmado, revisão relacionada e fingerprint da fonte.
2. **Autoridade delimitada:** confirmação válida define o conjunto operacional da análise daquela fonte, sem condicioná-lo à best-covering ou concordância do detector. Não permite combinação nova, contornar schema/segurança/policy, inventar exames ou decidir aceitação médica. Fonte/revisão/declaração alteradas invalidam a confirmação.
3. **Proveniência separada:** LLM1 e união bruta dos eventos de detecção continuam intactos; `CaseProcedure.detection_status` permanece projeção operacional pós-reconciliação, agora com proveniência humana explícita nos eventos/artefato final/labels. A decisão médica permanece exclusivamente em doctor_disposition.
4. **Auditoria visível:** Linha do Tempo identifica pessoa, data/hora e procedimento confirmado, inclusive seleção mantida; justificativa escapada. Aplicação automática/invalidação são eventos sistêmicos distintos. Médico recebe aviso não bloqueante antes da decisão.
5. **Dados ausentes não são fabricados:** o conjunto fechado LLM2 vem da confirmação; um procedimento ausente no array LLM1 usa dados comuns/unknown, sem evidence_spans clínicos sintéticos nem exceção herdada.
6. **Persistência segura independente:** rejeitar U+0000 antes de writes de artefato/projeção; tratar erros com Case limpo e payload seguro. Falha ao persistir o desfecho de erro deve sair ao worker, não parecer sucesso. Sem normalização clínica silenciosa.
7. **Sem migração/backfill:** CaseEvent é autoridade; correções legadas não ganham consentimento retroativo. Rollout web/worker coordenado; depois de novos eventos de autoridade em voo, fix-forward é preferível a binário antigo que os ignore.

Esta ADR supera **parcialmente ADR-0011 decisões 2 e 5** apenas na presença de confirmação humana válida. Detecção/reconciliação automática, precedências ADR-0008/0010, best-covering e fail-closed sem confirmação permanecem. A matriz fechada e a decisão médica não são superadas.

## Alternativas Consideradas

1. **Só permitir seleção igual:** menor delta de UI, mas reprocessamento pode repetir gate; rejeitada como solução isolada.
2. **Ampliar heurísticas de argônio e capacidade CPRE:** reduz alguns falsos conflitos, mas não fornece saída geral nem autoridade à revisão humana; fora deste change.
3. **Exigir PDF reescrito ou override administrativo de status:** não atende operação e pode pular análise/decisão; rejeitada.
4. **Guardar `force=true` mutável no Case/task:** simples consumo, mas cria autoridade sem evento/fonte e consentimento implícito; evento append-only vinculado à revisão foi escolhido.
5. **Permitir revisão humana inclusive de policy/aceite:** extrapola o papel NIR; rejeitada.

## Consequências

### Positivas

- Revisão manual tem efeito determinístico; confirmação mantida deixa de ser proibida.
- Não exige relatório reescrito para corrigir interpretação automática.
- Evidências automática e humana ficam distinguidas e auditáveis; médico mantém controle clínico.
- Falhas de persistência não desaparecem da timeline enquanto o job parece sucesso.

### Negativas/Trade-offs

- O roteamento passa a depender de evento histórico/fingerprint (trade-off antes rejeitado na ADR-0011, agora deliberadamente escolhido).
- Campo legado chamado detection_status é projeção do conjunto efetivo, exigindo labels de origem humana quando aplicável.
- Escopo transversal >5 arquivos necessário para entregar ação, pipeline e visibilidade sem slice horizontal.
- Rollback para binário antigo pode ignorar confirmação; cutover coordenado e fix-forward após primeiro evento.

### Riscos e Mitigações

- **Confirmação humana errada:** justificativa, consentimento, autoria, aviso médico; sem aprovação automática.
- **Consentimento reaplicado a outra fonte:** fingerprint/revisão/declaração revalidados; não escolher evento antigo como fallback.
- **Informação clínica ausente:** unknown e policy preservada, sem fabricações.
- **Sucesso falso após falha do handler:** exceção propagada ao worker e teste fault-injection.
- **PII em evidências/logs:** fixtures sintéticas; erro técnico controlado, sem raw clínico/SQL recusado.

## Histórico de Mudanças

- 2026-10-09: Criada como Proposed; produto aprovado pelo operador, implementação não iniciada. Design completo, migração/rollback e slices em `openspec/changes/confirm-nir-procedure-review-and-harden-pipeline/`.
- 2026-10-09: Owner confirmou explicitamente o aceite técnico da ADR-0012 e design D1–D9 e autorizou registrar task 0.1 como concluída. Status alterado para Accepted, sem mudar as decisões aprovadas.
