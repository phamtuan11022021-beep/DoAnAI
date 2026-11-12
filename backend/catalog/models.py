from django.conf import settings
from django.db import models


class AdmissionRelease(models.Model):
    title = models.CharField('Tên đợt dữ liệu', max_length=160)
    rows = models.JSONField(default=list)
    status = models.CharField('Trạng thái', max_length=12, default='draft',
        choices=[('draft','Chờ đối chiếu'),('published','Đang hiển thị'),('withdrawn','Đã thu hồi')])
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField('Ngày nhập', auto_now_add=True)
    reviewed_at = models.DateTimeField('Ngày xử lý', null=True)
    source_sha256 = models.CharField(max_length=64)

    class Meta:
        verbose_name = 'Đợt dữ liệu tuyển sinh'
        verbose_name_plural = 'Dữ liệu tuyển sinh'
        permissions = [('publish_admissionrelease','Được duyệt và thu hồi dữ liệu tuyển sinh')]

    def __str__(self):
        return self.title


class AdmissionReleaseLock(models.Model):
    """Serialize publishing without editing any training CSV."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)


class SavedUniversity(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_universities",
    )
    university_key = models.CharField(
        max_length=220,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "university_key"],
                name="unique_saved_university_per_user",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id} saves {self.university_key}"
