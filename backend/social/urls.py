from django.urls import path
from . import interaction_views as interactions

from .views import (
    comments_view,
    like_view,
    posts_view,
    save_view,
    saved_posts_view,
)


urlpatterns = [
    path('posts/<int:post_id>/', interactions.post_detail),
    path('posts/<int:post_id>/vote/', interactions.vote),
    path('notifications/', interactions.notifications),
    path('inbox/', interactions.inbox),
    path('messages/<int:user_id>/', interactions.messages),
    path('messages/<int:user_id>/read/', interactions.read_messages),
    path("posts/", posts_view, name="social-posts"),
    path(
        "posts/<int:post_id>/comments/",
        comments_view,
        name="social-comments",
    ),
    path(
        "posts/<int:post_id>/like/",
        like_view,
        name="social-like",
    ),
    path(
        "posts/<int:post_id>/save/",
        save_view,
        name="social-save",
    ),
    path(
        "saved/",
        saved_posts_view,
        name="social-saved-posts",
    ),
]
