import os
from io import StringIO
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission, User
from django.core.files.base import ContentFile
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from config.database import database_config
from social.models import Post, PostImage


class DatabaseSettingsTests(SimpleTestCase):
    def test_mysql_unicode_strict_mode_and_no_fallback(self):
        config = database_config(Path('.'), {'DB_ENGINE': 'mysql', 'MYSQL_DATABASE': 'demo', 'MYSQL_USER': 'app'})
        self.assertEqual(config['OPTIONS']['charset'], 'utf8mb4')
        self.assertIn('STRICT_TRANS_TABLES', config['OPTIONS']['init_command'])
        self.assertEqual(config['OPTIONS']['isolation_level'], 'read committed')
        with self.assertRaisesMessage(ImproperlyConfigured, 'MYSQL_DATABASE'):
            database_config(Path('.'), {'DB_ENGINE': 'mysql'})

    def test_explicit_sqlite_override(self):
        config = database_config(Path('.'), {'DB_ENGINE': 'sqlite', 'MYSQL_DATABASE': 'demo', 'SQLITE_PATH': 'test.db'})
        self.assertEqual(config['ENGINE'], 'django.db.backends.sqlite3')
        self.assertEqual(config['NAME'], 'test.db')


class AdminDashboardTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser('owner', password='OwnerTestPass!892')
        self.member = User.objects.create_user('member', password='MemberTestPass!892')
        self.staff = User.objects.create_user('moderator', is_staff=True)
        self.post = Post.objects.create(author=self.member, content='Chọn ngành tiếng Việt 🎓')

    def test_dashboard_is_restricted_and_superuser_sees_totals(self):
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 302)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 302)
        self.client.force_login(self.owner)
        response = self.client.get(reverse('admin:index'))
        self.assertContains(response, 'Bạn muốn làm gì?')
        self.assertEqual(len(response.context['dashboard_cards']), 4)
        self.assertContains(response, 'Chọn ngành tiếng Việt 🎓')

    def test_staff_only_sees_authorized_data(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.context['dashboard_cards'], [])
        self.assertNotContains(response, self.post.content)
        self.staff.user_permissions.add(Permission.objects.get(codename='view_post'))
        response = self.client.get(reverse('admin:index'))
        self.assertEqual([card['label'] for card in response.context['dashboard_cards']], ['Bài viết cộng đồng'])
        self.assertContains(response, self.post.content)
        self.assertNotContains(response, 'Độ phủ dữ liệu tuyển sinh')
        self.assertEqual(self.client.get(reverse('admin:auth_user_changelist')).status_code, 403)

    def test_groups_are_idempotent_without_promoting_users(self):
        for _ in range(2):
            call_command('setup_admin_roles', stdout=StringIO())
        group = Group.objects.get(name='Kiểm duyệt cộng đồng')
        self.assertTrue(group.permissions.filter(codename='delete_post').exists())
        self.assertFalse(group.permissions.filter(content_type__app_label='auth').exists())
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_staff)

    def test_moderator_can_delete_post_and_attached_file(self):
        self.staff.user_permissions.add(*Permission.objects.filter(codename__in=['view_post', 'delete_post', 'delete_postimage']))
        self.client.force_login(self.staff)
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            attachment = PostImage.objects.create(post=self.post, image=ContentFile(b'image', name='sample.jpg'))
            file_path = Path(attachment.image.path)
            self.assertTrue(file_path.exists())
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(reverse('admin:social_post_delete', args=[self.post.pk]), {'post': 'yes'})
            self.assertEqual(response.status_code, 302)
            self.assertFalse(Post.objects.filter(pk=self.post.pk).exists())
            self.assertFalse(file_path.exists())

    def test_edit_post_keeps_read_only_image_attachment(self):
        self.client.force_login(self.owner)
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            image = PostImage.objects.create(post=self.post, image=ContentFile(b'image', name='sample.jpg'))
            response = self.client.get(reverse('admin:social_post_change', args=[self.post.pk]))
            self.assertContains(response, 'name="images-TOTAL_FORMS"')
            self.assertContains(response, f'name="images-0-id" value="{image.pk}"')
            response = self.client.post(reverse('admin:social_post_change', args=[self.post.pk]), {
                'content': 'Nội dung đã chỉnh sửa', 'category': 'general', 'tag': '',
                'images-TOTAL_FORMS': '1', 'images-INITIAL_FORMS': '1',
                'images-MIN_NUM_FORMS': '0', 'images-MAX_NUM_FORMS': '1000',
                'images-0-id': str(image.pk), 'images-0-post': str(self.post.pk), '_save': 'Lưu',
            })
            self.assertEqual(response.status_code, 302)
            self.post.refresh_from_db()
            self.assertEqual(self.post.content, 'Nội dung đã chỉnh sửa')
            self.assertTrue(PostImage.objects.filter(pk=image.pk).exists())

    def test_navigation_focuses_on_tasks_and_hides_technical_tables(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('admin:index'))
        urls = {item['url'] for item in response.context['admin_navigation']}
        self.assertIn(reverse('admin:auth_user_changelist'), urls)
        self.assertIn(reverse('admin:social_post_changelist'), urls)
        self.assertNotIn(reverse('admin:social_postlike_changelist'), urls)
        self.assertNotIn(reverse('admin:ai_chat_aichatmessage_changelist'), urls)
        self.assertNotContains(response, 'Database:')
        self.assertNotContains(response, 'Độ phủ dữ liệu tuyển sinh')

    def test_ai_transcript_is_readable_escaped_and_cannot_be_edited(self):
        from ai_chat.models import AIChatSession, AIChatMessage
        conversation = AIChatSession.objects.create(user=self.member, title='Chọn ngành phù hợp')
        message = AIChatMessage.objects.create(conversation=conversation, role='user', content='<script>alert(1)</script>')
        self.staff.user_permissions.add(Permission.objects.get(codename='view_aichatsession'))
        self.client.force_login(self.staff)
        url = reverse('admin:ai_chat_aichatsession_change', args=[conversation.pk])
        response = self.client.get(url)
        self.assertContains(response, 'Người hỏi')
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertEqual(self.client.post(url, {'title': 'Changed'}).status_code, 403)
        message.refresh_from_db()
        self.assertEqual(message.content, '<script>alert(1)</script>')

    def test_career_results_are_readable_and_read_only_for_owner(self):
        from career.models import CareerAssessment
        result = CareerAssessment.objects.create(user=self.member, holland_code='IAS',
            scores={'I': {'percent': 75}}, suggested_majors=[{'major_name': '<script>bad()</script>'}])
        self.client.force_login(self.owner)
        url = reverse('admin:career_careerassessment_change', args=[result.pk])
        response = self.client.get(url)
        self.assertContains(response, '75%')
        self.assertContains(response, '&lt;script&gt;bad()&lt;/script&gt;')
        self.assertNotContains(response, '<script>bad()</script>')
        self.assertEqual(self.client.post(url, {'holland_code': 'AAA'}).status_code, 403)
        result.refresh_from_db()
        self.assertEqual(result.holland_code, 'IAS')

    def test_member_manager_cannot_grant_administrator_privileges(self):
        self.staff.user_permissions.add(*Permission.objects.filter(codename__in=['view_user', 'change_user']))
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('admin:auth_user_change', args=[self.owner.pk])).status_code, 302)
        url = reverse('admin:auth_user_change', args=[self.member.pk])
        response = self.client.post(url, {'username': self.member.username, 'first_name': 'Member',
                                        'last_name': '', 'email': '', 'is_active': 'on',
                                        'is_staff': 'on', 'is_superuser': 'on', '_save': 'Lưu'})
        self.assertEqual(response.status_code, 302)
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_staff)
        self.assertFalse(self.member.is_superuser)


@skipUnless(connection.vendor == 'mysql', 'Requires MySQL destination')
class SQLiteTransferTests(TransactionTestCase):
    def test_unicode_password_permissions_and_relations_survive_transfer(self):
        project = Path(__file__).resolve().parents[2]
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source.sqlite3'
            env = {**os.environ, 'DB_ENGINE': 'sqlite', 'SQLITE_PATH': str(source), 'PYTHONUTF8': '1'}
            seed = '''
from django.core.management import call_command
from django.contrib.auth.models import User, Group, Permission
from social.models import Post, PollVote
call_command('migrate', verbosity=0)
user = User.objects.create_user('transfer-user', password='TransferPass!892', first_name='Nguyễn 🎓')
group = Group.objects.create(name='Nguồn SQLite')
group.permissions.add(Permission.objects.get(codename='view_post'))
user.groups.add(group)
post = Post.objects.create(author=user, content='Tư vấn đại học 🎓', poll_options=['Có', 'Không'])
PollVote.objects.create(post=post, user=user, option=0)
'''
            subprocess.run([sys.executable, '-X', 'utf8', str(project / 'backend/manage.py'), 'shell', '-c', seed],
                           env=env, check=True, capture_output=True)
            with override_settings(BASE_DIR=root / 'backend'), patch.object(type(self), 'databases', self.databases | {'sqlite_import_source'}):
                call_command('import_sqlite', source=source, stdout=StringIO())
                user = User.objects.get(username='transfer-user')
                self.assertTrue(user.check_password('TransferPass!892'))
                self.assertEqual(user.first_name, 'Nguyễn 🎓')
                self.assertTrue(user.has_perm('social.view_post'))
                post = Post.objects.get(author=user)
                self.assertEqual(post.content, 'Tư vấn đại học 🎓')
                self.assertEqual(post.poll_options, ['Có', 'Không'])
                self.assertEqual(post.votes.get().user_id, user.pk)
                self.assertEqual(len(list((root / 'backups').glob('before_mysql_*.sqlite3'))), 1)
                with self.assertRaisesMessage(CommandError, 'not empty'):
                    call_command('import_sqlite', source=source, stdout=StringIO())
                self.assertEqual(User.objects.count(), 1)
