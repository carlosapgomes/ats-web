"""Admin registration for LLM models."""

from __future__ import annotations

from django.contrib import admin

from apps.llm.models import PromptTemplate


@admin.register(PromptTemplate)
class PromptTemplateAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["name", "version", "is_active", "created_at", "updated_at", "updated_by"]
    list_filter = ["name", "is_active"]
    search_fields = ["name", "content"]
    ordering = ["name", "-version"]
    readonly_fields = ["created_at", "updated_at"]
