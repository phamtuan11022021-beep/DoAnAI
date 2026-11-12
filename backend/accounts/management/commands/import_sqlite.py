"""One-time transfer into an empty MySQL database, with an immutable source backup."""
import json
import sqlite3
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction


class Command(BaseCommand):
    help = 'Back up SQLite and import all application data into an empty MySQL database.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--source', type=Path, default=settings.BASE_DIR / 'db.sqlite3')

    def handle(self, source, **options):
        if connections['default'].vendor != 'mysql':
            raise CommandError('The destination must be MySQL. Set DB_ENGINE=mysql.')
        source = source.resolve()
        if not source.is_file():
            raise CommandError(f'SQLite source not found: {source}')
        alias = 'sqlite_import_source'
        if alias in connections:
            raise CommandError(f'Database alias already in use: {alias}')
        call_command('migrate', interactive=False, verbosity=0)
        excluded = {'contenttypes.contenttype', 'auth.permission'}
        models = [m for m in apps.get_models() if m._meta.managed and not m._meta.proxy
                  and m._meta.label_lower not in excluded]
        occupied = [m._meta.label_lower for m in models if m._default_manager.using('default').exists()]
        if occupied:
            raise CommandError('Destination is not empty; refusing to overwrite: ' + ', '.join(occupied))

        backup_dir = settings.BASE_DIR.parent / 'backups'
        backup_dir.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = backup_dir / f'before_mysql_{stamp}.sqlite3'
        # SQLite backup API also includes committed writes from a WAL file.
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as original:
            with closing(sqlite3.connect(backup)) as snapshot:
                original.backup(snapshot)
        config = deepcopy(connections['default'].settings_dict)
        config.update(ENGINE='django.db.backends.sqlite3', NAME=backup.as_uri() + '?mode=ro',
                      OPTIONS={'uri': True}, CONN_MAX_AGE=0, USER='', PASSWORD='', HOST='', PORT='')
        connections.databases[alias] = config
        try:
            expected = {m._meta.label_lower: m._base_manager.using(alias).count() for m in models}
            with TemporaryDirectory(prefix='uniconnect_mysql_') as temporary:
                fixture = Path(temporary) / 'transfer.json'
                # Explicit UTF-8 is necessary on Windows as well as for Vietnamese
                # names and emoji. dumpdata --output otherwise uses the locale.
                with fixture.open('w', encoding='utf-8') as stream:
                    call_command('dumpdata', database=alias, exclude=list(excluded),
                                 use_natural_foreign_keys=True, use_base_manager=True,
                                 stdout=stream, verbosity=0)
                with transaction.atomic(using='default'):
                    call_command('loaddata', str(fixture), database='default', verbosity=0)
                    actual = {m._meta.label_lower: m._base_manager.using('default').count() for m in models}
                    if actual != expected:
                        raise CommandError('Row counts differ; import rolled back. SQLite is unchanged.')
            report = backup_dir / f'mysql_transfer_{stamp}.json'
            report.write_text(json.dumps({'backup': str(backup), 'database': settings.DATABASES['default']['NAME'],
                                          'counts': actual}, indent=2), encoding='utf-8')
            self.stdout.write(self.style.SUCCESS(
                f'Imported {sum(actual.values())} records. Backup: backups/{backup.name}. Report: backups/{report.name}'))
        finally:
            connections[alias].close()
            del connections[alias]
            connections.databases.pop(alias, None)
