"""Forms for the doctor app."""

from typing import Any

from django import forms

from apps.cases.admission import ADMISSION_FLOW_CHOICES, SUPPORT_FLAG_CHOICES
from apps.cases.models import Case, DetectionStatus, DoctorDisposition, ProcedureType


class DoctorDecisionForm(forms.Form):
    """Formulário de decisão médica com validação condicional.

    Dois modos (Slice 003, design D9/ADR-0004):

    - **v2 (procedures)**: caso com ``structured_data.schema_version == 2.0`` —
      decisão por componente ``procedure_<type>`` + razão
      ``procedure_<type>_reason``; o campo global ``decision`` é derivado pelo
      serviço (zero aprovados → ``deny``; ≥1 aprovado → ``accept``); suporte e
      fluxo de admissão continuam obrigatórios quando houver aceite.
    - **legado 1.1**: comportamento anterior preservado (``decision`` global,
      ``reason`` global no deny, suporte/fluxo no accept).

    A validação é por componente e fail-closed (R1/R2): todo procedimento
    detectado exige disposição; negado exige razão própria; aprovado não
    detectado exige justificativa de inclusão própria; erro em qualquer
    componente invalida o formulário inteiro — nada é persistido.
    """

    decision = forms.ChoiceField(
        choices=[("accept", "Aceitar"), ("deny", "Negar")],
        required=False,
    )
    support_flag = forms.ChoiceField(
        choices=SUPPORT_FLAG_CHOICES,
        required=False,
    )
    admission_flow = forms.ChoiceField(
        choices=ADMISSION_FLOW_CHOICES,
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
        help_text="Opcional · Máx. 500 caracteres. Para pedir documentos, use Comunicação operacional.",
    )

    # ── Campos por procedimento (modo v2) ───────────────────────────────
    procedure_eda = forms.ChoiceField(
        choices=[("", "---"), ("approved", "Aprovar"), ("denied", "Negar")],
        required=False,
    )
    procedure_eda_reason = forms.CharField(widget=forms.Textarea, required=False)
    procedure_colonoscopy = forms.ChoiceField(
        choices=[("", "---"), ("approved", "Aprovar"), ("denied", "Negar")],
        required=False,
    )
    procedure_colonoscopy_reason = forms.CharField(widget=forms.Textarea, required=False)

    def __init__(self, *args: Any, case: Case | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.case = case
        # Modo v2: a decisão global é derivada das disposições por componente
        # (R4); o campo global só é exigido no modo legado 1.1.
        if self.is_v2_mode:
            self.fields["decision"].required = False

    @property
    def is_v2_mode(self) -> bool:
        """True quando o caso usa o contrato 2.0 (decisão por procedimento)."""
        if self.case is None:
            return False
        structured = self.case.structured_data
        return isinstance(structured, dict) and structured.get("schema_version") == "2.0"

    def _detected_procedure_types(self) -> set[str]:
        """Conjunto de procedimentos detectados a partir das rows do caso."""
        if self.case is None:
            return set()
        return {
            row.procedure_type for row in self.case.procedures.all() if row.detection_status == DetectionStatus.DETECTED
        }

    def clean(self) -> dict[str, Any]:
        cleaned: dict[str, Any] = super().clean() or {}
        if not self.is_v2_mode:
            return self._clean_legacy(cleaned)
        return self._clean_procedure_mode(cleaned)

    def _clean_legacy(self, cleaned: dict[str, Any]) -> dict[str, Any]:
        """Modo 1.1: decisão global com validação condicional anterior."""
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

    def _clean_procedure_mode(self, cleaned: dict[str, Any]) -> dict[str, Any]:
        """Modo 2.0: validação por componente, fail-closed (R1/R2/D9).

        - todo procedimento detectado exige disposição (approved|denied);
        - negado exige razão específica do componente;
        - aprovado sem ter sido detectado (inclusão) exige justificativa;
        - troca completa exige razão em ambas as rows afetadas;
        - pelo menos um aprovado exige suporte + fluxo de admissão;
        - disposição ``denied`` em procedimento não detectado é inválida.
        """
        detected = self._detected_procedure_types()
        approved_count = 0

        for procedure_type in (ProcedureType.EDA, ProcedureType.COLONOSCOPY):
            disposition = str(cleaned.get(f"procedure_{procedure_type}") or "")
            reason = str(cleaned.get(f"procedure_{procedure_type}_reason") or "").strip()

            if disposition == DoctorDisposition.DENIED:
                if procedure_type not in detected:
                    self.add_error(
                        f"procedure_{procedure_type}",
                        "Não é possível negar um procedimento não detectado.",
                    )
                elif not reason:
                    self.add_error(
                        f"procedure_{procedure_type}_reason",
                        "Informe o motivo da negativa deste procedimento.",
                    )
            elif disposition == DoctorDisposition.APPROVED:
                approved_count += 1
                if procedure_type not in detected and not reason:
                    self.add_error(
                        f"procedure_{procedure_type}_reason",
                        "Justifique a inclusão deste procedimento (não detectado na análise).",
                    )
            elif procedure_type in detected:
                self.add_error(
                    f"procedure_{procedure_type}",
                    "Defina a decisão para este procedimento detectado.",
                )

        if approved_count > 0:
            if not cleaned.get("support_flag"):
                self.add_error("support_flag", "Selecione o tipo de suporte.")
            if not cleaned.get("admission_flow"):
                self.add_error("admission_flow", "Selecione o fluxo de admissão.")

        return cleaned
