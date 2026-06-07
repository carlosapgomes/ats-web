# Relatório: Slice 002 — Prompt LLM1: não rastrear "Sem Exame" e datar todos os exames rastreados

## Resumo

Adicionadas instruções ao prompt renderizado do LLM1 para:
1. **Proibir** entradas de ausência de exame (Sem Exame, não realizado, etc.) em `tracked_exams`
2. **Exigir** `exam_datetime_iso` para **todo** exame rastreado quando houver data disponível

## Arquivos tocados

| Arquivo | Tipo de mudança |
|---------|----------------|
| `apps/pipeline/llm1_service.py` | Prompt instructions (R1, R2, R3) |
| `apps/pipeline/tests/test_llm1_service.py` | 3 novos testes |
| `apps/llm/tests/test_seed_prompts.py` | 1 novo teste |

## Mudanças no código

### 1. `apps/pipeline/llm1_service.py` — `_render_user_prompt()`

**Antes:**
```python
        "Marcar is_most_recent=true apenas para o mais recente de cada tipo.\n"
        "Para had_transfusion: resposta estritamente binaria (yes/no); "
```

**Depois:**
```python
        "Marcar is_most_recent=true apenas para o mais recente de cada tipo.\n"
        "Em tracked_exams, inclua apenas exames efetivamente realizados ou resultados "
        "disponiveis. Nao inclua entradas cujo resultado indique ausencia de exame, "
        "como 'Sem Exame', 'nao realizado', 'nao consta', 'ausente', 'sem laudo' ou "
        "equivalentes; use essas mencoes apenas como evidencia de ausencia em campos "
        "de pre-check quando aplicavel.\n"
        "Para todo exame incluido em tracked_exams, preencha exam_datetime_iso quando "
        "houver data/hora associada no laudo, nao apenas para o exame mais recente.\n"
        "Para had_transfusion: resposta estritamente binaria (yes/no); "
```

Isso implementa **R1** (proibir ausência) e **R2** (exigir data para todos os exames) no prompt renderizado final.

### 2. `apps/pipeline/llm1_service.py` — `LLM1_DEFAULT_USER_PROMPT`

**Antes:**
```python
        "Registrar had_transfusion como binario (yes/no); ausencia de "
        "evidencia de transfusao deve ser tratada como 'no'.\n\n"
        f"{LLM1_REQUIRED_SCHEMA_INSTRUCTIONS}"
```

**Depois:**
```python
        "Registrar had_transfusion como binario (yes/no); ausencia de "
        "evidencia de transfusao deve ser tratada como 'no'. "
        "Em tracked_exams, inclua apenas exames efetivamente realizados; "
        "nao inclua entradas com 'Sem Exame', 'nao realizado', 'nao consta', "
        "'ausente' ou equivalentes. "
        "Para todo exame em tracked_exams, preencha exam_datetime_iso quando "
        "houver data/hora associada.\n\n"
        f"{LLM1_REQUIRED_SCHEMA_INSTRUCTIONS}"
```

Isso implementa **R3** (versão curta no default para deploy greenfield).

### 3. `apps/pipeline/tests/test_llm1_service.py` — 3 novos testes

- `test_render_user_prompt_prohibits_absent_exam_entries_in_tracked_exams` — prova R1
- `test_render_user_prompt_requires_datetime_for_all_tracked_exams_when_available` — prova R2
- `test_default_user_prompt_prohibits_absent_exam_entries_and_requires_all_dates` — prova R3

### 4. `apps/llm/tests/test_seed_prompts.py` — 1 novo teste

- `test_llm1_user_seed_uses_updated_default_prompt_for_tracked_exam_hardening` — prova que `DEFAULT_CONTENTS["llm1_user"]` é `LLM1_DEFAULT_USER_PROMPT` e contém as regras de hardening

## Resultados do quality gate

| Comando | Resultado |
|---------|-----------|
| `ruff check .` | ✅ All checks passed |
| `ruff format --check .` | ✅ 145 files already formatted |
| `mypy .` | ✅ Success: no issues found in 157 source files |
| `pytest` | ✅ 1165 passed |

## Gates de autoavaliação

1. **A instrução de não incluir "Sem Exame" em `tracked_exams` fica no prompt renderizado mesmo se o template ativo no banco for antigo? Onde?**
   - Sim. A instrução está em `_render_user_prompt()`, que **sempre** adiciona as regras após o template (seja ele do banco ou default). Mesmo que o template no banco seja antigo, o rendered prompt conterá as novas regras.

2. **O default usado por deploy greenfield foi atualizado? Qual teste prova?**
   - Sim. `LLM1_DEFAULT_USER_PROMPT` foi atualizado. O teste `test_default_user_prompt_prohibits_absent_exam_entries_and_requires_all_dates` prova.

3. **O schema LLM1 foi alterado? Se sim, está errado.**
   - Não. Schema LLM1 permanece inalterado (schema_version 1.1).

4. **O LLM2 foi alterado? Se sim, está errado.**
   - Não. LLM2 não foi tocado.

5. **O comando `seed_prompts` continua sem sobrescrever prompts existentes?**
   - Sim. `seed_prompts` usa `if exists: skip; else: create`. O comando não foi alterado.

6. **Qual teste prova que `exam_datetime_iso` deve ser preenchido para todos os exames rastreados quando houver data?**
   - `test_render_user_prompt_requires_datetime_for_all_tracked_exams_when_available` em `test_llm1_service.py`.
