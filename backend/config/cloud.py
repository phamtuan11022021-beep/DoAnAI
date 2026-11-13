"""Render-only settings; local development continues to use config.settings."""
import os
import re

hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME', '')
if hostname and re.fullmatch(r'[a-z0-9-]+\.onrender\.com', hostname):
    os.environ.setdefault('DJANGO_ALLOWED_HOSTS', hostname)
    os.environ.setdefault('DJANGO_CSRF_TRUSTED_ORIGINS', f'https://{hostname}')
os.environ.setdefault('DJANGO_TRUST_PROXY', 'true')

from .production import *  # noqa: E402,F403

MIDDLEWARE = list(MIDDLEWARE)  # noqa: F405
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
WHITENOISE_ROOT = BASE_DIR.parent / 'frontend' / 'dist'  # noqa: F405
WHITENOISE_INDEX_FILE = True
WHITENOISE_MAX_AGE = 60
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}
# Render Free disks are ephemeral. Never treat uploaded media as durable backups.
ROOT_URLCONF = 'config.cloud_urls'
