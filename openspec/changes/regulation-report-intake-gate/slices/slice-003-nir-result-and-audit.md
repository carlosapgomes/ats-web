# Slice 003 — Resultado NIR, auditoria e UX para documento inválido

## Objetivo

Garantir que documentos barrados pela barreira de relatório de regulação apareçam claramente para o NIR como revisão manual obrigatória, com auditoria suficiente e sem confusão com negativa médica/agendamento.

## Escopo

Arquivos previstos:

- `apps/intake/views.py`
- `templates/intake/case_detail.html`, se necessário
- `apps/intake/tests/test_case_detail.py`
- possivelmente `apps/cases/models.py` apenas se for necessário formalizar evento/constante; evitar se não necessário.

## Fora de Escopo

- Não alterar a regra do detector.
- Não alterar pipeline LLM.
- Não criar dashboard de documentos barrados.

## Critérios de Sucesso

- Caso com `suggested_action.reason_code == invalid_regulation_report` mostra badge de revisão manual obrigatória.
- Texto exibido ao NIR explica que o PDF não apresenta sinais mínimos de relatório de regulação.
- Botão de confirmação/cleanup continua disponível em `WAIT_R1_CLEANUP_THUMBS`.
- Caso barrado não aparece como agendamento confirmado nem como negativa médica.
- Tela de detalhe preserva acesso ao texto extraído para auditoria, quando houver.

## Gates de Autoavaliação

- [ ] UX não expõe texto clínico sensível em logs.
- [ ] `manual_review_required` genérico continua funcionando para `non_eda`/`unknown`.
- [ ] Nenhum fluxo médico/scheduler é impactado.
- [ ] Testes cobrem renderização do novo `reason_code`.

## Prompt para Implementador LLM

```text
Implemente somente o Slice 003 do change openspec/changes/regulation-report-intake-gate.
Leia AGENTS.md, PROJECT_CONTEXT.md, proposal.md, design.md e slices 001-002.
Use TDD em apps/intake/tests/test_case_detail.py para um Case em WAIT_R1_CLEANUP_THUMBS com suggested_action decision=manual_review_required e reason_code=invalid_regulation_report.
Garanta que a tela mostre revisão manual obrigatória, motivo claro sobre PDF fora do padrão de relatório de regulação, e botão de confirmar recebimento.
Não mexa no detector nem na task salvo bug óbvio descoberto pelo teste.
Rode testes focados e checks dos arquivos tocados.
Gere relatório em /tmp/ats-web-slice-003-nir-result-audit-report.md.
Commit/push e pare.
```

## Validação Recomendada

```bash
uv run pytest apps/intake/tests/test_case_detail.py -q
uv run ruff check apps/intake/views.py apps/intake/tests/test_case_detail.py
uv run ruff format --check apps/intake/views.py apps/intake/tests/test_case_detail.py
uv run mypy apps/intake/views.py apps/intake/tests/test_case_detail.py
```
