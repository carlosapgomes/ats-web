# Slice 001: NIR cria e acompanha um único caso combinado

## Handoff com contexto zero

Leia antes de editar:

- `AGENTS.md`, `PROJECT_CONTEXT.md`;
- todos os artefatos deste change e ADR-0004 aceita;
- specs canônicas `openspec/specs/exam-type-intake-routing/spec.md` e `exam-type-correction/spec.md`;
- `apps/cases/{models.py,services.py,signals.py}` e migrations atuais;
- `apps/intake/{forms.py,services.py,views.py}`;
- `templates/intake/{intake_home.html,my_cases.html,_my_cases_content.html,case_detail.html}` e `static/js/upload.js`;
- testes de intake/exam type e migration.

### Estado atual

`Case.exam_type` é singular e o upload oferece EDA/Colonoscopia. Mixed é posteriormente bloqueado. Este slice cria a projeção normalizada e permite ao NIR declarar/acompanhar combinado, mantendo ponte temporária para consumidores ainda não migrados. O pipeline neutro vem somente no Slice 002; não tente fazê-lo agora.

### Fluxo entregue

```text
NIR escolhe EDA + Colonoscopia
→ envia lote
→ cada PDF cria exatamente um Case
→ cada Case possui duas rows CaseProcedure declaradas
→ evento registra conjunto
→ Meus Casos/detalhe mostram um card/badge combinado
```

## Protocolo obrigatório para implementador DeepSeek4-Flash

Este slice será implementado por um modelo rápido e com tendência a concluir cedo demais. **Se qualquer item falhar, o slice está INCOMPLETO**: não marque `tasks.md`, não faça commit/push e responda com bloqueio + evidência.

1. Confirme branch exata, árvore limpa, ADR-0004 aceita e registre `BASE_REF=$(git rev-parse HEAD)`.
2. Escreva no relatório a matriz `Requisito → arquivo(s) → teste(s)` e rode `uv run pytest` antes de editar. Baseline com failed/error bloqueia.
3. Crie testes primeiro e prove RED real por comportamento esperado, não import error acidental.
4. Faça GREEN mínimo; não implemente pipeline/decisão/CHD/dashboard futuros.
5. REFACTOR apenas no trecho tocado: clean code, DRY, YAGNI, nomes claros, funções coesas, baixo acoplamento e sem código morto.
6. Execute inspeções `rg`/diff abaixo e interprete resultados.
7. Rode exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`, `uv run pytest`; final exige exit 0, zero failures/errors e `passed_final >= passed_baseline`.
8. Gere relatório factual com snippets antes/depois e `Handoff para verificador`.
9. Só então marque Slice 001, commit normal, push, responda `REPORT_PATH` e PARE.

## Requisitos

### R1. Projeção mínima por procedimento

Adicionar `ProcedureType`, `DetectionStatus`, `DoctorDisposition` e `CaseProcedure` conforme design D1, com unique constraint `(case, procedure_type)`. Não adicionar CPRE, tabela de appointment ou framework genérico.

### R2. Backfill conservador

Migration cria exatamente uma row declarada correspondente ao `Case.exam_type` atual; não reprocessa nem altera status/eventos/PDF/JSON/agenda. Casos que já alcançaram `WAIT_DOCTOR` ou estado posterior após scope gate podem projetar o tipo antigo como detectado; anteriores ao gate/manual review permanecem pending salvo payload estruturado inequívoco. Definir/testar grupos de status e regra conservadora de disposição médica histórica. Migration forward e reverse devem ser determinísticas.

### R3. Serviço único de declaração

Centralizar criação/atualização de conjunto declarado, validação de `eda|colonoscopy|eda_colonoscopy`, ordenação/label e ponte transitória. Write atômico: falha em uma row não deixa caso/projeção parcial. Nenhuma view escreve rows diretamente.

### R4. Intake combinado e flag

Adicionar opção textual `EDA + Colonoscopia`, sem default visual. Flag falsa bloqueia Colonoscopia e combinado no backend e UI; EDA permanece. Um lote usa uma seleção para todos os PDFs.

### R5. Um caso, duas rows

Cada PDF combinado cria um `Case`, duas rows declaradas e um evento enxuto `CASE_PROCEDURES_DECLARED`. Não criar caso irmão, segundo PDF record ou agenda.

### R6. Acompanhamento NIR

Meus Casos e detalhe mostram `EDA + Colonoscopia` a partir da projeção declarada e mantêm EDA/Colonoscopia simples. Badge deve ser textual/acessível. Nenhuma template deve fazer query implícita por row.

### R7. Compatibilidade transitória explícita

Manter `Case.exam_type` somente como ponte documentada e centralizada. Adicionar valor transitório combinado apenas se necessário. Não migrar readers fora do intake neste slice. Combinado pode continuar scope-gated pelo pipeline antigo até Slice 002; teste deve deixar essa limitação explícita e a flag de produção permanece falsa.

## Arquivos esperados e cap

Esperados (preferir consolidação):

1. `apps/cases/models.py`;
2. uma migration nova em `apps/cases/migrations/`;
3. `apps/cases/services.py` ou módulo coeso único para seleção;
4. `apps/intake/forms.py`;
5. `apps/intake/services.py`;
6. templates/JS de upload e acompanhamento estritamente necessários;
7. até três arquivos de teste focados.

**Cap: 11 arquivos produto/teste, ignorando `tasks.md`.** Acima disso: INCOMPLETE sem aprovação prévia do planner. Justifique cada extra no relatório.

## Fora de escopo/proibido

- schemas/prompts/policy/orchestrator LLM;
- decisão médica por componente;
- CHD/dashboard;
- remoção de `Case.exam_type`;
- corrected resubmission/correção NIR (Slice 005);
- FSM/roles/permissões;
- CPRE ou terceiro procedimento.

## TDD obrigatório

### RED

Cobertura mínima:

1. constraint impede duplicata do mesmo procedimento;
2. migration EDA/Colon cria uma row e preserva campos/eventos;
3. combinado cria um caso e exatamente duas rows;
4. lote de N PDFs cria N casos, nunca 2N;
5. ausência/valor inválido não cria nada;
6. flag falsa rejeita colon e combinado, aceita EDA;
7. falha transacional não deixa rows/caso parcial;
8. cards/detalhe exibem labels simples/combinado pela projeção;
9. evento contém conjunto ordenado sem texto clínico;
10. regressões de upload/anexos existentes passam.

Registre comando RED, testes falhando e motivo funcional esperado.

### GREEN

Implementar apenas projeção/intake/acompanhamento. Não “preparar” pipeline futuro além da API mínima exigida.

### REFACTOR

Eliminar lógica duplicada de parsing/labels criada no slice; não generalizar para procedimentos desconhecidos.

## Inspeções obrigatórias

```bash
rg -n "class (ProcedureType|CaseProcedure|DetectionStatus|DoctorDisposition)|UniqueConstraint" apps/cases
rg -n "eda_colonoscopy|EDA \+ Colonoscopia|COLONOSCOPY_INTAKE_ENABLED" apps/intake templates/intake static/js/upload.js
rg -n "CASE_PROCEDURES_DECLARED|set_declared|get_declared|format_procedure" apps/cases apps/intake
rg -n "CaseProcedure\.objects\.(create|update)|procedures\.(create|add)" apps/intake || true
rg -n "CPRE|ERCP" apps/cases apps/intake templates/intake || true

git diff --name-only "$BASE_REF"
git diff -- apps/pipeline apps/doctor apps/scheduler apps/dashboard config
```

Interprete: writes devem passar pelo serviço; apps proibidas sem diff; CPRE ausente; cap respeitado.

## Critérios de sucesso binários

- [ ] R1–R7 provados por teste/inspeção.
- [ ] Um combinado é um Case com duas rows.
- [ ] Backfill não infere/reprocessa.
- [ ] Flag bloqueia colon/combinado somente no intake.
- [ ] NIR vê badge combinado sem duplicar cards.
- [ ] Ponte legada está centralizada e rotulada temporária.
- [ ] Regressões de upload/anexos passam.
- [ ] Cap, baseline, gates e relatório atendidos.

## Gates de autoavaliação

Responder no relatório:

1. Qual teste prova 1 PDF combinado → 1 Case + 2 rows?
2. Qual prova atomicidade?
3. O que migration altera e preserva?
4. Existe write direto fora do serviço?
5. Como flag trata cada seleção?
6. Algum reader de pipeline foi antecipado?
7. Como label é derivado sem query no template?
8. Qual é a limitação transitória até Slice 002?
9. Quantos arquivos e por quê?
10. Baseline vs final e zero failures/errors?

### Condições automáticas de INCOMPLETO

Baseline/RED/gate/relatório ausentes; ADR não aceita; mais de um Case por PDF; row duplicada; estado parcial; flag permite combinado desligada ou bloqueia EDA; migration altera JSON/status/evento; UI infere label do campo legado; write direto em view; pipeline/doctor/CHD/dashboard antecipado; FSM/role alterado; >11 arquivos sem revisão; final falha ou passed menor; `tasks.md` marcado antes das evidências.

## Relatório obrigatório

Criar `/tmp/support-combined-eda-colonoscopy-workflow-slice-001-report.md` com:

- `Status: COMPLETE|INCOMPLETE`;
- matriz requisito→arquivo→teste;
- BASE_REF/branch/status e baseline;
- RED/GREEN/REFACTOR com comandos/exit codes;
- snippets antes/depois de model, migration, serviço, form e badge;
- inspeções interpretadas;
- lista de arquivos/justificativas;
- quality gate e comparação pytest;
- respostas aos gates;
- **Handoff para verificador**: arquivos alterados, comandos exatos de rerun, riscos/limitações e checklist R1–R7.

## Prompt pronto para implementador

```text
Read AGENTS.md, PROJECT_CONTEXT.md, every artifact under openspec/changes/support-combined-eda-colonoscopy-workflow, accepted ADR-0004, canonical intake/correction specs, and all files listed in Slice 001. Implement ONLY Slice 001 on feature/support-combined-eda-colonoscopy-workflow.

Follow the DeepSeek4-Flash protocol literally: clean branch/BASE_REF, full pytest baseline before edits, requirement matrix, real RED, minimal GREEN, narrow clean-code/DRY/YAGNI REFACTOR, all inspection checks, exact full quality gate and baseline-vs-final comparison. Any missing/failing item, final failure/error, passed_final < passed_baseline, or cap violation means INCOMPLETE: do not update tasks.md, commit or push.

Deliver one combined NIR upload as one Case with two normalized CaseProcedure rows, conservative backfill, atomic declaration service, flag enforcement and combined badge in NIR tracking. Keep the legacy exam_type only as centralized temporary bridge. Do not implement neutral LLM, doctor, CHD, dashboard, correction/resubmission, FSM or CPRE.

Create /tmp/support-combined-eda-colonoscopy-workflow-slice-001-report.md with evidence and Handoff para verificador. If complete, mark only Slice 001, commit, push, reply REPORT_PATH=... and STOP.
```
