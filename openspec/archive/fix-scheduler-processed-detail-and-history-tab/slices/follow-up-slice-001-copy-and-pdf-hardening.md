# Follow-up Slice 001: Microcopy e link de PDF no detalhe scheduler

## Handoff para implementador LLM com contexto zero

Você está no projeto ATS Web, um monolito Django SSR. Antes de codar, leia integralmente:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/fix-scheduler-processed-detail-and-history-tab/proposal.md`
4. `openspec/changes/fix-scheduler-processed-detail-and-history-tab/design.md`
5. `openspec/changes/fix-scheduler-processed-detail-and-history-tab/tasks.md`
6. `openspec/changes/fix-scheduler-processed-detail-and-history-tab/slices/slice-001-unified-scheduler-detail-message-nir.md`
7. Este arquivo
8. Código atual em:
   - `apps/scheduler/views.py`
   - `templates/scheduler/context_detail.html`
   - `apps/scheduler/tests/test_views.py`

Implemente **somente este follow-up**. Não implemente a aba `Buscar caso antigo`; isso continua sendo o Slice 002.

Use TDD obrigatório: **RED → GREEN → REFACTOR**. Primeiro escreva testes falhando para as regressões apontadas, depois implemente o mínimo necessário.

Aplique clean code, DRY local e YAGNI:

- correção pequena e cirúrgica;
- sem novo endpoint;
- sem alteração de autorização;
- sem migration;
- sem novo model/tabela;
- sem alteração de FSM;
- sem refactor amplo do detalhe scheduler.

## Contexto do follow-up

Após implementação do Slice 001, o avaliador encontrou duas observações não bloqueantes, mas úteis para corrigir antes do Slice 002:

1. O bloco `Comunicar NIR` aparece também para casos processados hoje que ainda não estão encerrados, mas a microcopy diz:

```text
Este caso já está encerrado.
```

Isso é impreciso para casos recém-confirmados/recusados pelo agendador.

2. Antes do Slice 001, `scheduler_processed_detail` passava `pdf_url` ao template `intake/case_detail.html`. Após trocar para `scheduler/context_detail.html`, a rota `scheduler:processed_pdf` continuou existindo, mas não há mais link de UI para o PDF no detalhe de `Processados Hoje`.

## Objetivo do follow-up

Entrega vertical e enxuta:

```text
Agendador abre detalhe de caso em Processados Hoje
→ microcopy de Comunicar NIR serve tanto para caso encerrado quanto não encerrado
→ detalhe mostra link/atalho para PDF original quando a URL de PDF está disponível
→ rota scheduler:processed_pdf deixa de ficar órfã na UI desse fluxo
```

## Escopo funcional

### R1. Corrigir microcopy do bloco `Comunicar NIR`

Em `templates/scheduler/context_detail.html`, substituir texto específico de caso encerrado por texto neutro.

Texto sugerido:

```text
Use este formulário para enviar uma mensagem operacional ao NIR sobre este caso.
O sistema adicionará automaticamente a menção @nir para notificar a equipe NIR.
```

Critérios:

- não afirmar que o caso está encerrado;
- manter claro que a mensagem é operacional;
- manter claro que `@nir` será adicionado automaticamente.

### R2. Restaurar link de PDF para detalhe de `Processados Hoje`

Adicionar `pdf_url` ao contexto de `scheduler_processed_detail`, apontando para:

```python
reverse("scheduler:processed_pdf", args=[case.case_id])
```

Renderizar em `templates/scheduler/context_detail.html` um bloco/link pequeno para abrir o PDF quando `pdf_url` existir.

Sugestão de UI enxuta:

```django
{% if pdf_url %}
<div class="card p-4 mb-4">
  <h5 class="mb-3">📄 PDF original</h5>
  <a href="{{ pdf_url }}" class="btn btn-sm btn-hospital-outline" target="_blank" rel="noopener">
    Abrir PDF em nova aba
  </a>
</div>
{% endif %}
```

Não é obrigatório embutir `<embed>` neste follow-up; o objetivo é restaurar o atalho sem ampliar escopo.

### R3. Não expor PDF indevidamente na busca histórica institucional

A rota `scheduler:processed_pdf` exige `scheduler=request.user`. Portanto, neste follow-up, o `pdf_url` deve ser passado **somente** no contexto de `scheduler_processed_detail`.

Não adicionar `pdf_url` automaticamente em `scheduler_context_detail` para casos históricos de outros agendadores, a menos que também seja criada uma rota de PDF com autorização histórica institucional — isso está fora de escopo.

### R4. Manter segurança existente

Não alterar:

- `scheduler_processed_pdf` authorization;
- `_is_scheduler_historical_case`;
- `scheduler_historical_message_nir`;
- permissões de busca histórica;
- endpoints do NIR.

## Fora de escopo

Não implementar neste follow-up:

- terceira aba `Buscar caso antigo`;
- embed inline de PDF obrigatório;
- nova rota de PDF para busca histórica institucional;
- alteração de autorização de PDF;
- alteração em views/templates do NIR;
- alteração em comunicação/menções;
- models, migrations ou FSM.

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/scheduler/views.py`
2. `templates/scheduler/context_detail.html`
3. `apps/scheduler/tests/test_views.py`
4. `openspec/changes/fix-scheduler-processed-detail-and-history-tab/tasks.md`

Se precisar tocar mais arquivos, justificar no relatório.

## TDD obrigatório

Adicione testes falhando antes da implementação.

### Testes mínimos sugeridos

1. `test_scheduler_processed_detail_shows_processed_pdf_link`
   - cria caso processado pelo scheduler logado;
   - GET `/scheduler/processed/<case_id>/` retorna 200;
   - assert contém link para `/scheduler/processed/<case_id>/pdf/`;
   - assert contém texto como `PDF original` ou `Abrir PDF`.

2. `test_scheduler_processed_detail_message_nir_copy_is_status_neutral`
   - cria caso processado pelo scheduler logado em escopo histórico;
   - GET detalhe;
   - assert contém texto neutro como `mensagem operacional ao NIR sobre este caso`;
   - assert **não** contém `Este caso já está encerrado`.

3. Preservar teste existente de `scheduler_processed_pdf_404_for_other_scheduler_case`.

4. Opcional, se simples: teste que `scheduler_context_detail` histórico de caso de outro scheduler não recebe link `processed/<case_id>/pdf/`, evitando sugerir acesso por rota que retornaria 404.

## Critérios de aceitação do follow-up

- [ ] TDD RED → GREEN → REFACTOR documentado no relatório.
- [ ] Microcopy de `Comunicar NIR` não afirma que o caso está encerrado.
- [ ] Detalhe de `Processados Hoje` exibe link/atalho para PDF original.
- [ ] Link de PDF usa `scheduler:processed_pdf`.
- [ ] Autorização de `scheduler_processed_pdf` não foi relaxada.
- [ ] Busca histórica institucional não ganhou link quebrado para PDF de outro scheduler.
- [ ] Nenhuma migration criada.
- [ ] Nenhum estado FSM/model criado ou alterado.
- [ ] `tasks.md` atualizado marcando este follow-up ao concluir.
- [ ] Quality gate executado.
- [ ] Relatório temporário criado e informado via `REPORT_PATH`.

## Gates de autoavaliação

Responder no relatório:

1. Qual texto substituiu `Este caso já está encerrado`?
2. Que teste prova que a copy agora é neutra?
3. Onde `pdf_url` é passado no contexto? Ele é passado apenas para `scheduler_processed_detail`?
4. Que teste prova que o link de PDF aparece no detalhe de `Processados Hoje`?
5. A autorização de `scheduler_processed_pdf` foi alterada? Esperado: não.
6. A busca histórica institucional ganhou link de PDF? Esperado: não neste follow-up.
7. Alguma migration/FSM/model foi criado/alterado? Esperado: não.
8. Quais comandos de validação foram executados?

## Relatório obrigatório

Criar relatório markdown temporário em:

```text
/tmp/fix-scheduler-processed-detail-and-history-tab-follow-up-slice-001-report.md
```

O relatório deve conter:

- resumo da mudança;
- arquivos tocados;
- evidência TDD RED/GREEN/REFACTOR;
- snippets antes/depois dos pontos principais;
- resposta aos gates de autoavaliação;
- comandos de validação e resultados;
- riscos/observações.

Responder ao planner com:

```text
REPORT_PATH=/tmp/fix-scheduler-processed-detail-and-history-tab-follow-up-slice-001-report.md
```

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/fix-scheduler-processed-detail-and-history-tab/{proposal.md,design.md,tasks.md,slices/follow-up-slice-001-copy-and-pdf-hardening.md}.
Implement ONLY this follow-up slice. Do not implement Slice 002.
Use TDD: write failing tests first for neutral Comunicar NIR microcopy and PDF link in scheduler processed detail. Then implement the minimum change.
Keep it lean: prefer apps/scheduler/views.py, templates/scheduler/context_detail.html, apps/scheduler/tests/test_views.py, and tasks.md only.
Do not change permissions, PDF authorization, communication logic, models, migrations or FSM. Do not add a historical institutional PDF route.
Apply clean code, DRY local only, and YAGNI.
Run quality gate from AGENTS.md, update tasks.md, create /tmp/fix-scheduler-processed-detail-and-history-tab-follow-up-slice-001-report.md with before/after snippets and gate answers, commit and push, then reply only with REPORT_PATH and stop.
```
