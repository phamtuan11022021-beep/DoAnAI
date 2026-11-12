"""Portable offline backup, including business data, admissions data, models and media."""
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_DEFLATED

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand,CommandError


class Command(BaseCommand):
    help='Create a backup after stopping web workers and data writers. Never includes .env.'

    def add_arguments(self,parser):
        parser.add_argument('--maintenance-confirmed',action='store_true')

    def handle(self,*args,**options):
        if not options['maintenance_confirmed']:
            raise CommandError('Stop web workers and scrapers, then pass --maintenance-confirmed for a consistent backup.')
        root=settings.BASE_DIR.parent
        target=root/'backups'
        target.mkdir(exist_ok=True)
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        destination=target/f'project_{stamp}.zip'
        manifest={'created_at':stamp,'django_version':__import__('django').get_version(),
                  'maintenance_required':True,'files':{}}
        with TemporaryDirectory(dir=target) as temporary:
            fixture=Path(temporary)/'database.json'
            with fixture.open('w',encoding='utf-8') as stream:
                call_command('dumpdata',exclude=['contenttypes','auth.permission','sessions','config.requestbucket'],
                    use_natural_foreign_keys=True,use_natural_primary_keys=True,
                    use_base_manager=True,stdout=stream,verbosity=0)
            files=[('database.json',fixture)]
            for folder in ['backend/media','data/dataset','data/processed','ai/models','data/qa']:
                parent=root/folder
                if parent.exists():
                    for path in parent.rglob('*'):
                        if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root.resolve()):
                            files.append((path.relative_to(root).as_posix(),path))
            # Keep proof of admissions sources alongside the published datasets.
            for folder in ['data/raw']:
                parent=root/folder
                if parent.exists():
                    files.extend((p.relative_to(root).as_posix(),p) for p in parent.rglob('*')
                                 if p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(root.resolve()))
            pending=destination.with_suffix('.partial')
            with ZipFile(pending,'w',ZIP_DEFLATED) as archive:
                for name,path in files:
                    manifest['files'][name]=hashlib.sha256(path.read_bytes()).hexdigest()
                    archive.write(path,name)
                archive.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
            with ZipFile(pending) as archive:
                if archive.testzip(): raise CommandError('Backup ZIP verification failed.')
            pending.rename(destination)
        self.stdout.write(self.style.SUCCESS(f'Backup verified: {destination.name}; files={len(files)}'))
