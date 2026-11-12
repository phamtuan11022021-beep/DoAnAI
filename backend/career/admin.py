from django.contrib import admin
from django.utils.html import format_html_join

from config.admin_ui import FriendlyAdminMixin
from .models import CareerAssessment


DIMENSIONS = {'R': 'Thực tế', 'I': 'Nghiên cứu', 'A': 'Nghệ thuật',
              'S': 'Xã hội', 'E': 'Quản lý', 'C': 'Nghiệp vụ'}


@admin.register(CareerAssessment)
class CareerAssessmentAdmin(FriendlyAdminMixin, admin.ModelAdmin):
    change_form_template = 'admin/uniconnect_readonly.html'
    view_title = 'Kết quả hướng nghiệp'
    view_description = 'Xem kết quả trắc nghiệm và các ngành được gợi ý cho thành viên.'
    search_help_text = 'Tìm theo tên thành viên hoặc mã tính cách, ví dụ IAS.'
    list_select_related = ('user',)
    list_display = ('member_name', 'personality_code', 'created_time')
    search_fields = ('user__username', 'user__first_name', 'holland_code')
    readonly_fields = ('member_name', 'personality_code', 'created_time', 'score_summary', 'major_summary')
    fields = readonly_fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='Thành viên', ordering='user__username')
    def member_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    @admin.display(description='Nhóm tính cách', ordering='holland_code')
    def personality_code(self, obj):
        return obj.holland_code

    @admin.display(description='Điểm theo nhóm sở thích')
    def score_summary(self, obj):
        rows = []
        scores = obj.scores if isinstance(obj.scores, dict) else {}
        for code, name in DIMENSIONS.items():
            value = scores.get(code, {})
            try:
                percent = min(100, max(0, float(value.get('percent', 0))))
            except (ValueError, TypeError, AttributeError):
                percent = 0
            rows.append((f'{code} · {name}', percent, percent, f'{percent:g}%'))
        return format_html_join('', '<div class="uc-score"><span>{}</span><progress max="100" value="{}" aria-label="{} phần trăm"></progress><strong>{}</strong></div>', rows)

    @admin.display(description='Ngành được gợi ý')
    def major_summary(self, obj):
        majors = obj.suggested_majors if isinstance(obj.suggested_majors, list) else []
        return format_html_join('', '<p>• {}</p>', ((item.get('major_name', '') if isinstance(item, dict) else str(item),) for item in majors)) or 'Chưa có ngành gợi ý.'
