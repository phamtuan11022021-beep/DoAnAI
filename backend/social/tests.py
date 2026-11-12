import json
import tempfile
from io import BytesIO

from PIL import Image
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from accounts.models import Profile
from .models import DirectMessage, Notification, Post, PostImage


def image_upload():
    data = BytesIO()
    Image.new('RGB', (40, 30), 'blue').save(data, 'PNG')
    return SimpleUploadedFile('photo.png', data.getvalue(), content_type='image/png')


class CommunityTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.media = override_settings(MEDIA_ROOT=self.temp.name)
        self.media.enable()
        self.addCleanup(self.media.disable)
        self.alice = User.objects.create_user('alice', password='demo-password-482')
        self.bob = User.objects.create_user('bob', password='demo-password-483')
        self.eve = User.objects.create_user('eve', password='demo-password-484')
        self.client.force_login(self.alice)

    def post_json(self, url, data):
        return self.client.post(url, json.dumps(data), content_type='application/json')

    def test_upload_post_poll_and_share_detail(self):
        response = self.client.post('/api/social/posts/', {
            'content': 'Cùng chọn ngành nhé', 'images': [image_upload()],
            'poll_options': json.dumps(['CNTT', 'Marketing'])})
        self.assertEqual(response.status_code, 201)
        post = response.json()['post']
        self.assertEqual(len(post['images']), 1)
        self.assertTrue(post['images'][0]['url'].endswith('.jpg'))
        vote = self.post_json(f"/api/social/posts/{post['id']}/vote/", {'option': 0})
        self.assertEqual(vote.json()['poll']['total'], 1)
        vote = self.post_json(f"/api/social/posts/{post['id']}/vote/", {'option': 1})
        self.assertEqual(vote.json()['poll']['total'], 1)
        self.assertEqual(vote.json()['poll']['my_vote'], 1)
        self.assertEqual(self.client.get(f"/api/social/posts/?post={post['id']}").json()['count'], 1)

    def test_spoofed_images_and_bad_poll_do_not_create_posts(self):
        bad = SimpleUploadedFile('pretend.jpg', b'<script>not an image</script>', content_type='image/jpeg')
        self.assertEqual(self.client.post('/api/social/posts/', {'content': 'Test', 'images': bad}).status_code, 400)
        self.assertEqual(Post.objects.count(), 0)
        self.assertEqual(PostImage.objects.count(), 0)
        for options in (['same', 'SAME'], ['Only one'], None, [1, 2]):
            result = self.post_json('/api/social/posts/', {'content': 'Test', 'poll_options': options})
            self.assertEqual(result.status_code, 400)

    def test_edit_delete_permissions_and_media_cleanup(self):
        post = Post.objects.create(author=self.alice, content='Original')
        self.client.force_login(self.bob)
        url = f'/api/social/posts/{post.id}/'
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.assertEqual(self.client.patch(url, json.dumps({'content': 'Hijack'}), content_type='application/json').status_code, 403)
        self.client.force_login(self.alice)
        result = self.client.patch(url, json.dumps({'content': 'Updated'}), content_type='application/json')
        self.assertEqual(result.json()['post']['content'], 'Updated')
        media = PostImage.objects.create(post=post, image=image_upload())
        name, storage = media.image.name, media.image.storage
        self.assertTrue(storage.exists(name))
        self.assertEqual(self.client.delete(url).status_code, 200)
        self.assertFalse(storage.exists(name))

    def test_notifications_only_for_recipient_and_read_action(self):
        post = Post.objects.create(author=self.alice, content='Question')
        self.client.force_login(self.bob)
        self.post_json(f'/api/social/posts/{post.id}/comments/', {'content': 'Reply'})
        self.post_json(f'/api/social/posts/{post.id}/like/', {})
        self.assertEqual(self.client.get('/api/social/notifications/').json()['unread'], 0)
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get('/api/social/notifications/').json()['unread'], 2)
        self.post_json('/api/social/notifications/', {})
        self.assertEqual(self.client.get('/api/social/notifications/').json()['unread'], 0)

    def test_messages_private_and_read_marks_scoped_to_recipient(self):
        self.post_json(f'/api/social/messages/{self.bob.id}/', {'content': 'Private hello'})
        self.client.force_login(self.eve)
        self.assertEqual(self.client.get('/api/social/inbox/').json()['threads'], [])
        self.assertEqual(self.client.get(f'/api/social/messages/{self.alice.id}/').json()['messages'], [])
        self.post_json(f'/api/social/messages/{self.alice.id}/read/', {})
        self.assertFalse(DirectMessage.objects.get().read)
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get('/api/social/inbox/').json()['unread'], 1)
        self.post_json(f'/api/social/messages/{self.alice.id}/read/', {})
        self.assertEqual(self.client.get('/api/social/inbox/').json()['unread'], 0)

    def test_avatar_upload_visible_in_auth_and_community(self):
        result = self.client.post('/api/auth/avatar/', {'avatar': image_upload()})
        self.assertEqual(result.status_code, 200)
        url = result.json()['user']['avatar_url']
        self.assertTrue(url.startswith('/media/avatars/'))
        profile = Profile.objects.get(user=self.alice)
        with Image.open(profile.avatar.path) as image:
            self.assertEqual(image.size, (512, 512))
        post = self.post_json('/api/social/posts/', {'content': 'With avatar'}).json()['post']
        self.assertEqual(post['author']['avatar_url'], url)

    def test_authentication_and_csrf_are_required_for_writes(self):
        self.client.logout()
        for url in ('/api/auth/avatar/', '/api/social/posts/', '/api/social/notifications/',
                    f'/api/social/messages/{self.bob.id}/'):
            self.assertEqual(self.client.post(url, {}).status_code, 401)
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.alice)
        self.assertEqual(secure.post('/api/social/posts/', {'content': 'Rejected'}).status_code, 403)
