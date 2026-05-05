from django.urls import path

from . import views

app_name = "intake"

urlpatterns = [
    path("", views.intake_home, name="home"),
    path("<uuid:case_id>/", views.case_detail, name="case_detail"),
]
