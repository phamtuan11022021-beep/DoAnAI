import json
from unittest.mock import patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase,TestCase,override_settings

from .gemini_client import chat
from .ollama_client import OllamaError
from .service import respond


def response(status,body,headers=None):
    result=requests.Response()
    result.status_code=status
    result._content=json.dumps(body).encode()
    result.headers.update(headers or {})
    return result


OK={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'OK'}]}}]}


@override_settings(CHAT_PROVIDER='gemini',GEMINI_API_KEY='test-private-key',GEMINI_MODEL='gemini-3.1-flash-lite',
                   GEMINI_MAX_RETRIES=2,GEMINI_RETRY_BUDGET=8,GEMINI_COOLDOWN_ENABLED=True)
class GeminiResilienceTests(SimpleTestCase):
    def setUp(self): cache.clear()
    def tearDown(self): cache.clear()

    @patch('ai_chat.gemini_client.time.sleep')
    @patch('ai_chat.gemini_client.requests.post')
    def test_transient_error_then_success_and_minimal_thinking(self,post,sleep):
        post.side_effect=[response(503,{}),response(200,OK)]
        self.assertEqual(chat([{'role':'user','content':'Chào'}]),'OK')
        self.assertEqual(post.call_count,2)
        self.assertEqual(sleep.call_count,1)
        config=post.call_args.kwargs['json']['generationConfig']
        self.assertEqual(config['thinkingConfig'],{'thinkingLevel':'minimal'})

    @patch('ai_chat.gemini_client.time.sleep')
    @patch('ai_chat.gemini_client.requests.post')
    def test_long_retry_after_does_not_block_request_and_cools_down(self,post,sleep):
        post.return_value=response(429,{'error':{'details':[{'retryDelay':'60s'}]}})
        with self.assertRaises(OllamaError) as first: chat([])
        self.assertEqual(first.exception.reason,'rate_limit')
        with self.assertRaises(OllamaError) as second: chat([])
        self.assertEqual(second.exception.upstream_status,429)
        self.assertGreater(second.exception.retry_after,0)
        self.assertEqual(post.call_count,1)
        sleep.assert_not_called()
        self.assertNotIn('test-private-key',str(second.exception))

    @patch('ai_chat.gemini_client.time.sleep')
    @patch('ai_chat.gemini_client.requests.post')
    def test_daily_quota_is_not_retried(self,post,sleep):
        post.return_value=response(429,{'error':{'details':[{'violations':[{'quotaId':'GenerateRequestsPerDayPerProjectPerModel'}]}]}})
        with self.assertRaises(OllamaError) as caught: chat([])
        self.assertEqual(caught.exception.reason,'daily_quota')
        self.assertEqual(post.call_count,1)
        sleep.assert_not_called()

    @patch('ai_chat.gemini_client.time.sleep')
    @patch('ai_chat.gemini_client.requests.post')
    def test_authentication_failure_is_not_retried(self,post,sleep):
        post.return_value=response(403,{})
        with self.assertRaises(OllamaError) as caught: chat([])
        self.assertEqual(caught.exception.reason,'configuration')
        self.assertEqual(post.call_count,1)
        sleep.assert_not_called()

    @patch('ai_chat.gemini_client.time.monotonic',side_effect=[0,10])
    @patch('ai_chat.gemini_client.time.sleep')
    @patch('ai_chat.gemini_client.requests.post',side_effect=requests.Timeout())
    def test_slow_timeout_does_not_trigger_a_retry_storm(self,post,sleep,clock):
        with self.assertRaises(OllamaError) as caught: chat([])
        self.assertEqual(caught.exception.reason,'timeout')
        self.assertEqual(post.call_count,1)
        sleep.assert_not_called()


class ConversationQualityTests(TestCase):
    @patch('ai_chat.service.chat')
    def test_greeting_and_weather_work_without_provider_and_do_not_repeat_profile(self,provider):
        previous=dict(score=22,combination='A01',major='Kiến trúc',city='Hồ Chí Minh')
        for message in ['hello','thời tiết hôm nay','thời tiết Đà Nẵng hôm nay']:
            result=respond(message=message,previous_context=previous,ui_context={})
            self.assertNotIn('Kiến trúc',result['text'])
            self.assertNotIn('Engine',result['text'])
            self.assertNotIn('không khả dụng',result['text'])
            self.assertEqual(result['diagnostics']['answer_mode'],'local')
            self.assertEqual(result['context']['city'],'Hồ Chí Minh')
        provider.assert_not_called()

    @patch('ai_chat.service.chat')
    def test_friend_profile_does_not_inherit_major_combination_or_city(self,provider):
        result=respond(message='tôi có bạn thi được 25 điểm chọn nhành nào',
            previous_context=dict(score=22,combination='A01',major='Kiến trúc',city='Hồ Chí Minh'),
            ui_context=dict(score=22,combination='A01',major='Kiến trúc',city='Hồ Chí Minh'))
        self.assertEqual(result['intent'],'clarification')
        self.assertEqual(result['context']['score'],25)
        self.assertEqual(result['context']['major'],'')
        self.assertEqual(result['context']['combination'],'')
        self.assertEqual(result['context']['city'],'')
        self.assertEqual(result['context']['school_key'],'')
        self.assertNotIn('Kiến trúc',result['text'])
        self.assertNotIn('A01',result['text'])
        self.assertIn('thích',result['text'])
        provider.assert_not_called()

    @patch('ai_chat.service.chat',return_value='Điểm chuẩn là 15.')
    def test_clear_history_question_uses_one_provider_call(self,provider):
        result=respond(message='Điểm CNTT Đại học Tân Tạo năm 2026',previous_context={},ui_context={})
        self.assertEqual(provider.call_count,1)
        self.assertEqual(result['diagnostics']['route_mode'],'local')
        self.assertEqual(result['cards'][0]['history']['2026']['cutoff_score'],15)

    @patch('ai_chat.service.chat',side_effect=OllamaError('busy',503,reason='rate_limit',upstream_status=429,retry_after=30))
    def test_outage_keeps_verified_evidence_without_repeated_error_paragraph(self,provider):
        result=respond(message='Điểm CNTT Đại học Tân Tạo năm 2026',previous_context={},ui_context={})
        self.assertEqual(result['diagnostics']['provider_reason'],'rate_limit')
        self.assertEqual(result['diagnostics']['upstream_status'],429)
        self.assertEqual(result['cards'][0]['history']['2026']['cutoff_score'],15)
        self.assertNotIn('không khả dụng',result['text'])
