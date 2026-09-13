# Proposal: followup-authorized-procedures-only

## Problema

Com as trocas médicas (`trocar e aprovar`) e aprovações parciais
(ADR-0006), casos decididos contêm rows `CaseProcedure` negadas convivendo
com rows aprovadas. O follow-up atual exige desfecho para **todas** as rows
(`_validate_outcomes` cobre `case.procedures.all()`; formulário idem), forçando
o CHD a registrar um desfecho clínico para um procedimento nunca autorizado —
enquadrado artificialmente em "Outras causas". Isso polui a categoria com
artefatos de decisão e contamina indicadores de não realização, que passam a
misturar "autorizado mas não realizado" (falha operacional) com "nunca
autorizado" (fato do fluxo de decisão).

## Objetivo

Restringir a cobertura do follow-up às rows **autorizadas**
(`doctor_disposition == "approved"`): validador, formulário e eventos passam a
considerar somente o subconjunto autorizado. A disparidade
pedido↔autorizado permanece consultável na camada de decisão
(`CaseProcedure` + `CaseEvent.DOCTOR_PROCEDURE_SET_CHANGED`), derivada em
tempo de leitura, sem desnormalização. Decisão registrada na
ADR-0007.

## Escopo

### In

- `apps/cases/followup.py` — cobertura/pertencimento pelo subconjunto
  autorizado; mensagens de erro ajustadas.
- `apps/dashboard/views.py` — formulário constrói blocos apenas de rows
  autorizadas (ordem canônica do catálogo mantida); estado defensivo sem rows
  autorizadas.
- Testes de serviço, formulário e histórico (eras mistas).

### Out

- Mudança de modelo ou migration (`CaseFollowUp`/`ProcedureFollowUp`
  intocados).
- Backfill ou reescrita de versões históricas (append-only preservado).
- Novas categorias de desfecho ("não autorizado" NÃO vira `ProcedureFollowUp`).
- Analytics/manager (fatia do change ativo), CHD/NIR/doctor queues.
- Marcador visual de "não autorizado" no formulário de follow-up — a
  disparidade é consultada na camada de decisão (ADR-0007, alternativa 3).

## Sucesso

- Caso de troca (EDA negada + Ecoendoscopia autorizada): formulário exibe
  somente o bloco da Ecoendoscopia; POST sem desfecho para a EDA é aceito;
  evento `FOLLOWUP_RECORDED` carrega somente a row autorizada.
- Aprovação parcial (EDA aprovada + Colonoscopia negada) idem.
- Caso simples sem rows negadas: comportamento idêntico ao atual.
- Versões históricas exaustivas continuam renderizando no histórico/CSV
  exatamente como gravadas; atualização (nova versão) de caso legado segue a
  regra nova.
- Zero migrations; zero reescritas de dados.
