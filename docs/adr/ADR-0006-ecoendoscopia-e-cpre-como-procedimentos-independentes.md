# ADR-0006: Ecoendoscopia e CPRE como procedimentos independentes

## Status

Accepted

**Aceita em:** 2026-09-12

**Amplia e supera parcialmente:** [ADR-0004 — Procedimentos múltiplos e contrato LLM neutro](ADR-0004-procedimentos-multiplos-e-contrato-llm-neutro.md), nas decisões que limitavam `ProcedureType` e o contrato gravável a EDA/Colonoscopia e mantinham CPRE fora de escopo.

**Change associado:** [`support-independent-echoendoscopy-cpre-workflows`](../../openspec/changes/support-independent-echoendoscopy-cpre-workflows/proposal.md).

## Contexto

O ATS representa EDA e Colonoscopia como componentes independentes de um `Case`, preservando três fatos por `CaseProcedure`: declaração pelo NIR, detecção pela análise e autorização médica. Ecoendoscopia, porém, ainda aparece como subtipo/sinalização de EDA, enquanto CPRE é tratada como procedimento não suportado.

Essa representação não corresponde à operação hospitalar: Ecoendoscopia e CPRE são exames especializados, realizados separadamente da EDA e agendados como procedimentos próprios. O NIR precisa declará-los no upload, o pipeline precisa detectá-los e aplicar seus requisitos pré-operatórios, o médico precisa poder substituir qualquer exame solicitado por outro procedimento permitido e CHD/NIR precisam receber o procedimento efetivamente autorizado com destaque e auditoria.

As regras clínicas aprovadas exigem os critérios pré-operatórios da EDA, sem exceção de corpo estranho, acrescidos de imagem abdominal com conclusão ou achado de laudo. A sugestão automática deve negar quando qualquer requisito estiver ausente, mas nunca bloquear a decisão médica. Anexos clínicos não são processados no primeiro rollout; somente o conteúdo do relatório principal participa da automação.

A mudança é transversal e incompatível com uma simples extensão silenciosa do contrato LLM 2.0, fechado em EDA/Colonoscopia. Ela afeta intake, schemas e prompts, policy determinística, decisão médica, filas, comunicação, analytics, follow-up e operação de rollout/rollback.

## Decisão

### 1. Ecoendoscopia e CPRE serão `ProcedureType` independentes

O catálogo canônico passa a conter:

```text
eda
colonoscopy
echoendoscopy
cpre
```

Ecoendoscopia deixa de ser subtipo de EDA nos novos artefatos. Schemas 1.1/2.0 e o sinal histórico `echoendoscopy` permanecem apenas para leitura e apresentação de casos anteriores; não haverá backfill nem reclassificação automática de casos antigos.

### 2. A matriz de combinações será fechada e centralizada

Somente os conjuntos abaixo são válidos para declaração, detecção reconciliada e autorização final:

```text
{eda}
{colonoscopy}
{eda, colonoscopy}
{echoendoscopy}
{cpre}
```

Qualquer combinação com Ecoendoscopia ou CPRE, qualquer conjunto com três ou mais procedimentos e qualquer par diferente de EDA + Colonoscopia serão rejeitados ou encaminhados ao NIR conforme a etapa. A identificação de agendamento casado exige igualdade exata com `{eda, colonoscopy}`; quantidade de componentes não define combinação válida.

Troca parcial de um caso combinado que produza conjunto incompatível será bloqueada no MVP. O sistema não dividirá automaticamente um caso em dois casos ou dois agendamentos. Redução por negativa médica e substituição integral por um único procedimento permitido continuam possíveis.

### 3. Declaração, detecção e autorização continuam distintas

`CaseProcedure.declared_by_nir`, `detection_status` e `doctor_disposition` preservam, respectivamente, intenção do NIR, resultado da análise e decisão médica. Nenhuma dimensão sobrescreve outra. `CaseEvent` continua como fonte append-only do histórico.

Troca médica será uma operação atômica: o procedimento removido é negado, o destino é incluído/aprovado e as justificativas obrigatórias são persistidas. A troca já representa aprovação clínica deliberada; por isso não reexecuta LLM, não recalcula policy, não reapresenta sugestão e não devolve o caso ao pipeline.

### 4. Novos processamentos usarão contrato LLM 3.0

O contrato 2.0 não será alterado silenciosamente. Após o cutover, novos processamentos usarão schemas strict 3.0 procedure-neutral, mantendo leitores para 1.1 e 2.0 sem reescrita de JSON histórico.

O LLM1 3.0 aceita os quatro procedimentos, preserva evidências por procedimento e extrai imagem abdominal em coleção tipada, separando modalidade, localização anatômica, presença de conclusão/achado, trecho-fonte e data quando disponível. O LLM2 3.0 devolve exatamente uma recomendação por procedimento reconciliado, sem omissão, duplicata ou adição.

As frases abaixo têm precedência semântica e resultam em um único procedimento especializado:

```text
“EDA com ecoendoscopia” e “EDA e ecoendoscopia” → Ecoendoscopia
“EDA com CPRE” e “EDA e CPRE”                   → CPRE
```

A precedência deve constar no prompt e ser garantida pela reconciliação determinística. Não há upgrade automático entre um procedimento convencional e um especializado; divergências únicas retornam ao NIR. O upgrade automático existente permanece exclusivo de EDA/Colonoscopia únicas para EDA + Colonoscopia quando há evidência forte de ambas.

### 5. A policy será determinística, por perfil, e mostrará pendências agregadas

Todos os quatro procedimentos reutilizam os critérios comuns pré-operatórios da EDA. A exceção de corpo estranho continua exclusiva da EDA.

Ecoendoscopia exige adicionalmente pelo menos um laudo, no relatório principal processado, com conclusão ou achado de:

- TC de abdome ou abdome superior; ou
- RM/RNM de abdome ou abdome superior.

CPRE exige adicionalmente pelo menos um laudo, no relatório principal processado, com conclusão ou achado de:

- USG/US de abdome, abdome superior ou hepatobiliar; ou
- TC de abdome ou abdome superior; ou
- RM/RNM de abdome ou abdome superior; ou
- CPRM/colangiorressonância/colangiopancreatografia por ressonância.

Mera solicitação, agendamento, menção ao nome do exame ou imagem sem localização anatômica compatível não satisfaz o requisito. A data será registrada quando disponível, sem janela de validade. Anexos não entram na sugestão automática no primeiro rollout, e essa limitação será informada ao médico.

A policy acumulará todas as pendências documentais e clínicas aplicáveis em ordem determinística. Campos legados de motivo primário permanecerão para compatibilidade, mas LLM2 e relatório médico receberão a coleção completa. Qualquer falha determinística força sugestão de negativa; o médico continua livre para aprovar.

### 6. Comunicação downstream será explícita e sem notificação global

Quando o conjunto autorizado diferir do detectado, o sistema registrará `DOCTOR_PROCEDURE_SET_CHANGED` e projetará uma mensagem sistêmica idempotente na thread do caso. O evento e a mensagem explicitarão a transformação e a existência/motivo da decisão conforme o contrato de auditoria.

CHD e NIR verão:

- badge principal do conjunto autorizado;
- comparação textual detectado → autorizado nos cards e detalhes;
- resposta final comparando declarado, detectado e autorizado;
- evento auditável e mensagem sistêmica na thread.

A mensagem sistêmica não cria `UserNotification`, não incrementa badge global e não menciona todos os usuários de um papel.

### 7. Fluxos existentes serão reutilizados; salas ficam fora do domínio

Ecoendoscopia e CPRE podem usar os fluxos de admissão já suportados, incluindo agendamento, vinda imediata, fluxos relacionados à UTI e fluxos pediátricos. Nenhum estado FSM, role, lock ou modelo de agenda paralelo será criado.

O sistema não modelará sala específica nem validará compatibilidade entre procedimento e `appointment_location`; essa coordenação permanece fora do ATS com o CHD.

### 8. Flags independentes controlarão apenas novos intakes

Serão adotadas:

```text
ECHOENDOSCOPY_INTAKE_ENABLED
CPRE_INTAKE_ENABLED
```

As flags removem e bloqueiam as respectivas opções em upload, correção e reenvio, sem interromper casos existentes nem impedir uma decisão médica de substituição. O rollout ativa Ecoendoscopia antes de CPRE. Com uma flag desligada, detecção divergente continua fail-closed em revisão NIR; o sistema não converte silenciosamente o procedimento especializado em EDA.

### 9. Rollback será por flags e correção para frente

Após existir qualquer row de Ecoendoscopia/CPRE ou artefato 3.0, uma imagem antiga que conhece apenas EDA/Colonoscopia é insegura. Não haverá reverse migration destrutiva nem apagamento de rows para viabilizar downgrade.

Rollback operacional preferencial: desligar ambas as flags, preservar a imagem/schema novos, drenar jobs e corrigir para frente. Retorno à imagem antiga só é admissível antes do primeiro intake especializado e após prechecks binários comprovarem ausência de rows, eventos e artefatos 3.0 incompatíveis.

## Alternativas Consideradas

### 1. Manter Ecoendoscopia como subtipo de EDA e CPRE fora do sistema

- **Vantagens:** nenhuma mudança transversal imediata.
- **Desvantagens:** identidade operacional incorreta, seleção NIR impossível, agendamento e analytics ambíguos, CPRE sem fluxo.
- **Por que não escolhida:** não representa a execução separada nem atende o processo confirmado.

### 2. Tratar Ecoendoscopia/CPRE somente como badges ou sinais prioritários

- **Vantagens:** reaproveita a infraestrutura de sinalizações existente.
- **Desvantagens:** não cria declaração, detecção, autorização, filtro, policy ou agendamento próprios; mistura identidade de procedimento com alerta.
- **Por que não escolhida:** badges são apresentação, não fonte de verdade operacional.

### 3. Alterar silenciosamente o contrato LLM 2.0

- **Vantagens:** evita novo par de schemas/adapters.
- **Desvantagens:** o mesmo `schema_version` passaria a aceitar semântica incompatível, prejudicando auditoria, strict schema e rollback.
- **Por que não escolhida:** viola versionamento explícito e a ADR-0004.

### 4. Criar um caso/agenda separado automaticamente para cada componente incompatível

- **Vantagens:** permitiria trocar apenas parte de um combinado por procedimento especializado.
- **Desvantagens:** exige split de documentos, estado, comunicação, decisões, locks e agenda; aumenta risco de duplicidade e perda de vínculo.
- **Por que não escolhida:** complexidade e risco não são necessários no MVP; combinações incompatíveis serão bloqueadas.

### 5. Deixar os requisitos de imagem somente no prompt/LLM2

- **Vantagens:** implementação inicial menor.
- **Desvantagens:** regra clínica não determinística, difícil de auditar e sujeita a sugestão contraditória.
- **Por que não escolhida:** requisitos aprovados devem ser hard rules testáveis em código.

### 6. Reanalisar automaticamente após troca médica

- **Vantagens:** produziria sugestão específica para o destino.
- **Desvantagens:** contradiz o significado da troca, adiciona latência/custo e pode confundir ou bloquear uma decisão já tomada.
- **Por que não escolhida:** a troca é uma aprovação médica autoritativa; somente validações estruturais permanecem.

## Consequências

### Positivas

- Ecoendoscopia e CPRE passam a ter identidade, policy, agendamento, filtros e métricas próprios.
- Declaração, detecção e autorização permanecem auditáveis mesmo após troca médica.
- Requisitos clínicos de imagem são determinísticos, tipados e comprováveis.
- Todas as pendências são apresentadas de uma vez, reduzindo ciclos documentais.
- CHD e NIR recebem o procedimento autorizado sem depender de inferência por badge histórico.
- Rollout independente reduz blast radius clínico.

### Negativas/Trade-offs

- Mudança transversal em domínio, contrato LLM, prompts, policy e múltiplas superfícies SSR.
- Leitores históricos 1.1/2.0 e o sinal legado precisam ser preservados.
- Anexos não satisfazem automaticamente o requisito no primeiro rollout.
- Depois do primeiro caso especializado, downgrade para imagem antiga deixa de ser seguro.
- A matriz fechada bloqueia cenários que futuramente poderão exigir split explícito.

### Riscos e Mitigações

- **Combinação inválida ser tratada como agendamento casado:** matriz centralizada e igualdade exata com `{eda, colonoscopy}` em testes de domínio e integração.
- **LLM confundir EDA com procedimento especializado:** precedência no prompt e reconciliação determinística com evidência por ocorrência.
- **Imagem mencionada sem laudo satisfazer a policy:** modalidade/localização/achado tipados e hard rule que aceita somente conclusão ou achado.
- **Pendências agregadas quebrarem consumidores legados:** adicionar coleção preservando motivo primário e adapters históricos.
- **Troca médica disparar nova análise:** teste negativo de fila/job e serviço transacional sem chamada de pipeline.
- **Mensagem sistêmica gerar spam:** evento dedicado somente quando o conjunto muda e projeção sem `UserNotification`.
- **Ecoendoscopia aparecer simultaneamente como procedimento e sinal:** novos artefatos 3.0 não geram o sinal; payloads legados continuam legíveis.
- **Código assumir exatamente dois tipos:** catálogo/ordem/matriz centralizados e inventário obrigatório de loops, pares e checks `len == 2`.
- **Rollback incompatível:** flags desligadas por padrão, ativação sequencial, prechecks binários e fix-forward como caminho suportado.

## Histórico de Mudanças

- 2026-09-12: ADR criada e aceita para o change `support-independent-echoendoscopy-cpre-workflows`.
