from datetime import timedelta

from django.contrib.admin import AdminSite
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone


# Hide technical tables from navigation, keeping their existing permissions,
# deletion collection and autocomplete endpoints intact.
ADMIN_SECTIONS = (
    ('auth.user', 'Thành viên', 'Quản lý tài khoản và trạng thái hoạt động', 'users'),
    ('accounts.profile', 'Hồ sơ & mentor', 'Xem mục tiêu học tập và vai trò mentor', 'profile'),
    ('social.post', 'Bài viết', 'Tìm và kiểm duyệt nội dung cộng đồng', 'posts'),
    ('social.comment', 'Bình luận', 'Xem và xử lý bình luận trong cộng đồng', 'comments'),
    ('ai_chat.aichatsession', 'Tư vấn AI', 'Đọc lại các cuộc trao đổi với trợ lý AI', 'chat'),
    ('career.careerassessment', 'Hướng nghiệp', 'Xem kết quả và nhóm ngành được gợi ý', 'compass'),
    ('auth.group', 'Phân quyền', 'Thiết lập quyền cho người quản trị', 'shield'),
    ('catalog.admissionrelease', 'Dữ liệu tuyển sinh', 'Nhập tệp, đối chiếu nguồn và công bố dữ liệu', 'compass'),
)


class UniConnectAdminSite(AdminSite):
    site_header = 'UniConnect AI'
    site_title = 'Quản trị UniConnect AI'
    index_title = 'Tổng quan'
    index_template = 'admin/uniconnect_index.html'
    site_url = '/'

    def get_app_list(self, request, app_label=None):
        labels = {label: name for label, name, *_ in ADMIN_SECTIONS}
        result = []
        for app in super().get_app_list(request, app_label):
            models = []
            for model in app['models']:
                label = f"{app['app_label']}.{model['object_name'].lower()}"
                if label in labels:
                    model['name'] = labels[label]
                    models.append(model)
            if models:
                app['models'] = models
                result.append(app)
        return result

    def each_context(self, request):
        from django.apps import apps

        context = super().each_context(request)
        navigation = []
        if self.has_permission(request):
            for label, name, description, icon in ADMIN_SECTIONS:
                model = apps.get_model(label)
                model_admin = self._registry.get(model)
                if model_admin and model_admin.has_view_permission(request):
                    url = reverse(f'admin:{model._meta.app_label}_{model._meta.model_name}_changelist')
                    navigation.append({'name': name, 'description': description, 'url': url,
                                       'icon': icon, 'advanced': label == 'auth.group',
                                       'active': request.path.startswith(url)})
        context['admin_navigation'] = navigation
        context['admin_is_home'] = request.path == reverse('admin:index')
        return context

    def index(self, request, extra_context=None):
        from ai_chat.models import AIChatSession
        from social.models import Comment, Post

        week_start = timezone.now() - timedelta(days=7)
        cards = []
        for model, label, date_field, icon in [
            (get_user_model(), 'Thành viên', 'date_joined', 'users'),
            (Post, 'Bài viết cộng đồng', 'created_at', 'posts'),
            (Comment, 'Bình luận', 'created_at', 'comments'),
            (AIChatSession, 'Cuộc tư vấn AI', 'created_at', 'chat'),
        ]:
            model_admin = self._registry.get(model)
            if model_admin and model_admin.has_view_permission(request):
                queryset = model_admin.get_queryset(request)
                cards.append({'label': label, 'count': queryset.count(), 'icon': icon,
                              'recent': queryset.filter(**{f'{date_field}__gte': week_start}).count(),
                              'url': reverse(f'admin:{model._meta.app_label}_{model._meta.model_name}_changelist')})
        context = {'dashboard_cards': cards}
        post_admin = self._registry.get(Post)
        if post_admin and post_admin.has_view_permission(request):
            context['can_view_posts'] = True
            context['latest_posts'] = post_admin.get_queryset(request).select_related('author').order_by('-created_at')[:5]
        context.update(extra_context or {})
        return super().index(request, extra_context=context)
