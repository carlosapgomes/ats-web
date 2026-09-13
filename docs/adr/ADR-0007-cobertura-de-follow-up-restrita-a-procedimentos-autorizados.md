# ADR-0007: Cobertura de follow-up restrita a procedimentos autorizados

## Status

Accepted

## Contexto

O follow-up (pós-procedimento) do ATS registra, por caso, o desfecho de cada
procedimento: realizado ou não realizado com causa estruturada
(`FollowUpNonPerformanceReason`: absenteísmo, preparo inadequado, falta de
recursos com submotivo, outras causas com texto). O validador
(`apps/cases/followup.py::_validate_outcomes`) exige cobertura de **todas** as
rows `CaseProcedure` do caso, e o formulário lista blocos de
`case.procedures.all()`, independentemente da decisão médica.

Com a introdução das trocas médicas (`trocar e aprovar`, ADR-0006) e de
aprovações parciais, um caso decidido pode conter rows **negadas** convivendo
com rows aprovadas (ex.: EDA negada + Ecoendoscopia autorizada). A row negada
existe de propósito — preserva a rastreabilidade das três dimensões
autoritativas (`declared_by_nir`, `detection_status`, `doctor_disposition`) —,
mas o follow-up passa a **exigir um desfecho clínico para um procedimento que
nunca foi autorizado nem realizado**. O CHD é forçado a enquadrar a row negada
em "Outras causas", misturando duas populações com significados diferentes:

1. procedimentos **autorizados mas não realizados** (falhas operacionais:
   absenteísmo, preparo, recursos) — alvo de melhoria de processo;
2. procedimentos **nunca autorizados** (artefato do fluxo de decisão) — não é
   evento operacional.

Além disso, todo o vocabulário de não realização é operacional por construção;
"não autorizado" não tem categoria. A disparidade pedido↔autorizado já é
plenamente consultável na camada de decisão (`CaseProcedure` +
`CaseEvent.DOCTOR_PROCEDURE_SET_CHANGED` com razão), sem depender do follow-up.

A cláusula final do design D13 do change
`support-independent-echoendoscopy-cpre-workflows`
("Follow-up já grava uma row por `CaseProcedure`; será validado para labels e
formulários dos novos tipos, sem mudar o modelo ou a semântica de desfecho")
congelou deliberadamente essa semântica para não misturar duas mudanças de
comportamento. Esta ADR supersede especificamente essa cláusula.

## Decisão

O follow-up passa a cobrir **somente as rows `CaseProcedure` com
`doctor_disposition == "approved"`**:

1. `_validate_outcomes` valida cobertura e pertencimento contra o subconjunto
   autorizado; outcome informado para row não autorizada é rejeitado; rows
   negadas/pendentes ficam isentas.
2. O formulário constrói blocos apenas das rows autorizadas (ordem canônica do
   catálogo mantida).
3. A disparidade pedido↔autorizado é consultada na camada de decisão
   (`CaseProcedure` e eventos de auditoria), **não** no follow-up — tempo de
   leitura, sem desnormalização.
4. **Sem mudança de modelo, sem migration, sem backfill**: versões históricas
   que cobriam todas as rows permanecem íntegras (append-only) e continuam
   renderizando no histórico/CSV exatamente como gravadas; novas versões de
   casos legados seguem a regra nova.

Garantia de não-vazio: a matriz fechada de conjuntos aprovados
(`ALLOWED_PROCEDURE_SETS`) valida conjuntos aprovados não vazios e o
roteamento accept/deny da decisão médica (zero aprovados ⇒ deny integral,
jamais elegível a follow-up) garante ≥1 row autorizada por caso elegível;
portanto o formulário nunca fica vazio por construção; o erro defensivo
("sem procedimentos autorizados") permanece para estados inatingíveis.

## Alternativas Consideradas

1. **Manter como está (cobertura total)**: rows negadas continuam exigindo
   desfecho enquadrado em "Outras causas".
   - **Vantagens**: zero mudança; tabela de follow-up exaustiva por
     procedimento.
   - **Desvantagens**: fricção operacional; categoria "Outras causas" poluída;
     indicadores de não realização contaminados por artefatos de decisão.
   - **Por que não escolhida**: dado menos verdadeiro com custo humano real.

2. **Desfecho sintético automático "não autorizado" (opção C)**: row negada
   recebe row sintética não editável de follow-up.
   - **Vantagens**: tabela permanece exaustiva; categoria explícita.
   - **Desvantagens**: desnormaliza fato que já existe em
     `doctor_disposition` (risco de drift); rows sintéticas misturadas com
     rows atestadas por humano exigem proveniência; exige mudança de modelo.
   - **Por que não escolhida**: duplicação de verdade evitável; leitura em
     tempo de consulta resolve com menos estado.

3. **Follow-up somente de rows autorizadas + disparidade derivada em leitura
   (escolhida)**: cobertura pelo subconjunto autorizado; "não autorizado" é
   query sobre `CaseProcedure`, não desfecho.
   - **Vantagens**: cada tabela com responsabilidade única (decisão vs
     execução); sem mudança de modelo; sem duplicação; vocabulário de não
     realização volta a significar apenas falha operacional.
   - **Desvantagens**: tabela de follow-up deixa de ser exaustiva por
     procedimento (consumidores que assumiam cobertura total precisam saber);
     janelas históricas misturam eras (versões antigas cobrem rows negadas).
   - **Por que escolhida**: o mais limpo dado o sistema construído; a
     suposição de exaustividade só existia no próprio validador/formulário.

## Consequências

### Positivas

- Desfecho volta a ser exclusivamente fato de execução do que foi autorizado.
- "Outras causas" deixa de acumular artefatos de decisão; indicadores de não
  realização medem só falha operacional.
- Separação de camadas: disparidade (decisão) em `CaseProcedure`/eventos;
  realização (execução) no follow-up.
- Sem migration, sem backfill, sem modelo novo.

### Negativas/Trade-offs

- Consumidores do follow-up não podem mais assumir 1 row por procedimento do
  caso (para novas gravações); a cobertura é pelo subconjunto autorizado.
- Histórico em janelas que cruzam a mudança mistura eras (legado exaustivo,
  novo autorizado-apenas) — dado permanece verdadeiro "como gravado".

### Riscos e Mitigações

- **Risco**: caso elegível sem rows autorizadas (inatingível pelo domínio).
  **Mitigação**: erro defensivo no validador/formulário + teste.
- **Risco**: regressão silenciosa de cobertura (worker/reviewer negligenciam).
  **Mitigação**: testes RED→GREEN no slice com caso de troca real; spec delta
  canônica atualizada.
- **Risco**: leitura errada de indicadores misturando eras.
  **Mitigação**: documentar no change; eventuais relatórios de era devem
  classificar por data de gravação, não presumir.

## Referências

- Change: `openspec/changes/followup-authorized-procedures-only/`
- Supersede (parcial): cláusula final de D13 em
  `openspec/changes/support-independent-echoendoscopy-cpre-workflows/design.md`
  e o mesmo texto em ADR-0006.
- ADR-0006: `docs/adr/ADR-0006-ecoendoscopia-e-cpre-como-procedimentos-independentes.md`

## Histórico de Mudanças

- 2026-09-12: Criada com status Accepted (decisão do produto durante a
  execução do change de Ecoendoscopia/CPRE, pós-Slice 006).
