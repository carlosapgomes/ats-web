"""Forms for the doctor app."""

from typing import Any

from django import forms


class DoctorDecisionForm(forms.Form):
    """Formulário de decisão médica com validação condicional."""

    decision = forms.ChoiceField(
        choices=[("accept", "Aceitar"), ("deny", "Negar")],
    )
    support_flag = forms.ChoiceField(
        choices=[
            ("", "---"),
            ("none", "Nenhum"),
            ("anesthesist", "Anestesista"),
            ("anesthesist_icu", "Anestesista + UTI"),
        ],
        required=False,
    )
    admission_flow = forms.ChoiceField(
        choices=[
            ("", "---"),
            ("scheduled", "Agendamento"),
            ("immediate", "Vinda Imediata"),
        ],
        required=False,
    )
    reason = forms.CharField(widget=forms.Textarea, required=False)
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

    def clean(self) -> dict[str, Any]:
        cleaned: dict[str, Any] = super().clean() or {}
        decision: str = str(cleaned.get("decision", ""))
        support_flag: str = str(cleaned.get("support_flag", ""))
        admission_flow: str = str(cleaned.get("admission_flow", ""))
        reason: str = str(cleaned.get("reason", ""))

        if decision == "accept":
            if not support_flag:
                self.add_error("support_flag", "Selecione o tipo de suporte.")
            if not admission_flow:
                self.add_error("admission_flow", "Selecione o fluxo de admissão.")
        elif decision == "deny":
            if not reason:
                self.add_error("reason", "Informe o motivo da negativa.")

        return cleaned
