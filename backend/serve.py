"""Production WSGI worker behind a local HTTPS reverse proxy."""
import os
os.environ['DJANGO_SETTINGS_MODULE']='config.production'

from django.core.wsgi import get_wsgi_application
from waitress import serve

if __name__=='__main__':
    serve(get_wsgi_application(),listen='127.0.0.1:8000',threads=8,
          trusted_proxy='127.0.0.1',trusted_proxy_count=1,
          trusted_proxy_headers={'x-forwarded-for','x-forwarded-proto','x-forwarded-host'},
          clear_untrusted_proxy_headers=True,expose_tracebacks=False)
