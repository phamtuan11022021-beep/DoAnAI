"""Database-backed fixed windows shared across web workers; never store raw IPs."""
import time
from datetime import datetime, timezone

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils.crypto import salted_hmac

from .models import RequestBucket


def consume(scope, identity, limit, period, now=None):
    now = time.time() if now is None else now
    window = int(now // period)
    key = salted_hmac('request-limit', f'{scope}:{identity}:{window}', algorithm='sha256').hexdigest()
    with transaction.atomic():
        bucket, _ = RequestBucket.objects.select_for_update().get_or_create(
            key=key, defaults={'expires_at': datetime.fromtimestamp((window+1)*period, tz=timezone.utc)})
        if bucket.count >= limit:
            return max(1, int((window+1)*period-now)+1)
        bucket.count += 1
        bucket.save(update_fields=['count'])
    return 0


class RequestLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method != 'POST' or not settings.REQUEST_LIMITS_ENABLED:
            return self.get_response(request)
        ip = request.META.get('REMOTE_ADDR', '')
        rules = []
        if request.path in ('/api/auth/login/', '/admin/login/'):
            rules.append(('login-ip', ip, settings.LOGIN_REQUESTS_PER_MINUTE, 60))
        elif request.path in ('/api/auth/register/', '/api/auth/password-reset/'):
            rules.append(('register-ip', ip, 5, 600))
        elif request.path == '/api/ai-chat/chat/':
            identity = f'user:{request.user.pk}' if request.user.is_authenticated else f'ip:{ip}'
            rules.extend([('chat-user', identity, settings.CHAT_REQUESTS_PER_MINUTE, 60),
                          ('chat-ip', ip, settings.CHAT_IP_REQUESTS_PER_MINUTE, 60)])
        for scope, identity, limit, period in rules:
            retry = consume(scope, identity, limit, period)
            if retry:
                response = JsonResponse({'success':False,'error':'Bạn thao tác quá nhanh. Vui lòng thử lại sau.',
                                         'retry_after':retry}, status=429)
                response['Retry-After'] = str(retry)
                return response
        return self.get_response(request)
