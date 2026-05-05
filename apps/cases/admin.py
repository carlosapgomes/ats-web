from django.contrib import admin

from .models import Case, CaseEvent


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["case_id", "status", "created_by", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["case_id", "agency_record_number"]
    readonly_fields = ["case_id", "created_at", "updated_at"]


@admin.register(CaseEvent)
class CaseEventAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["case", "event_type", "actor_type", "actor", "timestamp"]
    list_filter = ["event_type", "actor_type", "timestamp"]
    search_fields = ["event_type"]
    readonly_fields = ["case", "timestamp", "actor_type", "actor", "event_type", "payload"]
