"""URL patterns for admin_ui app."""

from django.urls import path

from . import views

app_name = "admin_ui"

urlpatterns = [
    path("users/", views.user_list, name="user_list"),
    path("users/create/", views.user_create, name="user_create"),
    path("users/<int:pk>/", views.user_update, name="user_update"),
    path("users/<int:pk>/block/", views.user_block, name="user_block"),
    path("users/<int:pk>/unblock/", views.user_unblock, name="user_unblock"),
    # Prompt management
    path("prompts/", views.prompt_list, name="prompt_list"),
    path("prompts/create/", views.prompt_create, name="prompt_create"),
    path("prompts/<uuid:pk>/", views.prompt_detail, name="prompt_detail"),
    path("prompts/<uuid:pk>/activate/", views.prompt_activate, name="prompt_activate"),
    path("prompts/<uuid:pk>/deactivate/", views.prompt_deactivate, name="prompt_deactivate"),
]
