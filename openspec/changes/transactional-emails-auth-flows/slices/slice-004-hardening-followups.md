# Slice 004: Hardening futuro/opcional

## Status

- [ ] Pending / Optional

## Contexto zero para implementador

Slices 001-003 entregam os fluxos essenciais de email transacional. Este slice é opcional e só deve ser iniciado após teste realista em produção do branch `feat/transactional-emails-auth-flows` e confirmação explícita do usuário.

Leia antes de implementar:

- `AGENTS.md`
- `PROJECT_CONTEXT.md`
- `docs/adr/ADR-0002-emails-transacionais-autenticacao-cadastro.md`
- `openspec/changes/transactional-emails-auth-flows/proposal.md`
- `design.md`
- `tasks.md`
- relatórios dos slices 001-003

## Objetivo do slice

Endurecer ou ampliar os fluxos somente se o teste realista mostrar necessidade.

## Possíveis melhorias

Escolher apenas uma melhoria vertical por execução deste slice. Não implementar tudo de uma vez.

1. **Reenvio manual de convite**
   - ação admin para reenviar email de cadastro/reset;
   - permissões admin;
   - mensagem de sucesso/falha;
   - testes.

2. **Rate limit mais robusto**
   - limites ajustáveis por env var;
   - melhor separação IP/email;
   - logs sem expor dados sensíveis.

3. **Logs estruturados de email transacional**
   - logs de tentativa/sucesso/falha;
   - sem registrar tokens completos;
   - sem registrar senha ou segredo SMTP.

4. **Auditoria administrativa de convite**
   - se necessário, evento administrativo separado para “convite enviado”;
   - evitar poluir `CaseEvent`, que é para casos.

5. **Templates HTML/text refinados**
   - melhorar legibilidade;
   - manter texto puro como fallback;
   - não adicionar pipeline frontend.

6. **Envio assíncrono futuro**
   - avaliar `django-q2` apenas se latência SMTP atrapalhar;
   - preservar comportamento perceptível para admin.

7. **SES bounce/complaint tracking**
   - avaliar dependência/API específica somente se houver requisito operacional.

## Fora de escopo permanente salvo nova decisão

- Emails para notificações operacionais de casos.
- Framework JS.
- API REST.
- Envio de senha temporária por email.

## TDD obrigatório

Para qualquer melhoria escolhida:

1. escrever testes falhando que caracterizam o comportamento;
2. implementar o mínimo;
3. refatorar sem ampliar escopo;
4. atualizar este slice ou criar sub-slice dedicado, se o escopo crescer.

## Critérios de sucesso

- [ ] Apenas uma melhoria vertical foi escolhida e documentada.
- [ ] Testes cobrem comportamento novo.
- [ ] Nenhum token/senha/segredo aparece em logs/templates.
- [ ] Notificações operacionais seguem in-app.
- [ ] Quality gate do AGENTS.md passa.

## Gates de autoavaliação

Responder no relatório:

1. Qual problema real do teste em produção motivou o hardening?
2. Por que a melhoria escolhida não deveria esperar?
3. O escopo ficou vertical e pequeno?
4. Algum email operacional de caso foi introduzido? Deve ser não.
5. Há risco de vazamento de token/senha/segredo?

## Relatório final obrigatório

Criar markdown temporário com:

- motivação pós-teste realista;
- melhoria escolhida;
- arquivos alterados;
- snippets antes/depois;
- testes e gates;
- riscos remanescentes.

Atualizar `openspec/changes/transactional-emails-auth-flows/tasks.md` ao concluir.

Fazer commit e push para `origin feat/transactional-emails-auth-flows`.

Responder com:

```text
REPORT_PATH=<temp-markdown-path>
```

Parar e pedir confirmação para qualquer novo trabalho.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, ADR-0002, openspec/changes/transactional-emails-auth-flows/proposal.md, design.md, tasks.md, all completed slice reports and slices/slice-004-hardening-followups.md.
Implement ONLY one explicitly confirmed hardening improvement from Slice 004. Use TDD. Keep scope vertical and minimal. Do not introduce operational case emails, frontend frameworks, REST API, async email, bounce tracking or audit tables unless that exact sub-scope was explicitly confirmed.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update tasks.md, create a detailed temporary report, commit and push.
Return REPORT_PATH=<path> and stop.
```
