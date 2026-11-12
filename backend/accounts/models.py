from django.conf import settings
from django.db import models


class Profile(models.Model):
    avatar = models.ImageField(upload_to='avatars/', blank=True)
    ROLE_STUDENT = "student"
    ROLE_MENTOR = "mentor"

    ROLE_CHOICES = [
        (ROLE_STUDENT, "Học sinh / Sinh viên"),
        (ROLE_MENTOR, "Mentor"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="uniconnect_profile",
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_STUDENT,
    )
    expected_score = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
    )
    target_combination = models.CharField(
        max_length=10,
        blank=True,
    )
    target_major = models.CharField(
        max_length=200,
        blank=True,
    )
    city = models.CharField(
        max_length=120,
        blank=True,
    )
    bio = models.CharField(
        max_length=300,
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self) -> str:
        return f"{self.user.username} - {self.role}"
