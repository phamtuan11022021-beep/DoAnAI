"""Opt-in browser checks against the running Vite app and isolated Django test DB.

python backend/manage.py test social.ui_checks --verbosity 1
"""
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import requests
from pathlib import Path
from PIL import Image
from django.conf import settings
from django.contrib.auth.models import User
from django.test import LiveServerTestCase, override_settings
from playwright.sync_api import sync_playwright, expect
from .models import DirectMessage, Notification, Post


@override_settings(DEBUG=True)
class BrowserWorkflowChecks(LiveServerTestCase):
    def test_connected_advisor_and_community(self):
        alice = User.objects.create_user('ui-alice', first_name='An Nguyễn')
        bob = User.objects.create_user('ui-bob', first_name='Bình Trần')
        self.client.force_login(alice)
        notification_post = Post.objects.create(author=alice, content='Câu hỏi chọn ngành')
        Notification.objects.create(recipient=alice, actor=bob, post=notification_post, kind='comment')
        DirectMessage.objects.create(sender=bob, recipient=alice, content='Chào bạn, cùng tìm hiểu ngành nhé!')
        output = settings.BASE_DIR.parent / 'docs/ui_review_campus'
        output.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as temporary, override_settings(MEDIA_ROOT=temporary):
            photo = Path(temporary) / 'sample.png'
            Image.new('RGB', (640, 400), '#278f9e').save(photo)
            with sync_playwright() as runtime:
                upstream = self.live_server_url
                media_root = Path(temporary)
                class Proxy(SimpleHTTPRequestHandler):
                    def log_message(self, *args): pass
                    def proxy(self):
                        headers = {k:v for k,v in self.headers.items() if k.lower() not in ('host','connection','content-length')}
                        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
                        response = requests.request(self.command, upstream+self.path, data=body,
                                                    headers=headers, timeout=45, allow_redirects=False)
                        self.send_response(response.status_code)
                        for key, value in response.headers.items():
                            if key.lower() not in ('content-length','transfer-encoding','content-encoding','connection','set-cookie'):
                                self.send_header(key,value)
                        for cookie in response.raw.headers.getlist('Set-Cookie'):
                            self.send_header('Set-Cookie',cookie)
                        self.send_header('Content-Length',str(len(response.content)))
                        self.end_headers(); self.wfile.write(response.content)
                    def do_GET(self):
                        if self.path.startswith('/api/'): return self.proxy()
                        if self.path.startswith('/media/'):
                            path = (media_root/self.path.removeprefix('/media/')).resolve()
                            if not path.is_relative_to(media_root.resolve()) or not path.is_file():
                                return self.send_error(404)
                            data = path.read_bytes()
                            self.send_response(200);self.send_header('Content-Type','image/jpeg')
                            self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
                            return
                        return super().do_GET()
                    do_POST = proxy
                    do_PATCH = proxy
                    do_DELETE = proxy
                server = ThreadingHTTPServer(('localhost',0), partial(Proxy,directory=str(settings.BASE_DIR.parent/'frontend/dist')))
                threading.Thread(target=server.serve_forever,daemon=True).start()
                self.addCleanup(server.server_close)
                self.addCleanup(server.shutdown)
                origin = f'http://localhost:{server.server_port}'
                trusted = override_settings(CSRF_TRUSTED_ORIGINS=[origin])
                trusted.enable(); self.addCleanup(trusted.disable)
                browser = runtime.chromium.launch(headless=True, channel='chrome')
                context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                context.add_cookies([{'name': 'sessionid', 'value': self.client.cookies['sessionid'].value,
                                     'domain': 'localhost', 'path': '/'}])
                page = context.new_page()
                failures = []
                page.on('pageerror', lambda error: failures.append(str(error)))
                page.goto(origin, wait_until='networkidle')
                expect(page.locator('.profile-button')).to_contain_text('An Nguyễn')
                page.locator('.advisor-form input[type=number]').fill('25')
                page.locator('.advisor-form select').nth(0).select_option('A01')
                page.locator('.advisor-form label.wide input').fill('Quản trị kinh doanh')
                page.locator('.advisor-form select').nth(1).select_option('Hồ Chí Minh')
                page.locator('.analyze-btn').click()
                expect(page.locator('.match-card').first).to_be_visible(timeout=30000)
                self.assertGreaterEqual(page.locator('.match-card').count(), 3)
                expect(page.locator('.advisor-alternatives')).to_be_visible()
                page.evaluate('window.scrollTo(0,0)')
                page.screenshot(path=str(output/'advisor-desktop.png'), full_page=True)
                page.locator('.profile-button').click()
                page.get_by_role('button', name='Hồ sơ cá nhân', exact=True).click()
                page.locator('.profile-editor input[type=file]').set_input_files(str(photo))
                expect(page.locator('.profile-big-avatar img')).to_be_visible(timeout=10000)
                page.locator('.profile-editor-head .icon-btn').click()
                page.get_by_role('button', name='Feed cộng đồng', exact=False).first.click()
                page.get_by_role('button', name='Tạo bài viết', exact=False).first.click()
                page.locator('.standard-modal textarea').fill('Chia sẻ kinh nghiệm chọn ngành từ kiểm thử giao diện')
                page.locator('.standard-modal input[type=file]').set_input_files(str(photo))
                page.get_by_role('button', name='Tạo bình chọn', exact=True).click()
                page.get_by_placeholder('Lựa chọn 1').fill('Công nghệ thông tin')
                page.get_by_placeholder('Lựa chọn 2').fill('Marketing')
                page.get_by_role('button', name='Đăng bài', exact=True).click()
                expect(page.locator('.post-gallery img').first).to_be_visible(timeout=15000)
                expect(page.locator('.post-poll').first).to_be_visible()
                page.locator('.post-poll button').first.click()
                expect(page.locator('.post-poll').first).to_contain_text('1 lượt bình chọn')
                page.locator('.post-card').first.locator('.post-menu-wrap .icon-btn').click()
                page.get_by_role('button', name='Chỉnh sửa bài viết', exact=True).click()
                page.locator('.standard-modal textarea').fill('Kinh nghiệm chọn ngành đã cập nhật sau khi trao đổi')
                page.get_by_role('button', name='Lưu thay đổi', exact=True).click()
                expect(page.locator('.post-card').first).to_contain_text('đã cập nhật sau khi trao đổi')
                page.evaluate('window.scrollTo(0,0)')
                page.screenshot(path=str(output/'community-desktop.png'), full_page=True)
                page.get_by_role('button', name='Tin nhắn', exact=True).click()
                expect(page.locator('.community-inbox')).to_contain_text('Chào bạn')
                page.locator('.thread-item').filter(has_text='Bình Trần').first.click()
                page.get_by_label('Nội dung tin nhắn').fill('Cảm ơn bạn, mình đang tìm hiểu CNTT.')
                page.get_by_role('button', name='Gửi tin nhắn', exact=True).click()
                expect(page.locator('.direct-message.mine')).to_contain_text('Cảm ơn bạn')
                page.get_by_role('button', name='Đóng hộp thư', exact=True).click()
                page.set_viewport_size({'width':390,'height':844})
                page.wait_for_function("document.querySelector('.left-sidebar').getBoundingClientRect().right <= 0")
                expect(page.locator('.profile-button')).to_be_visible()
                page.evaluate('window.scrollTo(0,0)')
                page.screenshot(path=str(output/'community-mobile.png'), full_page=True)
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 391)
                page.locator('.post-card').first.locator('.post-menu-wrap .icon-btn').click()
                page.get_by_role('button', name='Xóa bài viết', exact=True).click()
                page.locator('.standard-modal').get_by_role('button', name='Xóa bài viết', exact=True).click()
                expect(page.locator('.post-card')).to_have_count(1)
                self.assertEqual(failures, [])
                browser.close()
        self.assertTrue(DirectMessage.objects.filter(sender=alice, recipient=bob).exists())
