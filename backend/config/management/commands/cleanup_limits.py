from django.core.management.base import BaseCommand
from django.utils import timezone
from config.models import RequestBucket


class Command(BaseCommand):
    help='Remove expired request-limit counters; schedule hourly.'

    def handle(self,*args,**options):
        count,_=RequestBucket.objects.filter(expires_at__lt=timezone.now()).delete()
        self.stdout.write(f'Removed {count} expired counters.')
