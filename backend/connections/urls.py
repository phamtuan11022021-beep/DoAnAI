from django.urls import path

from .views import (
    follow_toggle_view,
    following_view,
    suggestions_view,
)


urlpatterns = [
    path(
        "suggestions/",
        suggestions_view,
        name="connection-suggestions",
    ),
    path(
        "following/",
        following_view,
        name="connection-following",
    ),
    path(
        "follow/<int:user_id>/",
        follow_toggle_view,
        name="connection-follow-toggle",
    ),
]
