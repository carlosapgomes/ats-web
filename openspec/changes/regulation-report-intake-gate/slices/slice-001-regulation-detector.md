# Slice 001 — Detector determinístico de relatório de regulação

## Objetivo

Criar um detector puro e testável que classifica texto extraído como relatório de regulação ou não, sem tocar no fluxo assíncrono ainda.

## Escopo

Arquivos previstos:

- `apps/intake/regulation_gate.py` — novo utilitário.
- `apps/intake/tests/test_regulation_gate.py` — testes unitários com textos sintéticos/anonimizados.
- `config/settings/base.py` — settings dos thresholds, se necessário neste slice.

## Fora de Escopo

- Não integrar ainda em `execute_pdf_extraction()`.
- Não alterar FSM ou `CaseEvent`.
- Não usar PDFs reais como fixtures versionadas.

## Critérios de Sucesso

- Detector aceita texto com assinatura de regulação.
- Detector aceita relatório de regulação cujo `Motivo da Solicitação` seja colonoscopia, pois a barreira valida formato, não escopo EDA.
- Detector rejeita texto sintético de laudo ECG.
- Detector rejeita texto sintético de laboratório/hemograma.
- Detector rejeita texto curto ou vazio.
- Resultado retorna evidências não sensíveis: header encontrado, sinais institucionais, seções operacionais e tamanho do texto.

## Gates de Autoavaliação

- [ ] Sem dependência de banco.
- [ ] Sem dependência de LLM.
- [ ] Função determinística e idempotente.
- [ ] Normalização cobre acentos, caixa e whitespace.
- [ ] Testes não contêm dados reais identificáveis.

## Prompt para Implementador LLM

```text
Implemente somente o Slice 001 do change openspec/changes/regulation-report-intake-gate.
Leia AGENTS.md, PROJECT_CONTEXT.md, proposal.md e design.md.
Use TDD: primeiro crie testes em apps/intake/tests/test_regulation_gate.py para textos sintéticos de regulação, colonoscopia em relatório de regulação, ECG, laboratório e texto vazio/curto.
Depois crie apps/intake/regulation_gate.py com evaluate_regulation_report_text().
O resultado deve conter accepted, reason_code, reason_text, matched_header, matched_institutional_signals, matched_operational_sections e text_length.
Critério inicial: texto >= settings.INTAKE_REGULATION_MIN_TEXT_CHARS; header RELATÓRIO DE OCORRÊNCIAS; ao menos 1 sinal institucional; ao menos settings.INTAKE_REGULATION_MIN_OPERATIONAL_SECTIONS seções operacionais.
Não integre ainda na task de PDF.
Rode testes focados, ruff, mypy do arquivo novo.
Gere relatório em /tmp/ats-web-slice-001-regulation-detector-report.md.
Commit/push e pare.
```

## Validação Recomendada

```bash
uv run pytest apps/intake/tests/test_regulation_gate.py -q
uv run ruff check apps/intake/regulation_gate.py apps/intake/tests/test_regulation_gate.py config/settings/base.py
uv run ruff format --check apps/intake/regulation_gate.py apps/intake/tests/test_regulation_gate.py config/settings/base.py
uv run mypy apps/intake/regulation_gate.py apps/intake/tests/test_regulation_gate.py
```
