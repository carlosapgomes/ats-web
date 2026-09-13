"""Forms for the doctor app."""

from typing import Any

from django import forms

from apps.cases.admission import ADMISSION_FLOW_CHOICES, SUPPORT_FLAG_CHOICES
from apps.cases.models import Case, DetectionStatus, DoctorDisposition, ProcedureType
from apps.cases.procedures import (
    ALLOWED_PROCEDURE_SETS,
    PROCEDURE_ORDER,
    is_procedure_neutral_structured_data,
)

# Tipos que o médico pode manter, negar ou aprovar como destino da troca
# (design D10/D14). CPRE entra reutilizando esta mesma estrutura no Slice 004 —
# basta acrescentá-lo aqui, sem novo ramo de template ou validação.
SELECTABLE_PROCEDURE_TYPES: tuple[str, ...] = (
    ProcedureType.EDA,
    ProcedureType.COLONOSCOPY,
    ProcedureType.ECHOENDOSCOPY,
)


class DoctorDecisionForm(forms.Form):
    """Formulário de decisão médica com validação condicional.

    Dois modos (Slice 003, design D9/ADR-0004):

    - **v2/v3 (procedures)**: caso com ``structured_data.schema_version`` em
      ``{"2.0", "3.0"}`` — decisão por componente ``procedure_<type>`` + razão
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

    # ── Campos por procedimento (modo procedure-neutral) ─────────────
    # Construídos a partir de ``SELECTABLE_PROCEDURE_TYPES`` em ``__init__``:
    # um par ``procedure_<tipo>``/``procedure_<tipo>_reason`` por tipo, sem
    # ramo por procedimento. R1 do Slice 003 exige que Ecoendoscopia tenha
    # campo próprio (o template ligava todo tipo não-EDA a Colonoscopia).

    def __init__(self, *args: Any, case: Case | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.case = case
        if self.is_v2_mode:
            # Modo procedure-neutral: a decisão global é derivada das
            # disposições por componente (R4); o campo global só é exigido no
            # modo legado 1.1.
            self.fields["decision"].required = False
        for procedure_type in SELECTABLE_PROCEDURE_TYPES:
            self.fields[f"procedure_{procedure_type}"] = forms.ChoiceField(
                choices=[("", "---"), ("approved", "Aprovar"), ("denied", "Negar")],
                required=False,
            )
            self.fields[f"procedure_{procedure_type}_reason"] = forms.CharField(widget=forms.Textarea, required=False)

    @property
    def is_v2_mode(self) -> bool:
        """True quando o caso usa o contrato procedure-neutral (2.0 ou 3.0)."""
        if self.case is None:
            return False
        return is_procedure_neutral_structured_data(self.case.structured_data)

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
        """Modo 1.1: decisão global com validação condicional anterior.

        Decisão ausente/inválida é rejeitada (fail-closed): sem isso,
        ``doctor_decide(decision="")`` gravaria o evento corrompido ``DOCTOR_``
        e aceitaria o caso (qualquer valor ≠ "deny" vira accept).
        """
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
        else:
            self.add_error("decision", "Selecione a decisão.")

        return cleaned

    def _reject_unknown_procedure_fields(self) -> None:
        """Rejeita ``procedure_*`` fora do catálogo selecionável (fail-closed).

        Valor desconhecido NUNCA é descartado em silêncio (D2): um campo
        especializado não ofertado neste slice (ex.: CPRE) enviado por POST
        manipulado invalida o formulário inteiro antes de qualquer write.
        """
        known = set(self.fields)
        for key in self.data:
            if key.startswith("procedure_") and key not in known:
                self.add_error(None, f"Procedimento não suportado neste formulário: {key}.")

    def _clean_procedure_mode(self, cleaned: dict[str, Any]) -> dict[str, Any]:
        """Modo procedure-neutral: validação por componente, fail-closed (R1/R2/D9).

        - todo procedimento detectado exige disposição (approved|denied);
        - negado exige razão específica do componente;
        - aprovado sem ter sido detectado (inclusão/troca) exige justificativa;
        - pelo menos um aprovado exige suporte + fluxo de admissão;
        - o conjunto aprovado final precisa pertencer à matriz fechada (R4):
          conjunto parcial incompatível invalida o formulário sem write.
        """
        detected = self._detected_procedure_types()
        approved: list[str] = []
        saw_disposition = False
        self._reject_unknown_procedure_fields()

        for procedure_type in SELECTABLE_PROCEDURE_TYPES:
            disposition = str(cleaned.get(f"procedure_{procedure_type}") or "")
            reason = str(cleaned.get(f"procedure_{procedure_type}_reason") or "").strip()

            if disposition in (DoctorDisposition.APPROVED, DoctorDisposition.DENIED):
                saw_disposition = True

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
                approved.append(procedure_type)
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

        if approved and frozenset(approved) not in ALLOWED_PROCEDURE_SETS:
            labels = " + ".join(ProcedureType(t).label for t in sorted(approved, key=lambda t: PROCEDURE_ORDER[t]))
            self.add_error(
                None,
                f"Conjunto de procedimentos autorizado não suportado: {labels}. "
                "Substitua o conjunto inteiro ou negue os componentes excedentes.",
            )

        if approved:
            if not cleaned.get("support_flag"):
                self.add_error("support_flag", "Selecione o tipo de suporte.")
            if not cleaned.get("admission_flow"):
                self.add_error("admission_flow", "Selecione o fluxo de admissão.")
        elif not saw_disposition and not detected:
            # Sem nenhuma disposição e sem procedimento detectado, o submit
            # não pode decidir nada (um deny global vazio não tem razão de
            # componente) — fail-closed (BUG 2 pós-verificação).
            self.add_error(
                f"procedure_{SELECTABLE_PROCEDURE_TYPES[0]}",
                "Defina a decisão de ao menos um procedimento.",
            )

        return cleaned
