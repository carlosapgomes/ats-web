# Design: Labels de motivos de intercorrência pós-agendamento

## Decisão

Manter códigos internos em inglês no banco e traduzir apenas na camada de
apresentação.

Os códigos são úteis como valores canônicos estáveis:

```text
death
clinical_condition
transport_unavailable
external_regulation
reschedule_request
other
```

A UI deve sempre exibir labels em português:

```text
Paciente faleceu
Paciente sem condição clínica de transporte
Transporte indisponível pela unidade de origem
Exame realizado pela regulação estadual em outro serviço
Solicitação de reagendamento pela unidade de origem
Outro
```

## Fonte única

Preferir criar uma fonte única reutilizável perto do domínio, por exemplo em
`apps/cases/services.py` ou em módulo pequeno de constantes do app `cases`.

Sugestão simples:

```python
POST_SCHEDULE_ISSUE_REASON_LABELS = {
    "death": "Paciente faleceu",
    "clinical_condition": "Paciente sem condição clínica de transporte",
    "transport_unavailable": "Transporte indisponível pela unidade de origem",
    "external_regulation": "Exame realizado pela regulação estadual em outro serviço",
    "reschedule_request": "Solicitação de reagendamento pela unidade de origem",
    "other": "Outro",
}


def get_post_schedule_issue_reason_label(reason: str) -> str:
    return POST_SCHEDULE_ISSUE_REASON_LABELS.get(reason, reason)
```

Se já existir constante equivalente em `apps/intake/forms.py`, avaliar mover ou
reexportar para evitar duplicação. Evitar migration se não houver necessidade.

## Pontos de uso esperados

### Scheduler queue

`apps/scheduler/views.py::_build_case_card` deve enviar algo como:

```text
post_schedule_issue_reason_label
```

`templates/scheduler/_queue_content.html` deve renderizar a label, não o código.

### Scheduler confirm

`apps/scheduler/views.py::_build_confirm_context` deve enviar algo como:

```text
ps_issue_reason_label
```

`templates/scheduler/confirm_post_schedule_issue.html` deve renderizar a label,
não o código.

### Intake detail

`apps/intake/views.py` já possui mapeamento local para `result_info`. Trocar para
usar a fonte única se isso for simples e seguro.

## Testes esperados

- Fila scheduler com intercorrência `death` mostra `Paciente faleceu` e não
  mostra `death` na área de motivo.
- Tela scheduler de resolver intercorrência `death` mostra `Paciente faleceu` e
  não mostra `death` na área de motivo.
- Cobrir ao menos um motivo com mensagem obrigatória, por exemplo
  `reschedule_request`, para garantir que label e mensagem aparecem juntos.
- Detalhe NIR de intercorrência respondida continua mostrando label em
  português.

## Riscos

| Risco | Mitigação |
| --- | --- |
| Trocar valor persistido em vez de só label | Não alterar campos nem migrations |
| Deixar mapeamentos duplicados divergirem | Centralizar labels em um único helper/constante |
| Teste falso positivo por código aparecer em HTML técnico | Fazer assert focado no bloco visível ou contexto renderizado |
