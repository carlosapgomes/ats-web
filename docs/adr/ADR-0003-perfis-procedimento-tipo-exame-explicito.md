# ADR-0003: Perfis de procedimento e tipo de exame explícito

## Status

Accepted — parcialmente superada pela [ADR-0004](ADR-0004-procedimentos-multiplos-e-contrato-llm-neutro.md) nas decisões 1, 2, 3, 5, 6, 8 e 9. As decisões 4, 7, 10 e 11 permanecem válidas.

## Contexto

O ATS foi implantado como sistema de triagem de EDA. O `Case` não registra tipo de exame e o pipeline trata colonoscopia como `non_eda`. O hospital agora precisa incluir colonoscopia, com os mesmos exames mínimos, thresholds, suporte e fluxo pediátrico de EDA, mas sem a exceção de corpo estranho.

Há previsão próxima de CPRE, cujo conjunto de requisitos será mais amplo. Copiar a policy EDA para cada exame geraria divergência clínica; generalizar tudo em um único fluxo com condicionais espalhadas tornaria auditoria e evolução inseguras.

O tipo também precisa ser uma dimensão operacional nas filas médica, CHD, NIR e dashboard. Confiar apenas na classificação LLM não é suficiente para roteamento clínico e auditoria: o NIR deve declarar a intenção e o sistema deve verificar a compatibilidade documental.

Este ADR está associado ao change `openspec/archive/introduce-colonoscopy-exam-workflow/` e ao branch `feature/colonoscopy-exam-workflow`.

## Decisão

1. Adotar `Case.exam_type` como fonte operacional explícita, inicialmente com `eda` e `colonoscopy`.
2. Exigir seleção do tipo pelo NIR, um tipo por lote e sem opção visual padrão.
3. Verificar deterministicamente/por contrato o tipo declarado contra a solicitação atual do PDF; mismatch, tipo desconhecido ou EDA+colonoscopia atuais vão para revisão manual.
4. Separar policy por perfis pequenos de procedimento sobre funções pré-operatórias comuns:
   - EDA usa a base comum e mantém exceção de corpo estranho;
   - colonoscopia usa a base comum sem essa exceção;
   - CPRE não será implementada agora, mas poderá adicionar perfil/requisitos em change próprio.
5. Preservar o contrato JSON histórico sem migration de `structured_data`; evoluções incrementais devem usar `Case.exam_type` como discriminador operacional e adapters/presenters não devem inferir o tipo pelo nome do bloco legado `eda`.
6. Manter prompts EDA e colonoscopia versionados separadamente.
7. Manter lifecycle/FSM/forms/locks compartilhados após a decisão médica; não duplicar filas por modelo ou app.
8. Tratar tipo como filtro secundário dentro das tabs de lifecycle, com `Todos` como padrão.
9. Permitir correção do tipo no mesmo caso somente antes da fila médica/em manual review, com eventos append-only e reprocessamento controlado do LLM.
10. Usar `COLONOSCOPY_INTAKE_ENABLED` como kill switch de novos uploads, sem interromper casos existentes.
11. Extrair medicamentos relevantes para todos os perfis e destacar anticoagulantes/antiagregantes apenas como alerta informativo, sem hard rule ou orientação de suspensão.

## Alternativas Consideradas

### 1. Tipo inferido somente pelo LLM

- **Vantagens**: nenhuma etapa adicional no upload.
- **Desvantagens**: roteamento depende de inferência; histórico pode confundir; intenção do NIR não fica auditável.
- **Por que não escolhida**: insuficiente para fluxo clínico determinístico.

### 2. Tipo declarado pelo NIR sem verificação

- **Vantagens**: simples e determinístico para filas.
- **Desvantagens**: erro humano pode aplicar prompt/policy errados.
- **Por que não escolhida**: não oferece defesa contra seleção incorreta ou PDF misto.

### 3. Duplicar pipeline e policy completos para colonoscopia

- **Vantagens**: isolamento imediato.
- **Desvantagens**: duplicação de thresholds e gates; alto risco de drift; CPRE agravaria o problema.
- **Por que não escolhida**: viola DRY em regras clínicas compartilhadas.

### 4. Generalizar antecipadamente EDA, colonoscopia e CPRE em engine configurável

- **Vantagens**: aparente extensibilidade máxima.
- **Desvantagens**: requisitos CPRE ainda não formalizados; metaprogramação e schema novo ampliariam muito o risco.
- **Por que não escolhida**: YAGNI. Serão criados perfis mínimos somente para exames suportados.

### 5. Substituir tabs `Pendentes` por tabs de exame

- **Vantagens**: separação visual direta.
- **Desvantagens**: mistura tipo e estado; prejudica `Decididos/Processados/Histórico`; escala mal para CPRE.
- **Por que não escolhida**: tipo é dimensão de filtro, não lifecycle.

## Consequências

### Positivas

- Roteamento auditável e independente da inferência LLM.
- Reuso seguro das regras comuns com exceções explícitas.
- Inclusão futura de CPRE sem copiar integralmente a policy.
- Filas permanecem consistentes com o lifecycle existente.
- Rollback pode bloquear intake sem destruir dados.
- Alertas medicamentosos ganham estrutura e evidência sem automatizar conduta.

### Negativas/Trade-offs

- Mudança transversal em modelo, pipeline, prompts, presenters e filas.
- O envelope JSON legado `eda` permanece por compatibilidade neste change; uma versão procedure-neutral pode ser necessária com CPRE.
- Correção/reprocessamento exige cuidado com concorrência e invalidação de artefatos.
- Prompts separados aumentam itens administrados, embora reduzam regressão cruzada.

### Riscos e Mitigações

- **Policy errada por tipo**: dispatch explícito e testes de exceção negativa em colonoscopia.
- **Solicitação mista passar**: detector de solicitação atual e cenário obrigatório EDA+colonoscopia.
- **Race no reprocessamento**: lock transacional, estados estáveis e recusa quando worker/reserva incompatível.
- **Rollback com casos em voo**: flag apenas no intake e runbook de drenagem/encerramento.
- **Regressão histórica**: backfill simples para EDA, sem inferência nem reprocessamento.
- **Alerta medicamentoso interpretado como conduta**: copy neutra e proibição explícita de hard rule/suspensão.

## Histórico de Mudanças

- 2026-08-04: ADR criada e aceita para o change `introduce-colonoscopy-exam-workflow`.
- 2026-08-06: decisões 1, 2, 3, 5, 6, 8 e 9 parcialmente superadas pela ADR-0004; decisões 4, 7, 10 e 11 preservadas.
