from django.conf import settings
from django.db import models


class CareerAssessment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="career_assessments",
    )
    framework = models.CharField(
        max_length=30,
        default="RIASEC",
    )
    answers = models.JSONField(
        default=dict,
    )
    scores = models.JSONField(
        default=dict,
    )
    holland_code = models.CharField(
        max_length=6,
    )
    suggested_majors = models.JSONField(
        default=list,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return (
            f"{self.user_id} - "
            f"{self.holland_code} - "
            f"{self.created_at:%Y-%m-%d}"
        )
