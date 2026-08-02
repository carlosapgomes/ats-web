# Proposal: Sinalizações prioritárias de EDA em todo o fluxo operacional

**Change ID**: `eda-priority-signals-across-workflow`  
**Fase**: classificação clínica/procedimental e continuidade visual Médico → CHD → NIR  
**Risco**: PROFISSIONAL — altera contrato LLM1, scope gate clínico, dado persistido, backfill e informação usada por profissionais em múltiplas etapas; exige `design.md`, rollback, TDD e revisão por terceiro LLM.

## Problema

A classificação atual de EDA está distribuída entre prompt LLM1, schema Pydantic, detector de escopo, policy e presenter médico. Isso gera quatro problemas operacionais:

1. Solicitações de **ecoendoscopia** podem ser classificadas como `unknown`/`non_eda` e recusadas imediatamente para revisão manual, embora devam seguir o fluxo normal de EDA.
2. Procedimentos que exigem direcionamento manual entre médicos triadores e executores — ecoendoscopia, dilatação esofágica e gastrostomia — não recebem badges consistentes durante todo o ciclo do caso.
3. Pediatria, corpo estranho e ingestão cáustica/corrosiva possuem mecanismos de detecção e ênfase diferentes; alguns dependem do LLM e outros existem apenas no presenter médico.
4. As sinalizações não acompanham de forma canônica o caso quando ele passa do médico para o CHD/agendador e depois retorna ao NIR.

A ecoendoscopia é executada apenas em alguns turnos da semana e somente alguns médicos triadores avaliam esses casos. Dilatações esofágicas têm necessidade operacional semelhante. Os badges serão informativos: a equipe continuará coordenando manualmente triador, executor e agenda.

## Objetivo

Criar uma classificação persistida e determinística de sinalizações prioritárias, permitir que ecoendoscopia siga o fluxo padrão de EDA e exibir os mesmos badges ao longo do fluxo operacional.

Sinalizações canônicas:

- `foreign_body` — suspeita/retirada de corpo estranho;
- `caustic_ingestion` — ingestão cáustica/corrosiva;
- `pediatric` — paciente com idade menor que 16 anos;
- `echoendoscopy` — EDA com ecoendoscopia, inclusive com punção/biópsia;
- `esophageal_dilation` — EDA para dilatação esofágica;
- `gastrostomy` — EDA para gastrostomia.

Fluxo esperado:

```text
LLM1 + texto extraído
→ resolução determinística das sinalizações
→ persistência no Case
→ scope/policy
→ badges na fila e avaliação médica
→ mesmos badges no CHD
→ mesmos badges no NIR
```

## Decisões de produto confirmadas

1. `esophageal_dilation` continua sendo o subtipo existente para dilatação esofágica; não criar enum genérico `dilation`.
2. Solicitação explícita de ecoendoscopia entra no fluxo de EDA mesmo sem a palavra literal `EDA`.
3. Reconhecer ecoendoscopia, eco-endoscopia, ultrassonografia endoscópica, ultrassom endoscópico e `EUS` quando houver contexto procedimental suficiente.
4. Ecoendoscopia com punção, PAAF, biópsia, FNA ou FNB continua sendo ecoendoscopia; não criar subtipo adicional neste change.
5. Quando houver solicitação de EDA ou ecoendoscopia, o caso segue o fluxo de EDA mesmo que o texto também mencione exame atualmente fora do escopo. Colonoscopia será tratada em change posterior.
6. Ecoendoscopia, dilatação esofágica e gastrostomia seguem a policy padrão de EDA e os exames mínimos usuais.
7. Corpo estranho preserva a exceção determinística já existente para exames mínimos.
8. Corpo estranho e ingestão cáustica recebem o mesmo nível visual de alerta.
9. Badges são informativos; não atribuem médico, não restringem acesso e não validam turnos de agenda.
10. Sinalizações podem coexistir sem criar enums combinatórios.
11. Persistir para casos novos e fazer backfill somente dos casos ainda abertos. Casos históricos já `CLEANED` não serão classificados retroativamente; casos novos mantêm seus sinais quando posteriormente forem encerrados.

## Escopo incluído

- Adicionar `echoendoscopy` aos subtipos suportados no contrato LLM1.
- Atualizar prompt canônico e prompt renderizado final para ecoendoscopia, coexistência e menção no resumo.
- Detectar ecoendoscopia de forma determinística e encaminhá-la ao fluxo EDA.
- Garantir precedência de uma solicitação EDA/ecoendoscopia suportada sobre menções simultâneas a exame fora de escopo.
- Aplicar policy padrão a ecoendoscopia, dilatação e gastrostomia.
- Persistir coleção versionada de sinalizações prioritárias no `Case`.
- Backfill idempotente somente para `status != CLEANED`.
- Consolidar detecção de pediatria, corpo estranho, ingestão cáustica, ecoendoscopia, dilatação e gastrostomia.
- Suportar múltiplos sinais simultâneos com ordem de apresentação determinística.
- Exibir badges compartilhados em:
  - fila médica;
  - avaliação/relatório médico;
  - fila, confirmação e detalhes do CHD;
  - lista, detalhe operacional, resultado e detalhe encerrado do NIR para casos que possuem sinais persistidos.
- Evidenciar sinais no corpo do relatório médico sem depender exclusivamente do `summary.one_liner`.
- Registrar os códigos resolvidos na evidência de auditoria do pipeline para casos novos.
- Testes de contrato, detector, scope, policy, migration/backfill e renderização por papel.

## Fora de escopo

- Implementar colonoscopia ou outros novos exames.
- Criar fila exclusiva, atribuição automática ou permissão especial para ecoendoscopia/dilatação.
- Restringir quais médicos podem abrir ou decidir um caso.
- Validar dias/turnos disponíveis ou bloquear horários de agenda.
- Alterar FSM, decisão médica, formulários de aceite ou confirmação de agendamento.
- Criar subtipo separado para punção/PAAF/FNA/FNB.
- Reprocessar LLM de casos existentes.
- Backfill de casos já `CLEANED`.
- Alterar a exceção de corpo estranho ou criar negativa automática por ingestão cáustica.
- Criar regras clínicas novas para urgência.
- Implementar API/SPA/DRF, WebSocket ou framework frontend.

## Critérios de sucesso

- Ecoendoscopia explícita deixa de cair em revisão manual por tipo desconhecido e chega à fila médica.
- `echoendoscopy` é validado pelo schema LLM1 e tratado como EDA suportada.
- Ecoendoscopia segue exames mínimos e policy padrão; não herda o bypass de corpo estranho.
- Solicitação EDA/ecoendoscopia suportada prevalece sobre menção simultânea a exame fora de escopo.
- Casos novos persistem sinalizações canônicas; migration faz backfill apenas dos casos abertos.
- Casos `CLEANED` preexistentes permanecem sem backfill.
- Sinais coexistem e são exibidos em ordem estável, sem combinações de enum.
- Corpo estranho e ingestão cáustica usam o mesmo nível visual de alerta.
- Ecoendoscopia, dilatação e gastrostomia usam destaque operacional consistente.
- Pediatria permanece visível com idade quando disponível.
- Médico, CHD e NIR veem os mesmos códigos/labels persistidos.
- O relatório médico mostra sinais no topo e no corpo de forma determinística.
- Badges não alteram permissões, roteamento humano, agenda, FSM ou decisão final.
- Quality gate completo passa em cada slice.
- Cada slice produz relatório temporário verificável, commit e push antes de avançar.

## Dimensionamento

O change será entregue em **cinco slices verticais**:

1. Ecoendoscopia percorre contrato → scope → policy → relatório médico atual.
2. Sinalizações persistidas para novos/abertos aparecem na fila médica.
3. Topo e corpo do relatório médico usam a classificação canônica.
4. Os mesmos badges acompanham o caso no CHD.
5. Os mesmos badges acompanham o caso no NIR.

A separação evita um único slice com pipeline, migration e três apps de UI. Cada slice produz valor observável e não antecipa automação de direcionamento ou agenda.
