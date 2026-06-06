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


class PostScheduleIssueForm(forms.Form):
    """Formulário de resolução de intercorrência pós-agendamento.

    Ações: cancel | reschedule | maintain | deny
    """

    psi_action = forms.ChoiceField(
        choices=[
            ("cancel", "Cancelar agendamento"),
            ("reschedule", "Reagendar"),
            ("maintain", "Manter agendamento"),
            ("deny", "Negar solicitação"),
        ],
        label="Ação",
    )
    psi_response_message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        label="Mensagem do agendador",
    )
    psi_appointment_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Nova data",
    )
    psi_appointment_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={"type": "time"}),
        label="Novo horário",
    )
    psi_appointment_location = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ex: Hospital Central - Sala 2"}),
        label="Local",
    )
    psi_appointment_instructions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Instruções adicionais..."}),
        label="Instruções",
    )

    def clean(self) -> dict[str, Any]:
        cleaned: dict[str, Any] = super().clean() or {}
        action: str = str(cleaned.get("psi_action", ""))

        # Fix: template has three <textarea name="psi_response_message"> (one per
        # section). Browsers send all values; Django uses the last one (empty
        # maintain section), silently discarding what the user typed in the
        # visible cancel/deny section. We recover the first non-empty value here
        # as defense-in-depth (the primary fix is client-side JS).
        raw_messages: list[str] = (
            self.data.getlist("psi_response_message")
            if hasattr(self.data, "getlist")
            else [str(self.data.get("psi_response_message", ""))]
        )
        response_message: str = ""
        for msg in raw_messages:
            if msg.strip():
                response_message = msg
                break
        cleaned["psi_response_message"] = response_message

        appt_date = cleaned.get("psi_appointment_date")
        appt_time = cleaned.get("psi_appointment_time")

        # Response message required for cancel and deny
        if action in ("cancel", "deny") and not response_message.strip():
            self.add_error("psi_response_message", "Mensagem é obrigatória para esta ação.")

        # Date/time required for reschedule
        if action == "reschedule":
            if not appt_date:
                self.add_error("psi_appointment_date", "Informe a nova data do agendamento.")
            if not appt_time:
                self.add_error("psi_appointment_time", "Informe o novo horário do agendamento.")

        return cleaned
