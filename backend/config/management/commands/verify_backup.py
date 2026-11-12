import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from django.conf import settings
from django.core.management.base import BaseCommand,CommandError


class Command(BaseCommand):
    help='Verify hashes and test DB fixture restore in a temporary SQLite DB; never restores into live MySQL.'

    def add_arguments(self,parser):
        parser.add_argument('archive',type=Path)

    def handle(self,archive,**options):
        root=settings.BASE_DIR.parent
        backup_dir=root/'backups'
        backup_dir.mkdir(exist_ok=True)
        with ZipFile(archive) as z:
            manifest=json.loads(z.read('manifest.json'))
            for name,digest in manifest['files'].items():
                with z.open(name) as stream:
                    actual=hashlib.file_digest(stream,'sha256').hexdigest()
                if actual!=digest: raise CommandError(f'Backup hash mismatch: {name}')
            fixture=z.read('database.json')
        expected=Counter(r['model'] for r in json.loads(fixture))
        with TemporaryDirectory(prefix='restore_check_',dir=backup_dir) as temporary:
            path=Path(temporary).resolve()
            if not path.is_relative_to(backup_dir.resolve()): raise CommandError('Invalid temporary restore directory')
            source=path/'database.json'
            source.write_bytes(fixture)
            env={**os.environ,'DB_ENGINE':'sqlite','SQLITE_PATH':str(path/'test.sqlite3'),
                 'DJANGO_SETTINGS_MODULE':'config.settings','DJANGO_DEBUG':'true','PYTHONUTF8':'1'}
            # No source .env or MySQL configuration is changed.
            commands=[['migrate','--noinput'],['loaddata',str(source)],
                ['shell','-c','from django.apps import apps; import json; expected=json.loads('+repr(json.dumps(expected))+'); actual={label:apps.get_model(label)._base_manager.count() for label in expected}; assert actual==expected,(actual,expected)']]
            for command in commands:
                process=subprocess.run([sys.executable,'-X','utf8',str(settings.BASE_DIR/'manage.py'),*command],
                    env=env,capture_output=True,text=True,encoding='utf-8')
                if process.returncode:
                    raise CommandError('Temporary restore verification failed; live MySQL was not touched.')
        self.stdout.write(self.style.SUCCESS(f'PASS: {len(manifest["files"])} file hashes; {sum(expected.values())} database records restored in isolated SQLite.'))
