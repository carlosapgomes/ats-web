"""URL patterns for the scheduler app."""

from django.urls import path

from . import views

app_name = "scheduler"

urlpatterns = [
    path("", views.scheduler_queue, name="queue"),
    path("partials/queue/", views.scheduler_queue_partial, name="queue_partial"),
    path("<uuid:case_id>/immediate-ack/", views.immediate_ack, name="immediate_ack"),
    path("<uuid:case_id>/", views.scheduler_confirm, name="confirm"),
    path("<uuid:case_id>/submit/", views.scheduler_submit, name="submit"),
    path("<uuid:case_id>/lock/renew/", views.scheduler_lock_renew, name="lock_renew"),
    path("<uuid:case_id>/lock/release/", views.scheduler_lock_release, name="lock_release"),
]
