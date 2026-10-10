# Design — Confirmação humana de procedimento e persistência segura

## Context

Ver `proposal.md` e `evidence.md`. Baseline de leitura: `main` em `6ab9ef7`, produção rc.10. `PROJECT_CONTEXT.md` contém descrições históricas de release; não usá-las como evidência de implantação atual.

Hoje `correct_case_exam_type` serializa com confirmação de recebimento, exige seleção diferente, invalida derivados e retorna a LLM_STRUCT. `run_pipeline` reconcilia novamente o documento. ADR-0011 só resolve conflitos cobertos pela declaração com evidência atual; não há intenção explícita de revisão no histórico. Eventos são criados por post_save de Case. O catch do orchestrator tenta salvar o mesmo objeto que falhou.

## Goals / Non-Goals

**Goals:** revisão NIR efetivamente resolutiva; persistibilidade antes de gravações; autoria/seleção explícitas na Linha do Tempo; evidência bruta intacta; médico informado; menor mudança correta usando os 17 estados existentes.

**Non-Goals:** inferir intenção clínica no detector, ampliar matriz, aceitar combinação Eco+CPRE, aprovar pelo NIR, impor reescrita de PDF, backfill de autoridade, reabrir CLEANED, recovery automático de FAILED, refatorar todas as timelines, alterar contratos externos LLM ou tratar genericamente todos os problemas Unicode.

## Decisions

### D1 — Autoridade explícita, não igualdade de seleções

Novo fluxo substitui a correção operacional no mesmo endpoint interno `exam_type_correction`. Serviço coeso de confirmação (nome sugerido `confirm_case_procedure_review`) aceita `exam_type`, `review_acknowledged`, `review_justification`, `review_event_id`, `source_fingerprint` da tela e o token de reserva existente. Justificativa: trim, 1–500 caracteres, rejeitar U+0000; checkbox desmarcada/ausente não confirma. Motivo codificado da revisão vem do evento de revisão, não de input livre do cliente. Campos de consentimento NÃO têm defaults verdadeiros em backend/form.

Pode manter ou alterar a seleção; ambos exigem os mesmos passos. Não há comparação best-covering, requisito de ocorrência atual ou obrigação de selecionar um tipo já extraído para conceder a autoridade. O humano define **o procedimento solicitado a analisar**, não a disposição médica nem a existência de achados.

Alternativas rejeitadas: somente retirar o `disabled` (loop permanece); `force=true` no task (não é fonte de verdade auditável); atribuir autoridade a toda declaração/EXAM_TYPE_CORRECTED histórica (consentimento inventado).

### D2 — Elegibilidade, reserva e transação

Reutilizar a lista fechada atual de reasons elegíveis em `is_exam_type_correction_eligible`, status WAIT_R1_CLEANUP_THUMBS, manual_review_required, ausência de decisão médica, usuário NIR/papel ativo NIR e lease nir_receipt válido. Só singletons canônicos e EDA+Colonoscopia habilitados pela jornada atual. Não liberar FAILED, CLEANED, transitórios nem WAIT_DOCTOR.

Sob o MESMO `select_for_update` de confirmação de recebimento: revalidar estado, ator/reserva, revisão vista e fonte; gravar confirmação, atualizar declaração se necessário, limpar derivados/resetar projeções, usar a transição FSM existente para LLM_STRUCT, limpar lease. Evento primeiro, transição no save seguinte: não sobrescrever `_pending_event`. Enqueue único pós-commit e recovery já existente continuam, com mensagem verdadeira se enqueue/recovery falhar. Double POST/corrida com cleanup não criam duas confirmações/análises nem estado parcial.

### D3 — CaseEvent é a autoridade durável; sem migration

`CASE_PROCEDURE_REVIEW_CONFIRMED` (humano, actor obrigatório) tem payload versionado:

```text
version: 1
actor_role: nir (validado pelo serviço no momento da confirmação)
review_event_id: ID do EDA_SCOPE_GATED_MANUAL_REVIEW revisado
review_reason_code: reason daquele evento
previous_declared_procedures: códigos em ordem canônica
confirmed_procedures: códigos em ordem canônica
selection_changed: booleano (false é confirmação válida)
justification: texto breve validado
source_fingerprint: sha256 versionado da fonte
```

Fingerprint v1: SHA-256 dos bytes do PDF principal + SHA-256 do texto extraído UTF-8, combinados de forma determinística/versionada. Não incluir nome de arquivo nem anexos: análise automática permanece do documento principal. Form carrega ID da revisão e fingerprint visto; serviço recomputa sob lock e rejeita fonte/revisão que mudou desde o GET. Hash não autentica humano: permissões e lease continuam obrigatórios.

Helper de domínio enxuto em `apps/cases/procedure_review.py` consulta confirmação mais recente (ordem timestamp/id), valida payload, ator/papel registrado no momento da gravação, revisão relacionada, igualdade da declaração canônica atual e fingerprint atual. Evento antigo de correção não equivale a confirmação. Uma revisão mais recente ou alteração posterior da declaração invalida a resolução anterior. Mudança de fonte invalida antes de aplicar; emite evento enxuto `CASE_PROCEDURE_REVIEW_INVALIDATED` com ID e motivo técnico, sem fonte integral, e segue a detecção automática normal/revisão. Não escolher retrospectivamente uma confirmação mais antiga para substituir a mais recente inválida.

Eventos são append-only; não criar JSON mutável no Case como segunda autoridade. Cache/projeção durante request/job é permitido, mas não substitui revalidação. Payload no artefato final referencia o event_id; justificativa/ator são lidos do evento quando necessário.

### D4 — Pipeline: detecção automática permanece pura, conjunto efetivo muda

Continuar uma extração LLM1 4.0 sobre a fonte, mantendo história e JSON original. Detectar/reconciliar automaticamente com o código atual e preservar união bruta em CASE_PROCEDURES_DETECTED, mesmo se a confirmação vai resolver um conjunto inválido. Não passar flag humana para regex nem alterar regras automáticas globais.

Com confirmação válida, selecionar `confirmed_procedures` como conjunto **efetivo** em vez de reaplicar o gate de procedimento. Não emitir EDA_SCOPE_GATED_MANUAL_REVIEW/SCOPE_GATE_BYPASS pelo desacordo detector×NIR nessa execução. Registrar `CASE_PROCEDURE_REVIEW_APPLIED` (sistema) com confirmation_event_id, automatic_procedures e effective_procedures, antes de continuar. Sem confirmação, toda a matriz/precedência/ADR-0011 atual continua.

`CaseProcedure.detection_status` já é a projeção pós-reconciliação usada nas filas: passa a refletir o conjunto efetivo após confirmação, não a opinião bruta do LLM. Isso NÃO reescreve os eventos de detecção nem o structured_data. Interfaces para esses casos devem dizer **“Procedimento confirmado pelo NIR” / “Conjunto em análise”**, não fingir detecção automática. Não criar uma quarta dimensão de filtro/banco neste change. Declaração (NIR), projeção operacional e autorização médica mantêm a matriz atual.

Persistir em suggested_action apenas metadado aditivo de proveniência `nir_procedure_review: {confirmation_event_id, effective_procedures}`; leitores legados sem esse metadado funcionam igual. Policy, prior lookup, sinais, relatório, recomendação e fila médica usam o conjunto efetivo. Evento CASE_PROCEDURES_DETECTED mantém nomes/campos atuais para compatibilidade; nunca preencher seu union bruto com a escolha humana por conveniência.

### D5 — Seleção confirmada ausente no LLM1 não bloqueia nem inventa clínica

`project_v4_to_llm1_shape` já permite projetar common_preop quando não existe item específico; indicação/local/detalhes ausentes devem ser unknown/ausentes, sem emprestar subtipo ou exceção de outro componente. Tornar isso explícito nos testes e apresentação.

Visão efêmera LLM2 continua filtrando somente itens originais pertencentes ao conjunto efetivo, sem fabricar item com evidence_spans. Lista fechada de análise fornecida pelo código é o conjunto confirmado; acrescentar ao contexto de chamada indicação estruturada de fonte **human_confirmation**, lista confirmada e ID do evento, fora do JSON LLM1 persistido. Explicar que item ausente significa dado específico não extraído, não autorização para adicionar procedimentos ou inventar dados. Justificativa livre do NIR não deve ser interpolada como instrução de sistema ao LLM.

Recomendação deve cobrir exatamente a lista confirmada, com validação/retries já existentes. Ausência de imagem/laboratório/documentação permanece pendência de policy, não nova revisão de identificação. Pydantic/JSON/pt-BR/echo e guardrails de rc.10 continuam. Não alterar schema_version externo, introduzir evidence_spans fictícios ou exigir que o LLM concorde para honrar o evento humano.

### D6 — UX e Linha do Tempo como entrega obrigatória

Card: declarado inicialmente, identificado automaticamente (rotulado corretamente), motivo da revisão, seletor canônico habilitando seleção atual, justificativa, checkbox explícita e CTA **Confirmar procedimento e continuar análise**. A seleção inicial pode vir marcada, mas o consentimento nunca; erro preserva seleção/justificativa e exige confirmação explícita novamente. Erros de permissão/fonte não podem vazar detalhes clínicos.

Linha do Tempo para confirmação: **“Procedimento confirmado pelo NIR: <label canônico>”**, data/hora, nome completo do actor (fallback username), manutenção/troca, justificativa escapada. Ex.: “Ana confirmou Retossigmoidoscopia + Argônio”; não basta “reprocessamento solicitado” ou só código de evento. Aplicação/invalidação são eventos distintos rotulados como sistema, referenciando a confirmação sem aparentar outra decisão humana.

Formatador puro compartilhado de rótulos/detalhes de eventos novos (em apps/cases) e partial curto reutilizável nas timelines existentes; não consolidar layout inteiro nem mover todos os EVENT_LABELS. Integrar NIR ativo/encerrado, contexto CHD e superfícies médicas/gestor que já renderizam histórico. Levantamento do baseline: NIR/CHD possuem markup da timeline; doctor/dashboard enriquecem eventos — testar onde efetivamente aparecem, sem criar novas telas só para este change.

Na avaliação médica, aviso não bloqueante fora de condicionais de precedência automática: escolha confirmada, autor, justificativa, divergência registrada e orientação de que decisão clínica continua médica. Mesmo seleção mantida deve gerar aviso. Não enviar notificação operacional nova nem gerar mensagem na thread: Linha do Tempo é CaseEvent, não CaseCommunicationMessage.

### D7 — U+0000: rejeição sem alteração silenciosa e caminho de erro limpo

Helper puro percorre chaves/valores de dict, listas e strings dos artefatos, summary e projeções a persistir. Decodificar JSON antes da validação de U+0000: escape JSON vira caractere real; texto literal de seis caracteres `\\u0000` não deve ser alterado indevidamente. Validar LLM1 antes de set_detected_procedures; validar LLM2 antes de salvar recomendação/transicionar ao médico. Sem remover bytes de conteúdo clínico nem criar retry LLM novo.

Erro tipado contém código `llm_output_not_persistable`, stage e caminho técnico limitado, sem raw/excerpt/chave livre com conteúdo clínico. Persistibilidade guard central no orchestrator é fronteira obrigatória, inclusive com clientes injetados; não duplicar normalização nos schemas.

Handler de falha recarrega Case limpo do banco; grava PIPELINE_FAILED com payload seguro (mensagem controlada/limitada, error_code, stage) e usa FSM da etapa **persistida**, sem refresh_from_db do campo protegido nem salvar artefatos rejeitados. Transação curta para evento + transição, preservando eventos anteriores. Se fluxo já avançou por outro ator, não regredir WAIT_DOCTOR/CLEANED: registrar conflito de etapa/propagar conforme evidência; não forçar status.

Falhas gerais de persistência também usam esse caminho, mesmo quando o guard não antecipar o problema. Se registro/falha FSM não puder concluir, exceção sai de run_pipeline/execute_pipeline e django-q2 marca failure e aplica configuração de retries existente. Log de erro persistível seguro não deve repetir SQL/JSON clínico recusado; evitar logger.exception sobre exception DB contendo CONTEXT clínico. Não aumentar timeout/retry nem engolir erro secundário.

Tarefa que concluiu tratamento de falha com Case FAILED auditado pode continuar retornando normalmente como contrato atual; **proibido sucesso enquanto não foi possível persistir o desfecho de erro**. Não confundir success do job com aceitação clínica. Não há reprocessamento automático de FAILED neste escopo.

### D8 — Compatibilidade e interações

- Correções/eventos/payloads antigos ficam legíveis; não conceder autoridade retroativa.
- POST antigo sem novos campos é recusado com erro seguro e sem mutação, não convertido em confirmação automática. Mesmo endpoint interno; sem rota externa/API.
- Transição existente de reprocessamento pode ganhar alias/nome de domínio, mas mesmos source/target e 17 estados; nunca atribuir status diretamente.
- Specs canônicas têm herança 3.0 em alguns parágrafos: delta usa writer atual 4.0 onde o comportamento desta change depende dele; não limpar todas as inconsistências históricas.
- `llm2-v4-echo-nonfatal-overwrite` já está no código rc.10: preservar overwrite auditável sem retry extra. `followup-body-clue-detection-hardening` item 1.0 já está no código; não ressuscitar lista crua de pistas removida só porque spec canônica ainda contém requisito antigo de card. Delta atualiza esse requisito.

### D9 — Slices e blast radius justificado ANTES de código

**S1** fecha o incidente técnico end-to-end (artefato inválido → erro seguro → FAILED auditado ou job failure real). É independente da autoridade humana e vem primeiro.

**S2** entrega confirmação NIR end-to-end (POST seguro → evento/linha do tempo → pipeline → fila/aviso médico), incluindo mesma e outra seleção. Não separar schema/backend/template em slices horizontais sem saída operacional. É a menor entrega correta desta decisão, porém necessariamente >5 arquivos: envolve serviço NIR, domínio/eventos, orchestrator, card SSR, contexto médico e múltiplos leitores da timeline, além de testes. A expansão é autorizada por este design e delimitada no contrato; não incluir refactors de detector, filas ou CSS sem necessidade.

Se a implementação revelar que S2 não cabe numa execução limitada sem mudança de decisão/contrato, worker retorna BLOCKED_NEEDS_DECISION com inventário concreto; não entrega apenas botão ou apenas flag de bypass como slice concluído.

## Risks / Trade-offs

- Escolha humana pode discordar inclusive de negação/histórico → consentimento, justificativa, auditoria e avaliação médica; igualdade inicial sozinha continua sem autoridade.
- Projeção “detected” passa a incluir escolha humana → labels/proveniência obrigatórios; evidência bruta preservada no evento.
- Fonte/POST antigo podem reutilizar consentimento → ID da revisão e fingerprint revalidados; nenhuma autoridade derivada de input task.
- Dois especializados realmente pedidos → NIR só seleciona um conjunto permitido, assumindo explicitamente essa resolução; combinação proibida continua rejeitada. Não criar novos pacotes.
- Dados específicos ausentes → unknown/pendências, sem exceção clínica emprestada.
- Enqueue pós-commit falha → recovery existente e mensagem verdadeira, consentimento/evento permanecem duráveis.
- Timeline em superfícies distintas → formatador compartilhado/partial apenas de detalhes e testes HTML escopados ao evento.

## Migration Plan

1. Sem migration/backfill/seed obrigatório. S1 pode ser publicado antes de S2; S2 exige web/worker no mesmo código.
2. Antes de rollout S2, drenar jobs e trocar web/worker/pdf_worker coordenadamente, sem writers antigos consumindo novas confirmações. Rejeitar formulários de páginas antigas em vez de inferir consentimento.
3. Smoke sintético: confirmação mantida/alterada → Linha do Tempo → WAIT_DOCTOR e aviso; artefato U+0000 → FAILED com evento seguro. Sem usar dados/credenciais dos PDFs reais como fixture.
4. Após primeiro CASE_PROCEDURE_REVIEW_CONFIRMED, rollback para binário que ignora essa autoridade não é permitido com análises pendentes. Preferir fix-forward; para rollback operacional, drenar/parar e verificar todos os casos confirmados/em voo sob responsabilidade do owner, mantendo eventos. Não apagar eventos para facilitar downgrade.
5. Recuperação dos três UUIDs de produção é atividade posterior com autorização: este plano não reabre casos encerrados nem inclui comando automático de mutação de produção.

## Open Questions

Nenhuma decisão de produto bloqueante restante: confirmação explícita do NIR prevalece na identificação; matriz/policy/médico permanecem. Nomes finais dos helpers/partials e organização de testes são escolhas locais de implementação sem alterar contratos. Se nova decisão clínica/persistência/FSM surgir, escalar, não preencher esta seção depois de codar.
