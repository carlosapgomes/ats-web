"""Forms for the scheduler app."""

from typing import Any

from django import forms


class SchedulerDecisionForm(forms.Form):
    """Formulário de decisão do scheduler com validação condicional."""

    decision = forms.ChoiceField(
        choices=[("confirm", "Confirmar"), ("deny", "Negar")],
    )
    appointment_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    appointment_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={"type": "time"}),
    )
    notes = forms.CharField(widget=forms.Textarea, required=False)
    reason = forms.CharField(widget=forms.Textarea, required=False)

    def clean(self) -> dict[str, Any]:
        cleaned: dict[str, Any] = super().clean() or {}
        decision: str = str(cleaned.get("decision", ""))
        appointment_date = cleaned.get("appointment_date")
        appointment_time = cleaned.get("appointment_time")
        reason: str = str(cleaned.get("reason", ""))

        if decision == "confirm":
            if not appointment_date:
                self.add_error("appointment_date", "Informe a data do agendamento.")
            if not appointment_time:
                self.add_error("appointment_time", "Informe o horário do agendamento.")
        elif decision == "deny":
            if not reason:
                self.add_error("reason", "Informe o motivo da negativa.")

        return cleaned
