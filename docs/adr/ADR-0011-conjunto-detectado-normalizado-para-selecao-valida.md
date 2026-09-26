# ADR-0011: Conjunto detectado normalizado para seleção válida na decisão e na exibição

## Status
Accepted

## Contexto

Em produção (`v0.10.0-rc.1`, caso real de 2026-09-26), o painel NIR de correção
exibiu `Tipo detectado: EDA + EDA + Dilatação` — combinação que não existe no
catálogo selecionável — e a correção do NIR para o pacote `EDA + Dilatação`
não desfez a revisão, criando um beco sem saída. Investigação (dois revisores
read-only; relatório em
`.pi/reports/detected-set-normalization-investigation-2026-09-26.md`)
confirmou a cadeia:

1. O gate de conflito (`conflicting_procedure_evidence`) devolve
   `detected = any_set ∪ conflicting_set` — ex. `{eda, eda_dilation}` (base +
   pacote que já contém a base) — **antes** da precedência de variação e da
   validação da matriz (`apps/pipeline/procedure_reconciliation.py:481-495`).
2. O label do card concatena labels por identidade: `"EDA" + " + " + "EDA +
   Dilatação"` (`apps/intake/views.py:191-209`).
3. O gate é **cego ao declarado**: a correção preserva o texto extraído
   imutável e re-executa o LLM1, que reproduz o mesmo item estruturado — a
   revisão re-firma indefinidamente. Sem saída clínica pela UI (as únicas
   transições encerram o caso sem agendamento).

Esse comportamento é contrato vigente: a spec `procedure-neutral-analysis`
exige "incluindo o tipo conflitante no conjunto detectado", o design D4 do
change `detect-report-body-procedure-clues` (arquivado 2026-09-25) pina o
union e ~10 testes fixam conjuntos fora da matriz. Porém a spec
`procedure-combination-policy` declara a matriz fechada "após reconciliação" —
o gate retorna antes dessa validação. A mudança aqui decide como fechar essa
fresta **sem abandonar o fail-closed**.

Princípio do operador do sistema: "o sistema deve encaixar o que detectou nas
combinações POSSÍVEIS, nunca inventar combinação nova; e deve escolher a
opção mais completa/específica que cubra a maior parte do que foi detectado".

## Decisão

1. **Normalização por cobertura máxima** (nova função pura em
   `apps/cases/procedures.py`): `best_covering_selection(procedure_types)`
   mapeia um conjunto detectado arbitrário para a **seleção válida mais
   completa que o cobre** — base absorvida pelo pacote presente
   (`{eda, eda_dilation} → eda_dilation`); prefere pacote a componentes;
   devolve a sentinela `invalid` quando nenhuma combinação da matriz cobre
   (ex.: `{eda_capsule, eda_dilation}`, `{rectosigmoidoscopy_dilation,
   colonoscopy}`). Total, determinística, sem I/O. A relação base⊂pacote ganha
   constante autoritativa em `apps/cases` (`PROCEDURE_PACKAGE_BASES`),
   importada pelo pipeline.
2. **Resolução declarado-aware COM discriminador de evidência atual**
   (`procedure_reconciliation.py`, em dois pontos — branch de conflito e
   branch de matriz/`unsupported_procedure_combination`): **prossegue** com o
   declarado somente quando (i) existe ao menos uma ocorrência textual atual
   (`any_set ≠ ∅`), (ii) o declarado é seleção canônica válida não-vazia e
   (iii) `selection_key(declared) == best_covering_selection(union)` do
   conjunto bruto do ponto. O discriminador (i) mantém fechado o fail-open
   que o gate existe para fechar: quando a única evidência é o item
   contraditado/negado/histórico e a declaração "coincide" com ele
   (`any=∅`, `union==declared` — ex.: texto "Nao solicito cápsula..."), o caso
   PERMANECE em revisão. Nas passadas com evidência atual e declaração igual
   à cobertura máxima, o prosseguimento honra declaração+LLM com o conflito
   gravado no evento de auditoria e revisão médica a jusante (não é
   silencioso). Dois desfechos pinados mudam deliberadamente: o cenário
   "Solicito EDA" + dilatação histórica + declarado `eda_dilation` (pass-2 do
   caso real 26/09) e o item estruturado sem ocorrência textual com declaração
   do pacote passam a prosseguir.
3. **Evidência bruta preservada na auditoria**: o `CaseEvent` append-only
   (`CASE_PROCEDURES_DETECTED`) carrega o union bruto **em todos os
   desfechos** (na passada de resolução isso exige campo explícito no result,
   pois o conjunto detectado do result carrega o declarado); apenas o payload
   de revisão/correção é normalizado — e **somente quando o conjunto não
   pertence à matriz** (par válido `{eda, colonoscopy}` continua `[
   "eda","colonoscopy"]`; chave interna nunca vaza para a UI). O espírito do
   design D3/D12 ("não descartar valores") permanece intacto na fonte de
   verdade de histórico.
4. **Exibição sem duplicação**: o label do card renderiza o conjunto do
   payload com absorção de base (pacotes distintos juntam-se com " e ").
5. **Fail-closed inalterado onde nenhuma combinação cobre ou não há
   evidência atual**: union sem cobertura válida ou coincidência sem
   evidência atual continuam indo a revisão NIR com seu reason atual.

Esta ADR emenda pontualmente a ADR-0010 (decisão 4: o colapso da base
continua exigindo ocorrência atual **na precedência de detecção automática**;
a normalização aqui atua **no gate de conflito**, com resolução humana) e o
design D4 do change `detect-report-body-procedure-clues` (union cru segue no
evento; payload passa a ser normalizado).

## Alternativas Consideradas

1. **Fechamento operacional do caso (status quo)**: confirmar recebimento ou
   encerramento administrativo.
   - **Vantagens**: zero código.
   - **Desvantagens**: encerra sem agendamento clinicamente indicado;
     recursivo para toda a classe de casos.
   - **Por que não escolhida**: perda clínica inaceitável como padrão.

2. **Apenas corrigir o label (render)**: absorver base no pacote na
   formatação.
   - **Vantagens**: blast radius mínimo.
   - **Desvantagens**: o beco sem saída persiste (o gate continua cego ao
     declarado).
   - **Por que não escolhida**: não resolve o problema central; adotada como
     **parte** da decisão (item 4).

3. **Revisão-única (humano autoritativo)**: qualquer correção após uma
     revisão de conflito resolve; gate consulta histórico de eventos.
   - **Vantagens**: semântica simples ("humano manda"); sem novo helper.
   - **Desvantagens**: gate vira stateful (depende de histórico de eventos);
     aceita correções que ignoram a evidência; mais frágil de testar.
   - **Por que não escolhida**: o princípio do operador pede a opção **mais
     completa que cobre** a evidência, não qualquer escolha. A regra
     escolhida atinge o mesmo efeito de resolução humana de forma stateless,
     com o discriminador de evidência atual fechando a classe de
     coincidência sem revisão prévia (primeira passada).

4. **Corrigir só na fonte (Complemento da Solicitação como current_request)**:
   promovê-lo a seção de solicitação resolveria a classe deste documento sem
   tocar o gate.
   - **Vantagens**: elimina a fricção antes da revisão; sem mudança de
     contrato do gate.
   - **Desvantagens**: não resolve conflitos sustentados por menções
     genuinamente históricas; muda sensibilidade de detecção de todos os
     documentos e exige validação com amostra real.
   - **Por que não escolhida como única**: complementar — change separado
     (`solicitation-complement-as-current-request`), não substituto.

## Consequências

### Positivas
- O loop de correção deixa de ser beco sem saída: corrigir para a opção mais
  completa sustentada pela evidência prossegue o caso.
- O NIR nunca mais vê "Tipo detectado" impossível no card.
- Fail-closed preservado onde nenhuma combinação válida cobre a detecção.
- Auditoria mantém a evidência bruta (union) para rastreabilidade completa.

### Negativas/Trade-offs
- O payload de revisão deixa de carregar o union cru quando ele tem cobertura
  válida (migra para o normalizado) — consumidores do payload re-verificados
  (levantamento: único leitor de produção é o label do card).
- Dois desfechos pinados por teste mudam deliberadamente (cenário "Solicito
  EDA" + dilatação histórica com pacote declarado; item estruturado sem
  ocorrência textual com pacote declarado) — re-baseline documentada, não
  regressão.
- O gate ganha comparação adicional (declarado vs best-covering) em dois
  pontos — semântica de resolução explícita documentada em spec.

### Riscos e Mitigações
- **Risco**: normalização mascarar evidência em decisões.
  **Mitigação**: evento de auditoria preserva o union bruto em TODOS os
  desfechos (campo explícito na passada de resolução); specs exigem
  normalização apenas para decisão/exibição e só fora da matriz.
- **Risco**: coincidência declaração==item-contraditado sem evidência atual
  (fail-open original, ex.: negação explícita).
  **Mitigação**: discriminador `any_set ≠ ∅` obrigatório; testes de cápsula
  negada/histórica e reto permanecem `nir_review` como guardas.
- **Risco**: NIR "adivinhar" a best-covering para destravar caso.
  **Mitigação**: o card exibe o conjunto normalizado (a opção possível mais
  completa) — a escolha fica evidente na UI. Nota: a tabela por-procedimento
  da página segue derivada de rows declaradas e pode divergir do card no
  caso real; alinhamento é follow-up registrado.
- **Risco**: LLM1 abandonar o item estruturado no reprocessamento (caso cai
  em `exam_type_mismatch` e não prossegue).
  **Mitigação**: registrar a condicional; saída operacional é re-correção
  (monitorar na validação da rc.2).
- **Risco**: regressão do fail-closed.
  **Mitigação**: guardas de coincidência + conjuntos não-cobertos permanecem
  `invalid`/revisão; suíte pinada atualizada com classificação por tipo de
  mudança (design D7).

## Histórico de Mudanças
- 2026-09-26: Criada como Proposed no change
  `normalize-detected-set-to-valid-selection`.
- 2026-09-26: Revisão de planejamento incorporada (discriminador `any_set ≠
  ∅`, resolução também no branch de matriz, payload só fora da matriz, evento
  bruto via campo explícito, riscos residuais LLM1/card×tabela). Status mudado
  de Proposed para Accepted pelo operador.
- 2026-09-26: Implementada no change `normalize-detected-set-to-valid-selection`
  (3 slices, gate final 4602 testes; commit de fechamento `de4420a`).
