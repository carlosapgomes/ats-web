# Design — followup-authorized-procedures-only

Decisão de produto registrada na
[ADR-0007](../../../docs/adr/ADR-0007-cobertura-de-follow-up-restrita-a-procedimentos-autorizados.md).
Este design cobre apenas as decisões técnicas de implementação.

## D1. Universo de cobertura = rows autorizadas

`_validate_outcomes` passa a derivar o universo de `case.procedures.all()`
filtrado por `doctor_disposition == "approved"`:

- **Cobertura**: toda row autorizada deve ter exatamente um desfecho
  (ausência → erro; duplicata → erro, como hoje).
- **Pertencimento**: desfecho informado para row não autorizada (negada ou
  pendente) é **rejeitado** — não apenas ignorado. Fail-closed consistente com
  o resto do sistema.
- **Vazio defensivo**: sem rows autorizadas → erro explícito. Inatingível pelo
  domínio: a matriz fechada valida conjuntos aprovados não vazios e o
  roteamento accept/deny da decisão médica (zero aprovados ⇒ deny integral,
  jamais elegível a follow-up) garante ≥1 row autorizada em todo caso
  elegível; a elegibilidade de follow-up exige decisão médica registrada
  (agendamento confirmado ou vinda imediata com `doctor_decided_at`).
- Regras condicionais de causa (submotivo/texto) permanecem idênticas.

## D2. Formulário projeta o mesmo universo

`followup_form` constrói blocos do subconjunto autorizado, mantendo a ordenação
canônica do catálogo (`_followup_procedure_order`, introduzida no Slice 006 do
change ativo). O estado defensivo sem rows autorizadas reutiliza o
comportamento existente de "sem procedimentos" (aviso, sem campos, POST
rejeitado) — nota da revisão do plano: o texto desse aviso existente diz
"sem procedimentos declarados", literalmente impreciso no estado defensivo
zero-aprovadas; aceito como está (template fora do blast radius, estado
inatingível pelo domínio). `FollowUpForm`/`FollowUpAdmissionForm` não mudam
(fields idênticos; o que muda é quais rows geram blocos).

## D3. Dados legados e eras mistas — append-only preservado

- Nenhum backfill: versões que cobriam rows negadas permanecem íntegras e
  renderizam no histórico/CSV/summary exatamente como gravadas (a leitura é
  "como gravado"; `current_follow_ups()` não muda).
- Nova versão de caso legado (update) usa a regra nova — cada versão reflete a
  regra vigente no momento da gravação; o snapshot em `CaseEvent` espelha
  somente as rows gravadas.
- Consequência documentada: janelas históricas que cruzam a mudança misturam
  eras. É dado verdadeiro; relatórios de era devem classificar por data de
  gravação, não presumir exaustividade.

## D4. Deltas de spec — o que muda e o que não muda

- `supervisor-appointment-follow-up`: requisito de registro MODIFICADO
  ("desfecho de cada `CaseProcedure` autorizada") + cenários novos (row negada
  isenta na troca e na aprovação parcial; estado defensivo "sem procedimentos
  autorizados").
- `supervisor-followup-history`: **sem delta** — o requisito descreve "uma
  linha por desfecho de procedimento gravado"; a mecânica de leitura não muda
  (linhas = rows gravadas, por construção).
- `dashboard-case-list` / `case-work-lock`: sem delta — badges de
  "registrado/pendente" continuam baseados na existência de versão corrente.

## D5. Ordenação e não-interferência

Este change executa **entre** os Slices 006 e 007 do change
`support-independent-echoendoscopy-cpre-workflows`:

- Slice 007 (jornada NIR) não toca follow-up.
- Slice 008 (analytics manager) lista follow-up em `out_of_scope`;
  `apps/dashboard/procedure_analytics.py` não consulta desfechos.
- Slice 009 (rollout/rollback) é agnóstico à semântica de cobertura.
- `apps/dashboard/views.py` é também blast radius do Slice 008 do change
  ativo: a ordenação declarada (este change entre 006 e 007) elimina o
  conflito; **preservar o interleave ao mesclar** para evitar rebase.
- O freeze do D13 do change ativo ("sem mudar o modelo ou a semântica de
  desfecho") fica **parcialmente superseded** por este change/ADR-0007 apenas
  na cláusula de cobertura; o restante do D13 (filtros/analytics orientados ao
  catálogo) permanece vigente.

## D6. Riscos

- **Regressão de cobertura**: mitigada por RED→GREEN com caso de troca real no
  slice (POST sem desfecho da row negada deve ser aceito; hoje é rejeitado).
- **Assunção de exaustividade em consumidores**: única consumidora da
  suposição era a própria validação/formulário; histórico lê rows gravadas.
  Teste de caracterização de era mista pinna o comportamento.
- **Zero-approved atingível apenas por write direto**: erro defensivo + teste.
