import re
from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase,override_settings


@override_settings(PASSWORD_RESET_ENABLED=True,EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PasswordResetTests(TestCase):
    def test_reset_token_changes_password_and_is_single_use(self):
        user=User.objects.create_user('recover',email='recover@example.com',password='BeforeReset!782')
        response=self.client.post('/api/auth/password-reset/',{'email':user.email})
        self.assertEqual(response.status_code,302)
        self.assertEqual(len(mail.outbox),1)
        url=re.search(r'https?://[^/]+(/api/auth/reset/[^\s]+)',mail.outbox[0].body).group(1)
        response=self.client.get(url)
        self.assertEqual(response.status_code,302)
        self.client.post(response['Location'],{'new_password1':'AfterReset!6392','new_password2':'AfterReset!6392'})
        user.refresh_from_db(); self.assertTrue(user.check_password('AfterReset!6392'))
        self.assertContains(self.client.get(url),'Liên kết đã hết hạn')

    def test_unknown_email_has_same_redirect_and_sends_no_message(self):
        response=self.client.post('/api/auth/password-reset/',{'email':'missing@example.com'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(response['Location'],'/api/auth/password-reset/done/')
        self.assertEqual(len(mail.outbox),0)

    @override_settings(PASSWORD_RESET_ENABLED=False)
    def test_unconfigured_email_does_not_claim_sent(self):
        self.assertEqual(self.client.get('/api/auth/password-reset/').status_code,503)
