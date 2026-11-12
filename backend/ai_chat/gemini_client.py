"""Server-side Gemini REST adapter; credentials never enter URLs or prompts."""
import re
import hashlib
import logging
import math
import random
import time

import requests
from django.conf import settings
from django.core.cache import cache

from .ollama_client import OllamaError


def _request_once(messages, *, schema=None, timeout=None):
    if not settings.GEMINI_API_KEY:
        raise OllamaError('Chưa cấu hình GEMINI_API_KEY trên máy chủ.', 503,reason='configuration')
    model = settings.GEMINI_MODEL
    if not re.fullmatch(r'[a-zA-Z0-9._-]+', model):
        raise OllamaError('GEMINI_MODEL không hợp lệ.', 503,reason='configuration')
    contents, instructions = [], []
    for message in messages:
        role, text = message['role'], message['content']
        if role == 'system':
            instructions.append({'text': text})
        elif role in ('user', 'assistant'):
            contents.append({'role': 'model' if role == 'assistant' else 'user',
                             'parts': [{'text': text}]})
        else:
            raise OllamaError('Vai trò tin nhắn Gemini không hợp lệ.', 502)
    config = {'maxOutputTokens': 512 if schema else settings.GEMINI_MAX_OUTPUT_TOKENS}
    # Disable optional thinking on Flash 2.5 so the output budget covers the answer.
    if model in ('gemini-2.5-flash', 'gemini-2.5-flash-lite'):
        config['thinkingConfig'] = {'thinkingBudget': 0}
    elif model == 'gemini-3.1-flash-lite':
        config['thinkingConfig'] = {'thinkingLevel': 'minimal'}
    if schema:
        config.update(responseMimeType='application/json', responseJsonSchema=schema)
    payload = {'contents': contents, 'generationConfig': config}
    if instructions:
        payload['systemInstruction'] = {'parts': instructions}
    try:
        return requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
            headers={'x-goog-api-key': settings.GEMINI_API_KEY}, json=payload,
            timeout=(min(5,timeout) if timeout else 5, timeout if timeout is not None else settings.GEMINI_TIMEOUT))
    except requests.Timeout as exc:
        raise OllamaError('Gemini phản hồi quá lâu. Vui lòng thử lại.', 504, reason='timeout') from exc
    except requests.RequestException as exc:
        raise OllamaError('Không kết nối được dịch vụ Gemini.', 503, reason='network') from exc


def failure_info(response):
    """Read only safe categories/delays; never log provider messages or credentials."""
    status = response.status_code
    reason = 'rate_limit' if status == 429 else 'overloaded' if status >= 500 else 'configuration'
    delay = None
    try:
        value = float(response.headers.get('Retry-After'))
        if math.isfinite(value) and value >= 0: delay = value
    except (TypeError, ValueError, AttributeError):
        pass
    try:
        body = response.json()
        error = body.get('error', {}) if isinstance(body, dict) else {}
        details = error.get('details', []) if isinstance(error, dict) else []
        if not isinstance(details, list): details = []
        for detail in details:
            if not isinstance(detail, dict): continue
            retry = detail.get('retryDelay', '')
            if isinstance(retry, str) and re.fullmatch(r'\d+(?:\.\d+)?s', retry):
                delay = max(delay or 0, float(retry[:-1]))
            violations = detail.get('violations', [])
            if not isinstance(violations, list): continue
            for violation in violations:
                if not isinstance(violation, dict): continue
                metric = str(violation.get('quotaId', '')) + str(violation.get('quotaMetric', ''))
                if 'perday' in metric.lower() or 'per_day' in metric.lower():
                    reason = 'daily_quota'
        # Zero capacity / billing failures cannot be fixed by retrying immediately.
        message = error.get('message','') if isinstance(error, dict) else ''
        if status == 429 and isinstance(message, str) and re.search(r'limit:\s*0\b', message):
            reason = 'quota_unavailable'
    except (ValueError, TypeError, AttributeError):
        pass
    return reason, delay


def request(messages, *, schema=None):
    key = 'gemini-cooldown:' + hashlib.sha256((settings.GEMINI_MODEL + ':' + settings.GEMINI_API_KEY).encode()).hexdigest()
    cooldown = cache.get(key) if settings.GEMINI_COOLDOWN_ENABLED else None
    if isinstance(cooldown, dict):
        remaining = max(1, math.ceil(cooldown['until']-time.time()))
        raise OllamaError('Gemini đang tạm giới hạn yêu cầu.',503,reason=cooldown['reason'],
                          upstream_status=cooldown['status'],retry_after=remaining)
    start = time.monotonic()
    for attempt in range(min(2, max(0, settings.GEMINI_MAX_RETRIES))+1):
        response = None
        error = None
        try:
            remaining = max(1, settings.GEMINI_RETRY_BUDGET-(time.monotonic()-start)) if attempt else None
            response = _request_once(messages, schema=schema, timeout=min(settings.GEMINI_TIMEOUT,remaining) if remaining is not None else None)
            if response.status_code == 200: return response
            reason, delay = failure_info(response)
            status = response.status_code
            transient = status == 429 or status in (500,502,503,504)
        except OllamaError as exc:
            error = exc
            reason, delay, status = exc.reason, None, exc.upstream_status
            transient = reason in ('network','timeout')
        wait = delay if delay is not None else min(4, 2**attempt) + random.uniform(0,.2)
        retryable = transient and reason not in ('daily_quota','quota_unavailable')
        if (retryable and attempt < min(2, max(0, settings.GEMINI_MAX_RETRIES)) and wait <= 5
                and time.monotonic()-start+wait <= settings.GEMINI_RETRY_BUDGET):
            time.sleep(wait)
            continue
        if transient:
            seconds = max(delay or 0, 300 if reason in ('daily_quota','quota_unavailable') else 60 if status == 429 else 10)
            seconds = min(86400, math.ceil(seconds))
            if settings.GEMINI_COOLDOWN_ENABLED:
                cache.set(key,{'until':time.time()+seconds,'reason':reason,'status':status},timeout=seconds)
            logging.getLogger(__name__).warning('Gemini unavailable: http_status=%s reason=%s cooldown=%ss',status,reason,seconds)
        elif response is not None:
            logging.getLogger(__name__).warning('Gemini request rejected: http_status=%s reason=%s',status,reason)
        if error: raise error
        return response


def chat(messages, *, schema=None):
    response = request(messages, schema=schema)
    if response.status_code in (400, 401, 403):
        raise OllamaError('Kiểm tra key, quyền truy cập và cấu hình Gemini trên máy chủ.', 503,reason='configuration',upstream_status=response.status_code)
    if response.status_code == 404:
        raise OllamaError('Model Gemini chưa khả dụng. Kiểm tra GEMINI_MODEL.', 503,reason='model_unavailable',upstream_status=404)
    if response.status_code == 429:
        reason, delay = failure_info(response)
        raise OllamaError('Gemini đã đạt hạn mức hoặc giới hạn yêu cầu. Vui lòng thử lại sau.', 503,reason=reason,upstream_status=429,retry_after=delay)
    if response.status_code >= 500:
        raise OllamaError('Dịch vụ Gemini tạm thời không khả dụng.', 503,reason='overloaded',upstream_status=response.status_code)
    if response.status_code != 200:
        raise OllamaError('Gemini trả về lỗi yêu cầu.', 502)
    try:
        body = response.json()
        candidate = body['candidates'][0]
        if candidate.get('finishReason') != 'STOP':
            raise ValueError('Incomplete or blocked answer')
        parts = candidate['content']['parts']
        if not isinstance(parts, list):
            raise ValueError('Invalid parts')
        result = '\n'.join(part['text'] for part in parts
                           if isinstance(part, dict) and not part.get('thought')
                           and isinstance(part.get('text'), str)).strip()
        if not result:
            raise ValueError('Empty answer')
        return result
    except (ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
        raise OllamaError('Gemini chưa tạo được câu trả lời đầy đủ. Vui lòng thử lại.', 502,reason='incomplete') from exc
