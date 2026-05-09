from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_index, name="index"),
    path("summaries/", views.dashboard_summaries, name="summaries"),
    path("<uuid:case_id>/", views.dashboard_case_detail, name="case_detail"),
]
