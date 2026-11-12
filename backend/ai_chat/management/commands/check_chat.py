"""Explicit live smoke check; never prints the API key or persists a conversation."""
from django.core.management.base import BaseCommand, CommandError
from ai_chat.ollama_client import OllamaError
from ai_chat.provider import chat, provider_info
from ai_chat.service import respond


class Command(BaseCommand):
    help = "Check configured chat provider. --admissions also exercises routing and evidence."

    def add_arguments(self, parser):
        parser.add_argument('--admissions', action='store_true')
        parser.add_argument('--trace-status', action='store_true', help='Print only Gemini HTTP status for each smoke-check call')
        parser.add_argument('--diagnose', action='store_true', help='Print only HTTP status and safe error identifiers')

    def handle(self, *args, **options):
        info = provider_info()
        self.stdout.write(f"Provider: {info['chat_provider']}; model: {info['chat_model']}")
        if options['diagnose']:
            import json
            import requests
            from django.conf import settings
            if settings.CHAT_PROVIDER == 'gemini':
                from ai_chat.gemini_client import request
                try:
                    response = request([{'role': 'user', 'content': 'Reply OK'}])
                except OllamaError as exc:
                    raise CommandError(str(exc)) from None
            elif settings.CHAT_PROVIDER == 'openai':
                response = requests.post('https://api.openai.com/v1/responses',
                    headers={'Authorization': 'Bearer ' + settings.OPENAI_API_KEY},
                    json={'model': settings.OPENAI_MODEL, 'input': 'Reply OK',
                          'store': False, 'max_output_tokens': 16}, timeout=(5, 30))
            else:
                raise CommandError('--diagnose hỗ trợ OpenAI hoặc Gemini.')
            try:
                body = response.json()
            except ValueError:
                body = {}
            error = body.get('error', {}) if isinstance(body, dict) else {}
            if not isinstance(error, dict):
                error = {}
            # Never print response messages: authentication errors may echo a key.
            import re
            safe = lambda value: value if isinstance(value, str) and re.fullmatch(r'[a-zA-Z0-9_]{1,100}', value) else None
            self.stdout.write(json.dumps({'http_status': response.status_code,
                'error_type': safe(error.get('type') or error.get('status')),
                'error_code': error.get('code') if isinstance(error.get('code'), int) else safe(error.get('code'))}))
            return
        try:
            if options['admissions']:
                from contextlib import nullcontext
                from unittest.mock import patch
                from ai_chat import gemini_client
                original = gemini_client.request
                def traced_request(*args, **kwargs):
                    response = original(*args, **kwargs)
                    self.stdout.write(f'Gemini HTTP: {response.status_code}; structured: {bool(kwargs.get("schema"))}')
                    return response
                context = patch('ai_chat.gemini_client.request', side_effect=traced_request) if options['trace_status'] else nullcontext()
                with context:
                    result = respond(
                        message='Em được 28 điểm A00, muốn học Công nghệ thông tin ở Đà Nẵng. Tư vấn nguyện vọng giúp em.',
                        previous_context={}, ui_context={}, history=[])
                self.stdout.write(result['text'])
                self.stdout.write(f"Intent: {result['intent']}; cards: {len(result['cards'])}")
                diagnostics = result.get('diagnostics', {})
                self.stdout.write(f"Answer mode: {diagnostics.get('answer_mode', 'llm')}; provider status: {diagnostics.get('provider_status', 'ok')}")
            else:
                result = chat([{'role': 'user', 'content': 'Trả lời đúng một từ: OK'}])
                self.stdout.write(result)
        except OllamaError as exc:
            raise CommandError(str(exc)) from None
