from django.test import TestCase,override_settings
from unittest.mock import patch

from .models import RequestBucket
from .rate_limit import consume


class LimitTests(TestCase):
    def test_fixed_window_and_private_identity(self):
        self.assertEqual(consume('chat','192.0.2.1',2,60,now=120),0)
        self.assertEqual(consume('chat','192.0.2.1',2,60,now=121),0)
        self.assertGreater(consume('chat','192.0.2.1',2,60,now=122),0)
        self.assertEqual(consume('chat','192.0.2.1',2,60,now=180),0)
        self.assertFalse(RequestBucket.objects.filter(key__contains='192.0.2.1').exists())

    @override_settings(LOGIN_REQUESTS_PER_MINUTE=2)
    def test_login_429_has_retry_header_and_spoofed_proxy_does_not_bypass(self):
        for _ in range(2):
            self.assertEqual(self.client.post('/api/auth/login/',data='{}',content_type='application/json').status_code,401)
        result=self.client.post('/api/auth/login/',data='{}',content_type='application/json',HTTP_X_FORWARDED_FOR='198.51.100.2')
        self.assertEqual(result.status_code,429)
        self.assertIn('Retry-After',result)

    @override_settings(CHAT_REQUESTS_PER_MINUTE=1)
    @patch('ai_chat.views.respond')
    def test_chat_limit_runs_before_second_provider_call(self,respond):
        respond.return_value={'intent':'greeting','text':'Chào bạn','cards':[],'context':{},'suggestions':[]}
        self.client.post('/api/ai-chat/chat/',data={'message':'Chào'},content_type='application/json')
        response=self.client.post('/api/ai-chat/chat/',data={'message':'Chào'},content_type='application/json')
        self.assertEqual(response.status_code,429)
        self.assertEqual(respond.call_count,1)
