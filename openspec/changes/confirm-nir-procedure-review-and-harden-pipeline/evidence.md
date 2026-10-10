# Evidência de origem e contrato aprovado

## Investigação somente leitura — 09/10/2026

Produção eon, imagem rc.10, painel SSH tmux 0:8.1. Fonte: Case/CaseEvent/CaseProcedure, tarefas/fila/schedules e logs; consultas dentro de transação READ ONLY. Não houve mutation, LLM adicional ou restart.

- **5074806** (`cbacdb4d-5ab4-4d52-a706-32d25d76a749`): correção EDA → EDA+GTT às 07:16; resposta LLM1 não persistível em JSONB (`UntranslatableCharacter`, U+0000). Save do handler falhou com a mesma instância; último evento CASE_REPROCESSING_REQUESTED. Case LLM_STRUCT, tarefa success=True, fila/schedule ausentes. Texto/PDF preservados; NUL ausente na fonte. Guard + caminho limpo devem resolver o defeito.
- **5073320** (`2144f91f-18a4-487b-bce6-6557ae69f9f4`): documento indica tratamento com argônio em reto; LLM extrai pacote, detector exige base nominal na mesma expressão e marca conflito. EDA do cabeçalho + pacote de argônio não são cobertos pela matriz. Manual review → CLEANED, sem decisão médica. Trocar só declaração em reprodução pura não resolveu. Mesma razão nos casos de 06/10 e 08/10.
- **5075227** (`433a5c48-4158-478e-9ef7-1df90f0a9e4f`): EDA administrativa + Eco atual + CPRE extraída de menção à disponibilidade; união de dois especializados não é válida. Correção NIR para CPRE às 07:36 repetiu o gate; CLEANED às 07:38. Mesma combinação bloqueou casos de 07/10 e 08/10.

Limite: os dois últimos foram encerrados após revisão, não são jobs pendentes. CLEANED/FINAL_REPLY_POSTED não equivalem a aprovação clínica.

Relatórios completos temporários (não são pré-condição para worker fresh): `/tmp/chd-investigacao-5074806-20261009.md` e `/tmp/chd-investigacao-tres-casos-20261009.md`. Este arquivo contém toda a motivação técnica necessária para reconstruir a change sem esses arquivos temporários.

## Decisão do operador

O NIR já faz a confirmação do pedido real ao revisar. Não é aceitável depender de reescrita do relatório nem obrigá-lo a escolher um procedimento diferente para insistir. O operador concordou com **confirmação humana auditável** que define o conjunto de análise, mantendo decisão clínica no médico, e solicitou expressamente **Linha do Tempo com quem confirmou qual procedimento**.

Autorização desta etapa: abrir change e decompor com openspec-vertical-change-writer. Não implementa, recupera casos de produção ou delega workers/reviewers automaticamente.

## Seeds sintéticas para TDD

Sem nomes, datas identificáveis, credenciais, URLs privadas ou PDF real:

1. LLM1 válido com U+0000 aninhado em texto narrativo; LLM2 válido com U+0000 em rationale. Fonte sintética limpa.
2. Motivo EDA; complemento “necessita de coagulação endoscópica com plasma de argônio no reto”; histórico “foi submetido à retossigmoidoscopia”; LLM1 EDA + rectosigmoidoscopy_argon. Primeiro processamento continua automático/revisão; confirmação explícita para argônio continua ao médico, independentemente da repetição do detector.
3. Motivo EDA; justificativa “solicito regulação para ecoendoscopia”; corpo “serviço com disponibilidade de ecoendoscopia e CPRE”; LLM1 EDA + Eco + CPRE. Confirmar Eco ou CPRE como singleton permitido define análise; mesma seleção CPRE também é válida na revisão.
4. Confirmação de uma identidade ausente do array LLM1, com common_preop presente. Não fabricar evidence spans/exceção específica; conjunto fechado LLM2 segue o humano.
5. Payload antigo/sem consentimento, justificativa vazia, tipo desconhecido/combinação proibida, reserva expirada, outro papel, revisão/fonte desatualizada, double POST e corrida com recebimento.

São fixtures de software para provar autoridade/guardrails, não simulação de aprovação de pacientes reais.
