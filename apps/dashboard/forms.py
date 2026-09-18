"""Forms do dashboard — formulário de follow-up do supervisor (Slice 003)."""

from typing import Any

from django import forms

from apps.cases.models import (
    CURRENT_FOLLOWUP_NON_PERFORMANCE_REASON_CHOICES,
    FollowUpNonPerformanceReason,
)

RADIO_CLASS = "form-check-input"

REASON_PLACEHOLDER = "Selecione uma causa..."


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
    A causa é um ``select`` compacto com o catálogo oficial atual (design D4).
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
        choices=(("", REASON_PLACEHOLDER), *CURRENT_FOLLOWUP_NON_PERFORMANCE_REASON_CHOICES),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Causa da não realização",
        error_messages={"invalid_choice": "Selecione uma causa da lista oficial."},
    )
    other_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        label="Outra causa",
    )
    # Campo legado nunca renderizado (design D3): existe apenas para que um
    # ``resource_shortage_detail`` residual no POST chegue ao service, que é a
    # autoridade final da rejeição de submotivo em novas gravações.
    resource_shortage_detail = forms.CharField(required=False, widget=forms.HiddenInput())

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        if cleaned.get("performed") != "no":
            return cleaned
        if self.has_error("non_performance_reason"):
            return cleaned

        reason = str(cleaned.get("non_performance_reason") or "")
        other = str(cleaned.get("other_reason") or "").strip()

        if not reason:
            self.add_error("non_performance_reason", "Informe a causa do procedimento não realizado.")
            return cleaned
        if reason == FollowUpNonPerformanceReason.OTHER:
            if not other:
                self.add_error("other_reason", "Descreva a outra causa da não realização.")
        elif other:
            self.add_error(
                "other_reason",
                "Texto de outras causas só deve ser informado quando a causa é 'Outras causas'.",
            )
        return cleaned
