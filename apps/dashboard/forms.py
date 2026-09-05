"""Forms do dashboard — formulário de follow-up do supervisor (Slice 003)."""

from typing import Any

from django import forms

from apps.cases.models import (
    FollowUpNonPerformanceReason,
    FollowUpResourceShortageDetail,
)

RADIO_CLASS = "form-check-input"


class FollowUpAdmissionForm(forms.Form):
    """Internação no nível do caso — sempre informada (design D2/D6)."""

    patient_admitted = forms.ChoiceField(
        choices=(("no", "Não foi internado"), ("yes", "Foi internado")),
        widget=forms.RadioSelect(attrs={"class": RADIO_CLASS}),
        label="O paciente foi internado?",
        error_messages={"required": "Informe se o paciente foi internado."},
    )


class FollowUpForm(forms.Form):
    """Bloco de desfecho de um procedimento do caso (design D2/D6).

    Uma instância por ``CaseProcedure``, instanciada com
    ``prefix="proc_<id>"``: os campos chegam no POST como
    ``proc_<id>-performed``, ``proc_<id>-non_performance_reason`` etc.
    As regras condicionais de causa espelham o service
    (``record_case_follow_up``) para feedback por campo; o service permanece
    a validação autoritativa do contrato.
    """

    performed = forms.ChoiceField(
        choices=(("yes", "Realizado"), ("no", "Não realizado")),
        widget=forms.RadioSelect(attrs={"class": RADIO_CLASS}),
        label="Procedimento realizado?",
        error_messages={"required": "Informe se o procedimento foi realizado."},
    )
    non_performance_reason = forms.ChoiceField(
        choices=FollowUpNonPerformanceReason.choices,
        required=False,
        widget=forms.RadioSelect(attrs={"class": RADIO_CLASS}),
        label="Causa da não realização",
    )
    resource_shortage_detail = forms.ChoiceField(
        choices=FollowUpResourceShortageDetail.choices,
        required=False,
        widget=forms.RadioSelect(attrs={"class": RADIO_CLASS}),
        label="Submotivo da falta de recursos",
    )
    other_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        label="Outra causa",
    )

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        if cleaned.get("performed") != "no":
            return cleaned

        reason = str(cleaned.get("non_performance_reason") or "")
        detail = str(cleaned.get("resource_shortage_detail") or "")
        other = str(cleaned.get("other_reason") or "").strip()

        if not reason:
            self.add_error("non_performance_reason", "Informe a causa do procedimento não realizado.")
            return cleaned
        if reason == FollowUpNonPerformanceReason.RESOURCE_SHORTAGE:
            if not detail:
                self.add_error("resource_shortage_detail", "Informe o submotivo da falta de recursos.")
        elif detail:
            self.add_error(
                "resource_shortage_detail",
                "Submotivo só deve ser informado quando a causa é falta de recursos.",
            )
        if reason == FollowUpNonPerformanceReason.OTHER:
            if not other:
                self.add_error("other_reason", "Descreva a outra causa da não realização.")
        elif other:
            self.add_error(
                "other_reason",
                "Texto de outras causas só deve ser informado quando a causa é 'Outras causas'.",
            )
        return cleaned
