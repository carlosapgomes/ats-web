# ADR-0010: Catálogo ampliado e pacotes atômicos de procedimentos endoscópicos

## Status
Proposed

## Data
2026-09-25

## Contexto

Esta decisão integra o change [`support-expanded-endoscopy-procedure-catalog`](../../openspec/changes/support-expanded-endoscopy-procedure-catalog/proposal.md).

A arquitetura atual preserva procedimentos por rows `CaseProcedure`, usa matriz fechada de combinações, schemas LLM strict 3.0 e profiles clínicos reutilizáveis. Entretanto, o catálogo persistido contém somente EDA, Colonoscopia, Ecoendoscopia e CPRE. GTT e dilatação ainda aparecem parcialmente como sinais/subtipos de EDA; Retossigmoidoscopia e cápsula não possuem identidade de ponta a ponta.

As novas seleções têm semânticas diferentes de EDA + Colonoscopia. EDA + GTT, EDA + Cápsula, EDA + Dilatação, Retossigmoidoscopia + Dilatação e Retossigmoidoscopia + Argônio são pacotes indivisíveis: operação agenda e decide o pacote como uma unidade. Já EDA + Colonoscopia precisa continuar com duas rows e decisão independente por componente.

Há ainda dois detalhes clínicos que não devem alterar a policy automática: local anatômico informativo da EDA + Dilatação e revisão visual de possível infecção sistêmica em EDA + GTT. Essa revisão deve mostrar inclusive resultados laboratoriais normais presentes, sem thresholds implícitos e sem bloquear o fluxo.

## Decisão

1. O catálogo canônico terá dez identidades atômicas:
   - `eda`;
   - `eda_gastrostomy`;
   - `eda_capsule`;
   - `eda_dilation`;
   - `colonoscopy`;
   - `rectosigmoidoscopy`;
   - `rectosigmoidoscopy_dilation`;
   - `rectosigmoidoscopy_argon`;
   - `echoendoscopy`;
   - `cpre`.

2. O domínio manterá metadados centralizados por identidade: label, ordem, família/profile, aliases aprovados, capacidade de detalhe clínico e disponibilidade nas jornadas. Consumidores não manterão listas paralelas quando o metadado do catálogo for suficiente.

3. A matriz autorizável será fechada: qualquer identidade atômica isolada ou exatamente `{eda, colonoscopy}`. `eda_colonoscopy` continuará uma chave de seleção/projeção, não um `ProcedureType` persistido. Nenhuma variação poderá ser combinada com Colonoscopia ou com outra identidade.

4. Os cinco pacotes com `+` na label serão uma única row e uma única decisão. Detecção/reconciliação colapsará a identidade base somente quando uma ocorrência de solicitação atual sustentar o pacote. Duas variações atuais, valor desconhecido ou associação ambígua falharão fechados para revisão NIR.

5. As variações de EDA reutilizarão o profile determinístico da EDA. Retossigmoidoscopia e suas variações reutilizarão o profile da Colonoscopia. Família/profile não produzirá equivalência de histórico, filtro ou analytics: essas dimensões sempre usarão código exato.

6. Novos processamentos usarão schemas strict LLM 4.0. Leitores/adapters manterão compatibilidade com 1.1/2.0/3.0 sem reescrever JSON histórico. O cutover de web, workers e prompts será coordenado e sem writers concorrentes. Depois do primeiro write 4.0, rollback suportado será fix-forward.

7. `eda_dilation` terá detalhe informativo de local anatômico no vocabulário `esophagus|pylorus|duodenum|anastomosis|jejunum|other|unknown`, ancorado no relatório principal. O local não muda identidade, profile, policy ou sugestão.

8. `eda_gastrostomy` terá coleção tipada e ancorada de evidências nas categorias leucócitos, PCR, procalcitonina, lactato, culturas, temperatura/febre, infectologia e antibióticos. Todo resultado presente será exibido, inclusive normal/negativo. Qualificação clínica só será afirmada quando explícita no documento; nenhum threshold local será introduzido.

9. O alerta visual de possível infecção será acionado somente por preocupação explicitamente documentada e atual/não histórica, ou por infectologia/antibiótico atuais. Será estritamente consultivo: não integrará `failed_requirements`, não alterará policy, recomendação, suporte, decisão, validação, FSM ou fila.

10. Seletores de procedimento em upload, correção/reenvio e inclusão/substituição médica usarão um combobox acessível em JavaScript vanilla, com busca sem acentos e progressive enhancement sobre controle SSR. O backend continuará autoridade e aceitará somente código canônico exato.

11. Não haverá backfill, reclassificação histórica, nova flag ou rollout gradual das novas identidades. As flags preexistentes de Colonoscopia, Ecoendoscopia e CPRE mantêm a semântica atual.

Esta ADR parcialmente supera a ADR-0004 e a ADR-0006 apenas onde limitavam o catálogo/contrato gravável a quatro tipos e schema 3.0. As decisões sobre `CaseProcedure`, independência de EDA + Colonoscopia, profiles, auditoria, compatibilidade histórica e precedência de Ecoendoscopia/CPRE permanecem válidas.

## Alternativas Consideradas

1. **Manter GTT/dilatação/cápsula como sinais ou subtipos de EDA**
   - **Vantagens:** menor migration e menos opções visíveis.
   - **Desvantagens:** perde identidade solicitada/autorizada, mistura histórico e volume, dificulta correção e decisão.
   - **Por que não escolhida:** sinais não representam adequadamente um pacote operacional indivisível.

2. **Persistir a identidade base e uma segunda row para cada variação**
   - **Vantagens:** reaproveita a aparência do combinado atual.
   - **Desvantagens:** permitiria decisões parciais inválidas, dupla contagem e dois componentes onde existe um pacote.
   - **Por que não escolhida:** contradiz a indivisibilidade clínica/operacional confirmada.

3. **Modelar variações como atributos livres de EDA/Retossigmoidoscopia**
   - **Vantagens:** catálogo menor.
   - **Desvantagens:** combinações não tipadas, histórico ambíguo, filtros complexos e validação frágil.
   - **Por que não escolhida:** o conjunto de pacotes é fechado e merece identidade estável.

4. **Criar thresholds locais para identificar infecção**
   - **Vantagens:** alerta aparentemente mais automatizado.
   - **Desvantagens:** introduz regra clínica não aprovada, depende de unidade/faixa/contexto e pode gerar falsa certeza.
   - **Por que não escolhida:** a revisão é consultiva e deve refletir somente interpretação explícita do relatório.

5. **Adicionar biblioteca externa de combobox ou framework frontend**
   - **Vantagens:** mais comportamento pronto.
   - **Desvantagens:** dependência desnecessária, conflito com stack Vanilla JS/SSR e maior custo de manutenção.
   - **Por que não escolhida:** o comportamento necessário é limitado e pode ser progressivamente aprimorado sem mudar o contrato HTML/POST.

## Consequências

### Positivas

- O procedimento solicitado permanece rastreável por código exato até decisão, agenda, follow-up e analytics.
- Pacotes não podem ser parcialmente autorizados ou contados em duplicidade.
- Profiles clínicos são reutilizados sem confundir identidade operacional.
- O médico recebe informação infecciosa útil, inclusive resultados normais, sem bloqueio automático não aprovado.
- Seletores continuam utilizáveis à medida que o catálogo cresce e permanecem funcionais sem JavaScript.

### Negativas/Trade-offs

- O cutover 4.0 exige coordenação de prompts, web e workers e elimina rollback seguro para writer 3.0 após o primeiro write.
- O catálogo ampliado aumenta o número de filtros, labels e cenários de teste.
- Ancoragem conservadora pode omitir detalhes reais quando o relatório é ambíguo.
- Sem backfill, analytics das novas identidades começam no cutover e não representam retrospectivamente sinais antigos.

### Riscos e Mitigações

- **Divergência entre listas hardcoded:** catálogo central com testes de completude e inventário de consumidores.
- **Pacote virar combinado por label com `+`:** matriz por códigos/conjuntos e teste explícito de agendamento casado somente para `{eda, colonoscopy}`.
- **Dilatação anatômica gerar falso procedimento:** exigência de solicitação atual e vínculo local; achados como dilatação de colédoco são negativos obrigatórios.
- **Painel GTT alterar recomendação por acidente:** objeto consultivo separado da policy e testes de invariância de `failed_requirements`, sugestão e FSM.
- **Resultado normal interpretado como infecção:** qualificação fechada, sem thresholds; normais/negativos aparecem sem acionar alerta isoladamente.
- **Combobox bloquear usuário sem JS ou tecnologia assistiva:** fallback SSR, teclado/ARIA, foco visível e validação backend independente.
- **Histórico contaminado por família:** queries e testes usam igualdade de código, nunca profile compartilhado.

## Histórico de Mudanças

- 2026-09-25: ADR criada como `Proposed` junto ao change OpenSpec.
