# Relatório Slice 001 — Decisão médica sem ambiguidade

## Resumo

Implementada a vertical de mudança na UX de decisão médica: o campo genérico
"Observação Médica" foi renomeado para "Orientações para agendamento/execução",
movido para dentro da seção de aceite, e a view agora só persiste o campo em
decisões `accept`. Na negativa, o campo é ignorado/limpo. Adicionada microcopy
orientando médico a usar comunicação operacional para pedidos de documentos.
Botão "Cancelar" renomeado para "Voltar sem decidir".

## Arquivos tocados

| Arquivo | Tipo de mudança |
|---|---|
| `apps/doctor/forms.py` | Label, help_text, placeholder do campo observation |
| `apps/doctor/views.py` | Lógica condicional de persistência (accept vs deny) |
| `templates/doctor/decision.html` | Campo movido p/ accept-section, microcopy adicionada, botão renomeado |
| `apps/doctor/tests/test_views.py` | 3 testes novos, 2 substituídos, 1 adicionado |

## Snippets antes/depois

### forms.py — Antes
```python
observation = forms.CharField(
    required=False,
    max_length=500,
    widget=forms.Textarea(attrs={"rows": 2, "maxlength": 500}),
    label="Observação Médica",
    help_text="Visível para NIR, agendamento, supervisão e administração. Máx. 500 caracteres.",
)
```

### forms.py — Depois
```python
observation = forms.CharField(
    required=False,
    max_length=500,
    widget=forms.Textarea(
        attrs={
            "rows": 2,
            "maxlength": 500,
            "placeholder": "Ex.: priorizar por anemia; agendar com anestesia; paciente deve trazer exames recentes...",
        }
    ),
    label="Orientações para agendamento/execução",
    help_text="Opcional. Use para orientações que devem acompanhar o aceite, como suporte, preparo, prioridade ou cuidados no agendamento/execução. Para pedir documentos ou avisar outra equipe, use a comunicação operacional. Máx. 500 caracteres.",
)
```

### views.py — Antes
```python
case.doctor_observation = form.cleaned_data.get("observation", "")
```

### views.py — Depois
```python
if decision == "accept":
    case.doctor_observation = form.cleaned_data.get("observation", "").strip()
else:
    case.doctor_observation = ""
```

### decision.html — Antes (observação genérica fora das seções)
```html
<div class="mb-4">
  <label for="doctor-observation" class="form-label">{{ form.observation.label }}</label>
  <textarea ... placeholder="Informações adicionais sobre o caso...">...</textarea>
  <div class="form-text">{{ form.observation.help_text }}</div>
</div>
```

### decision.html — Depois (dentro de `#accept-section`, após `.row.g-3`)
```html
<div class="mb-3">
  <label for="doctor-observation" class="form-label">{{ form.observation.label }}</label>
  <textarea ... placeholder="{{ form.observation.field.widget.attrs.placeholder }}">...</textarea>
  {% if form.observation.errors %}<div class="invalid-feedback d-block">...{% endif %}
  <div class="form-text">{{ form.observation.help_text }}</div>
</div>
```

### decision.html — Antes (microcopy ausente, botão "Cancelar")
```html
<a href="{% url 'doctor:queue' %}" class="btn btn-outline-secondary btn-lg">Cancelar</a>
```

### decision.html — Depois (microcopy presente, botão "Voltar sem decidir")
```html
<div class="alert alert-info small mb-4 py-2" role="alert">
  💬 <strong>Precisa de mais informações?</strong>
  Se faltam documentos ou dados para decidir, envie uma mensagem na
  <strong>Comunicação operacional</strong> marcando o <strong>NIR</strong>
  e <strong>volte sem decidir</strong>.
  Não use negativa apenas para solicitar complemento.
</div>
...
<a href="{% url 'doctor:queue' %}" class="btn btn-outline-secondary btn-lg">Voltar sem decidir</a>
```

## Evidência TDD

### RED (antes da implementação): 4 testes falhando, 1 passando

| Teste | Resultado RED |
|---|---|
| `test_decision_form_uses_acceptance_orientation_label` | ❌ "Orientações para agendamento/execução" não encontrado |
| `test_decision_page_guides_missing_documents_to_operational_communication` | ❌ Microcopy ausente |
| `test_decision_page_cancel_link_says_back_without_deciding` | ❌ "Voltar sem decidir" não encontrado |
| `test_submit_deny_with_observation_ignores_orientation` | ❌ observation ainda persistia em deny |
| `test_submit_accept_strips_orientation_whitespace` | ✅ Django já faz strip |

### GREEN (após implementação): 5 passando

| Teste | Resultado GREEN |
|---|---|
| `test_decision_form_uses_acceptance_orientation_label` | ✅ |
| `test_decision_page_guides_missing_documents_to_operational_communication` | ✅ |
| `test_decision_page_cancel_link_says_back_without_deciding` | ✅ |
| `test_submit_deny_with_observation_ignores_orientation` | ✅ |
| `test_submit_accept_strips_orientation_whitespace` | ✅ |

Suite completa do app doctor: **176 passed**.

## Quality Gate

| Comando | Resultado |
|---|---|
| `ruff check .` | All checks passed ✅ |
| `ruff format --check .` | 165 files already formatted ✅ |
| `mypy .` | Success: no issues found ✅ |
| `pytest` | 1504 passed ✅ |

## Respostas aos Gates de Autoavaliação

1. **A tela médica ainda mostra "Observação Médica"?**
   Não. O label agora é "Orientações para agendamento/execução". O texto "Observação Médica" não aparece em nenhum lugar da tela de decisão médica.

2. **O campo de orientação fica visualmente dentro/associado ao aceite? Onde?**
   Sim. O `<textarea>` está dentro do `<div id="accept-section">`, após o `.row.g-3` com support_flag e admission_flow.

3. **A negativa consegue persistir `doctor_observation` via POST manual? Qual teste prova que não?**
   Não. A view condiciona a persistência a `decision == "accept"`. Em deny, define como `""`.
   Teste: `test_submit_deny_with_observation_ignores_orientation`.

4. **O médico recebe orientação clara para pedir documento via comunicação operacional? Onde?**
   Sim. Um `alert alert-info` acima do botão de submit com texto explícito sobre comunicação operacional com NIR e "volte sem decidir".

5. **O botão "Cancelar" da decisão médica foi substituído por "Voltar sem decidir" sem mudar comportamento?**
   Sim. Apenas o texto do link foi alterado; a URL (`{% url 'doctor:queue' %}`) e o comportamento permanecem idênticos.

6. **Alguma migration foi criada?**
   Não. Nenhuma migration foi criada ou alterada.

7. **Quais testes foram adicionados/alterados e quais comportamentos protegem?**
   - `test_decision_form_uses_acceptance_orientation_label`: protege label correto e ausência de "Observação Médica"
   - `test_decision_page_guides_missing_documents_to_operational_communication`: protege microcopy
   - `test_decision_page_cancel_link_says_back_without_deciding`: protege "Voltar sem decidir" no form actions
   - `test_submit_deny_with_observation_ignores_orientation` (substitui `test_submit_deny_with_observation_persists`): protege que deny não persiste orientation
   - `test_submit_accept_strips_orientation_whitespace`: protege `.strip()` no accept
   - `test_submit_accept_with_observation_persists`: atualizado com texto realista de orientação

## Riscos/Observações para o Próximo Slice

- Nenhum dado foi migrado; casos antigos com `doctor_observation` preenchido em negativas mantêm o dado.
- Slice 002 deve renomear labels downstream (`templates/intake/`, `templates/scheduler/`) sem alterar lógica de dados.
- Verificar se há outros templates que exibem "Observação Médica" usando `rg` antes do Slice 002.
