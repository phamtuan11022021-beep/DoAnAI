import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase,override_settings
from django.utils import timezone
from .models import RequestBucket


class OperationsTests(TestCase):
    def test_backup_requires_maintenance_and_verifies_database_and_hashes(self):
        with self.assertRaises(CommandError): call_command('backup_project',stdout=StringIO())
        User.objects.create_user('backup-user',email='backup@example.com')
        with TemporaryDirectory() as directory,override_settings(BASE_DIR=Path(directory)/'backend'):
            call_command('backup_project',maintenance_confirmed=True,stdout=StringIO())
            archive=next((Path(directory)/'backups').glob('*.zip'))
            with ZipFile(archive) as z:
                manifest=json.loads(z.read('manifest.json'))
                for name,digest in manifest['files'].items():
                    self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(),digest)
                self.assertIn('backup-user',z.read('database.json').decode())
                self.assertNotIn('.env',z.namelist())

    def test_cleanup_only_expired_limits(self):
        from datetime import timedelta
        RequestBucket.objects.create(key='expired',expires_at=timezone.now()-timedelta(minutes=1))
        RequestBucket.objects.create(key='active',expires_at=timezone.now()+timedelta(minutes=1))
        call_command('cleanup_limits',stdout=StringIO())
        self.assertEqual(list(RequestBucket.objects.values_list('key',flat=True)),['active'])

    def test_health_has_no_sensitive_configuration(self):
        response=self.client.get('/api/health/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json(),{'status':'ok'})
