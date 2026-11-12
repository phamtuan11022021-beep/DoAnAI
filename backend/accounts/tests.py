from django.contrib.auth.models import User
from django.test import Client, TestCase


class UnifiedLoginTests(TestCase):
    def setUp(self):
        self.password = 'LoginTestPass!892'
        self.admin = User.objects.create_superuser('admin', password=self.password)
        self.member = User.objects.create_user('member@example.com', email='member@example.com', password=self.password)

    def test_admin_username_uses_shared_csrf_protected_session(self):
        client = Client(enforce_csrf_checks=True)
        client.get('/api/auth/csrf/')
        response = client.post('/api/auth/login/', {
            'identifier': 'admin', 'password': self.password,
        }, content_type='application/json', HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['user']['is_staff'])
        self.assertEqual(client.get('/admin/').status_code, 200)

    def test_email_login_remains_compatible_and_cannot_grant_staff(self):
        for key in ['email', 'identifier']:
            with self.subTest(key=key):
                self.client.logout()
                response = self.client.post('/api/auth/login/', {
                    key: ' MEMBER@EXAMPLE.COM ', 'password': self.password, 'is_staff': True,
                }, content_type='application/json')
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.json()['user']['is_staff'])
                self.assertEqual(self.client.get('/admin/').status_code, 302)

    def test_wrong_password_and_disabled_admin_are_rejected(self):
        for password, active in [('wrong-password', True), (self.password, False)]:
            with self.subTest(active=active):
                self.admin.is_active = active
                self.admin.save(update_fields=['is_active'])
                response = self.client.post('/api/auth/login/', {
                    'identifier': 'admin', 'password': password,
                }, content_type='application/json')
                self.assertEqual(response.status_code, 401)
                self.assertEqual(self.client.get('/admin/').status_code, 302)

    def test_registration_cannot_create_administrator(self):
        response = self.client.post('/api/auth/register/', {
            'name': 'Người dùng mới', 'email': 'new@example.com',
            'password': self.password, 'password_confirm': self.password,
            'is_staff': True, 'is_superuser': True,
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username='new@example.com')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
