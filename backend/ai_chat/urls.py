from django.urls import path

from .views import (
    chat_history_view,
    chat_view,
    new_chat_view,
)


urlpatterns = [
    path(
        "chat/",
        chat_view,
        name="ai-chat",
    ),
    path(
        "history/",
        chat_history_view,
        name="ai-chat-history",
    ),
    path(
        "new/",
        new_chat_view,
        name="ai-chat-new",
    ),
]
