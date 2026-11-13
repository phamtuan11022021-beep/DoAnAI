"""Database settings shared by the web app and migration tools."""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


def database_config(base_dir: Path, env=None):
    env = os.environ if env is None else env
    engine = env.get('DB_ENGINE', 'mysql' if env.get('MYSQL_DATABASE') else 'sqlite').lower()
    if engine == 'sqlite':
        return {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': env.get('SQLITE_PATH') or base_dir / 'db.sqlite3',
        }
    if engine not in {'mysql', 'tidb'}:
        raise ImproperlyConfigured('DB_ENGINE must be mysql, tidb or sqlite.')
    if not env.get('MYSQL_DATABASE') or not env.get('MYSQL_USER'):
        raise ImproperlyConfigured('Set MYSQL_DATABASE and MYSQL_USER before selecting MySQL.')
    options = {
        'charset': 'utf8mb4',
        'init_command': "SET sql_mode='STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION'",
        'isolation_level': 'read committed',
        'connect_timeout': 10,
    }
    if env.get('MYSQL_SSL_CA'):
        options['ssl'] = {'ca': env['MYSQL_SSL_CA']}
    if engine == 'tidb':
        # TiDB needs its Django dialect and verified TLS on cloud connections.
        import certifi
        options['ssl'] = {'ca': env.get('MYSQL_SSL_CA') or certifi.where()}
        options['ssl_mode'] = 'VERIFY_IDENTITY'
        options['isolation_level'] = 'repeatable read'
    return {
        'ENGINE': 'django_tidb' if engine == 'tidb' else 'django.db.backends.mysql',
        'NAME': env['MYSQL_DATABASE'],
        'USER': env['MYSQL_USER'],
        'PASSWORD': env.get('MYSQL_PASSWORD', ''),
        'HOST': env.get('MYSQL_HOST', '127.0.0.1'),
        'PORT': env.get('MYSQL_PORT', '3306'),
        'CONN_MAX_AGE': int(env.get('DB_CONN_MAX_AGE', '0')),
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': options,
    }
