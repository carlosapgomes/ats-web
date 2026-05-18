# Slice 005 — Presenter Médico em 7 Blocos

## Handoff para Implementador LLM

Leia os artefatos do change e confirme que os slices 001 a 004 estão aplicados.

Implemente somente este slice.

## Problema

A tela médica atual mostra resumo simples, badges e JSON. O legado apresentava um relatório técnico otimizado com feedback médico real, organizado em 7 blocos.

## Objetivo

Criar um presenter Django sem dependência Matrix/Room que gere relatório equivalente ao legado para a tela de decisão médica.

## Fonte Legada

Use como referência principal:

- `/home/carlos/projects/augmented-triage-system/src/triage_automation/infrastructure/matrix/message_templates.py`

Funções relevantes:

- `build_room2_case_summary_message`
- `build_room2_case_summary_formatted_html`
- helpers `_build_room2_*`

Não copie nomenclatura Room/Matrix para a API pública do presenter Django.

## Escopo Preferencial

Arquivos prováveis:

- `apps/doctor/presenters.py` ou `apps/doctor/report_presenter.py`
- `apps/doctor/views.py`
- `templates/doctor/decision.html`
- `apps/doctor/tests/test_views.py`
- novo `apps/doctor/tests/test_presenter.py`, se útil

## Requisitos Funcionais

O presenter deve gerar estrutura com estes blocos:

1. `Resumo clínico`
2. `Achados críticos`
3. `Pendências críticas`
4. `Decisão sugerida`
5. `Suporte recomendado`
6. `ASA estimado`
7. `Motivo objetivo`

Também deve incluir contexto equivalente ao legado:

- procedimento solicitado canônico;
- origem;
- relato de transfusão;
- exames rastreados;
- marcador pediátrico;
- histórico de negativa recente, quando existir.

O template deve renderizar essa estrutura de forma legível, mantendo Bootstrap/tema atual.

Uma função auxiliar de texto/markdown pode existir para testes e auditoria, desde que não acople a Matrix.

## TDD — Testes RED Esperados

1. Presenter com payload completo gera os 7 blocos.
2. Procedimento canônico resolve:
   - `standard` → EDA;
   - `gastrostomy` → EDA para gastrostomia;
   - `esophageal_dilation` → EDA para dilatação esofágica;
   - `foreign_body` → EDA para retirada de corpo estranho.
3. Origem, transfusão, exames rastreados e pediatria aparecem quando presentes.
4. Decision page renderiza os títulos dos 7 blocos.
5. JSON completo pode continuar como detalhe colapsável, mas não deve ser o relatório principal.

## Critérios de Sucesso

- Médico vê relatório equivalente ao legado antes do formulário.
- Presenter é coeso, testável e sem dependência Matrix.
- Template não contém regra clínica complexa; lógica fica no presenter.

## Comandos de Validação Focados

```bash
uv run pytest apps/doctor/tests -q
uv run ruff check apps/doctor templates/doctor
uv run mypy apps/doctor
```

## Relatório Obrigatório

Crie:

```text
/tmp/ats-web-slice-005-doctor-report-presenter-report.md
```

Inclua comparação entre blocos legados e blocos Django.

Responda com:

```text
REPORT_PATH=/tmp/ats-web-slice-005-doctor-report-presenter-report.md
```

## Stop Rule

Não implemente role guard neste slice, exceto se estritamente necessário para testes existentes.
