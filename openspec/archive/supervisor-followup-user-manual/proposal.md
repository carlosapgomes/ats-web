# Proposal: Documentar o Follow-up do Supervisor no manual de usuários

**Change ID**: `supervisor-followup-user-manual`
**Tipo**: QUICK docs (manual do usuário)

## Why

A aba **Follow-up** do supervisor (change `supervisor-appointment-follow-up`) é UI nova visível para `manager`/`admin`, mas o `docs/manual/manual-usuarios.md` não a documenta — o manual cobre apenas os três papéis operacionais (NIR, Médico, CHD). Releases anteriores desta casa documentaram features de UI no manual; a validação de release usa o manual como artefato oficial.

## What Changes

- Nova seção **"6. Ações do usuário Supervisor"** no manual, com a subseção "6.1 Registrar follow-up de agendamento": como abrir a aba (Dashboard → Follow-up), o que lista (agendados confirmados + vindas imediatas de hoje/ontem, seletor de data, busca por ocorrência/nome, badge pendente/registrado), o formulário (desfecho por procedimento com causas estruturadas — absenteísmo, falta de recursos com submotivos, outras causas com descrição — e internação por caso), versionamento (atualização cria nova versão; histórico preservado com autor) e a regra de que follow-up é **registro de desfecho** (não abre intercorrência nem reagendamento).
- Renumerar as seções gerais atuais 6→7 (Boas práticas) e 7→8 (Observações finais) para manter papéis juntos (3 NIR, 4 Médico, 5 CHD, 6 Supervisor).
- Atualizar a lista de papéis da introdução (acrescenta Supervisor/gerência).

### Impact

- Apenas `docs/manual/manual-usuarios.md`. Sem specs (`skip_specs: true` — comportamento já especificado em `openspec/specs/supervisor-appointment-follow-up/`), sem código, sem migrations.

## Sucesso

Manual documenta a aba de forma suficiente para um supervisor operar sem treinamento extra; testes existentes do manual (`tests/test_user_manual_artifacts.py`, `tests/test_*_rollout_docs.py`) continuam verdes; PDF do manual (`scripts/build_user_manual_pdf.py`) continua gerando TOC válido.
