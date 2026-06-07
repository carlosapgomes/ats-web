from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_index, name="index"),
    path("summaries/", views.dashboard_summaries, name="summaries"),
    path("<uuid:case_id>/", views.dashboard_case_detail, name="case_detail"),
    path("<uuid:case_id>/pdf/", views.dashboard_case_pdf, name="case_pdf"),
    path("<uuid:case_id>/administrative-close/", views.dashboard_administrative_close, name="administrative_close"),
]
