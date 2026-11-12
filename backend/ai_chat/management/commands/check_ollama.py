import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ai_chat.ollama_client import OllamaError, chat


class Command(BaseCommand):
    help = 'Check local Ollama model metadata; optionally run a short generation.'

    def add_arguments(self, parser):
        parser.add_argument('--generate', action='store_true')

    def handle(self, *args, **options):
        try:
            response = requests.post(
                f'{settings.OLLAMA_BASE_URL}/api/show',
                json={'model': settings.OLLAMA_MODEL}, timeout=(5, 15),
            )
            response.raise_for_status()
            details = response.json().get('details', {})
        except (requests.RequestException, ValueError, AttributeError) as exc:
            raise CommandError(
                f'Ollama/model unavailable. Start Ollama, then run: ollama pull {settings.OLLAMA_MODEL}'
            ) from exc
        self.stdout.write(f'Model: {settings.OLLAMA_MODEL}')
        self.stdout.write(f'Size: {details.get("parameter_size", "unknown")}')
        self.stdout.write(f'Quantization: {details.get("quantization_level", "unknown")}')
        if options['generate']:
            try:
                self.stdout.write(chat([{'role': 'user', 'content': 'Say hello in Vietnamese.'}]))
            except OllamaError as exc:
                raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS('Ollama check passed.'))
