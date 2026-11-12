"""Small Ollama HTTP boundary; no cloud provider or silent fallback."""
import re

import requests
from django.conf import settings


class OllamaError(Exception):
    def __init__(self, message, status=503, *, reason='', upstream_status=None, retry_after=None):
        super().__init__(message)
        self.status = status
        self.reason = reason
        self.upstream_status = upstream_status
        self.retry_after = retry_after


def chat(messages, *, schema=None):
    payload = {
        'model': settings.OLLAMA_MODEL,
        'messages': messages,
        'stream': False,
        'think': False,
        'keep_alive': settings.OLLAMA_KEEP_ALIVE,
        'options': {
            'temperature': 0 if schema else 0.3,
            'num_ctx': settings.OLLAMA_NUM_CTX,
            'num_predict': 512 if schema else 1024,
        },
    }
    if schema:
        payload['format'] = schema
    try:
        response = requests.post(
            f'{settings.OLLAMA_BASE_URL}/api/chat', json=payload,
            timeout=(5, settings.OLLAMA_TIMEOUT),
        )
        if response.status_code == 404:
            raise OllamaError(
                f'Chưa tìm thấy model. Chạy: ollama pull {settings.OLLAMA_MODEL}'
            )
        response.raise_for_status()
        data = response.json()
    except requests.Timeout as exc:
        raise OllamaError('Model local phản hồi quá lâu. Vui lòng thử lại.', 504) from exc
    except requests.RequestException as exc:
        raise OllamaError('Không kết nối được Ollama. Hãy mở Ollama hoặc chạy ollama serve.') from exc
    except ValueError as exc:
        raise OllamaError('Ollama trả về dữ liệu không hợp lệ.', 502) from exc
    if not isinstance(data, dict) or not isinstance(data.get('message'), dict):
        raise OllamaError('Ollama trả về dữ liệu không hợp lệ.', 502)
    content = data['message'].get('content')
    if not isinstance(content, str) or data.get('done_reason') == 'length':
        raise OllamaError('Câu trả lời của model không đầy đủ. Vui lòng thử lại.', 502)
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.S).strip()
    if not content or '<think>' in content:
        raise OllamaError('Model chưa tạo được câu trả lời. Vui lòng thử lại.', 502)
    return content
