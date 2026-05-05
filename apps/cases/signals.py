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
