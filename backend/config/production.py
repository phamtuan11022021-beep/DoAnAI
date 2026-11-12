"""Use DJANGO_SETTINGS_MODULE=config.production on the deployed web service."""
from .settings import *  # noqa: F403
from django.core.exceptions import ImproperlyConfigured

DEBUG = False
if len(SECRET_KEY) < 50 or SECRET_KEY == 'development-only-uniconnect-key':
    raise ImproperlyConfigured('Production requires DJANGO_SECRET_KEY with at least 50 characters.')
if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS or set(ALLOWED_HOSTS) <= {'localhost','127.0.0.1'}:
    raise ImproperlyConfigured('Set DJANGO_ALLOWED_HOSTS to your public domain.')
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS','').split(',') if origin.strip()]
if not CSRF_TRUSTED_ORIGINS or any(not origin.startswith('https://') for origin in CSRF_TRUSTED_ORIGINS):
    raise ImproperlyConfigured('Set HTTPS DJANGO_CSRF_TRUSTED_ORIGINS for production.')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_HSTS_SECONDS', '3600'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get('DJANGO_HSTS_INCLUDE_SUBDOMAINS','false').lower() == 'true'
SECURE_HSTS_PRELOAD = os.environ.get('DJANGO_HSTS_PRELOAD','false').lower() == 'true'
SECURE_CONTENT_TYPE_NOSNIFF = True
# Enable only behind a trusted proxy that removes incoming spoofed headers.
if os.environ.get('DJANGO_TRUST_PROXY', '').lower() == 'true':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
LOGGING = {'version':1, 'disable_existing_loggers':False,
           'handlers':{'console':{'class':'logging.StreamHandler'}},
           'root':{'handlers':['console'],'level':'INFO'}}
