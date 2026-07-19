"""URL patterns for the scheduler app."""

from django.urls import path

from . import views

app_name = "scheduler"

urlpatterns = [
    path("", views.scheduler_queue, name="queue"),
    path("partials/queue/", views.scheduler_queue_partial, name="queue_partial"),
    path("processed/<uuid:case_id>/", views.scheduler_processed_detail, name="processed_detail"),
    path("processed/<uuid:case_id>/pdf/", views.scheduler_processed_pdf, name="processed_pdf"),
    path("processed/<uuid:case_id>/pdf-viewer/", views.scheduler_processed_pdf_viewer, name="processed_pdf_viewer"),
    path("<uuid:case_id>/immediate-ack/", views.immediate_ack, name="immediate_ack"),
    path("<uuid:case_id>/operational-issue-ack/", views.operational_issue_ack, name="operational_issue_ack"),
    path("context/<uuid:case_id>/", views.scheduler_context_detail, name="context_detail"),
    path("<uuid:case_id>/", views.scheduler_confirm, name="confirm"),
    path("<uuid:case_id>/submit/", views.scheduler_submit, name="submit"),
    path("<uuid:case_id>/lock/renew/", views.scheduler_lock_renew, name="lock_renew"),
    path("<uuid:case_id>/lock/release/", views.scheduler_lock_release, name="lock_release"),
    # ── Historical ────────────────────────────────────────────────────────
    path("historical/", views.scheduler_historical_search, name="historical_search"),
    path(
        "historical/<uuid:case_id>/message-nir/",
        views.scheduler_historical_message_nir,
        name="historical_message_nir",
    ),
]
