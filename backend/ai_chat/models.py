from django.conf import settings
from django.db import models


class AIChatSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uniconnect_ai_chat_sessions",
        null=True,
        blank=True,
    )
    session_key = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
    )
    title = models.CharField(
        max_length=180,
        blank=True,
    )
    context = models.JSONField(
        default=dict,
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-updated_at", "-id"]

    def __str__(self) -> str:
        owner = (
            self.user.username
            if self.user_id
            else self.session_key
        )
        return f"{owner} - {self.title or 'AI Chat'}"


class AIChatMessage(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"

    ROLE_CHOICES = [
        (ROLE_USER, "User"),
        (ROLE_ASSISTANT, "Assistant"),
    ]

    conversation = models.ForeignKey(
        AIChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
    )
    content = models.TextField()
    intent = models.CharField(
        max_length=50,
        blank=True,
    )
    payload = models.JSONField(
        default=dict,
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return (
            f"{self.conversation_id} "
            f"{self.role}: {self.content[:60]}"
        )
