"""Presentation helpers independent of database models and permissions."""
from django.contrib import admin
from django.utils import timezone


FIELD_LABELS = {
    'author': 'Người đăng', 'user': 'Thành viên', 'post': 'Bài viết', 'content': 'Nội dung',
    'category': 'Chuyên mục', 'tag': 'Hashtag', 'poll_options': 'Các lựa chọn bình chọn',
    'role': 'Vai trò', 'expected_score': 'Điểm dự kiến', 'target_combination': 'Tổ hợp xét tuyển',
    'target_major': 'Ngành quan tâm', 'city': 'Khu vực mong muốn', 'bio': 'Giới thiệu',
    'avatar': 'Ảnh đại diện', 'title': 'Tiêu đề', 'context': 'Ngữ cảnh tư vấn',
    'session_key': 'Mã phiên', 'created_at': 'Ngày tạo', 'updated_at': 'Cập nhật gần nhất',
    'is_active': 'Trạng thái hoạt động', 'is_staff': 'Quyền quản trị',
}


class FriendlyAdminMixin:
    list_per_page = 20
    list_max_show_all = 100
    view_title = ''
    view_description = ''

    def get_changelist_instance(self, request):
        changelist = super().get_changelist_instance(request)
        for spec in changelist.filter_specs:
            field_path = getattr(spec, 'field_path', '')
            spec.title = FIELD_LABELS.get(field_path, spec.title)
        return changelist

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            function, name, _ = actions['delete_selected']
            actions['delete_selected'] = (function, name, 'Xóa các mục đã chọn')
        return actions

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, extra_context={
            'title': self.view_title, 'admin_description': self.view_description,
            **(extra_context or {}),
        })

    def change_view(self, request, object_id, form_url='', extra_context=None):
        return super().change_view(request, object_id, form_url, extra_context={
            'title': self.view_title, 'admin_description': self.view_description,
            **(extra_context or {}),
        })

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if field is not None and db_field.name in FIELD_LABELS:
            field.label = FIELD_LABELS[db_field.name]
        return field

    @admin.display(description='Ngày tạo', ordering='created_at')
    def created_time(self, obj):
        return timezone.localtime(obj.created_at).strftime('%d/%m/%Y · %H:%M')

    @admin.display(description='Cập nhật gần nhất', ordering='updated_at')
    def updated_time(self, obj):
        return timezone.localtime(obj.updated_at).strftime('%d/%m/%Y · %H:%M')
