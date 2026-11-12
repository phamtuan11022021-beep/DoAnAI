"""Validate and re-encode uploaded images before storing them."""
from io import BytesIO
from uuid import uuid4

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError


def clean_image(upload, *, avatar=False):
    if upload.size > 5 * 1024 * 1024:
        raise ValueError('Mỗi ảnh tối đa 5 MB.')
    try:
        with Image.open(upload) as source:
            if source.format not in ('JPEG', 'PNG', 'WEBP'):
                raise ValueError('Chỉ hỗ trợ ảnh JPG, PNG hoặc WebP.')
            if source.width * source.height > 25_000_000:
                raise ValueError('Ảnh quá lớn, hãy chọn ảnh dưới 25 megapixel.')
            source.load()
            image = ImageOps.exif_transpose(source).convert('RGB')
            if avatar:
                image = ImageOps.fit(image, (512, 512))
            else:
                image.thumbnail((2048, 2048))
            output = BytesIO()
            image.save(output, 'JPEG', quality=88)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError('File không phải ảnh hợp lệ.') from exc
    return ContentFile(output.getvalue(), name=f'{uuid4().hex}.jpg')


def avatar_url(user):
    profile = getattr(user, 'uniconnect_profile', None)
    return profile.avatar.url if profile and profile.avatar else ''
