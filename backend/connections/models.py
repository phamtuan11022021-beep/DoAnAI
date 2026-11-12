from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class UserFollow(models.Model):
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uniconnect_following",
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uniconnect_followers",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["follower", "following"],
                name="unique_uniconnect_follow",
            ),
            models.CheckConstraint(
                check=~models.Q(
                    follower=models.F("following")
                ),
                name="prevent_uniconnect_self_follow",
            ),
        ]

    def clean(self):
        if self.follower_id == self.following_id:
            raise ValidationError(
                "Không thể tự theo dõi chính mình."
            )

    def __str__(self) -> str:
        return f"{self.follower_id} -> {self.following_id}"
