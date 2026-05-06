"""URL patterns for the doctor app."""

from django.urls import path

from . import views

app_name = "doctor"

urlpatterns = [
    path("", views.doctor_queue, name="queue"),
]
