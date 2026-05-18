# Design: Alinhar Contrato LLM e Roteamento NIR → Médico ao Legado

## D1. Nomes canônicos de prompts

Usar exatamente os nomes legados em todo o Django:

- `llm1_system`
- `llm1_user`
- `llm2_system`
- `llm2_user`

O orchestrator e os services devem buscar esses nomes. O admin UI já expõe esses nomes; o seed atual deve ser corrigido.

## D2. Defaults e renderização de prompts

Portar do legado:

- conteúdo default dos prompts ativos mais recentes;
- instruções adicionais montadas no `_render_user_prompt()` de LLM1 e LLM2.

Os prompts do banco são a fonte primária. Fallbacks de código existem para segurança operacional quando o banco não estiver semeado.

## D3. Validação Pydantic v2

Adicionar dependência explícita `pydantic>=2` em `pyproject.toml`.

Criar schemas Django equivalentes aos DTOs legados, preferencialmente em:

```text
apps/pipeline/schemas.py
```

ou, se ficar grande demais, dividir em:

```text
apps/pipeline/schemas/llm1.py
apps/pipeline/schemas/llm2.py
```

A validação deve ser literal o suficiente para preservar:

- `extra="forbid"`;
- `schema_version == "1.1"`;
- enums do legado;
- validações de consistência pediátrica e subtipo EDA;
- `model_dump(mode="json")` para persistência.

## D4. Auditoria via CaseEvent

Não criar tabela nova de interações LLM neste change.

Eventos devem cobrir:

- sucesso de LLM1 com nomes/versões dos prompts;
- falha de LLM1 com erro resumido;
- sucesso de LLM2 com nomes/versões dos prompts e `suggestion`;
- falha de LLM2 com erro resumido;
- scope gate manual review;
- envio para médico.

## D5. Scope gate web

No legado, `non_eda`/`unknown`:

- persiste `suggested_action` com `manual_review_required`;
- registra `EDA_SCOPE_GATED_MANUAL_REVIEW`;
- não chama LLM2;
- não envia para Room 2;
- envia resultado final ao NIR.

No Django, o equivalente aprovado é:

```text
LLM_STRUCT → WAIT_R1_CLEANUP_THUMBS
```

com `suggested_action` contendo `manual_review_required` e dados suficientes para o NIR ver resultado de revisão manual.

Não criar fila médica para esses casos.

## D6. Presenter médico equivalente ao legado

Criar presenter Django para gerar uma estrutura de dados com os 7 blocos legados:

1. Resumo clínico
2. Achados críticos
3. Pendências críticas
4. Decisão sugerida
5. Suporte recomendado
6. ASA estimado
7. Motivo objetivo

Também incluir contexto equivalente:

- procedimento solicitado canônico;
- origem;
- transfusão;
- exames rastreados;
- marcador pediátrico;
- histórico de negativa recente, quando existir.

O presenter deve evitar dependência de Matrix/Room. O template médico renderiza essa estrutura. Uma saída texto/markdown pode ser usada em testes para comparar blocos e facilitar auditoria.

## D7. Controle de acesso médico

Aplicar `@role_required("doctor")` às views médicas:

- `doctor_queue`
- `doctor_decision`
- `doctor_submit`

Adicionar testes garantindo bloqueio para papel ativo não médico.

## Plano de Slices

1. `slice-001-canonical-prompts.md` — nomes canônicos, seed e fallback de prompts.
2. `slice-002-llm1-pydantic-contract.md` — schema e service LLM1 alinhados ao legado.
3. `slice-003-llm2-pydantic-contract.md` — schema e service LLM2 alinhados ao legado.
4. `slice-004-scope-gate-nir-final.md` — `non_eda`/`unknown` direto ao NIR.
5. `slice-005-doctor-report-presenter.md` — relatório médico em 7 blocos equivalente ao legado.
6. `slice-006-doctor-role-guard.md` — autorização por papel ativo `doctor`.
7. `slice-007-quality-docs-closeout.md` — quality gate, documentação e relatório final.

## Gates Globais

Ao final do change:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

Cada slice deve executar testes focados e registrar relatório markdown com snippets antes/depois.
