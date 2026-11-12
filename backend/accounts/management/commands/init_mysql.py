import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create the configured MySQL database if missing; never drops existing data.'
    requires_system_checks = []

    def handle(self, **options):
        import MySQLdb

        config = settings.DATABASES['default']
        if config['ENGINE'] != 'django.db.backends.mysql':
            raise CommandError('Select DB_ENGINE=mysql first.')
        name = config['NAME']
        if not re.fullmatch(r'[A-Za-z0-9_]{1,64}', name):
            raise CommandError('MYSQL_DATABASE must contain only letters, digits and underscores (max 64).')
        connection = MySQLdb.connect(
            host=config['HOST'], port=int(config['PORT']),
            user=config['USER'], passwd=config['PASSWORD'],
            charset='utf8mb4', connect_timeout=10,
            **({'ssl': config['OPTIONS']['ssl']} if 'ssl' in config['OPTIONS'] else {}),
        )
        try:
            with connection.cursor() as cursor:
                # Binary collation preserves SQLite case-sensitive unique keys.
                cursor.execute(f'CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin')
        finally:
            connection.close()
        self.stdout.write(self.style.SUCCESS(f'MySQL database ready: {name}'))
