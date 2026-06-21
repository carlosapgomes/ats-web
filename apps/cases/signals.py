from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Case, CaseEvent


@receiver(post_save, sender=Case)
def record_case_event(sender: type[Case], instance: Case, created: bool, **kwargs: object) -> None:
    """Registra evento pendente após save do Case."""
    if created:
        CaseEvent.objects.create(
            case=instance,
            event_type="CASE_CREATED",
            actor=instance.created_by,
            actor_type="human",
            payload={"status": instance.status},
        )
        return

    pending = getattr(instance, "_pending_event", None)
    if pending:
        CaseEvent.objects.create(
            case=instance,
            event_type=pending["event_type"],
            actor=pending["actor"],
            actor_type=pending["actor_type"],
            payload=pending["payload"],
        )
        instance._pending_event = None  # type: ignore[assignment]


@receiver(post_save, sender=CaseEvent)
def create_case_event_system_notice(
    sender: type[CaseEvent],
    instance: CaseEvent,
    created: bool,
    **kwargs: object,
) -> None:
    """Projeta CaseEvent suportado em mensagem sistêmica na thread.

    Ignora eventos não suportados e CASE_COMMUNICATION_MESSAGE_POSTED
    para evitar loop/ruído. Idempotente por source_event.

    Não cria UserNotification para mensagens sistêmicas.
    """
    if not created:
        return

    # Importação tardia para evitar circular import
    from apps.cases.services import create_system_communication_notice_for_event

    create_system_communication_notice_for_event(instance)
