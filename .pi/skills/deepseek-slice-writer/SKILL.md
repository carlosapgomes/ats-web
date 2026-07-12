---
name: deepseek-slice-writer
description: Cria ou revisa arquivos de slice OpenSpec para implementação por DeepSeek4-Flash, reforçando TDD, critérios binários, inspeções obrigatórias, relatório verificável e condições de INCOMPLETO.
---

# Skill: DeepSeek Slice Writer

Use esta skill quando criar ou revisar slices que serão implementados por modelos rápidos, especialmente DeepSeek4-Flash, e que precisam reduzir conclusão prematura, erros pequenos de lógica e validação incompleta.

## Quando usar

- Ao criar `openspec/changes/<change>/slices/slice-*.md`.
- Ao revisar slices já escritos para deixá-los mais executáveis por DeepSeek4-Flash.
- Quando houver histórico de implementador marcar slice como pronto sem rodar todos os testes/gates.
- Quando o slice envolver UI/templates/rotas/permissões e precisar de checagens por inspeção além de testes.

## Objetivo

Transformar o slice em um contrato operacional, não apenas em descrição funcional:

1. requisito explícito;
2. teste obrigatório;
3. inspeção obrigatória;
4. condição de incompleto;
5. relatório com evidência;
6. handoff objetivo para verificador.

## Estrutura recomendada do slice

Todo slice para DeepSeek4-Flash deve conter, nesta ordem aproximada:

1. Handoff com contexto zero.
2. Protocolo obrigatório para DeepSeek4-Flash.
3. Objetivo do slice.
4. Contexto técnico atual.
5. Escopo funcional em requisitos `R1`, `R2`, `R3`...
6. Arquivos esperados e arquivos proibidos/fora de escopo.
7. TDD obrigatório: RED, GREEN, REFACTOR.
8. Checks de inspeção obrigatórios antes de concluir.
9. Critérios de sucesso binários.
10. Gates de autoavaliação em formato de perguntas.
11. Relatório obrigatório com caminho `/tmp/...-report.md`.
12. Prompt pronto para implementador LLM.

## Bloco obrigatório: Protocolo DeepSeek4-Flash

Inserir nos slices:

```markdown
## Protocolo obrigatório para implementador DeepSeek4-Flash

Este slice será implementado por um modelo rápido e com tendência a concluir cedo demais. Portanto, siga este protocolo literalmente. **Se qualquer item abaixo falhar, o slice está INCOMPLETO**: não marque `tasks.md`, não faça commit/push e responda com bloqueio + evidência.

1. **Plano antes de editar**: escreva no relatório uma mini matriz `Requisito → arquivo(s) → teste(s)`. Não implemente requisito sem teste ou justificativa explícita.
2. **RED real**: crie/ajuste testes primeiro e rode o subconjunto alvo. Pelo menos um teste novo deve falhar pelo motivo esperado. Se o teste passar antes da implementação, ele não prova o comportamento; corrija o teste.
3. **GREEN mínimo**: implemente somente o necessário para os testes do slice passarem. Não faça refactor amplo, não toque em apps fora do escopo e não antecipe slices futuros.
4. **Verificação por inspeção**: além dos testes, rode buscas `rg`/inspeções descritas neste slice para comprovar os contratos críticos do slice.
5. **Quality gate completo**: execute exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .` e `uv run pytest`. Se algum comando falhar, o slice não está pronto.
6. **Relatório com evidência, não opinião**: cole comandos executados, resumo das saídas, testes RED/GREEN, snippets antes/depois e respostas objetivas aos gates. Inclua também `Handoff para verificador` com: arquivos alterados, comandos exatos para rerun, riscos/limitações e checklist dos requisitos R1..Rn. Inclua uma seção final `Status: COMPLETE` somente se todos os critérios estiverem comprovados.
```

## Bloco obrigatório: Condições automáticas de INCOMPLETO

Adaptar ao slice, mantendo o espírito binário:

```markdown
### Condições automáticas de INCOMPLETO

Marque como incompleto se ocorrer qualquer uma destas situações:

- teste planejado não foi escrito ou não foi executado;
- quality gate completo não foi executado;
- qualquer teste/lint/mypy falhou;
- `tasks.md` foi marcado apesar de falha ou pendência;
- contrato crítico do slice não foi verificado por teste ou inspeção;
- comportamento antigo que deveria ser preservado foi removido sem teste de regressão;
- autorização/permissão existente foi relaxada sem requisito explícito;
- URL/parâmetro de retorno é usado sem validação/fallback canônico, quando aplicável;
- resposta/estado/efeito colateral exigido pelo slice ficou ausente;
- relatório temporário não foi criado no caminho exigido.
```

## Como escrever checks de inspeção

Use `rg` para contratos que modelos podem quebrar sem perceber:

- link ainda usa `target="_blank"`;
- `<embed>` desktop foi removido;
- rota errada foi usada;
- decorator de permissão sumiu;
- header exigido não aparece;
- helper de validação não foi chamado;
- texto/label crítico não está no template.

Modelo:

```markdown
## Checks de inspeção obrigatórios antes de concluir

Além dos testes automatizados, execute e cole o resultado/resumo no relatório:

```bash
rg -n "PADRAO_QUE_DEVE_EXISTIR|PADRAO_QUE_NAO_DEVE_EXISTIR" caminho/do/arquivo.html
rg -n "nome_da_view|decorator|helper|header" apps/app/views.py apps/app/urls.py
```

Interprete os resultados no relatório: explique quais ocorrências são esperadas, quais seriam erro, e confirme que nenhum contrato crítico ficou violado.
```

## Prompt final recomendado

No final do slice, incluir:

```text
Implement ONLY this slice. Follow the DeepSeek4-Flash protocol in this file: plan, RED real, GREEN mínimo, inspection checks, full quality gate and evidence report. If any required test/check/gate is missing or failing, report INCOMPLETE and do not update tasks.md or commit.
```

Depois acrescente o resumo específico do slice, por exemplo:

```text
Do not touch models, migrations, FSM or unrelated apps. Preserve existing permissions and add regression tests for old behavior that must remain. Run quality gate, update tasks.md only if all checks pass, create /tmp/<slice>-report.md, commit and push, reply with REPORT_PATH and stop.
```

## Template mínimo de relatório exigido

```markdown
# Relatório do slice

## Status
Status: COMPLETE | INCOMPLETE

## Matriz requisito → arquivo(s) → teste(s)
| Requisito | Arquivos | Testes/inspeções |
| --- | --- | --- |

## RED
- Comando:
- Testes falhando:
- Motivo esperado:

## GREEN
- Comandos:
- Resultado:

## Snippets antes/depois

## Checks de inspeção
- Comandos `rg` executados:
- Interpretação:

## Quality gate completo
- `uv run ruff check .`:
- `uv run ruff format --check .`:
- `uv run mypy .`:
- `uv run pytest`:

## Gates de autoavaliação

## Handoff para verificador
- Arquivos alterados:
- Comandos exatos para rerun:
- Riscos/limitações:
- Checklist R1..Rn:
```

## Checklist para revisar um slice já existente

Antes de considerar o slice pronto para DeepSeek4-Flash, verifique:

- [ ] Há requisitos numerados R1..Rn.
- [ ] Cada requisito tem teste esperado ou justificativa explícita.
- [ ] Há pelo menos um teste RED novo/ajustado.
- [ ] Há critérios de sucesso binários.
- [ ] Há condições de INCOMPLETO.
- [ ] Há comandos `rg` específicos para os contratos mais frágeis.
- [ ] O prompt final manda reportar INCOMPLETE se qualquer gate faltar/falhar.
- [ ] O relatório exige handoff para verificador.
- [ ] O slice proíbe escopo futuro e refactor amplo.
- [ ] O slice exige `tasks.md` somente após todos os gates.
