# Design: Clarificar UX de escrita na decisão médica

## Estado atual

O campo `doctor_observation` foi introduzido no change arquivado `openspec/archive/doctor-observation/` como observação médica opcional genérica.

### Modelo

`apps/cases/models.py::Case` já possui:

```python
doctor_observation = models.CharField(max_length=500, blank=True)

@property
def has_doctor_observation(self) -> bool:
    return bool(self.doctor_observation.strip())
```

Não há necessidade de migration para este change.

### Formulário médico

`apps/doctor/forms.py::DoctorDecisionForm` contém:

```python
observation = forms.CharField(
    required=False,
    max_length=500,
    widget=forms.Textarea(attrs={"rows": 2, "maxlength": 500}),
    label="Observação Médica",
    help_text="Visível para NIR, agendamento, supervisão e administração. Máx. 500 caracteres.",
)
```

A validação atual aceita observação tanto em `accept` quanto em `deny`.

### Submit médico

`apps/doctor/views.py::doctor_submit` persiste sempre:

```python
case.doctor_observation = form.cleaned_data.get("observation", "")
```

Isso permite gravar observação em uma negativa, criando sobreposição com `doctor_reason`.

### Template médico

`templates/doctor/decision.html` mostra o campo `Observação Médica` fora das seções condicionais de aceite/negativa, após o ID do caso. Assim o campo parece genérico para qualquer decisão.

O botão de saída é `Cancelar`, que pode soar como cancelamento do caso em vez de saída sem parecer.

### Templates downstream

Atualmente vários lugares renderizam `Observação Médica` ou badge `Obs. médica`:

- `templates/intake/_my_cases_content.html`
- `templates/intake/case_detail.html`
- `templates/scheduler/_queue_content.html`
- `templates/scheduler/confirm.html`
- `templates/scheduler/confirm_post_schedule_issue.html`
- testes relacionados em `apps/intake/tests/`, `apps/scheduler/tests/`, `apps/dashboard/tests/`

## Decisões

### D1. Não renomear coluna/model field

Manter `Case.doctor_observation`.

Motivos:

- mudança é semântica/UX, não estrutural;
- evita migration desnecessária;
- preserva compatibilidade com código e dados existentes;
- reduz risco do slice.

A nomenclatura externa ao usuário deve mudar; a nomenclatura interna pode permanecer por enquanto.

### D2. Nova semântica operacional

Definir explicitamente:

- `doctor_reason`: motivo de negativa.
- `doctor_observation`: **orientações médicas para agendamento/execução**, usadas quando o caso é aceito.
- comunicação operacional: mensagens entre equipes, pedido de complemento, aviso e coordenação.

### D3. Campo de orientação pertence ao aceite

No template médico, mover/renderizar o campo de orientação dentro da seção `accept-section`, abaixo de suporte/fluxo.

Label recomendado:

```text
Orientações para agendamento/execução
```

Help text recomendado:

```text
Opcional. Use para orientações que devem acompanhar o aceite, como suporte, preparo, prioridade ou cuidados no agendamento/execução. Para pedir documentos ou avisar outra equipe, use a comunicação operacional. Máx. 500 caracteres.
```

Placeholder recomendado:

```text
Ex.: priorizar por anemia; agendar com anestesia; paciente deve trazer exames recentes...
```

### D4. Negativa não deve persistir orientação

Em `doctor_submit`, persistir orientação apenas no aceite:

```python
if decision == "accept":
    case.doctor_observation = form.cleaned_data.get("observation", "").strip()
else:
    case.doctor_observation = ""
```

Motivos:

- evita duplicidade com `doctor_reason`;
- deixa a regra auditável via teste;
- impede POST manual com `observation` em negativa de gerar ambiguidade.

Observação: não é necessário invalidar o POST de negativa com `observation`; basta ignorar/limpar no submit. Isso é mais compatível com formulários antigos e menos disruptivo.

### D5. Validação de 500 caracteres permanece

Manter `max_length=500`. Mesmo que a observação seja ignorada em negativa, a validação de tamanho pode permanecer no form para simplicidade e consistência.

Não ampliar limite neste change.

### D6. Botão `Cancelar` vira `Voltar sem decidir`

Na tela de decisão médica, alterar apenas o label do link de retorno:

```text
Voltar sem decidir
```

Não alterar rota, lock release JS, nem comportamento do link neste change.

### D7. Incluir microcopy sobre comunicação operacional

Adicionar texto de ajuda próximo ao formulário de decisão, preferencialmente como alerta discreto:

```text
Se faltam documentos ou dados para decidir, envie uma mensagem na Comunicação operacional marcando o NIR e volte sem decidir. Não use negativa apenas para solicitar complemento.
```

Não implementar automação ou link âncora obrigatório. Se houver âncora simples para a thread sem ampliar escopo, é aceitável.

### D8. Downstream deve falar em orientação, não observação

Em telas downstream, mudar labels visíveis para usuário:

- badge: `📝 Orientação médica`
- bloco/card: `📝 Orientações médicas`

Não alterar lógica de `has_doctor_observation`, queries ou dados.

### D9. Compatibilidade com dados legados

Casos antigos podem ter `doctor_observation` preenchido mesmo em negativas. Slice 002 deve apenas renomear labels; não deve apagar nem migrar dados antigos.

A regra de limpeza aplica-se a novas submissões após o Slice 001.

## Plano de slices

### Slice 001 — Decisão médica sem ambiguidade

Arquivos previstos:

| Arquivo | Mudança |
|---|---|
| `apps/doctor/forms.py` | label/help_text/placeholder/widget coerentes com orientação de aceite |
| `templates/doctor/decision.html` | mover campo para seção de aceite; microcopy; `Cancelar` → `Voltar sem decidir` |
| `apps/doctor/views.py` | persistir orientação só em aceite; limpar em negativa |
| `apps/doctor/tests/test_views.py` | testes TDD de form/template/submit |

Não deve tocar modelos nem migrations.

### Slice 002 — Labels downstream alinhados

Arquivos previstos:

| Arquivo | Mudança |
|---|---|
| `templates/intake/_my_cases_content.html` | badge `Orientação médica` |
| `templates/intake/case_detail.html` | card `Orientações médicas` |
| `templates/scheduler/_queue_content.html` | badge/texto `Orientação médica` |
| `templates/scheduler/confirm.html` | label `Orientações médicas` |
| `templates/scheduler/confirm_post_schedule_issue.html` | label `Orientações médicas` |
| testes existentes | atualizar asserts para nova nomenclatura |

Se algum template adicional mostrar `Observação Médica`, incluir no mesmo slice somente se encontrado por busca (`rg`).

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Médico continuar usando negativa para pedir documento | Microcopy explícito orientando comunicação operacional |
| Médico escrever mensagem operacional no campo de aceite | Label/help text restringem a finalidade |
| POST manual preencher observação em negativa | Submit limpa/ignora quando `decision == "deny"` |
| Dados antigos de negativas com observação sumirem | Não migrar nem apagar dados antigos; só novas submissões limpam |
| Slice tocar arquivos demais | Separar entrada médica e downstream em 2 slices |
| Testes frágeis por HTML | Assert por textos-chave e persistência, não por estrutura extensa |

## Rollback

Como não há migration prevista:

1. Reverter alteração de `apps/doctor/forms.py`, `apps/doctor/views.py` e templates.
2. Reverter testes.
3. Dados existentes permanecem intactos.

Se a limpeza de observação em negativa for considerada disruptiva depois, pode ser revertida isoladamente no submit médico.
