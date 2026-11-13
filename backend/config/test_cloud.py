"""Cloud configuration and static routing without touching the local MySQL DB."""
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase, override_settings
from django.http import HttpResponse
from whitenoise.middleware import WhiteNoiseMiddleware

from .database import database_config


class CloudConfigTests(SimpleTestCase):
    def test_tidb_uses_its_dialect_and_verified_tls(self):
        config = database_config(Path('.'), {
            'DB_ENGINE': 'tidb', 'MYSQL_DATABASE': 'demo', 'MYSQL_USER': 'app',
            'MYSQL_HOST': 'example.tidbcloud.com', 'MYSQL_PORT': '4000',
        })
        self.assertEqual(config['ENGINE'], 'django_tidb')
        self.assertEqual(config['OPTIONS']['ssl_mode'], 'VERIFY_IDENTITY')
        self.assertTrue(Path(config['OPTIONS']['ssl']['ca']).is_file())
        self.assertEqual(config['OPTIONS']['isolation_level'], 'repeatable read')

    def test_frontend_index_and_assets_do_not_swallow_api_errors(self):
        from django.test import RequestFactory
        with TemporaryDirectory() as root, override_settings(
            DEBUG=False, STATIC_ROOT=root, STATIC_URL='/static/',
            WHITENOISE_ROOT=root, WHITENOISE_INDEX_FILE=True,
            WHITENOISE_AUTOREFRESH=True,
        ):
            Path(root, 'index.html').write_text('<html>UniConnect</html>')
            Path(root, 'assets').mkdir()
            Path(root, 'assets/app.js').write_text('console.log("ok")')
            app = WhiteNoiseMiddleware(lambda request: HttpResponse(status=404))
            factory = RequestFactory()
            for url in ['/', '/assets/app.js']:
                response = app(factory.get(url))
                self.assertEqual(response.status_code, 200)
                response.close()
            for url in ['/api/missing/', '/.env', '/assets/../../.env']:
                self.assertEqual(app(factory.get(url)).status_code, 404)
