"""Single Render worker: migrate the cloud DB, then serve on the assigned port."""
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.cloud')

import django
from django.core.management import call_command
from django.core.wsgi import get_wsgi_application
from waitress import serve


def main():
    django.setup()
    call_command('migrate', interactive=False)
    call_command('setup_admin_roles')
    serve(get_wsgi_application(), host='0.0.0.0',
          port=int(os.environ.get('PORT', '10000')), threads=4,
          # Render's edge is the only public ingress to this container.
          trusted_proxy='*', trusted_proxy_count=1,
          trusted_proxy_headers={'x-forwarded-for', 'x-forwarded-proto'},
          clear_untrusted_proxy_headers=True, expose_tracebacks=False)


if __name__ == '__main__':
    main()
