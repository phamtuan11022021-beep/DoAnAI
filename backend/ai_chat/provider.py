"""Select a server-side chat provider without loading local model weights."""
import requests
from django.conf import settings
from .ollama_client import OllamaError, chat as ollama_chat
from .gemini_client import chat as gemini_chat


def provider_info():
    provider = settings.CHAT_PROVIDER
    models = {'openai': settings.OPENAI_MODEL, 'gemini': settings.GEMINI_MODEL,
              'ollama': settings.OLLAMA_MODEL}
    return {'chat_provider': provider, 'chat_model': models.get(provider, '')}


def chat(messages, *, schema=None):
    if settings.CHAT_PROVIDER == 'gemini':
        return gemini_chat(messages, schema=schema)
    if settings.CHAT_PROVIDER == 'ollama':
        return ollama_chat(messages, schema=schema)
    if settings.CHAT_PROVIDER != 'openai':
        raise OllamaError('CHAT_PROVIDER phải là openai, gemini hoặc ollama.')
    if not settings.OPENAI_API_KEY:
        raise OllamaError('Chưa cấu hình OPENAI_API_KEY trên máy chủ.')
    payload = {
        'model': settings.OPENAI_MODEL, 'input': messages, 'store': False,
        'max_output_tokens': 800 if schema else settings.OPENAI_MAX_OUTPUT_TOKENS,
    }
    if schema:
        payload['text'] = {'format': {
            'type': 'json_schema', 'name': 'admission_route',
            'strict': True, 'schema': schema,
        }}
    try:
        response = requests.post(
            'https://api.openai.com/v1/responses', json=payload,
            headers={'Authorization': f'Bearer {settings.OPENAI_API_KEY}'},
            timeout=(5, settings.OPENAI_TIMEOUT),
        )
        if response.status_code == 429:
            try:
                error_code = response.json().get('error', {}).get('code')
            except (ValueError, AttributeError, TypeError):
                error_code = None
            if error_code in ('insufficient_quota', 'credit_balance_exhausted'):
                raise OllamaError('Tài khoản OpenAI chưa có hoặc đã hết hạn mức API. Cần kiểm tra billing của project.', 503)
            if error_code in ('organization_spend_limit_exceeded', 'project_spend_limit_exceeded', 'organization_usage_limit_exceeded'):
                raise OllamaError('Tài khoản hoặc project OpenAI đã đạt giới hạn chi tiêu/sử dụng API.', 503)
            raise OllamaError('OpenAI đang giới hạn yêu cầu hoặc tài khoản hết hạn mức. Vui lòng thử lại sau.', 503)
        if response.status_code in (401, 403):
            raise OllamaError('Cấu hình quyền truy cập OpenAI chưa hợp lệ. Vui lòng liên hệ quản trị viên.', 503)
        response.raise_for_status()
        body = response.json()
    except requests.Timeout as exc:
        raise OllamaError('OpenAI phản hồi quá lâu. Vui lòng thử lại.', 504) from exc
    except requests.RequestException as exc:
        raise OllamaError('Không kết nối được dịch vụ OpenAI. Vui lòng thử lại.', 503) from exc
    except ValueError as exc:
        raise OllamaError('OpenAI trả về dữ liệu không hợp lệ.', 502) from exc
    if not isinstance(body, dict) or body.get('status') != 'completed':
        raise OllamaError('OpenAI chưa tạo được câu trả lời đầy đủ. Vui lòng thử lại.', 502)
    parts = []
    output = body.get('output')
    if not isinstance(output, list):
        raise OllamaError('OpenAI trả về dữ liệu không hợp lệ.', 502)
    for item in output:
        if isinstance(item, dict) and item.get('type') == 'message':
            contents = item.get('content')
            if not isinstance(contents, list):
                raise OllamaError('OpenAI trả về dữ liệu không hợp lệ.', 502)
            for content in contents:
                if isinstance(content, dict) and content.get('type') == 'output_text' and isinstance(content.get('text'), str):
                    parts.append(content['text'])
    result = '\n'.join(parts).strip()
    if not result:
        raise OllamaError('OpenAI chưa tạo được câu trả lời. Vui lòng thử lại.', 502)
    return result
